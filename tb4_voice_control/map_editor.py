"""Qt semantic map editor with validated persistence and document-owned undo."""

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import cv2
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QAction, QActionGroup, QApplication, QFileDialog,
                             QFormLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
                             QSplitter, QVBoxLayout, QWidget)
from tb4_voice_control.editor_document import EditorDocument
from tb4_voice_control.map_canvas import MapCanvas
from tb4_voice_control.map_model import load_occupancy_map, pixel_to_ros
from tb4_voice_control.map_render import write_segmented_map
from tb4_voice_control.region_validation import validate_semantic_map, ValidationIssue
from tb4_voice_control.regions import GoalPose, load_regions, Region, save_regions, SemanticMap
import yaml


class MapEditorWindow(QMainWindow):
    """Connect native-pixel drawing intents to a validated semantic document."""

    def __init__(self, path=None):
        """Create an editor and optionally open occupancy or semantic YAML."""
        super().__init__()
        self.document = None
        self.occupancy = None
        self.regions_path = None
        self.issues = []
        self._hidden = set()
        self._form_pending = False
        self._property_error = None
        self.resize(1100, 800)
        self.canvas = MapCanvas()
        self.region_list = QListWidget()
        self.validation_list = QListWidget()
        self.id_edit, self.name_edit = QLineEdit(), QLineEdit()
        self.aliases_edit, self.color_edit = QLineEdit(), QLineEdit()
        self.color_edit.setPlaceholderText('R, G, B (0..255)')
        self.aliases_edit.setPlaceholderText('Aliases separated by commas')
        self.properties = QWidget()
        form = QFormLayout(self.properties)
        for label, field in (('ID', self.id_edit), ('Name', self.name_edit),
                             ('Aliases', self.aliases_edit), ('RGB color', self.color_edit)):
            form.addRow(label, field)
            field.textChanged.connect(self._form_changed)
            field.editingFinished.connect(self.apply_properties)
        apply_button = QPushButton('Apply properties')
        apply_button.clicked.connect(self.apply_properties)
        form.addRow(apply_button)
        sidebar = QWidget()
        layout = QVBoxLayout(sidebar)
        layout.addWidget(QLabel('Regions (check to show)'))
        layout.addWidget(self.region_list)
        layout.addWidget(self.properties)
        layout.addWidget(QLabel('Validation (click to focus)'))
        layout.addWidget(self.validation_list)
        splitter = QSplitter()
        splitter.addWidget(self.canvas)
        splitter.addWidget(sidebar)
        splitter.setStretchFactor(0, 1)
        self.setCentralWidget(splitter)
        toolbar = self.addToolBar('Editor')
        file_menu = self.menuBar().addMenu('File')
        edit_menu = self.menuBar().addMenu('Edit')

        def action(text, callback, shortcut=None, menu=None):
            item = QAction(text, self)
            item.triggered.connect(lambda checked=False: self._guard(callback))
            if shortcut:
                item.setShortcut(shortcut)
            toolbar.addAction(item)
            if menu:
                menu.addAction(item)
            return item

        self.open_action = action('Open', self._open_dialog, 'Ctrl+O', file_menu)
        self.save_action = action('Save', self.save_document, 'Ctrl+S', file_menu)
        self.save_as_action = action('Save As', self._save_as_dialog, 'Ctrl+Shift+S', file_menu)
        self.export_action = action('Export Image', self._export_dialog, None, file_menu)
        toolbar.addSeparator()
        self.undo_action = action('Undo', lambda: self._history('undo'), 'Ctrl+Z', edit_menu)
        self.redo_action = action('Redo', lambda: self._history('redo'), 'Ctrl+Shift+Z', edit_menu)
        self.delete_action = action('Delete region', self._delete_region, 'Delete', edit_menu)
        toolbar.addSeparator()
        group = QActionGroup(self)
        self.mode_actions = {}
        for mode, title in (('select', 'Select'), ('draw_polygon', 'Draw polygon'),
                            ('place_goal', 'Place goal / yaw'), ('pan', 'Pan')):
            item = QAction(title, self)
            item.setCheckable(True)
            item.triggered.connect(lambda checked, mode=mode: self.canvas.set_mode(mode))
            group.addAction(item)
            toolbar.addAction(item)
            self.mode_actions[mode] = item
        self.mode_actions['select'].setChecked(True)
        toolbar.addSeparator()
        self.zoom_in_action = action('Zoom +', lambda: self._zoom(1.25), 'Ctrl++')
        self.zoom_out_action = action('Zoom −', lambda: self._zoom(0.8), 'Ctrl+-')
        self.fit_action = action('Fit', lambda: self.canvas.fitInView(
            self.canvas.sceneRect(), Qt.KeepAspectRatio))
        self.region_list.currentItemChanged.connect(self._list_selected)
        self.region_list.itemChanged.connect(self._visibility_changed)
        self.validation_list.itemClicked.connect(self._focus_issue)
        self.canvas.selection_changed.connect(self._select_region)
        self.canvas.polygon_completed.connect(self._add_polygon)
        self.canvas.vertex_moved.connect(self._move_vertex)
        self.canvas.goal_changed.connect(self._change_goal)
        self.canvas.cursor_position_changed.connect(self._show_coordinates)
        self._refresh()
        if path is not None:
            self.open_path(path)

    def _guard(self, callback):
        try:
            return callback()
        except (OSError, ValueError, yaml.YAMLError, cv2.error) as exc:
            QMessageBox.critical(self, 'Map Editor', str(exc))
            return False

    def _show_coordinates(self, pixel, ros):
        self.statusBar().showMessage(
            f'Pixel: {pixel[0]:.2f}, {pixel[1]:.2f}   ROS: {ros[0]:.2f}, {ros[1]:.2f} m')

    def open_path(self, path):
        """Load both inputs before replacing the current document or canvas."""
        path = Path(path).resolve()
        if not self._confirm_unsaved():
            return False
        with path.open(encoding='utf-8') as stream:
            data = yaml.safe_load(stream)
        if isinstance(data, dict) and 'schema_version' in data:
            semantic = load_regions(path)
            occupancy = load_occupancy_map(semantic.map_yaml)
            regions_path = path
        else:
            occupancy = load_occupancy_map(path)
            semantic = SemanticMap(1, path, 'map', ())
            regions_path = None
        self.document, self.occupancy = EditorDocument(semantic), occupancy
        self.regions_path = regions_path
        self._hidden.clear()
        self.canvas.blockSignals(True)
        self.canvas.set_regions(())
        self.canvas.set_map(occupancy)
        self.canvas.blockSignals(False)
        self._refresh()
        self.canvas.fitInView(self.canvas.sceneRect(), Qt.KeepAspectRatio)
        return True

    def _open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open map or regions', '', 'YAML (*.yaml *.yml)')
        if path:
            return self.open_path(path)
        return False

    def _refresh(self):
        self._form_pending = False
        self._property_error = None
        self.region_list.blockSignals(True)
        self.region_list.clear()
        if self.document is not None:
            for region in self.document.semantic_map.regions:
                item = QListWidgetItem(f'{region.name} ({region.id})')
                item.setData(Qt.UserRole, region.id)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked if region.id in self._hidden else Qt.Checked)
                self.region_list.addItem(item)
                if region.id == self.document.selected_region_id:
                    self.region_list.setCurrentItem(item)
        self.region_list.blockSignals(False)
        self._refresh_canvas()
        self._load_properties()
        self._validate()

    def _refresh_canvas(self):
        if self.document is None:
            return
        self.canvas.blockSignals(True)
        self.canvas.set_regions(tuple(region for region in self.document.semantic_map.regions
                                      if region.id not in self._hidden))
        selected = self.document.selected_region_id
        self.canvas.set_selected_region(selected if selected not in self._hidden else None)
        self.canvas.blockSignals(False)

    def _load_properties(self):
        region = self.document.selected_region if self.document else None
        self.properties.setEnabled(region is not None)
        values = (region.id, region.name, ', '.join(region.aliases),
                  ', '.join(map(str, region.color))) if region else ('', '', '', '')
        for field, value in zip((self.id_edit, self.name_edit, self.aliases_edit,
                                self.color_edit), values):
            field.blockSignals(True)
            field.setText(value)
            field.blockSignals(False)

    def _form_changed(self):
        self._form_pending = True
        self._validate()

    def _property_region(self):
        color = tuple(int(value.strip()) for value in self.color_edit.text().split(','))
        aliases = tuple(value.strip() for value in self.aliases_edit.text().split(',')
                        if value.strip())
        return replace(self.document.selected_region, id=self.id_edit.text().strip(),
                       name=self.name_edit.text().strip(), aliases=aliases, color=color)

    def apply_properties(self):
        """Commit all property fields as one undoable edit, retaining invalid drafts."""
        if (not self._form_pending or self.document is None
                or self.document.selected_region is None):
            return self._property_error is None
        region = self.document.selected_region
        try:
            updated = self._property_region()
            self.document.update_region(updated, original_id=region.id)
        except ValueError as exc:
            self._property_error = ValidationIssue('invalid_property', str(exc), region.id)
            self._validate()
            return False
        if region.id in self._hidden:
            self._hidden.remove(region.id)
            self._hidden.add(updated.id)
        self.document.select_region(updated.id)
        self._refresh()
        return True

    def _validate(self):
        self.issues = []
        self._property_error = None
        if self.document:
            semantic = self.document.semantic_map
            selected = self.document.selected_region
            if self._form_pending and selected:
                try:
                    draft = self._property_region()
                    semantic = replace(semantic, regions=tuple(
                        draft if region.id == selected.id else region
                        for region in semantic.regions))
                except ValueError as exc:
                    self._property_error = ValidationIssue(
                        'invalid_property', str(exc), selected.id)
            self.issues = validate_semantic_map(semantic, self.occupancy)
            if self._form_pending and selected:
                self.issues = [replace(issue, region_id=selected.id)
                               if issue.code == 'invalid_schema' else issue
                               for issue in self.issues]
        if self._property_error is not None:
            self.issues.insert(0, self._property_error)
        self.validation_list.clear()
        for issue in self.issues:
            item = QListWidgetItem(f'{issue.region_id or "Document"}: {issue.message}')
            item.setData(Qt.UserRole, issue)
            self.validation_list.addItem(item)
        valid = self.document is not None and not self.issues
        self.save_action.setEnabled(valid)
        self.save_as_action.setEnabled(valid)
        self.export_action.setEnabled(valid)
        self.undo_action.setEnabled(bool(self.document and self.document.can_undo))
        self.redo_action.setEnabled(bool(self.document and self.document.can_redo))
        self.delete_action.setEnabled(bool(self.document and self.document.selected_region))
        dirty = self.document is not None and (self.document.is_dirty or self._form_pending)
        name = self.regions_path or 'Untitled'
        self.setWindowTitle(f'Map Editor — {name}{" *" if dirty else ""}')

    def _list_selected(self, item, previous):
        self._select_region(item.data(Qt.UserRole) if item else None)

    def _select_region(self, identifier):
        if self.document is None:
            return
        if not self.apply_properties():
            self._sync_list_selection()
            self._refresh_canvas()
            return
        self.document.select_region(identifier)
        self._sync_list_selection()
        self._refresh_canvas()
        self._load_properties()
        self._validate()

    def _sync_list_selection(self):
        self.region_list.blockSignals(True)
        self.region_list.setCurrentRow(next((index for index in range(self.region_list.count())
                                            if self.region_list.item(index).data(Qt.UserRole)
                                            == self.document.selected_region_id), -1))
        self.region_list.blockSignals(False)

    def _visibility_changed(self, item):
        identifier = item.data(Qt.UserRole)
        if item.checkState() == Qt.Checked:
            self._hidden.discard(identifier)
        else:
            self._hidden.add(identifier)
        self._refresh_canvas()

    def _focus_issue(self, item):
        issue = item.data(Qt.UserRole)
        if issue.region_id is not None and self.document is not None:
            self._hidden.discard(issue.region_id)
            for index in range(self.region_list.count()):
                region_item = self.region_list.item(index)
                if region_item.data(Qt.UserRole) == issue.region_id:
                    region_item.setCheckState(Qt.Checked)
            self._select_region(issue.region_id)
            region = self.document.selected_region
            if region:
                self.canvas.centerOn(*np.mean(region.polygon_pixels, axis=0))

    def focus_first_error(self):
        """Select the first actionable validation issue and its region."""
        if self.validation_list.count():
            item = self.validation_list.item(0)
            self._focus_issue(item)
            self.validation_list.setCurrentRow(0)
            self.validation_list.setFocus()

    def _move_vertex(self, identifier, index, point):
        region = next(region for region in self.document.semantic_map.regions
                      if region.id == identifier)
        points = list(region.polygon_pixels)
        points[index] = point
        self._commit_geometry(identifier, polygon_pixels=tuple(points))

    def _change_goal(self, identifier, goal):
        self._commit_geometry(identifier, goal=goal)

    def _commit_geometry(self, identifier, **changes):
        selected = self.document.selected_region_id
        if not self.apply_properties():
            self._refresh_canvas()
            return
        if identifier == selected:
            identifier = self.document.selected_region_id
        region = next(region for region in self.document.semantic_map.regions
                      if region.id == identifier)
        self.document.update_region(replace(region, **changes))
        self._refresh()

    def _add_polygon(self, points):
        if not self.apply_properties():
            return
        ids = {region.id for region in self.document.semantic_map.regions}
        number = 1
        while f'region_{number}' in ids:
            number += 1
        identifier = f'region_{number}'
        contour = np.asarray(points, dtype=np.float32)
        moments = cv2.moments(contour)
        center = ((moments['m10'] / moments['m00'], moments['m01'] / moments['m00'])
                  if moments['m00'] else tuple(contour.mean(axis=0)))
        x, y = pixel_to_ros(center, self.occupancy.metadata, self.occupancy.image.shape[0])
        self.document.add_region(Region(identifier, f'Region {number}', (identifier,),
                                        (66, 135, 245), tuple(points), GoalPose(x, y, 0)))
        self.document.select_region(identifier)
        self._refresh()

    def _delete_region(self):
        if self.document and self.document.selected_region_id:
            self.document.delete_region(self.document.selected_region_id)
            self._refresh()

    def _history(self, direction):
        if self.document:
            getattr(self.document, direction)()
            self._refresh()

    def _zoom(self, factor):
        if 0.05 <= self.canvas.transform().m11() * factor <= 100:
            self.canvas.scale(factor, factor)

    def save_document(self, path=None):
        """Commit pending fields, revalidate, and atomically save a valid document."""
        if self.document is None or not self.apply_properties():
            self.focus_first_error()
            return False
        self._validate()
        if self.issues:
            self.focus_first_error()
            return False
        if path is None:
            path = self.regions_path
        if path is None:
            return self._save_as_dialog()
        path = Path(path).resolve()
        if path in (self.occupancy.metadata.image_path, self.occupancy.metadata.yaml_path):
            raise ValueError('Regions cannot overwrite the source occupancy map')
        save_regions(path, self.document.semantic_map)
        self.regions_path = path
        self.document.mark_saved()
        self._validate()
        return True

    def _save_as_dialog(self):
        path, _ = QFileDialog.getSaveFileName(
            self, 'Save regions', str(self.regions_path or 'regions.yaml'), 'YAML (*.yaml)')
        return self.save_document(path) if path else False

    def export_image(self, path):
        """Validate and export all regions at the source image's native resolution."""
        if self.document is None or not self.apply_properties():
            return False
        self._validate()
        if self.issues:
            self.focus_first_error()
            return False
        write_segmented_map(Path(path), self.occupancy, self.document.semantic_map)
        return True

    def _export_dialog(self):
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export image', 'segmented_map.png', 'PNG (*.png)')
        return self.export_image(path) if path else False

    def _confirm_unsaved(self):
        if self.document is None or not (self.document.is_dirty or self._form_pending):
            return True
        choice = QMessageBox.question(self, 'Unsaved changes', 'Save changes before continuing?',
                                      QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                      QMessageBox.Cancel)
        if choice == QMessageBox.Save:
            return bool(self._guard(self.save_document))
        return choice == QMessageBox.Discard

    def closeEvent(self, event):
        """Allow save, discard, or cancel when a document or property draft is dirty."""
        event.accept() if self._confirm_unsaved() else event.ignore()


def main(argv=None):
    """Start the editor with an optional map or regions YAML path."""
    parser = argparse.ArgumentParser(description='Edit semantic map polygons and navigation goals')
    parser.add_argument('path', nargs='?', type=Path)
    arguments = parser.parse_args(argv)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    window = MapEditorWindow()
    if arguments.path is not None and not window._guard(lambda: window.open_path(arguments.path)):
        return 2
    window.show()
    return app.exec_()


if __name__ == '__main__':
    sys.exit(main())
