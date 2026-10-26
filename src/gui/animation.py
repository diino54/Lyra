"""Small paint-only transitions that leave button geometry and input unchanged."""
from PySide6.QtCore import QEasingCurve, QEvent, QObject, QVariantAnimation, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget, QCheckBox


class _Highlight(QWidget):
    def __init__(self, button):
        super().__init__(button)
        self.amount = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self.setGeometry(button.rect())
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, round(self.amount)))
        name = self.parentWidget().objectName()
        radius = 3 if name in ('tab', 'fpsStep') else 7
        inset = 5 if name == 'fpsStep' else 1
        if isinstance(self.parentWidget(), QCheckBox):
            painter.drawRoundedRect(0, (self.height() - 16) // 2, 16, 16, 3, 3)
        else:
            painter.drawRoundedRect(self.rect().adjusted(inset, inset, -inset, -inset), radius, radius)


class ButtonMotion(QObject):
    def __init__(self, button):
        super().__init__(button)
        self.button = button
        self.overlay = _Highlight(button)
        self.animation = QVariantAnimation(self)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self.update_amount)
        button.installEventFilter(self)
        button.toggled.connect(lambda _: self.pulse_toggle())

    def pulse_toggle(self):
        self.animation.stop()
        self.animation.setStartValue(32.)
        self.animation.setEndValue(12. if self.button.underMouse() else 0.)
        self.animation.setDuration(340)
        self.animation.start()

    def update_amount(self, amount):
        self.overlay.amount = float(amount)
        self.overlay.update()

    def transition(self, pressed=False):
        pressed_amount = 28 if self.button.objectName() == 'fpsStep' else 0
        target = (pressed_amount if pressed else 12 if self.button.underMouse() else 0) if self.button.isEnabled() else 0
        self.animation.stop()
        self.animation.setStartValue(self.overlay.amount)
        self.animation.setEndValue(float(target))
        self.animation.setDuration(160 if pressed else 320)
        self.animation.start()

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind == QEvent.Resize:
            self.overlay.setGeometry(self.button.rect())
        elif kind in (QEvent.Enter, QEvent.Leave, QEvent.EnabledChange, QEvent.MouseButtonRelease, QEvent.KeyRelease):
            self.transition()
        elif kind in (QEvent.MouseButtonPress, QEvent.KeyPress):
            self.transition(pressed=True)
        return False


class PageMotion(QObject):
    def __init__(self, parent, layouts):
        super().__init__(parent)
        self.layouts = layouts
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self.update_spacing)

    def start(self, *_):
        self.animation.stop()
        self.animation.setStartValue(10.)
        self.animation.setEndValue(0.)
        self.animation.start()

    def update_spacing(self, value):
        for layout in self.layouts:
            layout.setContentsMargins(0, round(value), 0, 0)
