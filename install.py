#!/usr/bin/env python3
"""Install Lyra for the current user; no root access or downloads required."""
import argparse
import importlib
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parent
VERSION = "0.1.0"


def atomic_write(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(dir=path.parent, delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(data.encode("utf-8"))
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def locations(prefix):
    data = prefix / "share"
    return (
        data / "lyra-equalizer",
        prefix / "bin" / "lyra-equalizer",
        data / "applications" / "lyra-equalizer.desktop",
        data / "icons" / "hicolor" / "scalable" / "apps" / "lyra-equalizer.svg",
    )


def check_dependencies():
    missing = []
    if sys.version_info < (3, 10):
        missing.append("Python >= 3.10")
    for name in ("PySide6.QtWidgets", "PySide6.QtSvg", "PySide6.QtNetwork"):
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append(name)
    try:
        from PySide6 import __version__
        if tuple(int(part) for part in __version__.split(".")[:2]) < (6, 6):
            missing.append("PySide6 >= 6.6")
    except ImportError:
        pass
    for name in ("pactl", "pw-cli", "pw-dump"):
        if not shutil.which(name):
            missing.append(name)
    plugin_paths = [Path("/usr/lib64/ladspa/mbeq_1197.so"), Path("/usr/lib/ladspa/mbeq_1197.so")]
    plugin_paths += list(Path("/usr/lib").glob("*/ladspa/mbeq_1197.so"))
    plugin_paths += [Path(path) / "mbeq_1197.so" for path in os.environ.get("LADSPA_PATH", "").split(os.pathsep) if path]
    if not any(path.is_file() for path in plugin_paths):
        missing.append("SWH LADSPA mbeq_1197")
    if missing:
        raise RuntimeError(
            "Missing dependencies: " + ", ".join(missing)
            + "\nOn Fedora, install them with:\n"
            + "sudo dnf install python3-pyside6 pulseaudio-utils pipewire-utils ladspa-swh-plugins\n"
            + "A running PipeWire server with pipewire-pulse and a session manager is also required."
        )


def uninstall(prefix):
    root, launcher, desktop, icon = locations(prefix)
    marker = root / ".lyra-install.json"
    if not marker.is_file():
        raise RuntimeError("No Lyra installation found in " + str(prefix))
    saved = json.loads(marker.read_text(encoding="utf-8"))
    if saved.get("application") != "lyra-equalizer" or saved.get("prefix") != str(prefix):
        raise RuntimeError("Invalid installation marker; uninstallation aborted.")
    for path in (launcher, desktop, icon):
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise RuntimeError("Unexpected installation file: " + str(path))
    for path in (launcher, desktop, icon):
        path.unlink(missing_ok=True)
    shutil.rmtree(root)
    print("Lyra has been uninstalled. Your settings have been preserved.")


def install(prefix):
    check_dependencies()
    if not (SOURCE / "src" / "app.py").is_file():
        raise RuntimeError("Run install.py from a complete Lyra source checkout.")
    root, launcher, desktop, icon = locations(prefix)
    if root.exists() and not (root / ".lyra-install.json").is_file():
        raise RuntimeError("The destination directory contains another installation: " + str(root))
    if not root.exists() and any(path.exists() for path in (launcher, desktop, icon)):
        raise RuntimeError("Destination files already exist outside a Lyra installation; they have not been overwritten.")
    for path in (root, launcher, desktop, icon):
        if path.is_symlink():
            raise RuntimeError("The installation path is a symbolic link: " + str(path))
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".lyra-install-", dir=root.parent) as staging:
        stage = Path(staging) / "application"
        shutil.copytree(
            SOURCE / "src", stage / "lyra_equalizer",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        for name in ("LICENSE", "README.md"):
            shutil.copy2(SOURCE / name, stage / name)
        (stage / ".lyra-install.json").write_text(json.dumps({
            "application": "lyra-equalizer", "version": VERSION, "prefix": str(prefix),
        }), encoding="utf-8")
        previous = Path(staging) / "previous"
        if root.exists():
            root.rename(previous)
        try:
            stage.rename(root)
            wrapper = (
                "#!" + sys.executable + "\n# Installed by Lyra\n"
                + "import sys\nsys.path.insert(0, " + repr(str(root)) + ")\n"
                + "from lyra_equalizer.app import main\nmain()\n"
            )
            atomic_write(launcher, wrapper, 0o755)
            executable = str(launcher).replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$").replace("%", "%%")
            desktop_text = (
                "[Desktop Entry]\nType=Application\nName=Lyra\n"
                "Comment=Adjust the sound of a PipeWire playback output\n"
                + 'Exec="' + executable + '"\n'
                + "Icon=lyra-equalizer\nTerminal=false\n"
                "Categories=AudioVideo;Audio;Mixer;\nStartupWMClass=Lyra\n"
            )
            atomic_write(desktop, desktop_text)
            atomic_write(icon, (root / "lyra_equalizer/assets/lyra-equalizer.svg").read_text(encoding="utf-8"))
        except Exception:
            if root.exists():
                shutil.rmtree(root)
            if previous.exists():
                previous.rename(root)
            raise
    updater = shutil.which("update-desktop-database")
    if updater:
        subprocess.run([updater, str(desktop.parent)], capture_output=True, check=False)
    print("Installed Lyra " + VERSION + ".")
    print("Launch it from the application menu: Lyra")
    print("or run: " + shlex.quote(str(launcher)))
    print("Uninstall: " + shlex.join([sys.executable, str(Path(__file__).resolve()), "--prefix", str(prefix), "--uninstall"]))
    if str(prefix / "bin") not in os.environ.get("PATH", "").split(os.pathsep):
        print("The installation bin directory is not in PATH; the menu shortcut uses an absolute path.")


def main():
    parser = argparse.ArgumentParser(description="Lyra installer for Linux (no sudo required)")
    parser.add_argument("--prefix", type=Path, default=Path.home() / ".local", help="Installation directory")
    parser.add_argument("--check", action="store_true", help="Check dependencies without installing")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall the application and preserve settings")
    parser.add_argument("--version", action="version", version="Lyra " + VERSION)
    args = parser.parse_args()
    prefix = args.prefix.expanduser().resolve()
    try:
        if args.check:
            check_dependencies()
            print("Dependencies are available. You can install Lyra.")
        elif args.uninstall:
            uninstall(prefix)
        else:
            install(prefix)
    except (OSError, ValueError, RuntimeError) as error:
        print("Installation: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
