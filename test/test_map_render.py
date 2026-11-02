"""Deterministic RGB export includes geometry, Unicode text, and heading."""

from dataclasses import replace
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from tb4_voice_control.map_model import MapMetadata, OccupancyMap
from tb4_voice_control.map_render import main, render_segmented_map
from tb4_voice_control.regions import GoalPose, Region, save_regions, SemanticMap


def test_render_is_repeatable_with_rgb_fill_centroid_label_and_rotated_yaw():
    image = np.full((180, 200), 200, dtype=np.uint8)
    image.flags.writeable = False
    metadata = MapMetadata(Path('/tmp/map.yaml'), Path('/tmp/map.pgm'), 1,
                           (0, 0, math.pi / 2), False, 0.65, 0.2, 'trinary')
    occupancy = OccupancyMap(metadata, image, image == 200, image == 0, image == 127)
    # Image goal (40, 130), world yaw pi/2 => arrow points right in the image.
    region = Region('a', 'Khu vực A', ('a',), (255, 0, 0),
                    ((10, 10), (180, 10), (180, 160), (10, 160)),
                    GoalPose(-49.5, 40.5, math.pi / 2))
    document = SemanticMap(1, metadata.yaml_path, 'map', (region,))
    result = render_segmented_map(occupancy, document)
    assert result.shape == (180, 200, 3) and result.dtype == np.uint8
    assert np.array_equal(result, render_segmented_map(occupancy, document))
    assert np.all(image == 200)
    assert tuple(result[30, 30]) == (219, 130, 130)
    assert tuple(result[0, 0]) == (200, 200, 200)
    assert np.any(np.all(result[75:96, 60:130] < 50, axis=2))  # centroid (95, 85)
    assert tuple(result[130, 40]) == (255, 255, 255)  # high contrast goal dot
    assert np.any(np.all(result[126:135, 50:57] < 50, axis=2))  # rightward arrow
    assert np.all(result[115:120, 38:43, 0] > 100)  # no upward arrow


def test_cli_writes_png_without_modifying_map_and_rejects_invalid_regions(tmp_path, capsys):
    Image.new('L', (80, 60), 255).save(tmp_path / 'map.pgm')
    original = (tmp_path / 'map.pgm').read_bytes()
    map_path = tmp_path / 'map.yaml'
    map_path.write_text('image: map.pgm\nresolution: 1\norigin: [0, 0, 0]\n'
                        'negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.2\n')
    region = Region('a', 'Khu A', ('a',), (10, 100, 200),
                    ((5, 5), (70, 5), (70, 50), (5, 50)), GoalPose(20.5, 29.5, 0))
    document = SemanticMap(1, map_path, 'map', (region,))
    regions_path, output = tmp_path / 'regions.yaml', tmp_path / 'output.png'
    save_regions(regions_path, document)
    assert main([str(regions_path), str(output)]) == 0
    assert cv2.imread(str(output)).shape == (60, 80, 3)
    assert Image.open(output).getpixel((8, 8)) == (169, 201, 236)
    assert (tmp_path / 'map.pgm').read_bytes() == original
    assert main([str(regions_path), str(tmp_path / 'map.pgm')]) == 2
    assert (tmp_path / 'map.pgm').read_bytes() == original
    invalid = replace(document, regions=(replace(region, goal=GoalPose(-10, 0, 0)),))
    save_regions(regions_path, invalid)
    assert main([str(regions_path), str(tmp_path / 'invalid.png')]) == 2
    assert not (tmp_path / 'invalid.png').exists()
    assert 'goal_out_of_bounds' in capsys.readouterr().err
