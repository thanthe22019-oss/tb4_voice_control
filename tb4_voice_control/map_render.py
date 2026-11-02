"""Deterministic, native-resolution RGB semantic overlays without modifying maps."""

import argparse
import math
from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from tb4_voice_control.map_model import load_occupancy_map, OccupancyMap, ros_to_pixel
from tb4_voice_control.region_validation import validate_semantic_map
from tb4_voice_control.regions import load_regions, SemanticMap
import yaml


def render_segmented_map(occupancy: OccupancyMap, semantic_map: SemanticMap) -> np.ndarray:
    """Return RGB pixels with 35% fills, centroid names, and world-yaw goal arrows."""
    result = cv2.cvtColor(occupancy.image, cv2.COLOR_GRAY2RGB)
    contours = []
    for region in semantic_map.regions:
        contour = np.asarray(region.polygon_pixels, dtype=np.float32)
        pixels = np.floor(contour + 0.5).astype(np.int32)
        mask = np.zeros(occupancy.image.shape, dtype=np.uint8)
        cv2.fillPoly(mask, [pixels], 255)
        tint = np.empty_like(result)
        tint[:] = region.color
        blended = cv2.addWeighted(result, 0.65, tint, 0.35, 0)
        result[mask != 0] = blended[mask != 0]
        cv2.polylines(result, [pixels], True, region.color, 1, cv2.LINE_8)
        contours.append(contour)

    # OpenCV's Hershey fonts cannot render Vietnamese. Pillow supplies Unicode
    # glyphs; drawing stays deterministic and independent of a Qt display.
    image = Image.fromarray(result)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('DejaVuSans.ttf', 14)
    for region, contour in zip(semantic_map.regions, contours):
        moments = cv2.moments(contour)
        if moments['m00']:
            center = (moments['m10'] / moments['m00'], moments['m01'] / moments['m00'])
        else:
            center = tuple(contour.mean(axis=0))
        draw.text(center, region.name, font=font, anchor='mm', fill='black',
                  stroke_width=2, stroke_fill='white')
    result = np.array(image)

    for region in semantic_map.regions:
        x, y = ros_to_pixel((region.goal.x, region.goal.y), occupancy.metadata,
                            occupancy.image.shape[0])
        angle = region.goal.yaw - occupancy.metadata.origin[2]
        start = (round(x), round(y))
        end = (round(x + 16 * math.cos(angle)), round(y - 16 * math.sin(angle)))
        cv2.arrowedLine(result, start, end, (0, 0, 0), 5, cv2.LINE_8, tipLength=0.35)
        cv2.arrowedLine(result, start, end, (255, 255, 255), 1, cv2.LINE_8, tipLength=0.35)
        cv2.circle(result, start, 5, (0, 0, 0), -1, cv2.LINE_8)
        cv2.circle(result, start, 3, (255, 255, 255), -1, cv2.LINE_8)
    return result


def write_segmented_map(path: Path, occupancy: OccupancyMap, semantic_map: SemanticMap):
    """Write a PNG export while protecting the source map image and YAML files."""
    path = Path(path).resolve()
    if path.suffix.lower() != '.png':
        raise ValueError('Export image must use the .png extension')
    if path in (occupancy.metadata.image_path.resolve(), semantic_map.map_yaml.resolve()):
        raise ValueError('Export cannot overwrite a source map file')
    rgb = render_segmented_map(occupancy, semantic_map)
    if not cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)):
        raise OSError(f'Cannot write image: {path}')


def main(argv=None) -> int:
    """Validate a semantic document and export a PNG; return 2 on invalid input."""
    parser = argparse.ArgumentParser(description='Render semantic map regions as a PNG')
    parser.add_argument('regions', type=Path)
    parser.add_argument('output', type=Path)
    arguments = parser.parse_args(argv)
    try:
        document = load_regions(arguments.regions)
        occupancy = load_occupancy_map(document.map_yaml)
        issues = validate_semantic_map(document, occupancy)
        if issues:
            for issue in issues:
                print(f'{issue.code} [{issue.region_id}]: {issue.message}', file=sys.stderr)
            return 2
        write_segmented_map(arguments.output, occupancy, document)
    except (OSError, ValueError, yaml.YAMLError, cv2.error) as exc:
        print(f'export_error: {exc}', file=sys.stderr)
        return 2
    print(f'Exported {len(document.regions)} regions to {arguments.output}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
