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
    build_cli_review_config,
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
            raise PermissionError("Environment is read-only; shell commands cannot be executed.")

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
    mode = (_clean_text(payload.get("mode")) or "review").lower()
    config_path = _clean_text(payload.get("config"))
    profile = _clean_text(payload.get("profile"))
    coder_cli = _clean_text(payload.get("coder_cli"))
    reviewer_cli = _clean_text(payload.get("reviewer_cli"))

    if mode == "review":
        if config_path or profile or coder_cli:
            raise ValueError("review mode only accepts reviewer options.")
        reviewer_cli = reviewer_cli or "kimi"
        config = build_cli_review_config(
            reviewer_cli=reviewer_cli,
            max_iterations=1,
            target_file=_clean_text(payload.get("target_file")),
            reviewer_model=_clean_text(payload.get("reviewer_model")),
            reviewer_command=_clean_text(payload.get("reviewer_command")),
        )
        return config, f"review:{reviewer_cli}"

    if mode not in {"pair", "config"}:
        raise ValueError(f"unsupported UI mode: {mode}")

    should_generate = uses_generated_cli_config(
        profile=profile,
        coder_cli=coder_cli,
        reviewer_cli=reviewer_cli,
    )
    if mode == "pair" and not config_path and not should_generate:
        coder_cli = "codex"
        reviewer_cli = "kimi"
        should_generate = True

    if (mode == "config" or config_path) and should_generate:
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

        review_json = _clean_text(payload.get("json"))
        if review_json and context.review:
            json_path = Path(review_json)
            if not json_path.is_absolute():
                json_path = workspace / json_path
            json_path.parent.mkdir(parents=True, exist_ok=True)
            review_payload = {
                **context.review.to_dict(),
                "request": context.request,
                "workspace": str(workspace),
                "target_file": _clean_text(payload.get("target_file")),
                "reviewer_cli": _clean_text(payload.get("reviewer_cli")) or "kimi",
            }
            json_path.write_text(
                json.dumps(review_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            record.emit(
                "review_json_written",
                {
                    "path": str(json_path),
                    "review": review_payload,
                },
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
  <title>AgentChain Review Monitor</title>
  <!-- Google Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;700;800&display=swap" rel="stylesheet">

  <style>
    :root {
      color-scheme: dark;
      --bg: #0d0f10;
      --panel: #171a1c;
      --panel-glass: rgba(23, 26, 28, 0.78);
      --line: rgba(255, 255, 255, 0.08);
      --text: #f3f4f6;
      --muted: #9ca3af;
      --accent: #06b6d4;
      --accent-hover: #0891b2;
      --accent-bg-glow: rgba(6, 182, 212, 0.15);
      --accent-2: #7c8a92;
      --warn: #f59e0b;
      --bad: #ef4444;
      --good: #10b981;
      --shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
      --shadow-neon: 0 0 15px rgba(6, 182, 212, 0.35);
      --transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
      line-height: 1.5;
      letter-spacing: 0;
      overflow-x: hidden;
    }

    /* Scrollbars */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.15); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.3); }

    header {
      height: 64px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px;
      border-bottom: 1px solid var(--line);
      background: rgba(17, 24, 39, 0.6);
      backdrop-filter: blur(16px);
      position: sticky;
      top: 0;
      z-index: 100;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .logo-glow {
      width: 10px;
      height: 10px;
      background: var(--accent);
      border-radius: 50%;
      box-shadow: 0 0 10px var(--accent), 0 0 20px var(--accent);
    }

    h1 {
      font-family: 'Outfit', sans-serif;
      font-size: 20px;
      margin: 0;
      font-weight: 800;
      letter-spacing: 0;
      background: linear-gradient(to right, #ffffff, #94a3b8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    main {
      height: calc(100vh - 64px);
      display: grid;
      grid-template-columns: 380px minmax(500px, 1fr);
      gap: 0;
    }

    aside {
      overflow-y: auto;
      border-right: 1px solid var(--line);
      background: rgba(13, 18, 30, 0.45);
      backdrop-filter: blur(10px);
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    section {
      min-width: 0;
      overflow: hidden;
      display: grid;
      grid-template-rows: auto minmax(280px, 1fr) 300px;
      background: rgba(15, 23, 42, 0.1);
    }

    label {
      display: block;
      font-size: 11px;
      color: var(--muted);
      margin: 16px 0 6px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(15, 23, 42, 0.6);
      color: var(--text);
      padding: 10px 14px;
      font: inherit;
      font-size: 13.5px;
      min-height: 40px;
      transition: var(--transition);
    }

    input:focus, textarea:focus, select:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 1px var(--accent-bg-glow), 0 0 8px rgba(6, 182, 212, 0.2);
      background: rgba(15, 23, 42, 0.8);
    }

    textarea { min-height: 120px; resize: vertical; }

    button {
      border: 1px solid var(--accent);
      border-radius: 8px;
      background: var(--accent);
      color: #090d16;
      min-height: 40px;
      padding: 0 20px;
      font-family: 'Inter', sans-serif;
      font-weight: 700;
      font-size: 14px;
      cursor: pointer;
      transition: var(--transition);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      box-shadow: 0 4px 12px rgba(6, 182, 212, 0.2);
    }

    button:hover {
      background: var(--accent-hover);
      border-color: var(--accent-hover);
      transform: translateY(-1px);
      box-shadow: 0 6px 16px rgba(6, 182, 212, 0.35);
    }

    button:active {
      transform: translateY(0);
    }

    button.secondary {
      background: transparent;
      color: var(--text);
      border-color: var(--line);
      box-shadow: none;
    }

    button.secondary:hover {
      background: rgba(255, 255, 255, 0.05);
      border-color: rgba(255, 255, 255, 0.2);
    }

    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .controls { display: flex; gap: 10px; margin-top: 20px; }

    .segmented {
      display: grid;
      grid-template-columns: 1fr 1fr;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: rgba(15, 23, 42, 0.4);
      padding: 3px;
    }

    .segmented button {
      border: 0;
      border-radius: 6px;
      background: transparent;
      color: var(--muted);
      min-height: 34px;
      font-weight: 600;
      font-size: 13px;
      box-shadow: none;
    }

    .segmented button:hover {
      background: rgba(255, 255, 255, 0.03);
      color: var(--text);
      transform: none;
    }

    .segmented button.active {
      background: var(--accent);
      color: #090d16;
      box-shadow: 0 2px 8px rgba(6, 182, 212, 0.25);
    }

    .segmented button.active:hover {
      background: var(--accent);
      color: #090d16;
    }

    .topbar {
      display: grid;
      grid-template-columns: repeat(5, minmax(120px, 1fr));
      gap: 12px;
      padding: 16px 24px;
      border-bottom: 1px solid var(--line);
      background: rgba(17, 24, 39, 0.4);
      backdrop-filter: blur(12px);
    }

    .metric {
      border: 1px solid var(--line);
      border-radius: 10px;
      background: rgba(30, 41, 59, 0.2);
      padding: 12px 14px;
      box-shadow: var(--shadow);
      transition: var(--transition);
    }

    .metric:hover {
      border-color: rgba(255, 255, 255, 0.15);
      background: rgba(30, 41, 59, 0.35);
    }

    .metric span {
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .metric strong {
      display: block;
      margin-top: 4px;
      font-size: 18px;
      font-family: 'Outfit', sans-serif;
      font-weight: 700;
      color: #fff;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .work {
      min-height: 0;
      overflow: auto;
      padding: 24px;
      display: grid;
      grid-template-columns: minmax(320px, 1fr) minmax(320px, 1fr);
      gap: 24px;
    }

    .panel {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(17, 24, 39, 0.45);
      backdrop-filter: blur(10px);
      box-shadow: var(--shadow);
      overflow: hidden;
      display: flex;
      flex-direction: column;
      transition: var(--transition);
    }

    .panel:hover {
      border-color: rgba(255, 255, 255, 0.12);
    }

    .panel h2 {
      margin: 0;
      padding: 14px 18px;
      font-family: 'Outfit', sans-serif;
      font-size: 14px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border-bottom: 1px solid var(--line);
      background: rgba(30, 41, 59, 0.15);
      color: #e2e8f0;
    }

    .timeline {
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      overflow-y: auto;
      flex-grow: 1;
    }

    .step {
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 14px;
      align-items: center;
      padding: 12px 16px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: rgba(15, 23, 42, 0.3);
      transition: var(--transition);
    }

    .step:hover {
      transform: translateX(2px);
      background: rgba(15, 23, 42, 0.5);
    }

    .step.running {
      border-color: var(--accent-2);
      background: rgba(99, 102, 241, 0.08);
      box-shadow: 0 0 15px rgba(99, 102, 241, 0.15);
    }

    .step.done {
      border-color: rgba(16, 185, 129, 0.3);
      background: rgba(16, 185, 129, 0.05);
    }

    .step.fail {
      border-color: rgba(239, 68, 68, 0.3);
      background: rgba(239, 68, 68, 0.05);
    }

    .badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 80px;
      min-height: 26px;
      padding: 0 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      color: var(--muted);
      background: rgba(255, 255, 255, 0.05);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }

    /* Live pulse animation for connection badge */
    @keyframes pulse {
      0% { opacity: 0.6; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
      50% { opacity: 1; box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
      100% { opacity: 0.6; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

    .badge.live {
      color: var(--good);
      border-color: rgba(16, 185, 129, 0.3);
      background: rgba(16, 185, 129, 0.1);
      animation: pulse 2s infinite;
    }

    .badge.running {
      color: #3b82f6;
      border-color: rgba(59, 130, 246, 0.3);
      background: rgba(59, 130, 246, 0.1);
    }

    .badge.approved {
      color: var(--good);
      border-color: rgba(16, 185, 129, 0.4);
      background: rgba(16, 185, 129, 0.12);
    }

    .badge.changes_requested {
      color: var(--warn);
      border-color: rgba(245, 158, 11, 0.4);
      background: rgba(245, 158, 11, 0.12);
    }

    .badge.failed {
      color: var(--bad);
      border-color: rgba(239, 68, 68, 0.4);
      background: rgba(239, 68, 68, 0.12);
    }

    .review {
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      overflow-y: auto;
      flex-grow: 1;
    }

    .review .message {
      white-space: pre-wrap;
      color: #e2e8f0;
      font-size: 13.5px;
      line-height: 1.6;
    }

    .review ul {
      margin: 0;
      padding-left: 20px;
      color: var(--muted);
      font-size: 13px;
      display: grid;
      gap: 6px;
    }

    .review li {
      position: relative;
    }

    .bottom {
      min-height: 0;
      display: grid;
      grid-template-columns: 1fr 1fr;
      border-top: 1px solid var(--line);
      background: #101214;
    }

    pre {
      margin: 0;
      height: 100%;
      overflow: auto;
      padding: 16px;
      background: #0b0d0f;
      color: #e2e8f0;
      font-family: 'Fira Code', 'JetBrains Mono', ui-monospace, monospace;
      font-size: 12.5px;
      line-height: 1.6;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    /* Terminal stream indicator */
    .log {
      border-left: 1px solid var(--line);
      color: #a7f3d0;
      background: #090b0d;
    }

    .muted { color: var(--muted); }
    .hidden { display: none; }

    @media (max-width: 1024px) {
      main { grid-template-columns: 1fr; height: auto; }
      section { min-height: 850px; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      .topbar, .work, .bottom { grid-template-columns: 1fr; }
      .bottom { grid-template-rows: 400px 300px; }
      .log { border-left: 0; border-top: 1px solid var(--line); }
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="logo-glow"></div>
      <h1>AgentChain Review Monitor</h1>
    </div>
    <div id="connection" class="badge">idle</div>
  </header>
  <main>
    <aside>
      <form id="runForm">
        <label for="request">Original Request</label>
        <textarea id="request" required>Review the current implementation.</textarea>

        <label for="reviewer">Reviewer Agent</label>
        <select id="reviewer"></select>

        <label for="target">Target File</label>
        <input id="target" value="src/generated.py">

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
            <label for="reviewerModel">Reviewer Model</label>
            <input id="reviewerModel" placeholder="Optional model">
          </div>
          <div>
            <label for="reviewerCommand">Reviewer Command</label>
            <input id="reviewerCommand" placeholder="Optional CLI path">
          </div>
        </div>
        <label for="jsonPath">Review JSON</label>
        <input id="jsonPath" value=".agent-chain-review.json">
        <label for="pluginsDir">Plugins Directory</label>
        <input id="pluginsDir" placeholder="Optional plugins path">
        <div class="controls">
          <button type="submit">Run Review</button>
          <button id="clearButton" class="secondary" type="button">Clear View</button>
        </div>
      </form>
    </aside>
    <section>
      <div class="topbar">
        <div class="metric"><span>Status</span><strong id="status">idle</strong></div>
        <div class="metric"><span>Run ID</span><strong id="runId">-</strong></div>
        <div class="metric"><span>Reviewer</span><strong id="reviewerName">-</strong></div>
        <div class="metric"><span>Last Review</span><strong id="reviewStatus">-</strong></div>
        <div class="metric"><span>Events</span><strong id="eventCount">0</strong></div>
      </div>
      <div class="work">
        <div class="panel">
          <h2>Reviewer Activity</h2>
          <div id="timeline" class="timeline"></div>
        </div>
        <div class="panel">
          <h2>Review Output</h2>
          <div id="review" class="review"><span class="muted">No review feedback received yet.</span></div>
        </div>
      </div>
      <div class="bottom">
        <pre id="result">// Review JSON will appear here...</pre>
        <pre id="log" class="log">// Server execution logs...</pre>
      </div>
    </section>
  </main>
  <script>
    const CLIS = ["codex", "kimi", "antigravity"];
    const state = { source: null, events: 0, steps: new Map(), startedAt: 0 };

    const $ = (id) => document.getElementById(id);
    const log = (line) => {
      const el = $("log");
      el.textContent += `[${new Date().toLocaleTimeString()}] ${line}\n`;
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
      el.textContent = text || value;
      return el;
    };

    CLIS.forEach((name) => {
      $("reviewer").appendChild(option(name));
    });
    $("reviewer").value = "kimi";
    $("clearButton").onclick = () => {
      if (state.source) state.source.close();
      state.events = 0;
      state.steps.clear();
      $("timeline").textContent = "";
      $("review").innerHTML = '<span class="muted">No review feedback received yet.</span>';
      $("result").textContent = "// Review JSON will appear here...";
      $("log").textContent = "// Server execution logs...\n";
      $("status").textContent = "idle";
      $("runId").textContent = "-";
      $("reviewerName").textContent = "-";
      $("reviewStatus").textContent = "-";
      $("eventCount").textContent = "0";
      setBadge("connection", "idle");
    };

    function payload() {
      return {
        mode: "review",
        request: $("request").value,
        workspace: $("workspace").value,
        language: $("language").value,
        reviewer_cli: $("reviewer").value,
        target_file: $("target").value,
        reviewer_model: $("reviewerModel").value,
        reviewer_command: $("reviewerCommand").value,
        json: $("jsonPath").value,
        plugins_dir: $("pluginsDir").value
      };
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
        main.innerHTML = `<strong>${item.agent}</strong><div class="muted" style="font-size: 11px; margin-top: 2px;">${item.output || ""}</div>`;
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
      const lineComments = (data.line_comments || [])
        .map((item) => `<li>${escapeHtml(item.line ? `Line ${item.line}: ${item.message || ""}` : item.message || JSON.stringify(item))}</li>`)
        .join("");
      $("review").innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
          <span class="badge ${cls}">${escapeHtml(status)}</span>
        </div>
        <div class="message">${escapeHtml(data.message || "")}</div>
        ${suggestions ? `<ul style="margin-top: 12px; border-top: 1px dashed var(--line); padding-top: 12px;">${suggestions}</ul>` : ""}
        ${lineComments ? `<ul style="margin-top: 12px; border-top: 1px dashed var(--line); padding-top: 12px;">${lineComments}</ul>` : ""}
      `;
      $("result").textContent = JSON.stringify(data, null, 2);
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
        setBadge("connection", data.status || "running", data.status === "completed" ? "approved" : data.status === "running" ? "running" : "");
      } else if (type === "config_loaded") {
        const step = (data.steps || [])[0] || {};
        $("reviewerName").textContent = step.agent || data.config || "-";
        log(`Loaded review configuration: ${data.config}`);
      } else if (type === "agents_resolved") {
        log(`Resolved agents: ${data.agents.join(", ")}`);
      } else if (type === "run_started") {
        log("Review run started.");
      } else if (type === "iteration_started") {
        log(`Starting review pass ${data.iteration}.`);
      } else if (type === "step_started") {
        const key = stepKey(data.iteration, data.agent, data.role);
        state.steps.set(key, { ...data, state: "running" });
        $("reviewerName").textContent = data.agent || "-";
        renderTimeline();
        log(`[Review] ${data.agent} started.`);
      } else if (type === "step_completed") {
        const key = stepKey(data.iteration, data.agent, data.role);
        state.steps.set(key, { ...data, state: "done" });
        renderTimeline();
        if (data.review) renderReview(data.review);
        log(`[Review] ${data.agent} completed.`);
      } else if (type === "review_gate") {
        renderReview(data);
        log(`[Review Gate] Status: ${data.status}`);
      } else if (type === "retry_scheduled") {
        log(`[Retry] Iteration retry scheduled for loop index: ${data.iteration}`);
      } else if (type === "shell_started") {
        log(`[Shell Exec] ${data.command.join(" ")}`);
      } else if (type === "shell_output") {
        log(`${data.stream}> ${String(data.text).trimEnd()}`);
      } else if (type === "review_json_written") {
        $("result").textContent = JSON.stringify(data.review || {}, null, 2);
        log(`[Review JSON] ${data.path}`);
      } else if (type === "run_completed") {
        $("status").textContent = "completed";
        if (data.review) renderReview(data.review);
        else if (data.result && data.result.review) renderReview(data.result.review);
        setBadge("connection", "completed", "approved");
        log("Review run completed.");
      } else if (type === "run_failed") {
        $("status").textContent = "failed";
        setBadge("connection", "failed", "failed");
        log(`[Error] Run failed: ${data.error}`);
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
        log(`[Error] Run submission failed: ${data.error || response.statusText}`);
        return;
      }
      $("runId").textContent = data.run_id;
      state.source = new EventSource(`/api/runs/${data.run_id}/events`);
      state.source.onopen = () => setBadge("connection", "live", "live");
      state.source.onerror = () => setBadge("connection", "closed");
      state.source.onmessage = (msg) => handleEvent(JSON.parse(msg.data));
      ["server_status", "config_loaded", "agents_resolved", "run_started", "iteration_started",
       "step_started", "step_completed", "review_gate", "retry_scheduled", "shell_started",
       "shell_output", "shell_completed", "review_json_written", "run_completed", "run_failed"].forEach((name) => {
        state.source.addEventListener(name, (msg) => handleEvent(JSON.parse(msg.data)));
      });
    };
  </script>
</body>
</html>
"""
