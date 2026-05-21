"""AgentChain CLI 인터페이스."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from .core import Agent, Context, Pipeline
from .integrations import (
    SUPPORTED_CLIS,
    SUPPORTED_PROFILES,
    build_cli_pair_config,
    uses_generated_cli_config,
)
from .pipeline import run_pipeline
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
        print("`ac i` 로 기본 설정을 생성하세요.")
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
    print("  ac r \"요청문\"  # 파이프라인 실행")
    print("  ac r \"요청문\" --plugins-dir ./agents")


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
        aliases=["p"],
        help="CLI 코더/리뷰어 쌍을 짧게 실행합니다.",
    )
    add_run_arguments(pair_parser)
    pair_parser.set_defaults(
        profile=None,
        coder_cli="codex",
        reviewer_cli="kimi",
        max_iterations=3,
    )

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

    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in {"run", "r", "pair", "p"}:
        cmd_run(args)
    elif args.command in {"init", "i"}:
        cmd_init(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
