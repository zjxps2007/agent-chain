"""파이프라인 실행 유틸리티."""

from pathlib import Path
from typing import Any, Dict, Optional

from .core import Agent, Context, Pipeline


def run_pipeline(
    agents: Dict[str, Agent],
    config: Dict[str, Any],
    request: str,
    workspace: Path,
    env: Optional[Any] = None,
    language: str | None = None,
) -> Context:
    """에이전트 맵과 설정으로 파이프라인을 간편하게 실행.

    Args:
        agents: 이름 -> Agent 인스턴스 매핑.
        config: Pipeline 설정 dict (max_iterations, steps 등).
        request: 사용자 요청 문자열.
        workspace: 작업 디렉토리 경로.
        env: Tool Environment 인스턴스.
        language: 타겟 언어 (선택).

    Returns:
        최종 실행 컨텍스트.
    """
    pipeline = Pipeline(config)
    return pipeline.execute(agents, request, workspace, env, language)
