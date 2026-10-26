"""Vela's palette and control styling, shared by Lyra."""
from pathlib import Path
from PySide6.QtGui import QColor, QFont, QPalette


def apply_appearance(window):
    palette = window.palette()
    for role, color in (
        (QPalette.Window, '#0f0f0f'), (QPalette.Base, '#1a1a1a'),
        (QPalette.Button, '#1a1a1a'), (QPalette.Text, '#f5f5f5'),
        (QPalette.WindowText, '#f5f5f5'), (QPalette.ButtonText, '#f5f5f5'),
        (QPalette.Highlight, '#246bce'), (QPalette.HighlightedText, '#ffffff'),
        (QPalette.Light, '#444444'), (QPalette.Mid, '#333333'),
        (QPalette.Dark, '#080808'),
    ):
        palette.setColor(role, QColor(color))
    window.setPalette(palette)
    window.setFont(QFont('Noto Sans', 10))
    window.setProperty('eqBackground', '#101010')
    window.setProperty('eqCurve', '#dddddd')
    window.setObjectName('LyraWindow')
    assets = Path(__file__).resolve().parent.parent / 'assets'
    stylesheet = QSS.replace('@CHEVRON@', (assets / 'chevron-down.svg').as_posix())
    window.setStyleSheet(stylesheet)
    return '#aaaaaa'


QSS = """
            QWidget { font-family: 'Noto Sans'; font-size: 13px; color: #dddddd; }
            QWidget#LyraWindow { background: transparent; }
            QWidget#sidebar { background: transparent; border: none; }
            QWidget#settingsContent { background: transparent; }
            QLabel { background: transparent; }
            QFrame#previewSettings { background: #181818; border: 1px solid #383838; border-radius: 8px; }
            QPushButton#helpIcon { min-height: 0; padding: 0; border-radius: 14px; font-size: 15px; color: #dddddd; background: transparent; border: 1px solid #484848; }
            QLabel#panelTitle { color: #eeeeee; font-size: 15px; font-weight: 600; }
            QLabel#sectionTitle { color: #bdbdbd; font-size: 12px; font-weight: 600; }
            QFrame#sectionDivider { background: #2b2b2b; border: none; max-height: 1px; }
            QLabel#status { color: #aaaaaa; font-size: 12px; }
            QPushButton { min-height: 30px; padding: 0 8px; border-radius: 7px;
                background: #333333; border: 1px solid #373737; color: #d0d0d0; }
            QPushButton:pressed { background: #242424; border-color: #242424; }
            QPushButton#helpIcon:pressed { background: #242424; border-color: #242424; }
            QFrame#customizationTabs { background: #131313; border: 1px solid #383838; border-radius: 6px; }
            QFrame#customizationTabs QPushButton#tab { border: none; border-radius: 4px;
                background: transparent; color: #999999; padding: 0 4px; min-height: 30px; }
            QFrame#customizationTabs QPushButton#tab:checked { color: #eeeeee; background: #303030; }
            QFrame#customizationTabs QPushButton#tab:pressed { background: #242424; }
            QPushButton#apply { background: #246bce; color: #ffffff; border-color: #347cde; }
            QPushButton#apply:hover { background: #307bdf; border-color: #307bdf; }
            QPushButton#apply:pressed { background: #1855ac; border-color: #1855ac; }
            QPushButton#purpleAction { background: #7946c4; color: #ffffff; border-color: #925fdd; }
            QPushButton#purpleAction:hover { background: #8956d4; border-color: #a477e8; }
            QPushButton#purpleAction:pressed { background: #60339f; border-color: #7041b4; }
            QPushButton#purpleAction:focus { border-color: #c6a0ff; }
            QPushButton:disabled, QPushButton#apply:disabled, QPushButton#purpleAction:disabled {
                background: #303030; color: #777777; border-color: #333333; }
            QLineEdit, QComboBox, QDoubleSpinBox { background: #111111;
                border: 1px solid #2c2c2c; border-radius: 5px;
                min-height: 30px; padding: 0 10px; selection-background-color: #246bce; selection-color: #ffffff; }
            QLineEdit:hover, QComboBox:hover, QDoubleSpinBox:hover { background: #181818; border-color: #444444; }
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus { border-color: #686868; }
            QComboBox { padding-right: 30px; }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right;
                width: 28px; border: none; background: transparent; }
            QComboBox::down-arrow { image: url(@CHEVRON@); width: 12px; height: 8px; }
            QFrame#fpsControl { background: #111111; border: 1px solid #2c2c2c; border-radius: 5px; }
            QFrame#fpsControl:hover { background: #191919; }
            QFrame#fpsControl QDoubleSpinBox, QFrame#fpsControl QLineEdit {
                border: none; background: transparent; border-radius: 0; padding: 0; min-height: 0; }
            QFrame#fpsControl QPushButton#fpsStep { min-height: 0; padding: 0; font-size: 16px;
                background: transparent; border: none; border-radius: 0; outline: none; }
            QFrame#fpsControl QFrame#fpsSeparator { background: #2c2c2c; border: none; }
            QFrame#comboPopup { border: none; background: #1a1a1a; }
            QComboBox QAbstractItemView { background: #1a1a1a; color: #f5f5f5;
                selection-background-color: #303030; selection-color: #ffffff;
                border: none; outline: none; padding: 3px; }
            QComboBox QAbstractItemView::item { min-height: 30px; padding: 0 7px;
                border: none; border-radius: 3px; }
            QComboBox QAbstractItemView::item:selected { background: #303030; color: #eeeeee; border: none; }
            QComboBox QAbstractItemView::item:hover { background: #292929; }
            QSplitter::handle { background: transparent; }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: #0f0f0f; width: 8px; }
            QScrollBar::handle:vertical { background: #444444; min-height: 24px; }
        """
QSS += """
    QFrame#centerPanel { background: #101010; border: 1px solid #303030; border-radius: 12px; }
    QLabel#connectionStatus { color: #aaaaaa; font-size: 12px; }
    QLabel#connectionStatus[state="active"] { color: #7946c4; }
    QWidget#eqSurface { background: transparent; border: none; }
    QFrame#toneRow { background: transparent; border: none; }
    QLabel#toneHint, QLabel#curveHint { color: #999999; font-size: 12px; }
    QLabel#toneValue { color: #aaaaaa; font-size: 12px; }
    QLabel#toneName { color: #dddddd; font-size: 13px; }
    QScrollBar:horizontal { background: transparent; height: 8px; }
    QScrollBar::handle:horizontal { background: #444444; min-width: 24px; }
    QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
    QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
    QSlider::groove:horizontal { height: 3px; background: #333333; border-radius: 1px; }
    QSlider::sub-page:horizontal { background: #777777; border-radius: 1px; }
    QSlider::handle:horizontal { background: #dddddd; width: 10px; margin: -4px 0; border-radius: 5px; }
    QSlider::groove:vertical { width: 3px; background: #333333; }
    QSlider::handle:vertical { background: #dddddd; height: 10px; margin: 0 -4px; border-radius: 5px; }
    QToolTip { background: #1a1a1a; color: #dddddd; border: 1px solid #383838; padding: 6px; }
"""
