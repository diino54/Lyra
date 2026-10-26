"""Vela's shared desktop controls and surfaces, adapted for Lyra.

Derived from diino54/Vela, Copyright (c) 2026 Szymon Łaszcz, MIT licensed.
See assets/VELA-LICENSE.txt.
"""
from PySide6.QtCore import Qt, QRectF, QPointF, QPropertyAnimation, QEasingCurve, QVariantAnimation
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient, QLinearGradient
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QComboBox, QListView,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle, QDoubleSpinBox,
    QHBoxLayout, QPushButton, QScrollArea, QGraphicsOpacityEffect,
    QGraphicsScene, QGraphicsBlurEffect)
from .background import frosted_pixels

class PopupDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        option = QStyleOptionViewItem(option)
        option.state &= ~QStyle.State_HasFocus
        super().paint(painter, option, index)

class NoWheelComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        view = QListView(self)
        view.setItemDelegate(PopupDelegate(view))
        view.setFrameShape(QFrame.NoFrame)
        self.setView(view)
        self.view().window().setObjectName("comboPopup")

    def wheelEvent(self, event):
        event.ignore()

class NoWheelSpinBox(QDoubleSpinBox):
    def focusInEvent(self, event):
        container = getattr(self, 'editing_container', None)
        if container is not None:
            container.set_editing(True)
        self.display_suffix = self.suffix()
        self.display_special = self.specialValueText()
        self.setSuffix('')
        self.setSpecialValueText('')
        super().focusInEvent(event)
        self.selectAll()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        container = getattr(self, 'editing_container', None)
        if container is not None:
            container.set_editing(False)
        self.setSuffix(getattr(self, 'display_suffix', self.suffix()))
        self.setSpecialValueText(getattr(self, 'display_special', self.specialValueText()))

    def stepBy(self, steps):
        super().stepBy(steps)
        self.lineEdit().deselect()

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.clearFocus()

    def wheelEvent(self, event):
        event.ignore()

class NumberControl(QFrame):
    """Shared minus/value/plus control for every numeric setting."""
    def __init__(self, field):
        super().__init__()
        self.setObjectName('fpsControl')
        self.edit_amount = 0.
        self.edit_motion = QVariantAnimation(self)
        self.edit_motion.setDuration(240)
        self.edit_motion.setEasingCurve(QEasingCurve.OutCubic)
        self.edit_motion.valueChanged.connect(self.set_edit_amount)
        self.setFixedHeight(36)
        row = QHBoxLayout(self)
        row.setContentsMargins(1, 1, 1, 1)
        row.setSpacing(0)
        field.setMinimumWidth(0)
        field.setAlignment(Qt.AlignCenter)
        self.down = QPushButton('−')
        self.up = QPushButton('+')
        for button, direction, action in ((self.down, 'Decrease', field.stepDown),
                                          (self.up, 'Increase', field.stepUp)):
            button.setObjectName('fpsStep')
            button.setFocusPolicy(Qt.NoFocus)
            button.setAutoDefault(False)
            button.setFixedSize(36, 32)
            button.setAccessibleName(f'{direction} {field.accessibleName()}')
            button.setAutoRepeat(True)
            button.clicked.connect(action)
        def separator():
            line = QFrame()
            line.setObjectName('fpsSeparator')
            line.setFixedSize(1, 18)
            return line
        row.addWidget(self.down)
        row.addWidget(separator())
        row.addWidget(field, 1)
        row.addWidget(separator())
        row.addWidget(self.up)
        field.editing_container = self


    def set_edit_amount(self, value):
        self.edit_amount = float(value)
        self.update()

    def set_editing(self, active):
        self.edit_motion.stop()
        if active:
            self.set_edit_amount(1.)
        else:
            self.edit_motion.setStartValue(self.edit_amount)
            self.edit_motion.setEndValue(0.)
            self.edit_motion.start()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.edit_amount <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(self.edit_amount)
        painter.setPen(QPen(QColor('#484848'), 1))
        painter.setBrush(QColor('#242424'))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 5, 5)

class ScrollFade(QWidget):
    def __init__(self, parent, top=False):
        super().__init__(parent)
        self.top = top
        self.amount = 0.
        self.present = False
        self.dot_opacity = 1.
        self.pulse = QVariantAnimation(self)
        self.pulse.setDuration(1800)
        self.pulse.setStartValue(1.)
        self.pulse.setKeyValueAt(.5, .35)
        self.pulse.setEndValue(1.)
        self.pulse.setEasingCurve(QEasingCurve.InOutSine)
        self.pulse.setLoopCount(-1)
        self.pulse.valueChanged.connect(self.set_dot_opacity)
        self.motion = QVariantAnimation(self)
        self.motion.setDuration(260)
        self.motion.setEasingCurve(QEasingCurve.OutCubic)
        self.motion.valueChanged.connect(self.set_amount)
        self.motion.finished.connect(self.finish_transition)
        self.hide()
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)

    def set_dot_opacity(self, value):
        self.dot_opacity = float(value)
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if self.present:
            self.pulse.start()

    def hideEvent(self, event):
        self.pulse.stop()
        super().hideEvent(event)

    def set_amount(self, amount):
        self.amount = float(amount)
        self.update()

    def finish_transition(self):
        if not self.present:
            self.hide()

    def set_present(self, present):
        if self.present == present:
            return
        self.present = present
        self.motion.stop()
        self.show()
        self.motion.setStartValue(self.amount)
        self.motion.setEndValue(1. if present else 0.)
        self.motion.start()

    def paintEvent(self, event):
        gradient = QLinearGradient(0, self.height() if self.top else 0,
                                   0, 0 if self.top else self.height())
        gradient.setColorAt(0, QColor(24, 24, 24, 0))
        gradient.setColorAt(1, QColor(24, 24, 24, 255))
        painter = QPainter(self)
        painter.setOpacity(self.amount)
        painter.fillRect(self.rect(), gradient)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setOpacity(self.amount * self.dot_opacity)
        painter.setBrush(QColor('#929292'))
        y = 7 if self.top else self.height() - 7
        for offset in (-6, 0, 6):
            painter.drawEllipse(QPointF(self.width() / 2 + offset, y), 1.5, 1.5)

class SettingsScroll(QScrollArea):
    def __init__(self):
        super().__init__()
        self.viewport().setAutoFillBackground(False)
        self.fade = ScrollFade(self.viewport())
        self.top_fade = ScrollFade(self.viewport(), top=True)
        self.verticalScrollBar().rangeChanged.connect(self.update_fade)
        self.verticalScrollBar().valueChanged.connect(self.update_fade)

    def update_fade(self, *_):
        viewport = self.viewport()
        self.fade.setGeometry(0, max(0, viewport.height() - 48), viewport.width(), 48)
        self.fade.set_present(self.verticalScrollBar().value() < self.verticalScrollBar().maximum())
        self.fade.raise_()
        self.top_fade.setGeometry(0, 0, viewport.width(), 48)
        self.top_fade.set_present(self.verticalScrollBar().value() > self.verticalScrollBar().minimum())
        self.top_fade.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_fade()

class AnimatedStatus(QLabel):
    def __init__(self):
        super().__init__()
        self.fade = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.fade)
        self.fade.setOpacity(1.)
        self.motion = QPropertyAnimation(self.fade, b'opacity', self)
        self.motion.setDuration(220)
        self.motion.setEasingCurve(QEasingCurve.OutCubic)

    def setText(self, text):
        if text == self.text():
            return
        super().setText(text)
        self.motion.stop()
        self.motion.setStartValue(.3)
        self.motion.setEndValue(1.)
        self.motion.start()

class FrostedPanel(QFrame):
    def __init__(self):
        super().__init__()
        pixels = frosted_pixels(268, 576, .35, 24)
        self.texture = QImage(pixels, 268, 576, QImage.Format_RGB888).copy()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 6, 6)
        painter.setClipPath(shape)
        painter.drawImage(self.rect(), self.texture)
        painter.setClipping(False)
        painter.setPen(QPen(QColor('#303030'), 1))
        painter.drawPath(shape)


def blurred_grid(pixmap):
    """Blur only the cached background grid, keeping controls and the EQ crisp."""
    scene = QGraphicsScene()
    item = scene.addPixmap(pixmap)
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(5)
    effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
    item.setGraphicsEffect(effect)
    result = QPixmap(pixmap.size())
    result.setDevicePixelRatio(pixmap.devicePixelRatioF())
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    bounds = QRectF(0, 0, pixmap.width() / pixmap.devicePixelRatioF(),
                    pixmap.height() / pixmap.devicePixelRatioF())
    scene.render(painter, bounds, bounds)
    painter.end()
    return result


class BackgroundWidget(QWidget):
    def paintEvent(self, event):
        # Cache the static background; hovering controls never rebuilds the grid.
        scale = self.devicePixelRatioF()
        key = (self.width(), self.height(), scale)
        if getattr(self, '_background_key', None) != key:
            canvas = QPixmap(round(self.width() * scale), round(self.height() * scale))
            canvas.setDevicePixelRatio(scale)
            canvas.fill(QColor('#090909'))
            center = QPointF(self.width() * .5, self.height() * .5)
            radius = max(self.width() * .75, self.height() * .95)
            glow = QRadialGradient(center, radius)
            glow.setColorAt(0, QColor('#121212'))
            glow.setColorAt(1, QColor('#090909'))
            painter = QPainter(canvas)
            painter.fillRect(self.rect(), glow)
            grid = QPixmap(canvas.size())
            grid.setDevicePixelRatio(scale)
            grid.fill(Qt.transparent)
            lines = QPainter(grid)
            lines.setPen(QPen(QColor(255, 255, 255, 16), 1))
            for x in range(0, self.width(), 36):
                lines.drawLine(x, 0, x, self.height())
            for y in range(0, self.height(), 36):
                lines.drawLine(0, y, self.width(), y)
            fade = QRadialGradient(center, radius)
            fade.setColorAt(0, QColor(0, 0, 0, 255))
            fade.setColorAt(.45, QColor(0, 0, 0, 130))
            fade.setColorAt(.8, QColor(0, 0, 0, 20))
            fade.setColorAt(1, QColor(0, 0, 0, 0))
            lines.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            lines.fillRect(self.rect(), fade)
            lines.end()
            painter.drawPixmap(0, 0, blurred_grid(grid))
            painter.end()
            self._background = canvas
            self._background_key = key
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._background)
