"""Validate semantic geometry at the occupancy map's pixel resolution."""

from dataclasses import dataclass
import math

import cv2
import numpy as np
from tb4_voice_control.map_model import OccupancyMap, ros_to_pixel
from tb4_voice_control.regions import _validate_structure, normalize_alias, SemanticMap


@dataclass(frozen=True)
class ValidationIssue:
    """An actionable issue optionally associated with a region for editor focus."""

    code: str
    message: str
    region_id: str | None = None


def _segments_intersect(a, b, c, d):
    """Include endpoint contact and collinear intersections of nonadjacent edges."""
    def orientation(p, q, r):
        cross = ((q[0] - p[0]) * (r[1] - p[1])
                 - (q[1] - p[1]) * (r[0] - p[0]))
        return 0 if abs(cross) < 1e-9 else (1 if cross > 0 else -1)

    def on_segment(p, q, r):
        return (min(p[0], r[0]) <= q[0] <= max(p[0], r[0])
                and min(p[1], r[1]) <= q[1] <= max(p[1], r[1]))

    abc, abd = orientation(a, b, c), orientation(a, b, d)
    cda, cdb = orientation(c, d, a), orientation(c, d, b)
    if abc * abd < 0 and cda * cdb < 0:
        return True
    return ((abc == 0 and on_segment(a, c, b))
            or (abd == 0 and on_segment(a, d, b))
            or (cda == 0 and on_segment(c, a, d))
            or (cdb == 0 and on_segment(c, b, d)))


def _simple_polygon(polygon, contour):
    if len(set(polygon)) != len(polygon) or cv2.contourArea(contour) <= 0:
        return False
    count = len(polygon)
    # ponytail: quadratic edge checks are sufficient for manually drawn region polygons.
    for first in range(count):
        for second in range(first + 1, count):
            if second == first + 1 or (first == 0 and second == count - 1):
                continue
            if _segments_intersect(polygon[first], polygon[(first + 1) % count],
                                   polygon[second], polygon[(second + 1) % count]):
                return False
    return True


def validate_semantic_map(document: SemanticMap,
                          occupancy: OccupancyMap) -> list[ValidationIssue]:
    """Collect schema, alias, goal, polygon, and eroded-interior overlap issues."""
    try:
        _validate_structure(document)
    except ValueError as exc:
        return [ValidationIssue('invalid_schema', str(exc))]
    height, width = occupancy.image.shape
    issues = []
    aliases = {}
    interiors = []
    kernel = np.ones((3, 3), dtype=np.uint8)
    for region in document.regions:
        def issue(code, message):
            issues.append(ValidationIssue(code, message, region.id))

        for alias in region.aliases:
            normalized = normalize_alias(alias)
            if normalized in aliases:
                issue('duplicate_alias', f'Alias {alias!r} duplicates alias in '
                      f'{aliases[normalized]}')
            else:
                aliases[normalized] = region.id

        polygon = region.polygon_pixels
        bounds_valid = all(0 <= x <= width - 1 and 0 <= y <= height - 1
                           for x, y in polygon)
        if not bounds_valid:
            issue('vertex_out_of_bounds', 'Polygon vertex lies outside image pixel centers')
        contour = np.asarray(polygon, dtype=np.float32)
        simple = _simple_polygon(polygon, contour)
        if not simple:
            issue('invalid_polygon',
                  'Polygon must be simple with nonzero area and distinct vertices')

        goal_pixel = ros_to_pixel((region.goal.x, region.goal.y), occupancy.metadata, height)
        # Continuous image coordinates denote cell centers: cell edges are at n +/- 0.5.
        if not (-0.5 <= goal_pixel[0] < width - 0.5
                and -0.5 <= goal_pixel[1] < height - 0.5):
            issue('goal_out_of_bounds', 'Goal lies outside the occupancy image')
        else:
            x, y = (math.floor(value + 0.5) for value in goal_pixel)
            if not occupancy.free_mask[y, x]:
                issue('goal_not_free', 'Goal is on an occupied or unknown occupancy cell')
        if simple and cv2.pointPolygonTest(contour, goal_pixel, False) < 0:
            issue('goal_outside_polygon', 'Goal lies outside its region polygon')

        if bounds_valid and simple:
            mask = np.zeros((height, width), dtype=np.uint8)
            cv2.fillPoly(mask, [np.floor(contour + 0.5).astype(np.int32)], 1)
            interior = cv2.erode(mask, kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0)
            for identifier, other in interiors:
                if np.any(interior & other):
                    issue('overlapping_regions', f'Eroded pixel interior overlaps {identifier}')
            interiors.append((region.id, interior))
    return issues
