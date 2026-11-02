"""Plan ordered semantic goals from the current ROS map pose."""

import cv2

import numpy as np

from tb4_voice_control.command_parser import Intent, VoiceCommand
from tb4_voice_control.map_model import OccupancyMap, ros_to_pixel
from tb4_voice_control.regions import Region, SemanticMap


def find_current_region(point_ros: tuple[float, float],
                        semantic_map: SemanticMap,
                        occupancy: OccupancyMap) -> Region | None:
    """Find a unique strict polygon interior; edges belong to no region."""
    pixel = ros_to_pixel(point_ros, occupancy.metadata,
                         occupancy.image.shape[0])
    inside = []
    for region in semantic_map.regions:
        contour = np.asarray(region.polygon_pixels, dtype=np.float32)
        distance = cv2.pointPolygonTest(contour, pixel, True)
        if distance > 1e-7:
            inside.append(region)
    return inside[0] if len(inside) == 1 else None


def plan_route(command: VoiceCommand,
               current_region_id: str | None) -> tuple[str, ...]:
    """Return only the semantic region goals still needed."""
    if command.intent is Intent.GO_TO:
        return (() if current_region_id == command.destination_id
                else (command.destination_id,))
    if command.intent is Intent.FROM_TO:
        if current_region_id == command.source_id:
            return (command.destination_id,)
        return (command.source_id, command.destination_id)
    raise ValueError(f'Unsupported intent: {command.intent}')
