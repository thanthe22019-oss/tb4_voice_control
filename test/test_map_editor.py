"""Window workflows exercise real documents, widgets, and YAML persistence."""

from dataclasses import replace

from PIL import Image
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QMessageBox
import pytest

from tb4_voice_control.map_editor import MapEditorWindow
from tb4_voice_control.regions import GoalPose, load_regions, Region, save_regions, SemanticMap


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def source(tmp_path):
    Image.new('L', (160, 120), 255).save(tmp_path / 'map.pgm')
    map_path = tmp_path / 'map.yaml'
    map_path.write_text('image: map.pgm\nresolution: 1\norigin: [0, 0, 0]\n'
                        'negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.2\n')
    region = Region('a', 'Area', ('area',), (255, 0, 0),
                    ((10, 10), (90, 10), (90, 100), (10, 100)), GoalPose(30.5, 69.5, 0))
    path = tmp_path / 'regions.yaml'
    save_regions(path, SemanticMap(1, map_path, 'map', (region,)))
    return path


@pytest.fixture
def window(app, source):
    widget = MapEditorWindow(source)
    widget.show()
    app.processEvents()
    yield widget
    widget.document.mark_saved()
    widget._form_pending = False
    widget.close()


def test_open_select_edit_properties_and_undo_rename(window, source):
    assert window.occupancy.image.shape == (120, 160)
    assert not window.document.is_dirty
    window.region_list.setCurrentRow(0)
    assert window.canvas.selected_region_id == 'a'
    for field, value in ((window.id_edit, 'renamed'), (window.name_edit, 'Khu vực mới'),
                         (window.aliases_edit, 'new, phòng mới'),
                         (window.color_edit, '20, 40, 60')):
        field.setText(value)
    assert window.apply_properties()
    region = window.document.selected_region
    assert (region.id, region.name, region.aliases, region.color) == (
        'renamed', 'Khu vực mới', ('new', 'phòng mới'), (20, 40, 60))
    assert window.document.is_dirty
    window.undo_action.trigger()
    assert window.document.semantic_map == load_regions(source)
    window.redo_action.trigger()
    assert window.document.semantic_map.regions[0] == region


def test_invalid_geometry_disables_save_and_focuses_first_error(window, tmp_path):
    region = window.document.semantic_map.regions[0]
    window.canvas.goal_changed.emit('a', replace(region.goal, x=-100))
    assert not window.save_action.isEnabled()
    assert not window.save_as_action.isEnabled()
    assert window.issues[0].code == 'goal_out_of_bounds'
    assert not window.save_document(tmp_path / 'invalid.yaml')
    assert not (tmp_path / 'invalid.yaml').exists()
    assert window.document.selected_region_id == 'a'
    assert window.validation_list.currentRow() == 0
    window.canvas.goal_changed.emit('a', region.goal)
    assert window.save_action.isEnabled()


def test_focusing_hidden_region_error_reveals_overlay_and_checks_visibility(window):
    region = window.document.semantic_map.regions[0]
    window.canvas.goal_changed.emit('a', replace(region.goal, x=-100))
    window.region_list.item(0).setCheckState(Qt.Unchecked)
    assert not window.canvas._polygons
    window.focus_first_error()
    assert window.document.selected_region_id == 'a'
    assert 'a' in window.canvas._polygons
    assert window.region_list.item(0).checkState() == Qt.Checked
    # The displayed state must remain usable after automatic reveal.
    window.region_list.item(0).setCheckState(Qt.Unchecked)
    assert not window.canvas._polygons


def test_invalid_property_draft_cannot_save_old_document(window, tmp_path):
    window.region_list.setCurrentRow(0)
    window.color_edit.setText('999, 0, 0')
    assert not window.apply_properties()
    assert not window.save_action.isEnabled()
    assert not window.save_document(tmp_path / 'invalid.yaml')
    assert not (tmp_path / 'invalid.yaml').exists()
    window.color_edit.setText('30, 60, 90')
    assert window.apply_properties()
    assert window.save_action.isEnabled()


def test_geometry_commit_retains_invalid_property_draft(window):
    window.region_list.setCurrentRow(0)
    before = window.document.semantic_map
    window.name_edit.setText('')
    assert not window.apply_properties()
    window.canvas.vertex_moved.emit('a', 0, (11, 11))
    assert window.name_edit.text() == ''
    assert not window.save_action.isEnabled()
    assert window.document.semantic_map == before
    window.canvas.goal_changed.emit('a', GoalPose(-100, 0, 0))
    assert window.document.semantic_map == before


def test_selecting_other_region_retains_invalid_draft_and_selection(window):
    region = window.document.semantic_map.regions[0]
    points = ((100, 10), (150, 10), (150, 100), (100, 100))
    window.document.add_region(replace(region, id='b', name='Other', aliases=('other',),
                                       polygon_pixels=points, goal=GoalPose(120.5, 69.5, 0)))
    window._refresh()
    window.region_list.setCurrentRow(0)
    window.name_edit.setText('')
    assert not window.apply_properties()
    window.region_list.setCurrentRow(1)
    assert window.region_list.currentRow() == 0
    assert window.document.selected_region_id == 'a'
    assert window.name_edit.text() == ''


def test_pending_form_is_dirty_on_close_and_save_failure_keeps_window_open(window, monkeypatch):
    window.region_list.setCurrentRow(0)
    window.name_edit.setText('')
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Save)
    assert not window.close()
    assert window.isVisible()


def test_save_and_export_protect_source_map_files(window, source):
    for path in (source.parent / 'map.pgm', source.parent / 'map.yaml'):
        original = path.read_bytes()
        with pytest.raises(ValueError, match='source occupancy'):
            window.save_document(path)
        with pytest.raises(ValueError):
            window.export_image(path)
        assert path.read_bytes() == original


def test_delete_key_in_property_field_does_not_delete_region(window, app):
    window.region_list.setCurrentRow(0)
    window.name_edit.setFocus()
    window.name_edit.setCursorPosition(0)
    app.processEvents()
    QTest.keyClick(window.name_edit, Qt.Key_Delete)
    assert len(window.document.semantic_map.regions) == 1
    assert window.name_edit.text() == 'rea'


def test_open_with_dirty_document_can_cancel_without_losing_edits(window, source, monkeypatch):
    window.region_list.setCurrentRow(0)
    window.name_edit.setText('Unsaved')
    assert window.apply_properties()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Cancel)
    assert not window.open_path(source.parent / 'map.yaml')
    assert window.document.selected_region.name == 'Unsaved'
    assert window.regions_path == source


def test_save_before_reopening_current_file_loads_the_saved_edits(window, source, monkeypatch):
    window.region_list.setCurrentRow(0)
    window.name_edit.setText('Saved before reopen')
    assert window.apply_properties()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Save)
    assert window.open_path(source)
    assert window.document.semantic_map == load_regions(source)
    assert window.document.semantic_map.regions[0].name == 'Saved before reopen'
    assert not window.document.is_dirty


def test_save_shortcut_commits_valid_focused_property_draft(window, source, app):
    window.region_list.setCurrentRow(0)
    window.name_edit.setFocus()
    window.name_edit.selectAll()
    QTest.keyClicks(window.name_edit, 'Shortcut saved')
    assert window.save_action.isEnabled()
    app.processEvents()
    QTest.keyClick(window.name_edit, Qt.Key_S, Qt.ControlModifier)
    assert load_regions(source).regions[0].name == 'Shortcut saved'
    assert not window.document.is_dirty


def test_save_as_revalidates_persists_edits_and_clears_dirty(window, tmp_path):
    window.region_list.setCurrentRow(0)
    window.name_edit.setText('Saved area')
    assert window.apply_properties()
    destination = tmp_path / 'saved.yaml'
    assert window.save_document(destination)
    assert load_regions(destination) == window.document.semantic_map
    assert window.regions_path == destination
    assert not window.document.is_dirty
    # Revalidation protects callers even if a document changed outside the UI.
    region = window.document.selected_region
    window.document.update_region(replace(region, goal=replace(region.goal, x=-100)))
    assert not window.save_document(destination)
    assert load_regions(destination).regions[0].goal == region.goal


def test_close_cancel_discard_and_save_choices(window, monkeypatch, source):
    window.region_list.setCurrentRow(0)
    window.name_edit.setText('Close saved')
    assert window.apply_properties()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Cancel)
    assert not window.close()
    assert window.isVisible()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Save)
    assert window.close()
    assert load_regions(source).regions[0].name == 'Close saved'
    window.show()
    window.name_edit.setText('Discard me')
    assert window.apply_properties()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Discard)
    assert window.close()
    assert load_regions(source).regions[0].name == 'Close saved'


def test_visibility_modes_geometry_zoom_status_and_export(window, tmp_path):
    window.region_list.setCurrentRow(0)
    item = window.region_list.item(0)
    item.setCheckState(Qt.Unchecked)
    assert not window.canvas._polygons
    assert len(window.document.semantic_map.regions) == 1
    item.setCheckState(Qt.Checked)
    window.mode_actions['draw_polygon'].trigger()
    assert window.canvas.mode == 'draw_polygon'
    window.canvas.polygon_completed.emit(((100, 10), (150, 10), (150, 60), (100, 60)))
    assert len(window.document.semantic_map.regions) == 2
    assert not window.issues
    window.canvas.vertex_moved.emit(window.document.selected_region_id, 0, (101, 11))
    assert window.document.selected_region.polygon_pixels[0] == (101, 11)
    before = window.canvas.transform().m11()
    window.zoom_in_action.trigger()
    assert window.canvas.transform().m11() > before
    window.canvas.cursor_position_changed.emit((12, 34), (56, 78))
    assert '12.00' in window.statusBar().currentMessage()
    assert '78.00' in window.statusBar().currentMessage()
    image_path = tmp_path / 'view.png'
    assert window.export_image(image_path)
    assert Image.open(image_path).size == (160, 120)


def test_open_map_yaml_starts_empty_semantic_document(window, source):
    window.open_path(source.parent / 'map.yaml')
    assert window.document.semantic_map.regions == ()
    assert window.regions_path is None
    assert window.occupancy.image.shape == (120, 160)


def test_open_failure_preserves_current_document(window, tmp_path):
    before = window.document
    with pytest.raises(OSError):
        window.open_path(tmp_path / 'missing.yaml')
    assert window.document is before
