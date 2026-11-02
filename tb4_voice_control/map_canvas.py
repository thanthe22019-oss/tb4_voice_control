"""Native-pixel occupancy map view emitting semantic edit intents."""

import math

from PyQt5.QtCore import pyqtSignal, QPointF, Qt
from PyQt5.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt5.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem, QGraphicsScene,
                             QGraphicsView)

from tb4_voice_control.map_model import OccupancyMap, pixel_to_ros, ros_to_pixel
from tb4_voice_control.regions import GoalPose


class _VertexHandle(QGraphicsEllipseItem):
    """Keep handles a usable screen size and emit one command per drag."""

    def __init__(self, canvas, identifier, index, point):
        super().__init__(-4, -4, 8, 8)
        self.canvas, self.identifier, self.index = canvas, identifier, index
        self.setBrush(QColor('white'))
        self.setPen(QPen(QColor('black')))
        self.setFlags(QGraphicsItem.ItemIsMovable
                      | QGraphicsItem.ItemSendsGeometryChanges
                      | QGraphicsItem.ItemIgnoresTransformations)
        self.setZValue(4)
        self.setPos(QPointF(*point))
        self._start = self.pos()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.canvas._preview_vertex(self.identifier, self.index, value)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self._start = self.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.pos() != self._start:
            self.canvas.vertex_moved.emit(self.identifier, self.index,
                                          (self.pos().x(), self.pos().y()))


class MapCanvas(QGraphicsView):
    """
    Display maps and overlays; controllers apply emitted edits to documents.

    Polygon and vertex payloads use continuous image pixel centers. Goal poses
    and cursor ROS positions include map origin rotation and image Y inversion.
    """

    polygon_completed = pyqtSignal(object)
    vertex_moved = pyqtSignal(str, int, object)
    goal_changed = pyqtSignal(str, object)
    selection_changed = pyqtSignal(object)
    cursor_position_changed = pyqtSignal(object, object)

    def __init__(self, parent=None):
        """Create an empty scene in selection mode."""
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setMouseTracking(True)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.occupancy = None
        self.mode = 'select'
        self.selected_region_id = None
        self._regions = {}
        self._polygons = {}
        self._overlays = []
        self._handles = []
        self._draw_points = []
        self._draw_item = None
        self._goal_start = None

    def set_map(self, occupancy: OccupancyMap):
        """Load an independent QImage copy with integer pixel centers."""
        self._cancel_draw()
        self._goal_start = None
        self.scene().clear()
        self._overlays, self._handles, self._polygons = [], [], {}
        self.occupancy = occupancy
        height, width = occupancy.image.shape
        image = QImage(occupancy.image.tobytes(), width, height, width,
                       QImage.Format_Grayscale8).copy()
        background = self.scene().addPixmap(QPixmap.fromImage(image))
        background.setPos(-0.5, -0.5)
        background.setZValue(-1)
        self.setSceneRect(-0.5, -0.5, width, height)
        self.resetTransform()
        self._render_regions()

    def set_regions(self, regions):
        """Refresh frozen region overlays after a controller applies an edit."""
        self._regions = {region.id: region for region in regions}
        if self.selected_region_id not in self._regions:
            self.set_selected_region(None)
        self._render_regions()

    def set_selected_region(self, identifier):
        """Focus a stable region ID and expose its draggable vertex handles."""
        if identifier is not None and identifier not in self._regions:
            raise KeyError(identifier)
        if identifier != self.selected_region_id:
            self.selected_region_id = identifier
            self._render_handles()
            self.selection_changed.emit(identifier)

    def set_mode(self, mode):
        """Choose an input mode and cancel incomplete gestures."""
        if mode not in ('select', 'draw_polygon', 'place_goal', 'pan'):
            raise ValueError(f'Unknown canvas mode: {mode}')
        self._cancel_draw()
        self._goal_start = None
        self.mode = mode
        self.setDragMode(QGraphicsView.ScrollHandDrag if mode == 'pan'
                         else QGraphicsView.NoDrag)
        self.setCursor(Qt.CrossCursor if mode in ('draw_polygon', 'place_goal')
                       else Qt.ArrowCursor)
        self._render_handles()

    def _render_regions(self):
        for item in self._overlays:
            self.scene().removeItem(item)
        self._overlays, self._polygons = [], {}
        for region in self._regions.values():
            color = QColor(*region.color)
            fill = QColor(color)
            fill.setAlpha(65)
            pen = QPen(color, 2)
            pen.setCosmetic(True)
            polygon = self.scene().addPolygon(
                QPolygonF([QPointF(*point) for point in region.polygon_pixels]), pen, fill)
            polygon.setData(0, region.id)
            polygon.setZValue(1)
            self._polygons[region.id] = polygon
            self._overlays.append(polygon)
            if self.occupancy is not None:
                x, y = ros_to_pixel((region.goal.x, region.goal.y),
                                    self.occupancy.metadata, self.occupancy.image.shape[0])
                marker = self.scene().addEllipse(x - 2, y - 2, 4, 4, pen, color)
                angle = region.goal.yaw - self.occupancy.metadata.origin[2]
                tip = (x + 12 * math.cos(angle), y - 12 * math.sin(angle))
                lines = [(x, y, *tip)]
                for offset in (-0.5, 0.5):
                    lines.append((*tip, tip[0] - 4 * math.cos(angle + offset),
                                  tip[1] + 4 * math.sin(angle + offset)))
                for item in [marker] + [self.scene().addLine(*line, pen) for line in lines]:
                    item.setData(0, region.id)
                    item.setZValue(2)
                    self._overlays.append(item)
        self._render_handles()

    def _render_handles(self):
        for item in self._handles:
            self.scene().removeItem(item)
        self._handles = []
        region = self._regions.get(self.selected_region_id)
        if region is not None and self.mode == 'select':
            for index, point in enumerate(region.polygon_pixels):
                handle = _VertexHandle(self, region.id, index, point)
                self.scene().addItem(handle)
                self._handles.append(handle)

    def _preview_vertex(self, identifier, index, point):
        polygon = self._polygons.get(identifier)
        if polygon is not None:
            points = polygon.polygon()
            points[index] = point
            polygon.setPolygon(points)

    def _cancel_draw(self):
        if self._draw_item is not None:
            self.scene().removeItem(self._draw_item)
        self._draw_item = None
        self._draw_points = []

    def _show_draw(self, cursor=None):
        if self._draw_item is not None:
            self.scene().removeItem(self._draw_item)
        path = QPainterPath()
        if self._draw_points:
            path.moveTo(QPointF(*self._draw_points[0]))
            for point in self._draw_points[1:]:
                path.lineTo(QPointF(*point))
            if cursor is not None:
                path.lineTo(cursor)
        pen = QPen(QColor('cyan'), 2, Qt.DashLine)
        pen.setCosmetic(True)
        self._draw_item = self.scene().addPath(path, pen)
        self._draw_item.setZValue(3)

    def _complete_polygon(self):
        if len(self._draw_points) >= 3:
            points = tuple(self._draw_points)
            self._cancel_draw()
            self.polygon_completed.emit(points)

    def mousePressEvent(self, event):
        """Route a click to polygon drawing, goal placement, or selection."""
        if event.button() != Qt.LeftButton or self.occupancy is None:
            super().mousePressEvent(event)
            return
        point = self.mapToScene(event.pos())
        if self.mode == 'draw_polygon':
            if (len(self._draw_points) >= 3
                    and (self.mapFromScene(QPointF(*self._draw_points[0]))
                         - event.pos()).manhattanLength() <= 8):
                self._complete_polygon()
            else:
                self._draw_points.append((point.x(), point.y()))
                self._show_draw()
            event.accept()
            return
        if self.mode == 'place_goal':
            if self.selected_region_id is not None:
                self._goal_start = point
            event.accept()
            return
        if self.mode == 'select':
            item = self.itemAt(event.pos())
            if not isinstance(item, _VertexHandle):
                self.set_selected_region(item.data(0) if item is not None else None)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Report cursor coordinates and preview an unfinished polygon."""
        point = self.mapToScene(event.pos())
        if self.occupancy is not None:
            pixel = (point.x(), point.y())
            self.cursor_position_changed.emit(pixel, pixel_to_ros(
                pixel, self.occupancy.metadata, self.occupancy.image.shape[0]))
        if self.mode == 'draw_polygon' and self._draw_points:
            self._show_draw(point)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Finish goal position and heading from one click or drag."""
        if (self.mode == 'place_goal' and event.button() == Qt.LeftButton
                and self._goal_start is not None):
            start, self._goal_start = self._goal_start, None
            region = self._regions.get(self.selected_region_id)
            if region is not None:
                height = self.occupancy.image.shape[0]
                x, y = pixel_to_ros((start.x(), start.y()), self.occupancy.metadata, height)
                end = self.mapToScene(event.pos())
                target = pixel_to_ros((end.x(), end.y()), self.occupancy.metadata, height)
                yaw = math.atan2(target[1] - y, target[0] - x) if end != start else region.goal.yaw
                self.goal_changed.emit(region.id, GoalPose(x, y, yaw))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        """Cancel gestures with Escape or complete a polygon with Enter."""
        if event.key() == Qt.Key_Escape:
            self._cancel_draw()
            self._goal_start = None
            event.accept()
        elif self.mode == 'draw_polygon' and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._complete_polygon()
            event.accept()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        """Zoom around the cursor with bounded, reversible scale steps."""
        if event.angleDelta().y():
            factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            if 0.05 <= self.transform().m11() * factor <= 100:
                self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)
