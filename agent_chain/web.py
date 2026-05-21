"""Small real-time web UI for AgentChain runs."""

from __future__ import annotations

import json
import os
import queue
import shlex
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from .integrations import (
    build_cli_pair_config,
    uses_generated_cli_config,
)
from .pipeline import run_pipeline
from .registry import resolve_agents
from .tools.env import Environment, ShellResult


Event = Dict[str, Any]


@dataclass
class RunRecord:
    id: str
    created_at: float
    status: str = "queued"
    events: List[Event] = field(default_factory=list)
    subscribers: List[queue.Queue[Event]] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    _seq: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def emit(self, event_type: str, data: Dict[str, Any] | None = None) -> None:
        with self._lock:
            self._seq += 1
            event = {
                "seq": self._seq,
                "type": event_type,
                "time": time.time(),
                "run_id": self.id,
                "data": data or {},
            }
            self.events.append(event)
            subscribers = list(self.subscribers)

        for subscriber in subscribers:
            subscriber.put(event)

    def subscribe(self) -> tuple[queue.Queue[Event], List[Event]]:
        subscriber: queue.Queue[Event] = queue.Queue()
        with self._lock:
            replay = list(self.events)
            self.subscribers.append(subscriber)
        return subscriber, replay

    def unsubscribe(self, subscriber: queue.Queue[Event]) -> None:
        with self._lock:
            if subscriber in self.subscribers:
                self.subscribers.remove(subscriber)

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            last_event = self.events[-1] if self.events else None
        return {
            "id": self.id,
            "created_at": self.created_at,
            "status": self.status,
            "event_count": len(self.events),
            "last_event": last_event,
            "result": self.result,
            "error": self.error,
        }


class RunStore:
    def __init__(self) -> None:
        self._runs: Dict[str, RunRecord] = {}
        self._lock = threading.Lock()

    def create(self) -> RunRecord:
        record = RunRecord(id=uuid.uuid4().hex[:12], created_at=time.time())
        with self._lock:
            self._runs[record.id] = record
        return record

    def get(self, run_id: str) -> Optional[RunRecord]:
        with self._lock:
            return self._runs.get(run_id)

    def list(self) -> List[Dict[str, Any]]:
        with self._lock:
            runs = list(self._runs.values())
        return [run.summary() for run in sorted(runs, key=lambda item: item.created_at, reverse=True)]


class EventEnvironment(Environment):
    """Environment variant that streams subprocess output into UI events."""

    def __init__(self, workspace: Path, emit) -> None:  # type: ignore[no-untyped-def]
        super().__init__(workspace, read_only=False)
        self._emit = emit

    def run_shell(self, command: Union[str, List[str]]) -> ShellResult:
        if self.read_only:
            raise PermissionError("현재 Environment는 read-only 모드입니다. 셸 명령을 실행할 수 없습니다.")

        if isinstance(command, str):
            cmd_list = shlex.split(command, posix=(os.name != "nt"))
        else:
            cmd_list = list(command)

        if cmd_list:
            executable = shutil.which(str(cmd_list[0]))
            if executable:
                cmd_list[0] = executable

        self._emit("shell_started", {"command": cmd_list})
        process = subprocess.Popen(
            cmd_list,
            cwd=self.workspace,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )

        stdout_parts: List[str] = []
        stderr_parts: List[str] = []

        def read_stream(stream, name: str, sink: List[str]) -> None:  # type: ignore[no-untyped-def]
            assert stream is not None
            for line in iter(stream.readline, ""):
                sink.append(line)
                self._emit("shell_output", {"stream": name, "text": line})
            stream.close()

        stdout_thread = threading.Thread(
            target=read_stream,
            args=(process.stdout, "stdout", stdout_parts),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=read_stream,
            args=(process.stderr, "stderr", stderr_parts),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()
        returncode = process.wait()
        stdout_thread.join()
        stderr_thread.join()

        stdout = "".join(stdout_parts)
        stderr = "".join(stderr_parts)
        self._emit(
            "shell_completed",
            {
                "returncode": returncode,
                "stdout_length": len(stdout),
                "stderr_length": len(stderr),
            },
        )
        return ShellResult(returncode=returncode, stdout=stdout, stderr=stderr)


def _load_yaml(path: Path) -> Dict[str, Any]:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    return int(value)


def _build_config(payload: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
    config_path = _clean_text(payload.get("config"))
    profile = _clean_text(payload.get("profile"))
    coder_cli = _clean_text(payload.get("coder_cli"))
    reviewer_cli = _clean_text(payload.get("reviewer_cli"))

    should_generate = uses_generated_cli_config(
        profile=profile,
        coder_cli=coder_cli,
        reviewer_cli=reviewer_cli,
    )
    if not config_path and not should_generate:
        coder_cli = "codex"
        reviewer_cli = "kimi"
        should_generate = True

    if config_path and should_generate:
        raise ValueError("config mode cannot be combined with profile/coder/reviewer options.")

    if should_generate:
        config = build_cli_pair_config(
            profile=profile,
            coder_cli=coder_cli,
            reviewer_cli=reviewer_cli,
            max_iterations=_int_or_none(payload.get("max_iterations")),
            target_file=_clean_text(payload.get("target_file")),
            coder_model=_clean_text(payload.get("coder_model")),
            reviewer_model=_clean_text(payload.get("reviewer_model")),
            coder_command=_clean_text(payload.get("coder_command")),
            reviewer_command=_clean_text(payload.get("reviewer_command")),
        )
        label = profile or f"{coder_cli or 'codex'}-{reviewer_cli or 'antigravity'}"
        return config, f"generated:{label}"

    path = Path(config_path or "config.yaml")
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    config = _load_yaml(path)
    max_iterations = _int_or_none(payload.get("max_iterations"))
    if max_iterations is not None:
        config["max_iterations"] = max_iterations
    return config, str(path)


def _run_worker(record: RunRecord, payload: Dict[str, Any]) -> None:
    record.status = "running"
    record.emit("server_status", {"status": "running"})
    started = time.time()

    try:
        request = _clean_text(payload.get("request"))
        if not request:
            raise ValueError("request is required.")

        config, config_label = _build_config(payload)
        workspace = Path(_clean_text(payload.get("workspace")) or ".").resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        plugins_dir_text = _clean_text(payload.get("plugins_dir"))
        plugins_dir = Path(plugins_dir_text) if plugins_dir_text else None
        language = _clean_text(payload.get("language")) or "python"

        record.emit(
            "config_loaded",
            {
                "config": config_label,
                "workspace": str(workspace),
                "language": language,
                "steps": config.get("steps", []),
                "max_iterations": config.get("max_iterations", 3),
            },
        )

        agents = resolve_agents(config, plugins_dir=plugins_dir)
        record.emit("agents_resolved", {"agents": sorted(agents)})

        env = EventEnvironment(workspace, record.emit)
        context = run_pipeline(
            agents=agents,
            config=config,
            request=request,
            workspace=workspace,
            env=env,
            language=language,
            event_callback=record.emit,
        )

        record.status = "completed"
        record.result = context.to_dict()
        record.emit(
            "server_status",
            {
                "status": "completed",
                "duration": time.time() - started,
            },
        )
    except Exception as exc:
        record.status = "failed"
        record.error = str(exc)
        record.emit(
            "run_failed",
            {
                "error": str(exc),
                "duration": time.time() - started,
            },
        )


class AgentChainHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], store: RunStore) -> None:
        super().__init__(server_address, AgentChainHandler)
        self.store = store


class AgentChainHandler(BaseHTTPRequestHandler):
    server: AgentChainHTTPServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/":
            self._send_html(INDEX_HTML)
            return
        if path == "/api/runs":
            self._send_json({"runs": self.server.store.list()})
            return
        if path.startswith("/api/runs/") and path.endswith("/events"):
            run_id = path.split("/")[3]
            self._send_events(run_id)
            return
        if path.startswith("/api/runs/"):
            run_id = path.split("/")[3]
            record = self.server.store.get(run_id)
            if record is None:
                self._send_json({"error": "run not found"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json(record.summary())
            return

        self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.rstrip("/") != "/api/runs":
            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except json.JSONDecodeError:
            self._send_json({"error": "invalid json"}, HTTPStatus.BAD_REQUEST)
            return

        record = self.server.store.create()
        record.emit("server_status", {"status": "queued"})
        thread = threading.Thread(target=_run_worker, args=(record, payload), daemon=True)
        thread.start()
        self._send_json({"run_id": record.id, "status": record.status})

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_sse(self, event: Event) -> None:
        payload = json.dumps(event, ensure_ascii=False)
        self.wfile.write(f"event: {event['type']}\n".encode("utf-8"))
        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
        self.wfile.flush()

    def _send_events(self, run_id: str) -> None:
        record = self.server.store.get(run_id)
        if record is None:
            self._send_json({"error": "run not found"}, HTTPStatus.NOT_FOUND)
            return

        subscriber, replay = record.subscribe()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        try:
            for event in replay:
                self._write_sse(event)
            while True:
                if record.status in {"completed", "failed"} and subscriber.empty():
                    break
                try:
                    event = subscriber.get(timeout=10)
                    self._write_sse(event)
                except queue.Empty:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            record.unsubscribe(subscriber)
            self.close_connection = True


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    store = RunStore()
    server = AgentChainHTTPServer((host, port), store)
    print(f"AgentChain UI: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


INDEX_HTML = r"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AgentChain UI</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7fa;
      --panel: #ffffff;
      --line: #d9e0e8;
      --text: #18212f;
      --muted: #657386;
      --accent: #0f766e;
      --accent-2: #2563eb;
      --warn: #b45309;
      --bad: #b91c1c;
      --good: #15803d;
      --shadow: 0 1px 2px rgba(15, 23, 42, .06);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    header {
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 18px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1 { font-size: 17px; margin: 0; font-weight: 650; }
    main {
      height: calc(100vh - 56px);
      display: grid;
      grid-template-columns: 360px minmax(480px, 1fr);
      gap: 0;
    }
    aside {
      overflow: auto;
      border-right: 1px solid var(--line);
      background: #fbfcfe;
      padding: 16px;
    }
    section {
      min-width: 0;
      overflow: hidden;
      display: grid;
      grid-template-rows: auto minmax(240px, 1fr) 260px;
    }
    label {
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin: 13px 0 6px;
      font-weight: 620;
    }
    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      padding: 9px 10px;
      font: inherit;
      min-height: 36px;
    }
    textarea { min-height: 112px; resize: vertical; }
    button {
      border: 1px solid #0b5f59;
      border-radius: 6px;
      background: var(--accent);
      color: white;
      min-height: 38px;
      padding: 0 14px;
      font-weight: 700;
      cursor: pointer;
    }
    button.secondary {
      background: white;
      color: var(--text);
      border-color: var(--line);
    }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .controls { display: flex; gap: 8px; margin-top: 14px; }
    .segmented {
      display: grid;
      grid-template-columns: 1fr 1fr;
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow: hidden;
      background: #fff;
    }
    .segmented button {
      border: 0;
      border-radius: 0;
      background: transparent;
      color: var(--muted);
    }
    .segmented button.active { background: #e7f4f2; color: #075e57; }
    .topbar {
      display: grid;
      grid-template-columns: repeat(5, minmax(110px, 1fr));
      gap: 10px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      padding: 9px 10px;
      box-shadow: var(--shadow);
      min-width: 0;
    }
    .metric span { display: block; color: var(--muted); font-size: 11px; font-weight: 650; }
    .metric strong {
      display: block;
      margin-top: 3px;
      font-size: 15px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .work {
      min-height: 0;
      overflow: auto;
      padding: 16px;
      display: grid;
      grid-template-columns: minmax(320px, 1fr) minmax(320px, 1fr);
      gap: 16px;
    }
    .panel {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .panel h2 {
      margin: 0;
      padding: 11px 12px;
      font-size: 13px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfe;
    }
    .timeline { padding: 12px; display: grid; gap: 8px; }
    .step {
      display: grid;
      grid-template-columns: 88px 1fr auto;
      gap: 10px;
      align-items: center;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
    }
    .step.running { border-color: var(--accent-2); background: #eff6ff; }
    .step.done { border-color: #bbf7d0; background: #f0fdf4; }
    .step.fail { border-color: #fecaca; background: #fef2f2; }
    .badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 72px;
      min-height: 24px;
      padding: 0 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      color: var(--muted);
      background: #fff;
      font-size: 12px;
      font-weight: 700;
    }
    .badge.running { color: #1d4ed8; border-color: #bfdbfe; background: #eff6ff; }
    .badge.approved { color: var(--good); border-color: #bbf7d0; background: #f0fdf4; }
    .badge.changes_requested { color: var(--warn); border-color: #fed7aa; background: #fff7ed; }
    .badge.failed { color: var(--bad); border-color: #fecaca; background: #fef2f2; }
    .review { padding: 12px; display: grid; gap: 10px; }
    .review .message { white-space: pre-wrap; color: var(--text); }
    .review ul { margin: 0; padding-left: 18px; color: var(--muted); }
    .bottom {
      min-height: 0;
      display: grid;
      grid-template-columns: 1fr 1fr;
      border-top: 1px solid var(--line);
      background: var(--panel);
    }
    pre {
      margin: 0;
      height: 100%;
      overflow: auto;
      padding: 12px;
      background: #0b1220;
      color: #dbeafe;
      font: 12px/1.5 ui-monospace, SFMono-Regular, Consolas, monospace;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .log { border-left: 1px solid var(--line); }
    .muted { color: var(--muted); }
    .hidden { display: none; }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; height: auto; }
      section { min-height: 780px; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      .topbar, .work, .bottom { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>AgentChain</h1>
    <div id="connection" class="badge">idle</div>
  </header>
  <main>
    <aside>
      <div class="segmented">
        <button id="pairMode" class="active" type="button">Pair</button>
        <button id="configMode" type="button">Config</button>
      </div>
      <form id="runForm">
        <label for="request">Request</label>
        <textarea id="request" required>사용자 입력을 검증하는 함수를 작성해줘</textarea>

        <div id="pairFields">
          <div class="row">
            <div>
              <label for="coder">Coder</label>
              <select id="coder"></select>
            </div>
            <div>
              <label for="reviewer">Reviewer</label>
              <select id="reviewer"></select>
            </div>
          </div>
          <label for="profile">Profile</label>
          <select id="profile"></select>
          <label for="target">Target File</label>
          <input id="target" value="src/generated.py">
        </div>

        <div id="configFields" class="hidden">
          <label for="config">Config File</label>
          <input id="config" value="config.yaml">
        </div>

        <div class="row">
          <div>
            <label for="workspace">Workspace</label>
            <input id="workspace" value=".">
          </div>
          <div>
            <label for="language">Language</label>
            <input id="language" value="python">
          </div>
        </div>
        <div class="row">
          <div>
            <label for="maxIterations">Max Iterations</label>
            <input id="maxIterations" type="number" min="1" value="3">
          </div>
          <div>
            <label for="pluginsDir">Plugins Dir</label>
            <input id="pluginsDir" placeholder="">
          </div>
        </div>
        <div class="controls">
          <button type="submit">Run</button>
          <button id="clearButton" class="secondary" type="button">Clear</button>
        </div>
      </form>
    </aside>
    <section>
      <div class="topbar">
        <div class="metric"><span>Status</span><strong id="status">idle</strong></div>
        <div class="metric"><span>Run</span><strong id="runId">-</strong></div>
        <div class="metric"><span>Iteration</span><strong id="iteration">0</strong></div>
        <div class="metric"><span>Review</span><strong id="reviewStatus">-</strong></div>
        <div class="metric"><span>Events</span><strong id="eventCount">0</strong></div>
      </div>
      <div class="work">
        <div class="panel">
          <h2>Timeline</h2>
          <div id="timeline" class="timeline"></div>
        </div>
        <div class="panel">
          <h2>Review</h2>
          <div id="review" class="review"><span class="muted">No review yet.</span></div>
        </div>
      </div>
      <div class="bottom">
        <pre id="code">// code preview</pre>
        <pre id="log" class="log">// event log</pre>
      </div>
    </section>
  </main>
  <script>
    const CLIS = ["codex", "kimi", "antigravity"];
    const PROFILES = ["", "codex-antigravity", "codex-kimi", "kimi-codex", "kimi-antigravity", "antigravity-codex", "antigravity-kimi"];
    const state = { mode: "pair", source: null, events: 0, steps: new Map(), startedAt: 0 };

    const $ = (id) => document.getElementById(id);
    const log = (line) => {
      const el = $("log");
      el.textContent += `${new Date().toLocaleTimeString()} ${line}\n`;
      el.scrollTop = el.scrollHeight;
    };
    const setBadge = (id, text, cls = "") => {
      const el = $(id);
      el.textContent = text;
      el.className = `badge ${cls}`;
    };
    const option = (value, text = value) => {
      const el = document.createElement("option");
      el.value = value;
      el.textContent = text || "manual";
      return el;
    };

    CLIS.forEach((name) => {
      $("coder").appendChild(option(name));
      $("reviewer").appendChild(option(name));
    });
    $("reviewer").value = "kimi";
    PROFILES.forEach((name) => $("profile").appendChild(option(name, name || "manual pair")));

    function setMode(mode) {
      state.mode = mode;
      $("pairMode").classList.toggle("active", mode === "pair");
      $("configMode").classList.toggle("active", mode === "config");
      $("pairFields").classList.toggle("hidden", mode !== "pair");
      $("configFields").classList.toggle("hidden", mode !== "config");
    }

    $("pairMode").onclick = () => setMode("pair");
    $("configMode").onclick = () => setMode("config");
    $("clearButton").onclick = () => {
      if (state.source) state.source.close();
      state.events = 0;
      state.steps.clear();
      $("timeline").textContent = "";
      $("review").innerHTML = '<span class="muted">No review yet.</span>';
      $("code").textContent = "// code preview";
      $("log").textContent = "// event log\n";
      $("status").textContent = "idle";
      $("runId").textContent = "-";
      $("iteration").textContent = "0";
      $("reviewStatus").textContent = "-";
      $("eventCount").textContent = "0";
      setBadge("connection", "idle");
    };

    function payload() {
      const data = {
        request: $("request").value,
        workspace: $("workspace").value,
        language: $("language").value,
        max_iterations: $("maxIterations").value,
        plugins_dir: $("pluginsDir").value
      };
      if (state.mode === "config") {
        data.config = $("config").value;
      } else {
        data.target_file = $("target").value;
        if ($("profile").value) data.profile = $("profile").value;
        else {
          data.coder_cli = $("coder").value;
          data.reviewer_cli = $("reviewer").value;
        }
      }
      return data;
    }

    function stepKey(iteration, agent, role) {
      return `${iteration}:${agent}:${role}`;
    }

    function renderTimeline() {
      const timeline = $("timeline");
      timeline.textContent = "";
      for (const item of state.steps.values()) {
        const row = document.createElement("div");
        row.className = `step ${item.state}`;
        const badge = document.createElement("span");
        badge.className = `badge ${item.state === "running" ? "running" : item.state === "done" ? "approved" : ""}`;
        badge.textContent = `#${item.iteration} ${item.role}`;
        const main = document.createElement("div");
        main.innerHTML = `<strong>${item.agent}</strong><div class="muted">${item.output || ""}</div>`;
        const status = document.createElement("span");
        status.className = "muted";
        status.textContent = item.state;
        row.appendChild(badge);
        row.appendChild(main);
        row.appendChild(status);
        timeline.appendChild(row);
      }
    }

    function renderReview(data) {
      const status = data.status || "-";
      $("reviewStatus").textContent = status;
      const cls = status === "approved" ? "approved" : status === "changes_requested" ? "changes_requested" : "";
      const suggestions = (data.suggestions || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
      $("review").innerHTML = `
        <span class="badge ${cls}">${escapeHtml(status)}</span>
        <div class="message">${escapeHtml(data.message || "")}</div>
        ${suggestions ? `<ul>${suggestions}</ul>` : ""}
      `;
    }

    function escapeHtml(text) {
      return String(text).replace(/[&<>"']/g, (ch) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
      }[ch]));
    }

    function handleEvent(event) {
      state.events += 1;
      $("eventCount").textContent = state.events;
      const type = event.type;
      const data = event.data || {};

      if (type === "server_status") {
        $("status").textContent = data.status || "running";
        setBadge("connection", data.status || "running", data.status === "completed" ? "approved" : "");
      } else if (type === "config_loaded") {
        log(`config ${data.config}`);
      } else if (type === "agents_resolved") {
        log(`agents ${data.agents.join(", ")}`);
      } else if (type === "run_started") {
        log(`run started max=${data.max_iterations}`);
      } else if (type === "iteration_started") {
        $("iteration").textContent = `${data.iteration}/${data.max_iterations}`;
        log(`iteration ${data.iteration} started`);
      } else if (type === "step_started") {
        const key = stepKey(data.iteration, data.agent, data.role);
        state.steps.set(key, { ...data, state: "running" });
        renderTimeline();
        log(`step ${data.role}:${data.agent} started`);
      } else if (type === "step_completed") {
        const key = stepKey(data.iteration, data.agent, data.role);
        state.steps.set(key, { ...data, state: "done" });
        renderTimeline();
        if (data.result && data.result.kind === "text" && data.output === "code") {
          $("code").textContent = data.result.preview || "";
        }
        if (data.review) renderReview(data.review);
        log(`step ${data.role}:${data.agent} completed`);
      } else if (type === "review_gate") {
        renderReview(data);
        log(`review ${data.status}${data.retry ? " retry" : ""}`);
      } else if (type === "retry_scheduled") {
        log(`retry scheduled iteration ${data.iteration}`);
      } else if (type === "shell_started") {
        log(`shell ${data.command.join(" ")}`);
      } else if (type === "shell_output") {
        log(`${data.stream}> ${String(data.text).trimEnd()}`);
      } else if (type === "run_completed") {
        $("status").textContent = "completed";
        if (data.result && data.result.code) $("code").textContent = data.result.code;
        setBadge("connection", "completed", "approved");
        log("run completed");
      } else if (type === "run_failed") {
        $("status").textContent = "failed";
        setBadge("connection", "failed", "failed");
        log(`failed ${data.error}`);
      }
    }

    $("runForm").onsubmit = async (evt) => {
      evt.preventDefault();
      if (state.source) state.source.close();
      $("clearButton").click();
      $("status").textContent = "queued";
      setBadge("connection", "connecting", "running");
      const response = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload())
      });
      const data = await response.json();
      if (!response.ok) {
        log(`failed ${data.error || response.statusText}`);
        return;
      }
      $("runId").textContent = data.run_id;
      state.source = new EventSource(`/api/runs/${data.run_id}/events`);
      state.source.onopen = () => setBadge("connection", "live", "running");
      state.source.onerror = () => setBadge("connection", "closed");
      state.source.onmessage = (msg) => handleEvent(JSON.parse(msg.data));
      ["server_status", "config_loaded", "agents_resolved", "run_started", "iteration_started",
       "step_started", "step_completed", "review_gate", "retry_scheduled", "shell_started",
       "shell_output", "shell_completed", "run_completed", "run_failed"].forEach((name) => {
        state.source.addEventListener(name, (msg) => handleEvent(JSON.parse(msg.data)));
      });
    };
  </script>
</body>
</html>
"""
