"""One unprivileged PipeWire LADSPA sink, updated without rebuilding."""

import json
import queue
import subprocess
import threading
import time
import shlex

from PySide6.QtCore import QObject, Signal

from lyra_equalizer.branding import APP_NAME
from lyra_equalizer.store import FREQUENCIES, valid_gains

SINK = "Lyra_Equalizer"
PORTS = ["50Hz gain (low shelving)"] + [
    f"{frequency}Hz gain" for frequency in FREQUENCIES[1:]
]


def command(*arguments):
    try:
        result = subprocess.run(
            arguments, capture_output=True, text=True, timeout=8, check=False
        )
    except FileNotFoundError as error:
        raise RuntimeError(f"Required audio tool is missing: {arguments[0]}") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"Audio command timed out: {arguments[0]}") from error
    if result.returncode:
        raise RuntimeError(f"{shlex.join(arguments)}: {result.stderr.strip() or 'command failed'}")
    return result.stdout.strip()


def physical_outputs(sinks):
    return [
        sink
        for sink in sinks
        if not sink.get("name", "").startswith(("Lyra_", "Arctis_"))
        and sink.get("properties", {}).get("device.class") != "filter"
    ]


def live_properties(gains):
    return (
        "{ params = [ "
        + " ".join(
            f"{json.dumps(port)} {gain:.3f}"
            for port, gain in zip(PORTS, valid_gains(gains), strict=True)
        )
        + " ] }"
    )


class AudioSession:
    def __init__(self, run=command):
        self.run = run
        self.module = None
        self.output = ""
        self.active = False
        self.original_default = ""
        self.routes = {}
        self.last_gains = None
        self._backend_checked = False
    def outputs(self):
        return physical_outputs(self._sinks())

    def _sinks(self):
        return json.loads(self.run("pactl", "-f", "json", "list", "sinks"))

    def modules(self):
        result = []
        for line in self.run("pactl", "list", "short", "modules").splitlines():
            fields = line.split("\t")
            if (
                len(fields) >= 3
                and fields[0].isdigit()
                and fields[1] == "module-ladspa-sink"
            ):
                if f"sink_name={SINK}" in fields[2].split():
                    result.append(int(fields[0]))
        return result

    def _node(self):
        for node in json.loads(self.run("pw-dump")):
            if ((node.get("info") or {}).get("props") or {}).get("node.name") == SINK:
                return node["id"]
        raise RuntimeError(
            "The equalizer audio node disappeared. Reconnect the output and retry."
        )

    def _streams(self):
        return json.loads(self.run("pactl", "-f", "json", "list", "sink-inputs"))

    def _check_backend(self):
        if not self._backend_checked:
            info = json.loads(self.run("pactl", "-f", "json", "info"))
            if "pipewire" not in info.get("server_name", "").lower():
                raise RuntimeError(f"{APP_NAME} requires PipeWire with pipewire-pulse.")
            self._backend_checked = True

    def needs_reconfigure(self, outputs):
        modules = self.modules()
        present = self.module is not None and self.module in modules
        sink_present = any(sink.get("name") == SINK for sink in self._sinks())
        if not present or not sink_present:
            self.active = False
        return not self.active or self.output not in [sink["name"] for sink in outputs]

    def _prune_routes(self, streams):
        clients = {stream["index"]: stream.get("client") for stream in streams}
        self.routes = {
            index: route for index, route in self.routes.items()
            if index in clients and clients[index] == route[0]
        }

    def _wait_for_sink(self, name, timeout=3):
        deadline = time.monotonic() + timeout
        while True:
            sink = next((s for s in self._sinks() if s.get("name") == name), None)
            if sink is not None:
                return sink
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Audio output {name} is not ready. Retry audio.")
            time.sleep(0.05)

    def _set_default(self, name):
        self._wait_for_sink(name)
        deadline = time.monotonic() + 2
        while True:
            try:
                self.run("pactl", "set-default-sink", name)
                return
            except RuntimeError as error:
                if "no such entity" not in str(error).lower() or time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)

    def _move_stream(self, stream, target):
        try:
            self.run("pactl", "move-sink-input", str(stream["index"]), target)
        except RuntimeError:
            # Applications can close between listing and moving their stream.
            # Do not suppress failures for streams which are still present.
            current = next((s for s in self._streams()
                            if s["index"] == stream["index"]
                            and s.get("client") == stream.get("client")), None)
            if current is None:
                return
            target_sink = next((s for s in self._sinks() if s.get("name") == target), None)
            if target_sink and str(current.get("sink")) == str(target_sink["index"]):
                return
            raise

    def configure(self, output, gains, enabled):
        self._check_backend()
        gains = valid_gains(gains) if enabled else [0.0] * 15
        self.active = False
        existing = self.modules()
        sinks = self._sinks()
        if existing and not any(sink.get("name") == SINK for sink in sinks):
            # A half-removed module cannot be repaired by setting parameters.
            for module in existing:
                self.run("pactl", "unload-module", str(module))
            existing = []
        if self.module not in existing:
            self.module = None
            self.last_gains = None
        outputs = physical_outputs(sinks)
        if not outputs:
            raise RuntimeError(
                "No playback device found. Connect headphones or speakers and retry."
            )
        names = [sink["name"] for sink in outputs]
        if output not in names:
            if self.output in names:
                output = self.output
            else:
                default = self.run("pactl", "get-default-sink")
                output = default if default in names else names[0]
        previous_output = self.output
        self.output = output
        if self.module is None:
            default = self.run("pactl", "get-default-sink")
            if default != SINK and not self.original_default:
                self.original_default = default
            for module in existing[:-1]:
                self.run("pactl", "unload-module", str(module))
            if existing:
                self.module = existing[-1]
            else:
                controls = ",".join(f"{gain:.3f}" for gain in gains)
                arguments = (
                    f"sink_name={SINK} sink_master={output} "
                    f"sink_properties=\"device.description='{APP_NAME}'\" "
                    f"label=mbeq plugin=mbeq_1197 control={controls}"
                )
                self.module = int(
                    self.run("pactl", "load-module", "module-ladspa-sink", arguments)
                )
                self.last_gains = list(gains)
        if gains != self.last_gains:
            self.run(
                "pw-cli",
                "set-param",
                str(self._node()),
                "Props",
                live_properties(gains),
            )
            self.last_gains = list(gains)
        self._wait_for_sink(SINK)
        # Move the filter's own playback stream instead of replacing its input node.
        streams = self._streams()
        self._prune_routes(streams)
        targets = {str(sink["index"]): sink["name"] for sink in outputs}
        for stream in streams:
            if str(stream.get("owner_module")) == str(self.module):
                current = targets.get(str(stream["sink"]))
                requested = stream.get("properties", {}).get("target.object")
                # A newly created filter may still be waiting for the policy
                # manager to link it to the requested sink.
                if current != output and not (current is None and requested == output):
                    self._move_stream(stream, output)
        output_id = next(sink["index"] for sink in outputs if sink["name"] == output)
        for stream in streams:
            if (
                str(stream.get("sink")) == str(output_id)
                and stream.get("owner_module") is None
            ):
                self.routes.setdefault(stream["index"], (stream.get("client"), output))
                self._move_stream(stream, SINK)
        self._set_default(SINK)
        self.active = True
        return output, previous_output != output

    def close(self):
        """Restore live applications before removing the EQ."""
        if self.module is None:
            return
        existing = self.modules()
        outputs = self.outputs()
        names = [sink["name"] for sink in outputs]
        fallback = self.output if self.output in names else (names[0] if names else "")
        if fallback:
            if self.run("pactl", "get-default-sink") == SINK:
                original = self.original_default
                self.run("pactl", "set-default-sink",
                         original if original in names else fallback)
            own_ids = {str(s["index"]) for s in self._sinks()
                       if s.get("name") == SINK}
            for stream in self._streams():
                if (str(stream.get("sink")) not in own_ids
                        or stream.get("owner_module") is not None):
                    continue
                old_client, original = self.routes.get(stream["index"], (None, fallback))
                target = (original if original in names and old_client == stream.get("client")
                          else fallback)
                self._move_stream(stream, target)
        if self.module in existing:
            self.run("pactl", "unload-module", str(self.module))
        self.module = None
        self.active = False
        self.last_gains = None
        self.routes.clear()


class AudioEngine(QObject):
    outputs_changed = Signal(object)
    state_changed = Signal(str)
    failed = Signal(str)
    stopped = Signal(str)

    def __init__(self, parent=None, session=None):
        super().__init__(parent)
        self._queue = queue.Queue()
        self._pending = set()
        self._desired = None
        self._lock = threading.Lock()
        self._closing = False
        self._session = session if session is not None else AudioSession()
        self._thread = threading.Thread(
            target=self._work, daemon=True, name="lyra-audio"
        )
        self._thread.start()

    def configure(self, output, gains, enabled):
        with self._lock:
            if self._closing:
                return
            self._desired = (output, list(gains), bool(enabled))
        self._enqueue("apply")

    def _enqueue(self, action):
        with self._lock:
            if self._closing or action in self._pending:
                return
            self._pending.add(action)
            self._queue.put(action)

    def refresh(self):
        self._enqueue("refresh")

    def stop(self):
        with self._lock:
            if self._closing:
                return
            self._closing = True
            self._queue.put("stop")

    def _work(self):
        last = None
        while True:
            action = self._queue.get()
            with self._lock:
                self._pending.discard(action)
            if action == "stop":
                try:
                    self._session.close()
                    self.stopped.emit("")
                except Exception as error:
                    with self._lock:
                        self._closing = False
                    last = None
                    self.stopped.emit(str(error))
                    continue
                return
            if self._closing:
                continue
            try:
                if action == "refresh":
                    outputs = self._session.outputs()
                    self.outputs_changed.emit(outputs)
                    with self._lock:
                        desired = self._desired
                    if desired and (last is None or self._session.needs_reconfigure(outputs)):
                        last = None
                        self._enqueue("apply")
                    continue
                with self._lock:
                    desired = self._desired
                if desired is None:
                    continue
                if desired == last and not self._session.needs_reconfigure(self._session.outputs()):
                    continue
                output, _ = self._session.configure(*desired)
                last = desired
                self.outputs_changed.emit(self._session.outputs())
                self.state_changed.emit(output)
            except Exception as error:
                last = None
                self.failed.emit(str(error))
