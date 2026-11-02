"""Route ordering and strict current-region geometry."""

from pathlib import Path

import numpy as np

import pytest

from tb4_voice_control.command_parser import Intent, VoiceCommand
from tb4_voice_control.map_model import MapMetadata, OccupancyMap, pixel_to_ros
from tb4_voice_control.regions import GoalPose, Region, SemanticMap
from tb4_voice_control.route_planner import find_current_region, plan_route


@pytest.mark.parametrize('command,current,expected', [
    (VoiceCommand(Intent.GO_TO, None, 'zone_b'), None, ('zone_b',)),
    (VoiceCommand(Intent.GO_TO, None, 'zone_b'), 'zone_b', ()),
    (VoiceCommand(Intent.FROM_TO, 'zone_a', 'zone_b'), None,
     ('zone_a', 'zone_b')),
    (VoiceCommand(Intent.FROM_TO, 'zone_a', 'zone_b'), 'zone_a', ('zone_b',)),
])
def test_route_uses_current_region(command, current, expected):
    """Visited source and current destination do not create needless goals."""
    assert plan_route(command, current) == expected


def test_shared_boundary_belongs_to_neither_region():
    """Polygon edges have no arbitrary owner, including a shared edge."""
    metadata = MapMetadata(Path('map.yaml'), Path('map.pgm'), 0.5,
                           (3.0, -2.0, 0.4), False, 0.65, 0.25, 'trinary')
    image = np.full((20, 20), 255, dtype=np.uint8)
    mask = np.zeros_like(image, dtype=bool)
    occupancy = OccupancyMap(metadata, image, ~mask, mask, mask)
    a = Region('zone_a', 'A', ('A',), (1, 2, 3),
               ((2, 2), (8, 2), (8, 12), (2, 12)), GoalPose(0, 0, 0))
    b = Region('zone_b', 'B', ('B',), (4, 5, 6),
               ((8, 2), (15, 2), (15, 12), (8, 12)), GoalPose(0, 0, 0))
    semantic = SemanticMap(1, metadata.yaml_path, 'map', (a, b))
    assert find_current_region(pixel_to_ros((5, 6), metadata, 20),
                               semantic, occupancy) == a
    assert find_current_region(pixel_to_ros((11, 6), metadata, 20),
                               semantic, occupancy) == b
    assert find_current_region(pixel_to_ros((8, 6), metadata, 20),
                               semantic, occupancy) is None
    assert find_current_region(pixel_to_ros((17, 6), metadata, 20),
                               semantic, occupancy) is None
