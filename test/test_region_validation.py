"""Pixel-resolution polygon safety and the standalone validation CLI."""

from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import warnings

import numpy as np
from PIL import Image
import pytest
from tb4_voice_control.map_model import load_occupancy_map
from tb4_voice_control.region_validation import validate_semantic_map
from tb4_voice_control.regions import GoalPose, load_regions, Region, save_regions, SemanticMap
import yaml


@pytest.fixture
def occupancy(tmp_path):
    """Use unit-resolution free space with one occupied and one unknown cell."""
    image = np.full((24, 24), 255, dtype=np.uint8)
    image[4, 4] = 0
    image[4, 5] = 128
    Image.fromarray(image).save(tmp_path / 'map.pgm')
    path = tmp_path / 'map.yaml'
    path.write_text(yaml.safe_dump({
        'image': 'map.pgm', 'resolution': 1.0, 'origin': [0, 0, 0],
        'negate': 0, 'free_thresh': 0.25, 'occupied_thresh': 0.65,
    }), encoding='utf-8')
    return load_occupancy_map(path)


@pytest.fixture
def region():
    """Create a rectangle with an interior goal at pixel (6, 6)."""
    return Region('zone_a', 'Khu vực A', ('A', 'khu vực A'), (66, 135, 245),
                  ((2, 2), (10, 2), (10, 10), (2, 10)), GoalPose(6.5, 17.5, 0))


def document(occupancy, *regions):
    """Bind synthetic regions to the actual fixture map."""
    return SemanticMap(1, occupancy.metadata.yaml_path, 'map', tuple(regions))


def test_valid_polygon_with_free_goal(occupancy, region):
    """Only goal occupancy is required; walls elsewhere inside the region are allowed."""
    assert validate_semantic_map(document(occupancy, region), occupancy) == []


@pytest.mark.parametrize('polygon', [
    ((2, 2), (10, 10), (10, 2), (2, 10)),
    ((2, 2), (10, 10), (10, 2), (2, 8)),
    ((2, 2), (10, 2), (6, 2), (6, 10), (2, 10)),
    ((2, 2), (6, 6), (10, 10)),
    ((2, 2), (10, 2), (10, 2), (2, 10)),
])
def test_rejects_crossing_degenerate_and_retraced_polygons(occupancy, region, polygon):
    """Crossings, retraced edges, repeated vertices and zero area are invalid."""
    issues = validate_semantic_map(document(occupancy, replace(
        region, polygon_pixels=polygon)), occupancy)
    assert any(issue.code == 'invalid_polygon' and issue.region_id == 'zone_a'
               for issue in issues)


@pytest.mark.parametrize('polygon', [
    ((-0.1, 2), (10, 2), (10, 10)),
    ((2, 2), (24, 2), (10, 10)),
    ((2, 2), (10, 24), (10, 10)),
])
def test_rejects_out_of_image_vertices(occupancy, region, polygon):
    """Continuous vertices must stay inside the image's pixel center extent."""
    issues = validate_semantic_map(document(occupancy, replace(
        region, polygon_pixels=polygon)), occupancy)
    assert any(issue.code == 'vertex_out_of_bounds' for issue in issues)


def test_extreme_out_of_bounds_vertices_do_not_overflow_opencv(occupancy, region):
    """Report extreme finite coordinates without crashing or warning."""
    changed = replace(region, polygon_pixels=((2, 2), (1e100, 2), (10, 10)))
    with warnings.catch_warnings():
        warnings.simplefilter('error', RuntimeWarning)
        issues = validate_semantic_map(document(occupancy, changed), occupancy)
    assert any(issue.code == 'vertex_out_of_bounds' for issue in issues)


@pytest.mark.parametrize('goal,code', [
    (GoalPose(15.5, 8.5, 0), 'goal_outside_polygon'),
    (GoalPose(4.5, 19.5, 0), 'goal_not_free'),
    (GoalPose(5.5, 19.5, 0), 'goal_not_free'),
    (GoalPose(-1, 20, 0), 'goal_out_of_bounds'),
    (GoalPose(24, 20, 0), 'goal_out_of_bounds'),
])
def test_rejects_unsafe_goals(occupancy, region, goal, code):
    """Containment, image bounds, and occupied/unknown classification are independent."""
    issues = validate_semantic_map(document(occupancy, replace(region, goal=goal)), occupancy)
    assert any(issue.code == code for issue in issues)


def test_goal_cell_lookup_uses_cell_centers(occupancy, region):
    """Continuous pixel 3.6 belongs to occupied cell 4, rather than free cell 3."""
    changed = replace(region, goal=GoalPose(4.1, 19.5, 0))
    issues = validate_semantic_map(document(occupancy, changed), occupancy)
    assert any(issue.code == 'goal_not_free' for issue in issues)


@pytest.mark.parametrize('aliases', [
    ('phòng thí nghiệm', 'PHONG  THI NGHIEM'),
    ('điểm đến', 'diem-den'), ('Khu vực A', 'khu vuc a!'),
])
def test_rejects_duplicate_normalized_aliases_within_region(occupancy, region, aliases):
    """Accents, Vietnamese đ, case, punctuation and whitespace cannot hide duplicates."""
    issues = validate_semantic_map(document(occupancy, replace(region, aliases=aliases)),
                                   occupancy)
    assert any(issue.code == 'duplicate_alias' for issue in issues)


def test_rejects_duplicate_normalized_aliases_across_regions(occupancy, region):
    """An alias must identify a single region across the whole map."""
    other = replace(region, id='zone_b', aliases=('khu vuc a',))
    issues = validate_semantic_map(document(occupancy, region, other), occupancy)
    assert any(issue.code == 'duplicate_alias' and issue.region_id == 'zone_b'
               for issue in issues)


@pytest.mark.parametrize('left,overlap', [(10, False), (9, False), (8, True)])
def test_overlap_uses_eroded_pixel_interiors(occupancy, region, left, overlap):
    """Shared edges and boundary-band contact pass; a surviving interior pixel fails."""
    other = replace(region, id='zone_b', aliases=('B',),
                    polygon_pixels=((left, 2), (18, 2), (18, 10), (left, 10)),
                    goal=GoalPose(15.5, 17.5, 0))
    issues = validate_semantic_map(document(occupancy, region, other), occupancy)
    overlaps = [issue for issue in issues if issue.code == 'overlapping_regions']
    assert bool(overlaps) is overlap
    if not overlap:
        assert issues == []


def test_validation_reports_all_independent_issues(occupancy, region):
    """The editor/CLI can show each affected region in one validation pass."""
    bad_goal = replace(region, goal=GoalPose(4.5, 19.5, 0))
    other = replace(region, id='zone_b', aliases=('a',),
                    goal=GoalPose(15.5, 8.5, 0))
    issues = validate_semantic_map(document(occupancy, bad_goal, other), occupancy)
    assert {'goal_not_free', 'goal_outside_polygon', 'duplicate_alias',
            'overlapping_regions'} <= {issue.code for issue in issues}
    assert all(issue.message for issue in issues)


def test_cli_exit_codes_and_all_issues(occupancy, region, tmp_path):
    """Standalone use needs neither ROS nor UI and returns 0/2 with useful output."""
    path = tmp_path / 'regions.yaml'
    save_regions(path, document(occupancy, region))
    result = subprocess.run([sys.executable, '-m', 'tb4_voice_control.validate_regions',
                             str(path)], capture_output=True, text=True)
    assert result.returncode == 0
    assert '1 valid regions' in result.stdout

    other = replace(region, id='zone_b', aliases=('a',), goal=GoalPose(4.5, 19.5, 0))
    save_regions(path, document(occupancy, region, other))
    result = subprocess.run([sys.executable, '-m', 'tb4_voice_control.validate_regions',
                             str(path)], capture_output=True, text=True)
    assert result.returncode == 2
    assert all(code in result.stdout + result.stderr for code in (
        'goal_not_free', 'duplicate_alias', 'overlapping_regions'))


@pytest.mark.parametrize('content', ['schema_version: 42', '[malformed'])
def test_cli_reports_schema_errors_without_traceback(tmp_path, content):
    """Bad schema or YAML syntax returns the same invalid-file status."""
    path = tmp_path / 'regions.yaml'
    path.write_text(content, encoding='utf-8')
    result = subprocess.run([sys.executable, '-m', 'tb4_voice_control.validate_regions',
                             str(path)], capture_output=True, text=True)
    assert result.returncode == 2
    assert 'Traceback' not in result.stderr
    assert result.stdout or result.stderr


def test_cli_reports_invalid_referenced_map_yaml(occupancy, region, tmp_path):
    """Syntax errors in referenced occupancy metadata are invalid-file errors too."""
    path = tmp_path / 'regions.yaml'
    save_regions(path, document(occupancy, region))
    occupancy.metadata.yaml_path.write_text('[malformed', encoding='utf-8')
    result = subprocess.run([sys.executable, '-m', 'tb4_voice_control.validate_regions',
                             str(path)], capture_output=True, text=True)
    assert result.returncode == 2
    assert 'Traceback' not in result.stderr


def test_real_regions_keep_nav2_goals_and_canonical_laboratory_alias():
    """The delivered map resolves the three existing goals and one canonical lab alias."""
    semantic = load_regions(Path('config/regions.yaml'))
    occupancy = load_occupancy_map(semantic.map_yaml)
    assert validate_semantic_map(semantic, occupancy) == []
    goals = yaml.safe_load(Path('config/goals.yaml').read_text())['goals']
    assert [region.id for region in semantic.regions] == ['zone_a', 'zone_b', 'zone_c']
    for index, region in enumerate(semantic.regions, start=1):
        expected = goals[f'goal_{index}']
        assert (region.goal.x, region.goal.y, region.goal.yaw) == (
            expected['x'], expected['y'], expected['yaw'])
    assert 'phòng thí nghiệm' in semantic.regions[1].aliases
    assert 'phong thi nghiem' not in semantic.regions[1].aliases
