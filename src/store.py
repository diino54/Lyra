"""Validated user preferences and the current equalizer curve."""

import json
import math
import os
import tempfile
from pathlib import Path

FREQUENCIES = [
    50,
    100,
    156,
    220,
    311,
    440,
    622,
    880,
    1250,
    1750,
    2500,
    3500,
    5000,
    10000,
    20000,
]


def bands(gains):
    return [
        {"frequency": frequency, "gain": float(gain)}
        for frequency, gain in zip(FREQUENCIES, gains, strict=True)
    ]


def valid_gains(values):
    if not isinstance(values, list) or len(values) != 15:
        raise ValueError("The equalizer curve must contain fifteen bands")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
        raise ValueError("Gains must be numbers")
    try:
        gains = [float(value) for value in values]
    except OverflowError as error:
        raise ValueError("Gains must be finite values between -12 and +12 dB") from error
    if not all(math.isfinite(value) and -12 <= value <= 12 for value in gains):
        raise ValueError("Gains must be finite values between -12 and +12 dB")
    return gains


def default_settings():
    return {
        "mode": "simple",
        "output": "",
        "gains": [0.0] * 15,
    }


class Store:
    def __init__(self, directory=None):
        self.directory = (
            Path(directory)
            if directory is not None
            else Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
            / "lyra-equalizer"
        )
        self.path = self.directory / "settings.json"
        self.data = default_settings()
        self.migration_error = ""
        self._damaged_bytes = None
        self._load_error = None
        self.backup_path = None
        if self.path.exists():
            self._load()

    def _load(self):
        warnings = []
        try:
            raw = self.path.read_bytes()
        except OSError as error:
            # Never replace a file we could not read and preserve.
            self._load_error = error
            self.migration_error = f"Could not load settings: {error}"
            return
        try:
            saved = json.loads(raw)
            if not isinstance(saved, dict):
                raise ValueError("Settings must be an object")
        except (ValueError, UnicodeError) as error:
            saved = {}
            warnings.append(str(error))
        validators = {
            "gains": valid_gains,
            "output": valid_output,
            "mode": valid_mode,
        }
        for key, validate in validators.items():
            if key not in saved:
                continue
            try:
                self.data[key] = validate(saved[key])
            except (ValueError, TypeError, OverflowError) as error:
                warnings.append(f"{key}: {error}")
        if warnings:
            self._damaged_bytes = raw
            self.migration_error = "Some settings were recovered: " + "; ".join(warnings)

    def save(self):
        if self._load_error is not None:
            raise OSError(f"Refusing to overwrite unreadable settings: {self._load_error}")
        payload = json.dumps(self.data, indent=2, allow_nan=False) + "\n"
        self.directory.mkdir(parents=True, exist_ok=True)
        if self._damaged_bytes is not None:
            # A unique backup also protects an earlier recovery backup.
            with tempfile.NamedTemporaryFile(
                dir=self.directory, prefix="settings-recovered-", suffix=".json", delete=False
            ) as backup:
                backup.write(self._damaged_bytes)
                backup.flush()
                os.fsync(backup.fileno())
                self.backup_path = Path(backup.name)
            self._damaged_bytes = None
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.directory,
                prefix=".settings-", suffix=".tmp", delete=False
            ) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def valid_output(value):
    if not isinstance(value, str):
        raise ValueError("Output must be text")
    return value


def valid_mode(value):
    if value not in ("simple", "advanced"):
        raise ValueError("Mode must be simple or advanced")
    return value

