"""Undoable semantic edits without a Qt dependency."""

from dataclasses import replace
from pathlib import Path

import pytest

from tb4_voice_control.editor_document import EditorDocument
from tb4_voice_control.map_model import load_occupancy_map
from tb4_voice_control.regions import GoalPose, Region, save_regions, SemanticMap


def region(identifier='a'):
    return Region(identifier, identifier.upper(), (identifier,), (50, 100, 150),
                  ((1, 1), (8, 1), (8, 8), (1, 8)), GoalPose(4, 4, 0))


@pytest.fixture
def source():
    return SemanticMap(1, Path('/tmp/map.yaml'), 'map', (region(), region('b')))


def test_edits_undo_redo_preserve_source_and_region_order(source):
    document = EditorDocument(source)
    changed = replace(region(), name='Changed', goal=GoalPose(5, 5, 1))
    document.add_region(region('c'))
    document.update_region(changed)
    document.delete_region('b')
    assert document.semantic_map.regions == (changed, region('c'))
    assert source.regions == (region(), region('b'))
    assert document.undo()
    assert document.semantic_map.regions == (changed, region('b'), region('c'))
    assert document.undo()
    assert document.semantic_map.regions == (region(), region('b'), region('c'))
    assert document.undo()
    assert document.semantic_map == source
    assert not document.undo()
    for _ in range(3):
        assert document.redo()
    assert document.semantic_map.regions == (changed, region('c'))
    assert not document.redo()


def test_dirty_tracks_saved_state_through_undo_redo_and_branch(source):
    document = EditorDocument(source)
    assert not document.is_dirty
    document.update_region(replace(region(), name='Saved'))
    assert document.is_dirty
    document.mark_saved()
    assert not document.is_dirty
    document.undo()
    assert document.is_dirty
    document.redo()
    assert not document.is_dirty
    document.undo()
    document.update_region(replace(region(), name='Different branch'))
    assert document.is_dirty
    assert not document.can_redo


def test_selection_follows_id_and_stays_out_of_saved_yaml(source, tmp_path):
    document = EditorDocument(source)
    document.select_region('b')
    document.update_region(replace(region('b'), name='Renamed'))
    assert document.selected_region_id == 'b'
    assert document.selected_region.name == 'Renamed'
    document.undo()
    assert document.selected_region_id == 'b'
    document.delete_region('a')
    assert document.selected_region_id == 'b'
    document.delete_region('b')
    assert document.selected_region_id is None
    document.undo()
    path = tmp_path / 'regions.yaml'
    save_regions(path, document.semantic_map)
    assert 'selected' not in path.read_text()


def test_history_discards_oldest_commands_after_one_hundred(source):
    document = EditorDocument(source)
    for index in range(105):
        document.update_region(replace(region(), name=f'Edit {index}'))
    for _ in range(100):
        assert document.undo()
    assert document.semantic_map.regions[0].name == 'Edit 4'
    assert not document.can_undo
    assert document.is_dirty
    for _ in range(100):
        assert document.redo()
    assert document.semantic_map.regions[0].name == 'Edit 104'


def test_noop_update_preserves_clean_state_and_redo(source):
    document = EditorDocument(source)
    document.update_region(replace(region(), name='Changed'))
    document.undo()
    document.update_region(region())
    assert not document.is_dirty
    assert document.can_redo


def test_invalid_region_ids_do_not_modify_document(source):
    document = EditorDocument(source)
    with pytest.raises(ValueError, match='duplicate'):
        document.add_region(region())
    with pytest.raises(KeyError):
        document.update_region(region('missing'))
    with pytest.raises(KeyError):
        document.delete_region('missing')
    with pytest.raises(KeyError):
        document.select_region('missing')
    assert document.semantic_map == source
    assert not document.is_dirty
    assert not document.can_undo


def test_structural_errors_are_atomic_but_geometry_can_be_validated(source):
    document = EditorDocument(source)
    with pytest.raises(ValueError, match='color'):
        document.update_region(replace(region(), color=(999, 0, 0)))
    assert document.semantic_map == source
    assert not document.can_undo
    document.update_region(replace(
        region(), polygon_pixels=((-1, 1), (8, 1), (8, 8), (1, 8))))
    occupancy = load_occupancy_map(Path(__file__).resolve().parents[1] / 'maps/map.yaml')
    assert any(issue.code == 'vertex_out_of_bounds' and issue.region_id == 'a'
               for issue in document.validate(occupancy))
