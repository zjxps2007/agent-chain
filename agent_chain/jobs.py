"""File-backed background job tracking for AgentChain CLI runs."""

from __future__ import annotations

import json
import os
import signal
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


TERMINAL_STATUSES = {"approved", "changes_requested", "comment", "failed", "cancelled"}


def default_jobs_dir(workspace: Path | str = ".") -> Path:
    return Path(workspace).resolve() / ".agent-chain" / "jobs"


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)
    return value


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@dataclass
class JobPaths:
    metadata: Path
    stdout: Path
    stderr: Path


class JobStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def paths(self, job_id: str) -> JobPaths:
        return JobPaths(
            metadata=self.root / f"{job_id}.json",
            stdout=self.root / f"{job_id}.stdout.log",
            stderr=self.root / f"{job_id}.stderr.log",
        )

    def create(
        self,
        *,
        kind: str,
        request: str,
        workspace: Path,
        command: List[str],
        reviewer_cli: Optional[str] = None,
        target_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        job_id = uuid.uuid4().hex[:12]
        now = time.time()
        paths = self.paths(job_id)
        job: Dict[str, Any] = {
            "id": job_id,
            "kind": kind,
            "status": "queued",
            "request": request,
            "workspace": str(workspace),
            "reviewer_cli": reviewer_cli,
            "target_file": target_file,
            "command": command,
            "pid": None,
            "created_at": now,
            "updated_at": now,
            "stdout": str(paths.stdout),
            "stderr": str(paths.stderr),
            "result": None,
            "error": None,
            "exit_code": None,
        }
        self.write(job)
        return job

    def write(self, job: Dict[str, Any]) -> None:
        job = {str(key): _json_safe(value) for key, value in job.items()}
        job["updated_at"] = time.time()
        paths = self.paths(str(job["id"]))
        paths.metadata.write_text(
            json.dumps(job, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def read(self, job_id: str) -> Dict[str, Any]:
        path = self.paths(job_id).metadata
        if not path.exists():
            raise FileNotFoundError(f"job not found: {job_id}")
        job = json.loads(path.read_text(encoding="utf-8"))
        return self.refresh(job)

    def list(self) -> List[Dict[str, Any]]:
        jobs = []
        for path in self.root.glob("*.json"):
            try:
                jobs.append(self.refresh(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(jobs, key=lambda item: float(item.get("created_at", 0)), reverse=True)

    def latest(self) -> Dict[str, Any]:
        jobs = self.list()
        if not jobs:
            raise FileNotFoundError(f"no jobs found in {self.root}")
        return jobs[0]

    def update(self, job_id: str, **changes: Any) -> Dict[str, Any]:
        job = self.read(job_id)
        job.update(changes)
        self.write(job)
        return job

    def refresh(self, job: Dict[str, Any]) -> Dict[str, Any]:
        status = str(job.get("status", ""))
        pid = job.get("pid")
        if status == "running" and isinstance(pid, int) and not _process_alive(pid):
            job["status"] = "failed"
            job["error"] = job.get("error") or "process exited before writing a final result"
            self.write(job)
        return job

    def cancel(self, job_id: str) -> Dict[str, Any]:
        job = self.read(job_id)
        if job.get("status") in TERMINAL_STATUSES:
            return job

        pid = job.get("pid")
        if isinstance(pid, int) and _process_alive(pid):
            os.kill(pid, signal.SIGTERM)
        job["status"] = "cancelled"
        self.write(job)
        return job
