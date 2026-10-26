"""Lyra's equalizer model, painted preview, and gain editors."""

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal, QSignalBlocker
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QAbstractSpinBox, QLabel, QSizePolicy, QSlider, QVBoxLayout, QWidget,
)

from .design import NoWheelSpinBox, NumberControl
from lyra_equalizer.store import FREQUENCIES
from lyra_equalizer.tone_controls import apply_tone_curve, split_tone_curve


def gain_field(name, limit):
    field = NoWheelSpinBox()
    field.setRange(-limit, limit)
    field.setDecimals(1)
    field.setSingleStep(0.1)
    field.setSuffix(" dB")
    field.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    field.setAccessibleName(name)
    return field


class ToneSlider(QSlider):
    def wheelEvent(self, event):
        event.ignore()


class EqualizerCurve(QWidget):
    """Logarithmic frequency plot with bounded, smoothstep gain interpolation."""

    gain_edited = Signal(int, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bands = []
        self.editable = True
        self.active_band = None
        self.dragging = False
        self.setMinimumSize(160, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Equalizer curve")
        self.setAccessibleDescription("Drag band points or use arrow keys to adjust gain. Home resets the selected band.")

    def plot_rect(self):
        return QRectF(38, 20, max(1, self.width() - 60), max(1, self.height() - 54))

    def point(self, index):
        area = self.plot_rect()
        frequency = self.bands[index]["frequency"]
        low, high = self.bands[0]["frequency"], self.bands[-1]["frequency"]
        ratio = math.log(frequency / low) / math.log(high / low) if high > low else 0.5
        return QPointF(area.left() + ratio * area.width(), self.gain_y(self.bands[index]["gain"]))

    def gain_y(self, gain):
        area = self.plot_rect()
        return area.center().y() - gain * area.height() / 24

    def set_bands(self, bands):
        self.bands = [dict(band) for band in bands]
        if self.active_band is not None and self.active_band >= len(self.bands):
            self.active_band = None
        self.update()

    def set_editable(self, editable):
        self.editable = editable
        self.dragging = False
        self.active_band = None
        self.unsetCursor()
        self.update()

    def hit_band(self, position):
        candidates = [((self.point(i) - position).manhattanLength(), i) for i in range(len(self.bands))]
        distance, index = min(candidates, default=(float("inf"), None))
        return index if distance <= 16 else None

    def edit_gain(self, index, gain):
        value = round(max(-12.0, min(12.0, gain)), 3)
        if self.bands[index]["gain"] != value:
            self.bands[index]["gain"] = value
            self.gain_edited.emit(index, value)
            self.update()

    def mousePressEvent(self, event):
        if self.editable and event.button() == Qt.MouseButton.LeftButton:
            self.active_band = self.hit_band(event.position())
            if self.active_band is None and self.bands and self.plot_rect().contains(event.position()):
                self.active_band = min(
                    range(len(self.bands)),
                    key=lambda index: abs(self.point(index).x() - event.position().x()),
                )
                area = self.plot_rect()
                self.edit_gain(self.active_band, (area.center().y() - event.position().y()) * 24 / area.height())
            self.dragging = self.active_band is not None
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            event.accept()
            self.update()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        if not self.editable:
            event.ignore()
            return
        if self.dragging and self.active_band is not None:
            area = self.plot_rect()
            self.edit_gain(self.active_band, (area.center().y() - event.position().y()) * 24 / area.height())
        index = self.hit_band(event.position())
        self.setCursor(Qt.CursorShape.SizeVerCursor if index is not None else Qt.CursorShape.ArrowCursor)
        self.setToolTip("" if index is None else f'{self.bands[index]["frequency"]:g} Hz: {self.bands[index]["gain"]:+.3f} dB')

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
        self.update()

    def mouseDoubleClickEvent(self, event):
        if self.editable and event.button() == Qt.MouseButton.LeftButton:
            index = self.hit_band(event.position())
            if index is not None:
                self.active_band = index
                self.edit_gain(index, 0.0)

    def keyPressEvent(self, event):
        if not self.editable or not self.bands:
            event.ignore()
            return
        index = self.active_band if self.active_band is not None else 0
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            index = max(0, min(len(self.bands) - 1, index + (1 if key == Qt.Key.Key_Right else -1)))
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.edit_gain(index, self.bands[index]["gain"] + (0.1 if key == Qt.Key.Key_Up else -0.1))
        elif key == Qt.Key.Key_Home:
            self.edit_gain(index, 0.0)
        else:
            super().keyPressEvent(event)
            return
        self.active_band = index
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        area = self.plot_rect()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.window().property("eqBackground") or palette.color(QPalette.ColorRole.Base)))
        painter.drawRoundedRect(QRectF(self.rect()), 10, 10)
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        grid_color = QColor("#292929")
        zero_color = QColor("#505050")
        label_color = QColor("#999999")
        for gain in (-12, -6, 0, 6, 12):
            y = self.gain_y(gain)
            painter.setPen(QPen(zero_color if gain == 0 else grid_color, 1))
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            painter.setPen(label_color)
            painter.drawText(QRectF(0, y - 9, 32, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "0" if gain == 0 else f"{gain:+d}")
        points = [self.point(i) for i in range(len(self.bands))]
        label_edge = -1.0
        for index, point in enumerate(points):
            painter.setPen(QPen(grid_color, 1))
            painter.drawLine(QPointF(point.x(), area.top()), QPointF(point.x(), area.bottom()))
            frequency = self.bands[index]["frequency"]
            label = f"{frequency / 1000:g}k" if frequency >= 1000 else f"{frequency:g}"
            width = painter.fontMetrics().horizontalAdvance(label) + 10
            left = point.x() - width / 2
            if left > label_edge:
                painter.setPen(label_color)
                painter.drawText(QRectF(left, area.bottom() + 8, width, 20), Qt.AlignmentFlag.AlignCenter, label)
                label_edge = left + width + 5
        if not points:
            return
        path = QPainterPath(points[0])
        for left, right in zip(points, points[1:]):
            # Horizontal tangents keep each segment within its endpoint gains.
            middle = (left.x() + right.x()) / 2
            path.cubicTo(QPointF(middle, left.y()), QPointF(middle, right.y()), right)
        color = QColor(self.window().property("eqCurve") or palette.color(QPalette.ColorRole.Highlight))
        shade = QColor(color)
        shade.setAlpha(24)
        fill = QPainterPath(path)
        fill.lineTo(QPointF(points[-1].x(), self.gain_y(0)))
        fill.lineTo(QPointF(points[0].x(), self.gain_y(0)))
        fill.closeSubpath()
        painter.fillPath(fill, shade)
        # The curve is open: a brush would implicitly close and fill it,
        # painting a diagonal wedge over the grid and the intended shading.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(color, 2))
        painter.drawPath(path)
        for index, point in enumerate(points):
            painter.setBrush(palette.color(QPalette.ColorRole.Text) if index == self.active_band else color)
            painter.drawEllipse(point, 5 if index == self.active_band else 3.5, 5 if index == self.active_band else 3.5)


class ToneControls(QWidget):
    controls_edited = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fields = []
        self.sliders = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        for index, (title, hint) in enumerate((("Bass", "Depth and low-end punch"), ("Vocals", "Voices and dialogue"), ("Treble", "Detail and brightness"))):
            name = QLabel(title)
            name.setObjectName("toneName")
            layout.addWidget(name)
            field = gain_field(title, 12)
            layout.addWidget(NumberControl(field))
            slider = ToneSlider(Qt.Orientation.Horizontal)
            slider.setRange(-120, 120)
            slider.setAccessibleName(title)
            slider.setToolTip("Adjust from −12 to +12 dB. 0 dB is neutral.")
            layout.addWidget(slider)
            description = QLabel(hint)
            description.setObjectName("toneHint")
            layout.addWidget(description)
            self.fields.append(field)
            self.sliders.append(slider)
            field.valueChanged.connect(lambda value, i=index: self.edit(i, value))
            slider.valueChanged.connect(lambda value, i=index: self.edit(i, value / 10))

    def sync(self, values):
        for field, slider, value in zip(self.fields, self.sliders, values, strict=True):
            with QSignalBlocker(field), QSignalBlocker(slider):
                if field.value() != value:
                    field.setValue(value)
                slider.setValue(round(value * 10))

    def edit(self, index, value):
        values = [field.value() for field in self.fields]
        values[index] = value
        self.sync(values)
        self.controls_edited.emit(values)


class EqualizerView(QWidget):
    """Owns exact band values; display rounding never changes stored gains."""

    band_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bands = []
        self._residual = []
        self.simple = True
        self.disabled = False
        self.curve = EqualizerCurve(self)
        self.tone_controls = ToneControls(self)
        self.tone_controls.hide()
        self.tone_controls.controls_edited.connect(self.edit_tone)
        self.curve.gain_edited.connect(self.edit_band)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.curve)

    def get_bands(self):
        return [dict(band) for band in self._bands]

    def set_bands(self, bands, disabled=False):
        self._bands = [dict(band) for band in bands]
        self.disabled = disabled
        values, self._residual = split_tone_curve(self._bands)
        self.tone_controls.sync(values)
        self.tone_controls.setEnabled(not disabled)
        self.curve.set_bands(self._bands)
        self.curve.set_editable(not (self.simple or disabled))

    def set_simple_mode(self, simple):
        self.simple = simple
        self.tone_controls.setVisible(simple)
        self.curve.set_editable(not (simple or self.disabled))

    def edit_band(self, index, gain):
        if self.disabled or not 0 <= index < len(self._bands):
            return
        self._bands[index]["gain"] = max(-12.0, min(12.0, float(gain)))
        self.curve.set_bands(self._bands)
        self.band_changed.emit()

    def edit_tone(self, values):
        if self.disabled or not self._bands:
            return
        self._bands = apply_tone_curve(self._bands, values, self._residual)
        self.curve.set_bands(self._bands)
        self.band_changed.emit()


class BandControls(QWidget):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.fields = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        for index, frequency in enumerate(FREQUENCIES):
            layout.addWidget(QLabel(f"{frequency:g} Hz"))
            field = gain_field(f"{frequency:g} Hz gain", 12)
            field.valueChanged.connect(lambda value, i=index: view.edit_band(i, value))
            layout.addWidget(NumberControl(field))
            self.fields.append(field)

    def sync(self):
        for field, band in zip(self.fields, self.view.get_bands()):
            with QSignalBlocker(field):
                displayed = round(band["gain"], field.decimals())
                if field.value() != displayed:
                    field.setValue(band["gain"])
        self.setEnabled(not self.view.disabled)
