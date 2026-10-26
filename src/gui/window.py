"""Vela-style customization, equalizer preview and audio panels."""

from PySide6.QtCore import QSettings, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QVBoxLayout, QWidget,
)

from lyra_equalizer.branding import APP_NAME
from lyra_equalizer.gui.appearance import apply_appearance
from lyra_equalizer.gui.animation import ButtonMotion, PageMotion
from lyra_equalizer.gui.design import (
    AnimatedStatus, BackgroundWidget, FrostedPanel, NoWheelComboBox, SettingsScroll,
)
from lyra_equalizer.gui.widgets import BandControls, EqualizerView
from lyra_equalizer.store import bands


class EqualizerWindow(BackgroundWidget):
    exit_requested = Signal()

    def __init__(self, store, engine, tray_available=True):
        super().__init__()
        self.store, self.engine = store, engine
        self.tray_available = tray_available
        self._closing = False
        self._outputs = []
        self._save_error = ""
        self._geometry_error = ""
        self._audio_error = ""
        self._audio_active = False
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1060, 600)
        self.resize(1400, 780)
        apply_appearance(self)
        self.geometry_settings = QSettings(
            str(store.directory / "window.ini"), QSettings.Format.IniFormat
        )
        outer = QHBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(18)
        splitter.setChildrenCollapsible(False)
        outer.addWidget(splitter)

        sidebar = FrostedPanel()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(268)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(6, 6, 6, 6)
        sidebar_layout.setSpacing(0)
        self.settings_scroll = SettingsScroll()
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_layout.addWidget(self.settings_scroll)
        content = QWidget()
        content.setObjectName("settingsContent")
        content.setAutoFillBackground(False)
        self.settings_scroll.setWidget(content)
        panel = QVBoxLayout(content)
        panel.setContentsMargins(13, 15, 13, 15)
        panel.setSpacing(0)
        title = QLabel("Customization")
        title.setObjectName("panelTitle")
        panel.addWidget(title)
        panel.addSpacing(18)
        tabs = QFrame()
        tabs.setObjectName("customizationTabs")
        modes = QHBoxLayout(tabs)
        modes.setContentsMargins(2, 2, 2, 2)
        modes.setSpacing(0)
        self.mode_group = QButtonGroup(self)
        self.simple_button = QPushButton("Simple")
        self.advanced_button = QPushButton("Advanced")
        for button in (self.simple_button, self.advanced_button):
            button.setObjectName("tab")
            button.setCheckable(True)
            self.mode_group.addButton(button)
            modes.addWidget(button)
        self.simple_button.clicked.connect(lambda: self._set_mode("simple"))
        self.advanced_button.clicked.connect(lambda: self._set_mode("advanced"))
        panel.addWidget(tabs)
        panel.addSpacing(24)
        self.editor_title = QLabel("Tone")
        self.editor_title.setObjectName("sectionTitle")
        panel.addWidget(self.editor_title)
        panel.addSpacing(12)
        self.view = EqualizerView()
        self.view.band_changed.connect(self._edit)
        self.simple_controls = self.view.tone_controls
        panel.addWidget(self.simple_controls)
        self.advanced_controls = BandControls(self.view)
        panel.addWidget(self.advanced_controls)
        panel.addStretch()
        self.page_motion = PageMotion(self, (
            self.simple_controls.layout(), self.advanced_controls.layout(),
        ))
        splitter.addWidget(sidebar)

        center = QFrame()
        center.setObjectName("centerPanel")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(12, 12, 12, 14)
        center_layout.setSpacing(12)
        center_layout.addWidget(self.view, 1)
        self.editor_hint = QLabel()
        self.editor_hint.setObjectName("curveHint")
        self.editor_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.editor_hint.setWordWrap(True)
        center_layout.addWidget(self.editor_hint)
        splitter.addWidget(center)

        right_column = QWidget()
        right_column.setFixedWidth(268)
        right_column_layout = QVBoxLayout(right_column)
        right_column_layout.setContentsMargins(0, 0, 0, 0)
        right_column_layout.setSpacing(12)
        right = FrostedPanel()
        right.setObjectName("sidebar")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(19, 21, 19, 21)
        right_layout.setSpacing(12)
        title = QLabel("Audio output")
        title.setObjectName("panelTitle")
        right_layout.addWidget(title)
        right_layout.addSpacing(6)
        label = QLabel("Playback device")
        label.setObjectName("sectionTitle")
        right_layout.addWidget(label)
        self.output_combo = NoWheelComboBox()
        self.output_combo.setPlaceholderText("Finding devices…")
        self.output_combo.setAccessibleName("Playback device")
        self.output_combo.currentIndexChanged.connect(self._select_output)
        right_layout.addWidget(self.output_combo)
        self.refresh_button = QPushButton("Refresh devices")
        self.refresh_button.setObjectName("purpleAction")
        self.refresh_button.setAccessibleName("Refresh audio devices")
        self.refresh_button.clicked.connect(self.engine.refresh)
        right_layout.addWidget(self.refresh_button)
        line = QFrame()
        line.setObjectName("sectionDivider")
        line.setFixedHeight(1)
        right_layout.addSpacing(4)
        right_layout.addWidget(line)
        right_layout.addSpacing(4)
        label = QLabel("Status")
        label.setObjectName("sectionTitle")
        status_row = QHBoxLayout()
        status_row.addWidget(label)
        status_row.addStretch()
        self.activity = AnimatedStatus()
        self.activity.setObjectName("connectionStatus")
        self.activity.setText("Connecting…")
        status_row.addWidget(self.activity)
        right_layout.addLayout(status_row)
        equalizer_row = QHBoxLayout()
        equalizer_label = QLabel("Equalizer")
        equalizer_label.setObjectName("sectionTitle")
        equalizer_row.addWidget(equalizer_label)
        equalizer_row.addStretch()
        self.status = AnimatedStatus()
        self.status.setObjectName("connectionStatus")
        self.status.setText("Starting audio…")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        equalizer_row.addWidget(self.status)
        right_layout.addLayout(equalizer_row)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setTextFormat(Qt.TextFormat.PlainText)
        self.error.setStyleSheet("color: #e5a5a5;")
        self.error.hide()
        right_layout.addWidget(self.error)
        self.warning = QLabel(store.migration_error)
        self.warning.setWordWrap(True)
        self.warning.setTextFormat(Qt.TextFormat.PlainText)
        self.warning.setVisible(bool(store.migration_error))
        right_layout.addWidget(self.warning)
        right_layout.addStretch()
        self.retry_button = QPushButton("Retry audio")
        self.retry_button.setObjectName("apply")
        self.retry_button.clicked.connect(self.commit)
        self.retry_button.hide()
        right_layout.addWidget(self.retry_button)
        right_column_layout.addWidget(right, 1)
        curve_panel = FrostedPanel()
        curve_panel.setObjectName("sidebar")
        curve_layout = QVBoxLayout(curve_panel)
        curve_layout.setContentsMargins(18, 18, 18, 18)
        curve_layout.setSpacing(12)
        label = QLabel("Equalizer")
        label.setObjectName("sectionTitle")
        curve_layout.addWidget(label)
        note = QLabel("15 bands · −12 to +12 dB")
        curve_layout.addWidget(note)
        self.reset_button = QPushButton("Reset curve")
        self.reset_button.setObjectName("purpleAction")
        self.reset_button.setToolTip("Reset all fifteen bands to 0 dB")
        self.reset_button.clicked.connect(self._reset_curve)
        curve_layout.addWidget(self.reset_button)
        right_column_layout.addWidget(curve_panel)
        splitter.addWidget(right_column)
        splitter.setSizes([268, 800, 268])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        for control in self.findChildren(QWidget):
            control.setCursor(Qt.CursorShape.ArrowCursor)
            if control.focusPolicy() == Qt.FocusPolicy.WheelFocus:
                control.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.button_motion = [ButtonMotion(button) for button in self.findChildren(QPushButton)]
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(180)
        self._save_timer.timeout.connect(self.commit)
        self.engine.outputs_changed.connect(self.on_outputs)
        self.engine.state_changed.connect(self.on_active)
        self.engine.failed.connect(self.on_error)
        self._set_mode(store.data["mode"], save=False)
        self.view.set_bands(bands(store.data["gains"]))
        geometry = self.geometry_settings.value("geometry")
        if geometry is not None:
            try:
                if not self.restoreGeometry(geometry):
                    raise ValueError("Invalid window geometry")
            except (TypeError, ValueError):
                messages = (
                    store.migration_error,
                    "Could not restore window geometry; using the default size.",
                )
                self.warning.setText("\n".join(filter(None, messages)))
                self.warning.show()

    def _set_mode(self, mode, save=True):
        self.store.data["mode"] = mode
        self.simple_button.setChecked(mode == "simple")
        self.advanced_button.setChecked(mode == "advanced")
        self.editor_hint.setText(
            "Changes are applied and saved automatically." if mode == "simple"
            else "Click or drag the graph to adjust a band. Double-click a point to reset."
        )
        self.view.set_simple_mode(mode == "simple")
        self.view.set_bands(bands(self.store.data["gains"]))
        self.advanced_controls.setVisible(mode == "advanced")
        self.advanced_controls.sync()
        self.editor_title.setText("Tone" if mode == "simple" else "Frequency bands")
        self.settings_scroll.verticalScrollBar().setValue(0)
        if save:
            self.page_motion.start()
        if save:
            self.persist()

    def _edit(self):
        self.store.data["gains"] = [band["gain"] for band in self.view.get_bands()]
        self.advanced_controls.sync()
        self._save_timer.start()

    def persist(self):
        try:
            self.store.save()
            self._save_error = ""
        except (OSError, ValueError, TypeError) as error:
            self._save_error = f"Could not save settings: {error}"
        self._update_status()

    def commit(self):
        self._save_timer.stop()
        if self._geometry_error:
            self.save_geometry()
        else:
            self.persist()
        self.engine.configure(
            self.store.data["output"],
            self.store.data["gains"],
            True,
        )

    def _reset_curve(self):
        self.store.data["gains"] = [0.0] * 15
        self.view.set_bands(bands(self.store.data["gains"]))
        self.advanced_controls.sync()
        self.commit()

    def _select_output(self, index):
        if index >= 0:
            self.store.data["output"] = self.output_combo.itemData(index)
            self.commit()

    def on_outputs(self, outputs):
        self._outputs = outputs
        selected = self.store.data["output"]
        self.output_combo.blockSignals(True)
        self.output_combo.clear()
        for sink in outputs:
            self.output_combo.addItem(
                sink.get("description", sink["name"]), sink["name"]
            )
        self.output_combo.setPlaceholderText(
            "Select a playback device" if outputs else "No playback devices found"
        )
        self.output_combo.setCurrentIndex(self.output_combo.findData(selected))
        self.output_combo.blockSignals(False)

    def on_active(self, output):
        self.store.data["output"] = output
        self.on_outputs(self._outputs)
        self._audio_active = True
        self._audio_error = ""
        self.persist()

    def on_error(self, error):
        self._audio_error = error
        self._audio_active = False
        self._update_status()

    def _update_status(self):
        errors = [
            error for error in
            (self._save_error, self._geometry_error, self._audio_error) if error
        ]
        self.error.setText("\n".join(errors))
        self.error.setVisible(bool(errors))
        self.retry_button.setVisible(bool(errors))
        self.retry_button.setText(
            "Retry" if self._save_error or self._geometry_error else "Retry audio"
        )
        if errors:
            self.activity.setText("Needs attention")
            state = "error"
            self.status.setText(
                "Audio needs attention" if self._audio_error else "Settings need attention"
            )
        elif self._audio_active:
            self.activity.setText("Connected")
            state = "active"
            self.status.setText("Active")
        else:
            self.activity.setText("Connecting…")
            state = "pending"
            self.status.setText("Starting audio…")
        for label in (self.activity, self.status):
            if label.property("state") != state:
                label.setProperty("state", state)
                label.style().unpolish(label)
                label.style().polish(label)

    def save_geometry(self):
        self.geometry_settings.setValue("geometry", self.saveGeometry())
        self.geometry_settings.sync()
        self._geometry_error = (
            "Could not save window geometry."
            if self.geometry_settings.status() != QSettings.Status.NoError else ""
        )
        self.persist()

    def closeEvent(self, event):
        self.save_geometry()
        event.ignore()
        if self.tray_available and not self._closing:
            self.hide()
        else:
            self.exit_requested.emit()
