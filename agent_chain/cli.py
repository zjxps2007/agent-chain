"""AgentChain CLI 인터페이스."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .core import Agent, Context, Pipeline, _apply_agent_result, _context_output, _step_output_key
from .integrations import (
    SUPPORTED_CLIS,
    SUPPORTED_INSTALL_TARGETS,
    SUPPORTED_PROFILES,
    build_cli_pair_config,
    build_integration_setup,
    build_cli_review_config,
    copy_integration_pack,
    integration_assets_root,
    uses_generated_cli_config,
)
from .pipeline import run_pipeline
from .jobs import JobStore, default_jobs_dir
from .registry import resolve_agents
from .tools import Environment


DEFAULT_CONFIG = """\
max_iterations: 3

steps:
  - role: coder
    agent: primary_coder
  - role: reviewer
    agent: strict_reviewer

agent_configs:
  primary_coder:
    style: google
  strict_reviewer:
    require_docstring: true
    max_line_length: 100
    rules:
      - no_todo
"""

CUSTOM_AGENT_TEMPLATE = '''\
"""커스텀 에이전트 예시 템플릿."""

from agent_chain.core import Context, ReviewResult


class MyCoderAgent:
    """나만의 코딩 에이전트."""

    def __init__(self, name: str, config: dict | None = None) -> None:
        self.name = name
        self.config = config or {}

    def run(self, context: Context) -> str:
        # TODO: LLM API 호출 또는 자체 로직 구현
        return f"# {context.request}\\ndef solution():\\n    pass\\n"


class MyReviewerAgent:
    """나만의 검토 에이전트."""

    def __init__(self, name: str, config: dict | None = None) -> None:
        self.name = name
        self.config = config or {}

    def run(self, context: Context) -> ReviewResult:
        # TODO: 실제 검토 로직 구현
        return ReviewResult(
            status="approved",
            message="검토 통과 (stub).",
        )
'''


def _configure_stdio() -> None:
    """Keep CLI output from crashing on Windows legacy code pages."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _load_yaml(path: str) -> Dict[str, Any]:
    try:
        import yaml
    except ImportError:
        print("오류: YAML 파싱을 위해 PyYAML 설치가 필요합니다.")
        print("  pip install pyyaml")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_run_config(args: argparse.Namespace) -> tuple[Dict[str, Any], str]:
    should_generate = uses_generated_cli_config(
        profile=args.profile,
        coder_cli=args.coder_cli,
        reviewer_cli=args.reviewer_cli,
    )
    if args.config and should_generate:
        print("오류: --config는 --profile/--coder-cli/--reviewer-cli와 함께 사용할 수 없습니다.")
        sys.exit(2)

    if should_generate:
        config = build_cli_pair_config(
            profile=args.profile,
            coder_cli=args.coder_cli,
            reviewer_cli=args.reviewer_cli,
            max_iterations=args.max_iterations,
            target_file=args.target_file,
            coder_model=args.coder_model,
            reviewer_model=args.reviewer_model,
            coder_command=args.coder_command,
            reviewer_command=args.reviewer_command,
        )
        profile_label = args.profile or f"{args.coder_cli or 'codex'}-{args.reviewer_cli or 'antigravity'}"
        return config, f"generated:{profile_label}"

    config_path = Path(args.config or "config.yaml")
    if not config_path.exists():
        print(f"설정 파일을 찾을 수 없습니다: {config_path}")
        print("`agc i` 로 기본 설정을 생성하세요.")
        sys.exit(1)

    config = _load_yaml(str(config_path))
    if args.max_iterations is not None:
        config["max_iterations"] = args.max_iterations
    return config, str(config_path)


def cmd_run(args: argparse.Namespace) -> None:
    config, config_label = _load_run_config(args)

    # 에이전트 동적 로드
    plugins_dir = Path(args.plugins_dir) if args.plugins_dir else None
    agents = resolve_agents(config, plugins_dir=plugins_dir)

    # 작업 디렉토리 설정
    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    # Environment 생성 (리뷰어는 read-only sandbox로 실행할 수도 있음)
    env = Environment(workspace, read_only=False)

    print(f"요청: {args.request}")
    print(f"설정: {config_label}")
    print(f"작업 디렉토리: {workspace}")
    print(f"최대 반복: {config.get('max_iterations', 3)}\n")

    result = run_pipeline(
        agents=agents,
        config=config,
        request=args.request,
        workspace=workspace,
        env=env,
        language=args.language,
    )

    # 출력
    if args.output:
        out_path = Path(args.output)
        # 상대 경로이면 workspace 기준
        if not out_path.is_absolute():
            out_path = workspace / out_path
        out_path.write_text(result.code or "", encoding="utf-8")
        print(f"\n[OK] 코드를 저장했습니다: {out_path.resolve()}")
    else:
        print("\n========== 생성된 코드 ==========")
        print(result.code or "(코드 없음)")

    print("\n========== 실행 요약 ==========")
    print(f"총 반복 횟수: {result.iteration}")
    print(f"검토 수행: {len(result.reviews)}회")
    if result.review:
        print(f"최종 상태: {result.review.status}")
        print(f"메시지: {result.review.message}")
        if result.review.suggestions:
            print("제안:")
            for s in result.review.suggestions:
                print(f"  - {s}")
    else:
        print("최종 상태: N/A")

    if args.json:
        json_path = Path(args.json)
        json_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n[OK] 전체 결과 JSON 저장: {json_path.resolve()}")


def _cmd_review_sync(args: argparse.Namespace) -> int:
    config = build_cli_review_config(
        reviewer_cli=args.reviewer_cli,
        max_iterations=1,
        target_file=args.target_file,
        reviewer_model=args.reviewer_model,
        reviewer_command=args.reviewer_command,
        review_mode=getattr(args, "review_mode", "review"),
        review_focus=getattr(args, "focus", None),
    )
    plugins_dir = Path(args.plugins_dir) if args.plugins_dir else None
    agents = resolve_agents(config, plugins_dir=plugins_dir)

    workspace = Path(args.workspace).resolve()
    env = Environment(workspace, read_only=False)
    ctx = Context(
        request=args.request or "Review the current implementation.",
        workspace=workspace,
        env=env,
        language=args.language,
    )
    if args.stdin:
        ctx.code = sys.stdin.read()

    step = config["steps"][0]
    agent_name = step["agent"]
    agent = agents[agent_name]
    output_key = _step_output_key(step)
    result = agent.run(ctx)
    ctx, _ = _apply_agent_result(ctx, result, output_key)
    agent_display_name = getattr(agent, "name", agent_name)
    ctx.log_step(agent_display_name, step.get("role", "reviewer"), _context_output(ctx, output_key))

    if ctx.review is None:
        print("오류: 리뷰어가 ReviewResult를 반환하지 않았습니다.")
        return 2

    ctx.reviews.append(ctx.review)
    review_data = ctx.review.to_dict()
    payload = {
        **review_data,
        "request": ctx.request,
        "workspace": str(workspace),
        "target_file": args.target_file,
        "reviewer_cli": args.reviewer_cli,
    }

    print("\n========== 리뷰 결과 ==========")
    print(f"상태: {ctx.review.status}")
    print(f"메시지: {ctx.review.message}")
    if ctx.review.suggestions:
        print("제안:")
        for suggestion in ctx.review.suggestions:
            print(f"  - {suggestion}")

    if args.json:
        json_path = Path(args.json)
        if not json_path.is_absolute():
            json_path = workspace / json_path
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n[OK] 리뷰 JSON 저장: {json_path.resolve()}")

    if args.fail_on_changes and ctx.review.status == "changes_requested":
        return 10
    return 0


def _jobs_dir(args: argparse.Namespace, workspace: Path) -> Path:
    value = getattr(args, "jobs_dir", None)
    return Path(value).resolve() if value else default_jobs_dir(workspace)


def _job_result_path(store: JobStore, job_id: str) -> Path:
    return store.root / f"{job_id}.review.json"


def _review_command_for_background(args: argparse.Namespace, job_id: str, jobs_dir: Path) -> List[str]:
    result_path = jobs_dir / f"{job_id}.review.json"
    command = [
        sys.executable,
        "-m",
        "agent_chain",
        args.command,
        args.request or "Review the current implementation.",
        "--reviewer-cli",
        args.reviewer_cli,
        "--workspace",
        str(Path(args.workspace).resolve()),
        "--language",
        args.language,
        "--json",
        str(result_path),
        "--job-id",
        job_id,
        "--jobs-dir",
        str(jobs_dir),
    ]
    if args.target_file:
        command.extend(["--target-file", args.target_file])
    if args.reviewer_model:
        command.extend(["--reviewer-model", args.reviewer_model])
    if args.reviewer_command:
        command.extend(["--reviewer-command", args.reviewer_command])
    if args.plugins_dir:
        command.extend(["--plugins-dir", args.plugins_dir])
    if getattr(args, "focus", None):
        command.extend(["--focus", args.focus])
    if args.fail_on_changes:
        command.append("--fail-on-changes")
    return command


def _start_background_review(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    store = JobStore(_jobs_dir(args, workspace))
    job = store.create(
        kind=args.command,
        request=args.request or "Review the current implementation.",
        workspace=workspace,
        command=[],
        reviewer_cli=args.reviewer_cli,
        target_file=args.target_file,
    )
    command = _review_command_for_background(args, job["id"], store.root)
    job["command"] = command
    store.write(job)
    paths = store.paths(job["id"])
    with paths.stdout.open("w", encoding="utf-8") as stdout, paths.stderr.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(command, cwd=workspace, stdout=stdout, stderr=stderr)
    store.update(job["id"], status="running", pid=process.pid)
    print(f"Started {args.command} job: {job['id']}")
    print(f"Status: agc status {job['id']} --jobs-dir {store.root}")
    print(f"Result: agc result {job['id']} --jobs-dir {store.root}")
    return 0


def _read_review_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_review(args: argparse.Namespace) -> int:
    if getattr(args, "background", False):
        return _start_background_review(args)

    store: Optional[JobStore] = None
    result_path: Optional[Path] = None
    if getattr(args, "job_id", None):
        workspace = Path(args.workspace).resolve()
        store = JobStore(_jobs_dir(args, workspace))
        result_path = _job_result_path(store, args.job_id)
        args.json = str(result_path)
        store.update(args.job_id, status="running")

    try:
        exit_code = _cmd_review_sync(args)
    except Exception as exc:
        if store is not None:
            store.update(args.job_id, status="failed", error=str(exc), exit_code=1)
        raise

    if store is not None and result_path is not None:
        result = _read_review_json(result_path)
        status = result.get("status", "failed") if result else "failed"
        store.update(args.job_id, status=status, result=result, exit_code=exit_code)
    return exit_code


def cmd_init(args: argparse.Namespace) -> None:
    target = Path(args.path)
    target.mkdir(parents=True, exist_ok=True)

    config_file = target / "config.yaml"
    if config_file.exists():
        print(f"이미 존재하는 파일을 건드리지 않습니다: {config_file}")
    else:
        config_file.write_text(DEFAULT_CONFIG, encoding="utf-8")
        print(f"생성됨: {config_file.resolve()}")

    agent_file = target / "custom_agents.py"
    if agent_file.exists():
        print(f"이미 존재하는 파일을 건드리지 않습니다: {agent_file}")
    else:
        agent_file.write_text(CUSTOM_AGENT_TEMPLATE, encoding="utf-8")
        print(f"생성됨: {agent_file.resolve()}")

    plugins_dir = target / "agents"
    if not plugins_dir.exists():
        plugins_dir.mkdir(parents=True, exist_ok=True)
        print(f"생성됨: {plugins_dir.resolve()} (플러그인 에이전트를 이곳에 넣으세요)")

    print("\n프로젝트 초기화 완료!")
    print("  agc r \"요청문\"  # 파이프라인 실행")
    print("  agc r \"요청문\" --plugins-dir ./agents")


def _install_hosts(target: str) -> tuple[str, ...]:
    if target == "all":
        return SUPPORTED_CLIS
    return (target,)


def cmd_install(args: argparse.Namespace) -> None:
    hosts = _install_hosts(args.target)
    setups = []
    copy_root = Path(args.copy_to).resolve() if args.copy_to else None
    assets_root = integration_assets_root()

    for host in hosts:
        host_root = assets_root / host
        if copy_root:
            host_root = copy_integration_pack(
                host,
                copy_root,
                force=args.force,
            )
        setups.append(build_integration_setup(host, host_root.resolve()))

    if args.json:
        print(json.dumps({"integrations": setups}, ensure_ascii=False, indent=2))
        return

    print("AgentChain integration setup")
    print("Default flow: current CLI session codes, AgentChain calls only the reviewer via `agc review`.\n")
    for setup in setups:
        print(f"[{setup['host']}] {setup['path']}")
        commands = setup.get("commands", [])
        if commands:
            print("Commands:")
            for command in commands:
                print(f"  {command}")
        notes = setup.get("notes", [])
        if notes:
            print("Notes:")
            for note in notes:
                print(f"  - {note}")
        print()


def _status_store(args: argparse.Namespace) -> JobStore:
    root = Path(args.jobs_dir).resolve() if args.jobs_dir else default_jobs_dir(Path(args.workspace).resolve())
    return JobStore(root)


def _print_job_summary(job: Dict[str, Any]) -> None:
    print(f"{job['id']}\t{job.get('status')}\t{job.get('kind')}\t{job.get('request')}")


def cmd_status(args: argparse.Namespace) -> None:
    store = _status_store(args)
    if args.job_id:
        try:
            _print_job_summary(store.read(args.job_id))
        except FileNotFoundError as exc:
            print(str(exc))
        return
    jobs = store.list()
    if not jobs:
        print(f"No jobs found in {store.root}")
        return
    for job in jobs:
        _print_job_summary(job)


def cmd_result(args: argparse.Namespace) -> None:
    store = _status_store(args)
    try:
        job = store.read(args.job_id) if args.job_id else store.latest()
    except FileNotFoundError as exc:
        print(str(exc))
        return
    if args.json:
        print(json.dumps(job, ensure_ascii=False, indent=2))
        return

    _print_job_summary(job)
    result = job.get("result") or {}
    if result:
        print(f"message: {result.get('message', '')}")
        suggestions = result.get("suggestions") or []
        if suggestions:
            print("suggestions:")
            for suggestion in suggestions:
                print(f"  - {suggestion}")
    else:
        print("No result recorded yet.")
    if job.get("stdout"):
        print(f"stdout: {job['stdout']}")
    if job.get("stderr"):
        print(f"stderr: {job['stderr']}")


def cmd_cancel(args: argparse.Namespace) -> None:
    store = _status_store(args)
    try:
        job = store.cancel(args.job_id)
    except FileNotFoundError as exc:
        print(str(exc))
        return
    _print_job_summary(job)


def build_parser(prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="AgentChain: 범용 에이전트 코딩-검토 파이프라인",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_run_arguments(run_parser: argparse.ArgumentParser) -> None:
        run_parser.add_argument("request", help="코드 생성 요청 문장")
        run_parser.add_argument(
            "-c", "--config", default=None,
            help="파이프라인 설정 파일 (기본값: config.yaml)",
        )
        run_parser.add_argument(
            "--profile",
            "-P",
            choices=SUPPORTED_PROFILES,
            default=None,
            help="내장 CLI 조합 프로필",
        )
        run_parser.add_argument(
            "--coder-cli",
            "-C",
            choices=SUPPORTED_CLIS,
            default=None,
            help="코더로 사용할 CLI",
        )
        run_parser.add_argument(
            "--reviewer-cli",
            "-R",
            choices=SUPPORTED_CLIS,
            default=None,
            help="리뷰어로 사용할 CLI",
        )
        run_parser.add_argument(
            "--target-file",
            "-t",
            default=None,
            help="생성/리뷰 대상 파일 경로",
        )
        run_parser.add_argument(
            "--coder-model",
            default=None,
            help="코더 CLI 모델 이름",
        )
        run_parser.add_argument(
            "--reviewer-model",
            default=None,
            help="리뷰어 CLI 모델 이름",
        )
        run_parser.add_argument(
            "--coder-command",
            default=None,
            help="코더 CLI 실행 파일 이름 또는 경로",
        )
        run_parser.add_argument(
            "--reviewer-command",
            default=None,
            help="리뷰어 CLI 실행 파일 이름 또는 경로",
        )
        run_parser.add_argument(
            "-o", "--output", default=None,
            help="생성된 코드를 저장할 파일 경로 (상대경로는 workspace 기준)",
        )
        run_parser.add_argument(
            "-l", "--language", default="python",
            help="타겟 언어 (기본값: python)",
        )
        run_parser.add_argument(
            "-m", "--max-iterations", type=int, default=None,
            help="최대 반복 횟수 (설정 파일 오버라이드)",
        )
        run_parser.add_argument(
            "--plugins-dir", default=None,
            help="추가 에이전트 플러그인 폴더",
        )
        run_parser.add_argument(
            "--workspace", "-w", default=".",
            help="작업 디렉토리 (기본값: 현재 디렉토리)",
        )
        run_parser.add_argument(
            "--json", default=None, metavar="PATH",
            help="전체 실행 결과를 JSON으로 저장",
        )

    # run
    run_parser = subparsers.add_parser("run", aliases=["r"], help="파이프라인을 실행합니다.")
    add_run_arguments(run_parser)
    pair_parser = subparsers.add_parser(
        "pair",
        aliases=["p", "delegate", "d"],
        help="CLI 코더/리뷰어 쌍을 짧게 실행합니다.",
    )
    add_run_arguments(pair_parser)
    pair_parser.set_defaults(
        profile=None,
        coder_cli="codex",
        reviewer_cli="kimi",
        max_iterations=3,
    )

    review_parser = subparsers.add_parser(
        "review",
        aliases=["v", "challenge"],
        help="현재 CLI 세션이 만든 결과를 외부 리뷰어 CLI로 검토합니다.",
    )
    review_parser.add_argument(
        "request",
        nargs="?",
        default="Review the current implementation.",
        help="원래 사용자 요청 또는 리뷰 기준",
    )
    review_parser.add_argument(
        "--reviewer-cli",
        "-R",
        choices=SUPPORTED_CLIS,
        default="kimi",
        help="리뷰어로 사용할 CLI (기본값: kimi)",
    )
    review_parser.add_argument(
        "--target-file",
        "-t",
        default=None,
        help="리뷰 대상 파일 경로",
    )
    review_parser.add_argument(
        "--reviewer-model",
        default=None,
        help="리뷰어 CLI 모델 이름",
    )
    review_parser.add_argument(
        "--reviewer-command",
        default=None,
        help="리뷰어 CLI 실행 파일 이름 또는 경로",
    )
    review_parser.add_argument(
        "--workspace",
        "-w",
        default=".",
        help="작업 디렉토리 (기본값: 현재 디렉토리)",
    )
    review_parser.add_argument(
        "-l",
        "--language",
        default="python",
        help="타겟 언어 (기본값: python)",
    )
    review_parser.add_argument(
        "--plugins-dir",
        default=None,
        help="추가 에이전트 플러그인 폴더",
    )
    review_parser.add_argument(
        "--stdin",
        action="store_true",
        help="리뷰 대상 코드를 stdin에서 읽습니다. --target-file이 없을 때 유용합니다.",
    )
    review_parser.add_argument(
        "--json",
        default=None,
        metavar="PATH",
        help="리뷰 결과 JSON 저장 경로",
    )
    review_parser.add_argument(
        "--fail-on-changes",
        action="store_true",
        help="changes_requested이면 exit code 10으로 종료합니다.",
    )

    review_parser.add_argument(
        "--focus",
        default=None,
        help="Extra review focus, especially useful for challenge mode.",
    )
    review_parser.add_argument(
        "--background",
        action="store_true",
        help="Start the review as a background job and return immediately.",
    )
    review_parser.add_argument(
        "--jobs-dir",
        default=None,
        metavar="DIR",
        help="Directory for AgentChain background job metadata.",
    )
    review_parser.add_argument("--job-id", default=None, help=argparse.SUPPRESS)
    review_parser.set_defaults(review_mode="review")

    # init
    init_parser = subparsers.add_parser(
        "init",
        aliases=["i"],
        help="프로젝트 초기화 파일을 생성합니다.",
    )
    init_parser.add_argument(
        "--path", default=".",
        help="초기화할 디렉토리 (기본값: 현재 디렉토리)",
    )

    # install/setup
    install_parser = subparsers.add_parser(
        "install",
        aliases=["setup"],
        help="Print or copy prebuilt Codex/Kimi/Antigravity skill/plugin setup files.",
    )
    install_parser.add_argument(
        "target",
        choices=SUPPORTED_INSTALL_TARGETS,
        help="CLI host integration to set up.",
    )
    install_parser.add_argument(
        "--copy-to",
        default=None,
        metavar="DIR",
        help="Copy the prebuilt integration pack into DIR/<target> before printing setup steps.",
    )
    install_parser.add_argument(
        "--force",
        action="store_true",
        help="Allow --copy-to to merge into an existing target directory.",
    )
    install_parser.add_argument(
        "--json",
        action="store_true",
        help="Print setup metadata as JSON.",
    )

    def add_job_reader_args(job_parser: argparse.ArgumentParser, *, job_required: bool = False) -> None:
        job_parser.add_argument("job_id", nargs=None if job_required else "?", default=None)
        job_parser.add_argument(
            "--workspace",
            "-w",
            default=".",
            help="Workspace used to locate .agent-chain/jobs when --jobs-dir is omitted.",
        )
        job_parser.add_argument(
            "--jobs-dir",
            default=None,
            metavar="DIR",
            help="Directory for AgentChain background job metadata.",
        )

    status_parser = subparsers.add_parser("status", help="List background review/delegate jobs.")
    add_job_reader_args(status_parser)

    result_parser = subparsers.add_parser("result", help="Show the latest or selected job result.")
    add_job_reader_args(result_parser)
    result_parser.add_argument("--json", action="store_true", help="Print raw job metadata as JSON.")

    cancel_parser = subparsers.add_parser("cancel", help="Cancel a running background job.")
    add_job_reader_args(cancel_parser, job_required=True)

    # web UI
    web_parser = subparsers.add_parser(
        "web",
        aliases=["ui"],
        help="실시간 웹 UI를 실행합니다.",
    )
    web_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="웹 UI bind host (기본값: 127.0.0.1)",
    )
    web_parser.add_argument(
        "--port",
        type=int,
        default=8787,
        help="웹 UI port (기본값: 8787)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in {"run", "r", "pair", "p", "delegate", "d"}:
        cmd_run(args)
    elif args.command in {"review", "v", "challenge"}:
        if args.command == "challenge":
            args.review_mode = "challenge"
        return cmd_review(args)
    elif args.command in {"init", "i"}:
        cmd_init(args)
    elif args.command in {"install", "setup"}:
        cmd_install(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "result":
        cmd_result(args)
    elif args.command == "cancel":
        cmd_cancel(args)
    elif args.command in {"web", "ui"}:
        from .web import serve

        serve(host=args.host, port=args.port)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
