"""UI-independent occupancy maps and image cell center coordinate conversion."""

from dataclasses import dataclass
import math
from pathlib import Path

import numpy as np
from PIL import Image
import yaml


@dataclass(frozen=True)
class MapMetadata:
    """Validated map-server metadata with resolved source paths."""

    yaml_path: Path
    image_path: Path
    resolution: float
    origin: tuple[float, float, float]
    negate: bool
    occupied_thresh: float
    free_thresh: float
    mode: str


@dataclass(frozen=True)
class OccupancyMap:
    """Grayscale image and disjoint, read-only trinary occupancy masks."""

    metadata: MapMetadata
    image: np.ndarray
    free_mask: np.ndarray
    occupied_mask: np.ndarray
    unknown_mask: np.ndarray


def _number(value, field: str) -> float:
    """Parse a finite metadata number with a field-specific error."""
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{field} must be a finite number') from exc
    if not math.isfinite(result):
        raise ValueError(f'{field} must be a finite number')
    return result


def load_occupancy_map(path: Path) -> OccupancyMap:
    """Load ROS trinary metadata and its image relative to the YAML file."""
    yaml_path = path.resolve()
    with yaml_path.open(encoding='utf-8') as stream:
        document = yaml.safe_load(stream)
    if not isinstance(document, dict):
        raise ValueError('map YAML must contain metadata fields')

    image_name = document.get('image')
    if not isinstance(image_name, str) or not image_name:
        raise ValueError('image must be a nonempty path')
    image_path = (yaml_path.parent / image_name).resolve()
    resolution = _number(document.get('resolution'), 'resolution')
    if resolution <= 0:
        raise ValueError('resolution must be positive')
    origin = document.get('origin')
    if not isinstance(origin, (list, tuple)) or len(origin) != 3:
        raise ValueError('origin must contain x, y, and yaw')
    origin = tuple(_number(value, 'origin') for value in origin)
    mode = document.get('mode', 'trinary')
    if mode != 'trinary':
        raise ValueError('mode must be trinary')
    occupied_thresh = _number(document.get('occupied_thresh'), 'occupied_thresh')
    free_thresh = _number(document.get('free_thresh'), 'free_thresh')
    if not 0 <= occupied_thresh <= 1:
        raise ValueError('occupied_thresh must be between 0 and 1')
    if not 0 <= free_thresh <= 1:
        raise ValueError('free_thresh must be between 0 and 1')
    if free_thresh >= occupied_thresh:
        raise ValueError('free_thresh must be less than occupied_thresh')
    negate = document.get('negate')
    if negate not in (0, 1):
        raise ValueError('negate must be 0 or 1')

    try:
        with Image.open(image_path) as source:
            image = np.array(source.convert('L'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'image could not be loaded: {image_path}') from exc
    # Subtract before division to preserve exact threshold equality for 8-bit pixels.
    probability = (image if negate else 255 - image).astype(float) / 255.0
    free_mask = probability < free_thresh
    occupied_mask = probability > occupied_thresh
    unknown_mask = ~(free_mask | occupied_mask)
    for array in (image, free_mask, occupied_mask, unknown_mask):
        array.setflags(write=False)
    metadata = MapMetadata(yaml_path, image_path, resolution, origin, bool(negate),
                           occupied_thresh, free_thresh, mode)
    return OccupancyMap(metadata, image, free_mask, occupied_mask, unknown_mask)


def pixel_to_ros(pixel: tuple[float, float], metadata: MapMetadata,
                 image_height: int) -> tuple[float, float]:
    """Transform continuous image cell center coordinates to the ROS map frame."""
    x = (pixel[0] + 0.5) * metadata.resolution
    y = (image_height - pixel[1] - 0.5) * metadata.resolution
    origin_x, origin_y, yaw = metadata.origin
    cosine, sine = math.cos(yaw), math.sin(yaw)
    return origin_x + cosine * x - sine * y, origin_y + sine * x + cosine * y


def ros_to_pixel(point: tuple[float, float], metadata: MapMetadata,
                 image_height: int) -> tuple[float, float]:
    """Invert origin translation, yaw, image Y direction, and cell center offset."""
    origin_x, origin_y, yaw = metadata.origin
    x, y = point[0] - origin_x, point[1] - origin_y
    cosine, sine = math.cos(yaw), math.sin(yaw)
    local_x = cosine * x + sine * y
    local_y = -sine * x + cosine * y
    return (local_x / metadata.resolution - 0.5,
            image_height - local_y / metadata.resolution - 0.5)
