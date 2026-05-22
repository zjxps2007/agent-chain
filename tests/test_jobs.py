from __future__ import annotations

from pathlib import Path

from agent_chain.jobs import JobStore, default_jobs_dir


def test_job_store_creates_updates_and_lists_jobs(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    job = store.create(
        kind="review",
        request="review this",
        workspace=tmp_path,
        command=["agc", "review", "review this"],
        reviewer_cli="kimi",
        target_file="src/generated.py",
    )

    store.update(job["id"], status="approved", result={"status": "approved", "message": "ok"})

    loaded = store.read(job["id"])
    jobs = store.list()

    assert loaded["status"] == "approved"
    assert loaded["result"]["message"] == "ok"
    assert jobs[0]["id"] == job["id"]


def test_job_store_cancels_non_running_job(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    job = store.create(
        kind="challenge",
        request="challenge this",
        workspace=tmp_path,
        command=["agc", "challenge", "challenge this"],
    )

    cancelled = store.cancel(job["id"])

    assert cancelled["status"] == "cancelled"


def test_default_jobs_dir_uses_workspace(tmp_path: Path) -> None:
    assert default_jobs_dir(tmp_path) == tmp_path.resolve() / ".agent-chain" / "jobs"
