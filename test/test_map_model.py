"""Map loading and image cell center coordinate contracts."""

from dataclasses import FrozenInstanceError, replace
import math
from pathlib import Path

import numpy as np
import pytest
from tb4_voice_control.map_model import (
    load_occupancy_map, pixel_to_ros, ros_to_pixel,
)
import yaml


@pytest.fixture
def map_yaml(tmp_path):
    """Write a tiny map whose image path is relative to the YAML."""
    images = tmp_path / 'images'
    images.mkdir()
    (images / 'tiny.pgm').write_bytes(b'P5\n5 1\n255\n' + bytes([0, 51, 128, 204, 255]))
    document = {
        'image': 'images/tiny.pgm', 'resolution': 0.5,
        'origin': [10.0, 20.0, 0.0], 'negate': 0,
        'occupied_thresh': 0.8, 'free_thresh': 0.2, 'mode': 'trinary',
    }
    path = tmp_path / 'map.yaml'

    def write(**changes):
        path.write_text(yaml.safe_dump({**document, **changes}), encoding='utf-8')
        return path

    return write


def test_real_map_metadata_and_round_trip():
    """Real map dimensions and origin survive loading and conversion."""
    occupancy = load_occupancy_map(Path('maps/map.yaml'))
    assert occupancy.image.shape == (1101, 788)
    assert occupancy.metadata.resolution == pytest.approx(0.05)
    assert occupancy.metadata.origin == pytest.approx((-19.7, -27.5, 0.0))
    assert ros_to_pixel(pixel_to_ros((300.25, 700.75), occupancy.metadata, 1101),
                        occupancy.metadata, 1101) == pytest.approx((300.25, 700.75))


@pytest.mark.parametrize('negate, free, occupied', [
    (0, [[False, False, False, False, True]], [[True, False, False, False, False]]),
    (1, [[True, False, False, False, False]], [[False, False, False, False, True]]),
])
def test_relative_image_and_trinary_masks(map_yaml, negate, free, occupied):
    """Negation changes probability and threshold equality stays unknown."""
    path = map_yaml(negate=negate)
    occupancy = load_occupancy_map(path)
    assert occupancy.metadata.yaml_path == path.resolve()
    assert occupancy.metadata.image_path == (path.parent / 'images/tiny.pgm').resolve()
    np.testing.assert_array_equal(occupancy.image, [[0, 51, 128, 204, 255]])
    np.testing.assert_array_equal(occupancy.free_mask, free)
    np.testing.assert_array_equal(occupancy.occupied_mask, occupied)
    np.testing.assert_array_equal(
        occupancy.unknown_mask, ~(np.array(free) | np.array(occupied)))


def test_threshold_endpoints_are_unknown(map_yaml):
    """Strict inequalities leave probabilities equal to either threshold unknown."""
    occupancy = load_occupancy_map(map_yaml(free_thresh=0.0, occupied_thresh=1.0))
    assert occupancy.unknown_mask.all()


@pytest.mark.parametrize('field, value', [
    ('image', 'missing.pgm'), ('image', None),
    ('resolution', 0), ('resolution', -1), ('resolution', math.inf),
    ('resolution', 'invalid'), ('origin', [0, 0]), ('origin', 'bad'),
    ('origin', [0, 0, math.nan]), ('origin', [0, 'bad', 0]),
    ('mode', 'scale'), ('mode', 'raw'),
    ('free_thresh', -0.1), ('occupied_thresh', 1.1),
    ('free_thresh', 0.8), ('occupied_thresh', 0.1),
    ('free_thresh', math.nan), ('occupied_thresh', 'bad'),
])
def test_invalid_fields_are_named(map_yaml, field, value):
    """Invalid input is rejected with the responsible field in the error."""
    with pytest.raises(ValueError, match=field):
        load_occupancy_map(map_yaml(**{field: value}))


def test_model_is_immutable(map_yaml):
    """Consumers cannot modify shared metadata, source pixels, or masks."""
    occupancy = load_occupancy_map(map_yaml())
    with pytest.raises(FrozenInstanceError):
        occupancy.metadata.resolution = 1.0
    with pytest.raises(FrozenInstanceError):
        occupancy.image = np.zeros((1, 1))
    for array in (occupancy.image, occupancy.free_mask,
                  occupancy.occupied_mask, occupancy.unknown_mask):
        with pytest.raises(ValueError):
            array[0, 0] = 0


@pytest.mark.parametrize('yaw, pixel, expected', [
    (0.0, (0, 3), (10.25, 20.25)),
    (0.0, (0, 0), (10.25, 21.75)),
    (math.pi / 2, (0, 3), (9.75, 20.25)),
    (math.pi / 2, (2, 1), (8.75, 21.25)),
])
def test_cell_centers_and_yaw(map_yaml, yaw, pixel, expected):
    """Image Y flips before the origin yaw rotation and translation."""
    metadata = replace(load_occupancy_map(map_yaml()).metadata, origin=(10, 20, yaw))
    assert pixel_to_ros(pixel, metadata, 4) == pytest.approx(expected)
    assert ros_to_pixel(expected, metadata, 4) == pytest.approx(pixel)
