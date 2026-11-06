"""Exercise real Qt input and semantic edit signals with an offscreen display."""

from dataclasses import replace
import math
from pathlib import Path

import numpy as np
from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QMouseEvent, QWheelEvent
from PyQt5.QtTest import QSignalSpy, QTest
from PyQt5.QtWidgets import QApplication, QGraphicsPixmapItem, QGraphicsSimpleTextItem
import pytest

from tb4_voice_control.map_canvas import MapCanvas
from tb4_voice_control.map_model import MapMetadata, OccupancyMap
from tb4_voice_control.regions import GoalPose, Region


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def occupancy():
    metadata = MapMetadata(Path('/tmp/map.yaml'), Path('/tmp/map.pgm'), 0.5,
                           (10, 20, math.pi / 2), False, 0.65, 0.2, 'trinary')
    image = np.full((40, 50), 255, dtype=np.uint8)
    image[0, 0] = 0
    return OccupancyMap(metadata, image, image == 255, image == 0, image == 123)


@pytest.fixture
def canvas(app, occupancy):
    widget = MapCanvas()
    widget.resize(500, 400)
    widget.set_map(occupancy)
    widget.set_regions((Region('a', 'Area', ('area',), (255, 50, 20),
                               ((5, 5), (30, 5), (30, 30), (5, 30)),
                               GoalPose(-0.25, 30.25, math.pi / 2)),))
    widget.show()
    app.processEvents()
    yield widget
    widget.close()


def click(canvas, x, y):
    QTest.mouseClick(canvas.viewport(), Qt.LeftButton,
                     pos=canvas.mapFromScene(QPointF(x, y)))


def drag(canvas, start, end):
    QTest.mousePress(canvas.viewport(), Qt.LeftButton, pos=start)
    # The offscreen plugin does not deliver QTest.mouseMove during a press.
    event = QMouseEvent(QEvent.MouseMove, QPointF(end),
                        QPointF(canvas.viewport().mapToGlobal(end)), Qt.NoButton,
                        Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(canvas.viewport(), event)
    QTest.mouseRelease(canvas.viewport(), Qt.LeftButton, pos=end)


def test_native_image_pixels_are_not_resampled(canvas):
    items = [item for item in canvas.scene().items()
             if isinstance(item, QGraphicsPixmapItem)]
    assert len(items) == 1
    assert items[0].pixmap().size().width() == 50
    assert items[0].pixmap().toImage().pixelColor(0, 0).red() == 0
    assert items[0].pixmap().toImage().pixelColor(1, 0).red() == 255
    assert items[0].pos() == QPointF(-0.5, -0.5)


def test_unicode_region_label_refresh_and_selection(canvas):
    region = replace(canvas._regions['a'], name='Phòng thí nghiệm')
    canvas.set_regions((region,))
    labels = [item for item in canvas.scene().items()
              if isinstance(item, QGraphicsSimpleTextItem)]
    assert len(labels) == 1
    assert labels[0].text() == 'Phòng thí nghiệm'
    assert labels[0].data(0) == 'a'
    canvas.set_selected_region('a')
    assert labels[0].scene() is canvas.scene()
    canvas.set_regions(())
    assert not [item for item in canvas.scene().items()
                if isinstance(item, QGraphicsSimpleTextItem)]


def test_scene_bounds_include_entire_first_and_last_cells(canvas):
    assert canvas.sceneRect().left() == -0.5
    assert canvas.sceneRect().top() == -0.5
    assert canvas.sceneRect().right() == 49.5
    assert canvas.sceneRect().bottom() == 39.5


def test_replacing_map_cancels_goal_started_on_old_map(canvas, occupancy):
    goals = QSignalSpy(canvas.goal_changed)
    canvas.set_selected_region('a')
    canvas.set_mode('place_goal')
    point = canvas.mapFromScene(QPointF(20, 20))
    QTest.mousePress(canvas.viewport(), Qt.LeftButton, pos=point)
    canvas.set_map(occupancy)
    QTest.mouseRelease(canvas.viewport(), Qt.LeftButton, pos=point)
    assert not goals


@pytest.mark.parametrize('close_with', ['click', 'enter'])
def test_draw_polygon_emits_complete_pixel_vertices(canvas, close_with):
    completed = QSignalSpy(canvas.polygon_completed)
    canvas.set_mode('draw_polygon')
    for point in ((8, 8), (25, 8), (25, 25)):
        click(canvas, *point)
    assert not completed
    if close_with == 'click':
        click(canvas, 8, 8)
    else:
        QTest.keyClick(canvas, Qt.Key_Return)
    assert len(completed) == 1
    assert completed[0][0] == ((8.0, 8.0), (25.0, 8.0), (25.0, 25.0))


def test_escape_and_mode_change_cancel_unfinished_polygon(canvas):
    completed = QSignalSpy(canvas.polygon_completed)
    canvas.set_mode('draw_polygon')
    click(canvas, 2, 2)
    click(canvas, 20, 2)
    QTest.keyClick(canvas, Qt.Key_Escape)
    click(canvas, 20, 20)
    QTest.keyClick(canvas, Qt.Key_Return)
    assert not completed
    canvas.set_mode('select')
    canvas.set_mode('draw_polygon')
    QTest.keyClick(canvas, Qt.Key_Return)
    assert not completed


@pytest.mark.parametrize('zoom', [1, 2])
def test_select_drag_vertex_and_clear_selection(canvas, app, zoom):
    canvas.scale(zoom, zoom)
    selected = QSignalSpy(canvas.selection_changed)
    moved = QSignalSpy(canvas.vertex_moved)
    click(canvas, 15, 15)
    assert selected[-1][0] == 'a'
    start = canvas.mapFromScene(QPointF(5, 5))
    end = canvas.mapFromScene(QPointF(9, 11))
    drag(canvas, start, end)
    app.processEvents()
    assert len(moved) == 1
    assert moved[0] == ['a', 0, (9.0, 11.0)]
    click(canvas, 45, 35)
    assert selected[-1][0] is None


def test_goal_drag_emits_ros_position_and_world_yaw(canvas):
    goals = QSignalSpy(canvas.goal_changed)
    canvas.set_selected_region('a')
    canvas.set_mode('place_goal')
    start = canvas.mapFromScene(QPointF(20, 20))
    end = canvas.mapFromScene(QPointF(28, 20))
    drag(canvas, start, end)
    assert len(goals) == 1
    identifier, goal = goals[0]
    assert identifier == 'a'
    assert (goal.x, goal.y) == pytest.approx((0.25, 30.25))
    assert goal.yaw == pytest.approx(math.pi / 2)


def test_goal_requires_selection_and_click_keeps_existing_yaw(canvas):
    goals = QSignalSpy(canvas.goal_changed)
    canvas.set_mode('place_goal')
    click(canvas, 20, 20)
    assert not goals
    canvas.set_selected_region('a')
    click(canvas, 20, 20)
    assert goals[0][1].yaw == math.pi / 2


def test_zoom_changes_view_and_cursor_reports_pixel_and_ros(canvas, app):
    cursor = QSignalSpy(canvas.cursor_position_changed)
    point = canvas.mapFromScene(QPointF(10, 12))
    QTest.mouseMove(canvas.viewport(), point)
    app.processEvents()
    assert cursor[-1][0] == (10.0, 12.0)
    assert cursor[-1][1] == pytest.approx((-3.75, 25.25))
    before = canvas.transform().m11()
    event = QWheelEvent(QPointF(point), QPointF(canvas.mapToGlobal(point)),
                        QPoint(), QPoint(0, 120), Qt.NoButton, Qt.NoModifier,
                        Qt.NoScrollPhase, False)
    QApplication.sendEvent(canvas.viewport(), event)
    assert canvas.transform().m11() > before


def test_pan_does_not_emit_edits_and_bad_modes_are_rejected(canvas):
    polygons = QSignalSpy(canvas.polygon_completed)
    goals = QSignalSpy(canvas.goal_changed)
    canvas.set_mode('pan')
    canvas.scale(20, 20)
    canvas.centerOn(25, 20)
    before = canvas.horizontalScrollBar().value()
    start = canvas.mapFromScene(QPointF(25, 20))
    drag(canvas, start, start + QPoint(30, 0))
    assert canvas.horizontalScrollBar().value() == before - 30
    assert not polygons and not goals
    with pytest.raises(ValueError, match='mode'):
        canvas.set_mode('invalid')


def test_region_refresh_keeps_selection_and_uses_replaced_vertex_coordinates(canvas):
    selected = QSignalSpy(canvas.selection_changed)
    click(canvas, 15, 15)
    updated = Region('a', 'Updated', (), (0, 255, 0),
                     ((7, 7), (30, 5), (30, 30), (5, 30)), GoalPose(0, 30, 0))
    canvas.set_regions((updated,))
    assert canvas.selected_region_id == 'a'
    assert len(selected) == 1
    moved = QSignalSpy(canvas.vertex_moved)
    drag(canvas, canvas.mapFromScene(QPointF(7, 7)),
         canvas.mapFromScene(QPointF(10, 10)))
    assert moved[0] == ['a', 0, (10.0, 10.0)]
    assert updated.polygon_pixels[0] == (7, 7)
    canvas.set_regions(())
    assert selected[-1][0] is None


def test_reload_map_replaces_background_and_keeps_editing_usable(canvas, occupancy):
    canvas.set_selected_region('a')
    canvas.set_map(replace(occupancy, image=np.full((40, 50), 50, dtype=np.uint8)))
    backgrounds = [item for item in canvas.scene().items()
                   if isinstance(item, QGraphicsPixmapItem)]
    assert len(backgrounds) == 1
    assert backgrounds[0].pixmap().toImage().pixelColor(0, 0).red() == 50
    moved = QSignalSpy(canvas.vertex_moved)
    drag(canvas, canvas.mapFromScene(QPointF(5, 5)),
         canvas.mapFromScene(QPointF(9, 11)))
    assert moved[0] == ['a', 0, (9.0, 11.0)]
