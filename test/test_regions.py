"""Versioned semantic documents and atomic, portable YAML persistence."""

from dataclasses import FrozenInstanceError
import math
from pathlib import Path

import pytest
from tb4_voice_control.regions import load_regions, save_regions
import yaml


@pytest.fixture
def region_file(tmp_path):
    """Write a complete document with a relative occupancy map path."""
    data = {
        'schema_version': 1,
        'map': {'yaml': '../maps/map.yaml', 'frame_id': 'map'},
        'regions': [{
            'id': 'zone_a', 'name': 'Khu vực A',
            'aliases': ['A', 'khu vực A'], 'color': [66, 135, 245],
            'polygon_pixels': [[1, 1], [8, 1], [8, 8], [1, 8]],
            'goal': {'x': 2.5, 'y': 3.5, 'yaw': -0.3},
        }],
    }
    path = tmp_path / 'config' / 'regions.yaml'
    path.parent.mkdir()

    def write(change=None):
        if change:
            change(data)
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding='utf-8')
        return path

    return write


def test_relative_map_unicode_and_round_trip(region_file, tmp_path):
    """A moved save keeps the same map and all Unicode data and immutable fields."""
    source = region_file()
    document = load_regions(source)
    assert document.map_yaml == tmp_path / 'maps' / 'map.yaml'
    assert document.regions[0].name == 'Khu vực A'
    assert document.regions[0].aliases == ('A', 'khu vực A')
    assert document.regions[0].polygon_pixels == ((1, 1), (8, 1), (8, 8), (1, 8))
    with pytest.raises(FrozenInstanceError):
        document.regions[0].goal.x = 9

    destination = tmp_path / 'regions.yaml'
    save_regions(destination, document)
    text = destination.read_text(encoding='utf-8')
    assert 'Khu vực A' in text
    assert list(yaml.safe_load(text)) == ['schema_version', 'map', 'regions']
    assert yaml.safe_load(text)['map']['yaml'] == 'maps/map.yaml'
    assert load_regions(destination) == document


@pytest.mark.parametrize('version', [0, 2, '1', True, None])
def test_rejects_unsupported_schema(region_file, version):
    """Only integer version 1 is supported."""
    path = region_file(lambda data: data.update(schema_version=version))
    with pytest.raises(ValueError, match='schema_version'):
        load_regions(path)


@pytest.mark.parametrize('field,value', [
    ('id', ''), ('name', ''), ('aliases', 'A'), ('aliases', [7]),
    ('color', [-1, 0, 0]), ('color', [256, 0, 0]),
    ('color', [1.5, 0, 0]), ('color', [True, 0, 0]), ('color', [1, 2]),
    ('polygon_pixels', [[0, 0], [1, 1]]),
    ('polygon_pixels', [[0, 0], [1, 1], [2, math.inf]]),
    ('polygon_pixels', [[0, 0], [1, 1], [2]]),
    ('goal', {'x': math.nan, 'y': 0, 'yaw': 0}),
    ('goal', {'x': 0, 'y': math.inf, 'yaw': 0}),
    ('goal', {'x': 0, 'y': 0, 'yaw': '0'}),
    ('goal', {'x': True, 'y': 0, 'yaw': 0}),
    ('goal', {'x': 0, 'y': 0}),
])
def test_rejects_malformed_region_fields(region_file, field, value):
    """Malformed numeric and structural values fail before geometry or saving."""
    path = region_file(lambda data: data['regions'][0].update({field: value}))
    with pytest.raises(ValueError, match=field):
        load_regions(path)


@pytest.mark.parametrize('field,value', [('yaml', ''), ('frame_id', '')])
def test_rejects_empty_map_fields(region_file, field, value):
    """Map filename and goal frame must be usable strings."""
    path = region_file(lambda data: data['map'].update({field: value}))
    with pytest.raises(ValueError, match=field):
        load_regions(path)


def test_rejects_duplicate_region_ids(region_file):
    """Duplicate IDs cannot silently replace a region during lookup."""
    path = region_file(lambda data: data['regions'].append(dict(data['regions'][0])))
    with pytest.raises(ValueError, match='id'):
        load_regions(path)


@pytest.mark.parametrize('data', [
    None, [], {'schema_version': 1}, {'schema_version': 1, 'map': []},
])
def test_rejects_incomplete_documents(tmp_path, data):
    """Malformed YAML roots and missing fields produce actionable value errors."""
    path = tmp_path / 'regions.yaml'
    path.write_text(yaml.safe_dump(data), encoding='utf-8')
    with pytest.raises(ValueError):
        load_regions(path)


def test_save_atomically_replaces_complete_file(region_file, monkeypatch):
    """The destination stays intact until a complete same-directory file replaces it."""
    import os

    source = region_file()
    document = load_regions(source)
    previous = source.read_bytes()
    replace = os.replace
    observations = []

    def inspect_replace(temporary, destination):
        temporary, destination = Path(temporary), Path(destination)
        assert temporary.parent == destination.parent
        assert source.read_bytes() == previous
        assert load_regions(temporary) == document
        observations.append(temporary)
        replace(temporary, destination)

    monkeypatch.setattr(os, 'replace', inspect_replace)
    save_regions(source, document)
    assert len(observations) == 1
    assert not observations[0].exists()
    assert load_regions(source) == document


def test_failed_replace_preserves_original_and_cleans_temporary(region_file, monkeypatch):
    """An interrupted save leaves the last good document and no temporary debris."""
    import os

    source = region_file()
    document = load_regions(source)
    previous = source.read_bytes()

    def fail_replace(temporary, destination):
        raise OSError('simulated replace failure')

    monkeypatch.setattr(os, 'replace', fail_replace)
    with pytest.raises(OSError, match='simulated'):
        save_regions(source, document)
    assert source.read_bytes() == previous
    assert list(source.parent.iterdir()) == [source]
