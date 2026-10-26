"""Single-instance desktop/tray lifecycle. No daemon, D-Bus API or root access."""

import argparse
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, QStandardPaths, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from lyra_equalizer.branding import APP_ID, APP_NAME
from lyra_equalizer.audio import AudioEngine
from lyra_equalizer.gui.window import EqualizerWindow
from lyra_equalizer.store import Store


def app_icon():
    return QIcon(str(Path(__file__).resolve().parent / "assets" / "lyra-equalizer.svg"))


class Controller(QObject):
    def __init__(self, app, hidden=False, store=None, engine=None):
        super().__init__(app)
        self.app = app
        self.store = store or Store()
        self.engine = engine or AudioEngine(self)
        self._stopping = False
        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self.app.setQuitOnLastWindowClosed(False)
        self.window = EqualizerWindow(self.store, self.engine, self.tray_available)
        self.window.setWindowIcon(app_icon())
        self.window.exit_requested.connect(self.stop)
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        self.menu = QMenu()
        open_action = QAction(f"Open {APP_NAME}", self)
        open_action.triggered.connect(self.show_window)
        self.menu.addAction(open_action)
        self.menu.addSeparator()
        self.exit_action = QAction("Quit", self)
        self.exit_action.triggered.connect(self.stop)
        self.menu.addAction(self.exit_action)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._activate)
        if self.tray_available:
            self.tray.show()
        self.engine.stopped.connect(self._stopped)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(4000)
        self.refresh_timer.timeout.connect(self.engine.refresh)
        self.refresh_timer.start()
        self.engine.refresh()
        self.window.commit()
        if not hidden or not self.tray_available:
            self.show_window()

    def _activate(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_window()

    def show_window(self):
        if self._stopping:
            return
        if self.window.isMinimized():
            self.window.showNormal()
        else:
            self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def stop(self):
        if self._stopping:
            return
        self._stopping = True
        self.window._closing = True
        self.window._save_timer.stop()
        self.window.save_geometry()
        self.exit_action.setEnabled(False)
        self.refresh_timer.stop()
        self.window.setEnabled(False)
        self.window.hide()
        self.engine.stop()

    def _stopped(self, error):
        if error:
            self._stopping = False
            self.window._closing = False
            self.exit_action.setEnabled(True)
            self.window.setEnabled(True)
            self.refresh_timer.start()
            self.window.on_error("Could not fully release audio: " + error)
            self.show_window()
            return
        self.window.hide()
        self.tray.hide()
        self.app.quit()


def main():
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} — a standalone PipeWire equalizer"
    )
    parser.add_argument("--tray", action="store_true", help="Start in the system tray")
    options = parser.parse_args()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(app_icon())
    runtime = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation))
    socket_name = str(runtime / "lyra-equalizer.socket")
    existing = QLocalSocket()
    existing.connectToServer(socket_name)
    if existing.waitForConnected(200):
        existing.disconnectFromServer()
        return
    # Serialize startup before removing a stale socket.
    instance_lock = QLockFile(str(runtime / "lyra-equalizer.lock"))
    instance_lock.setStaleLockTime(0)
    if not instance_lock.tryLock(0):
        if instance_lock.error() != QLockFile.LockError.LockFailedError:
            QMessageBox.critical(
                None, APP_NAME,
                "Could not lock the application runtime directory.",
            )
            return
        existing.connectToServer(socket_name)
        existing.waitForConnected(1000)
        existing.disconnectFromServer()
        return
    QLocalServer.removeServer(socket_name)
    server = QLocalServer(app)
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(socket_name):
        QMessageBox.critical(None, APP_NAME, server.errorString())
        return
    controller = Controller(app, hidden=options.tray)

    def reopen():
        connection = server.nextPendingConnection()
        if connection:
            connection.disconnectFromServer()
            connection.deleteLater()
        controller.show_window()

    server.newConnection.connect(reopen)
    signal.signal(signal.SIGINT, lambda *_: controller.stop())
    signal.signal(signal.SIGTERM, lambda *_: controller.stop())
    signal_timer = QTimer(app)
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start(400)
    app.exec()


if __name__ == "__main__":
    main()
