"""동적 에이전트 발견 및 로딩."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Type

from .core import Agent


class AgentValidationError(TypeError):
    """에이전트 클래스가 AgentChain 인터페이스 계약을 만족하지 않을 때 발생."""


def _pascal_to_snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _import_module_from_path(module_name: str, file_path: Path):
    """파일 경로에서 파이썬 모듈을 임포트."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"모듈을 로드할 수 없습니다: {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _is_agent_candidate_class(obj: object) -> bool:
    """Return whether an object can be considered for AgentChain validation."""
    return inspect.isclass(obj) and not inspect.isabstract(obj)


def _constructor_call(
    signature: inspect.Signature,
    name: str,
    config: Dict[str, Any],
) -> tuple[tuple[object, ...], Dict[str, object]]:
    candidates: list[tuple[tuple[object, ...], Dict[str, object]]] = [
        ((name, config), {}),
        ((), {"name": name, "config": config}),
        ((), {"name": name}),
        ((), {"config": config}),
        ((), {"cfg": config}),
        ((), {"settings": config}),
        ((name,), {}),
        ((config,), {}),
        ((), {}),
    ]
    for args, kwargs in candidates:
        try:
            signature.bind(*args, **kwargs)
        except TypeError:
            continue
        return args, kwargs
    raise AgentValidationError("생성자가 지원되는 호출 형태와 맞지 않습니다.")


def _assert_constructor_bindable(signature: inspect.Signature, target: str) -> None:
    try:
        _constructor_call(signature, "agent_name", {})
    except AgentValidationError as exc:
        raise AgentValidationError(f"{target} 시그니처가 AgentChain 계약과 맞지 않습니다: {exc}") from exc


def _assert_run_bindable(signature: inspect.Signature, target: str) -> None:
    try:
        signature.bind(object(), object())
        return
    except TypeError:
        pass

    try:
        signature.bind(object())
    except TypeError as exc:
        raise AgentValidationError(f"{target} 시그니처가 AgentChain 계약과 맞지 않습니다: {exc}") from exc


def validate_agent_class(
    cls: object,
    *,
    expected_role: Optional[str] = None,
) -> Type[Any]:
    """동적으로 로드한 클래스가 실행 가능한 에이전트인지 검증.

    동적 import 자체의 부작용을 막을 수는 없으므로, 로드 이후에는 최소한
    AgentChain이 안전하게 인스턴스화하고 실행할 수 있는 인터페이스만 허용합니다.
    role은 오케스트레이션 메타데이터이며, 특정 베이스 클래스 상속을 강제하지 않습니다.
    """
    del expected_role

    if not _is_agent_candidate_class(cls):
        raise AgentValidationError(f"{cls!r}는 실행 가능한 구체 클래스가 아닙니다.")

    agent_cls = cls

    _assert_constructor_bindable(
        inspect.signature(agent_cls),
        target=f"{agent_cls.__module__}.{agent_cls.__name__}.__init__",
    )

    run_method = getattr(agent_cls, "run", None)
    if run_method is None or not callable(run_method):
        raise AgentValidationError(f"{agent_cls.__name__}에 run(context) 메서드가 없습니다.")

    _assert_run_bindable(
        inspect.signature(run_method),
        target=f"{agent_cls.__module__}.{agent_cls.__name__}.run",
    )

    return agent_cls


def discover_agents_from_dir(directory: Path) -> Dict[str, Type[Any]]:
    """지정된 디렉토리의 .py 파일을 스캔하여 에이전트 클래스를 발견."""
    discovered: Dict[str, Type[Any]] = {}
    root = Path(directory).resolve()
    if not root.exists():
        return discovered

    for py_file in root.rglob("*.py"):
        if py_file.name.startswith("_"):
            continue
        rel_parts = py_file.relative_to(root).with_suffix("").parts
        safe_name = "_".join(_pascal_to_snake(part) for part in rel_parts)
        module_name = f"agent_chain.discovered.{safe_name}"
        try:
            module = _import_module_from_path(module_name, py_file)
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if obj.__module__ != module.__name__:
                    continue
                try:
                    cls = validate_agent_class(obj)
                except AgentValidationError as e:
                    print(f"[Registry] {py_file}의 {name} 검증 실패: {e}")
                    continue
                # 클래스 이름과 snake_case 별칭을 에이전트 ID로 등록
                discovered[name] = cls
                discovered[_pascal_to_snake(name)] = cls
        except Exception as e:
            print(f"[Registry] {py_file} 로딩 실패: {e}")
    return discovered


def load_agent_from_class_path(class_path: str) -> Type[Any]:
    """'module.submodule.ClassName' 형태의 문자열에서 클래스를 로드."""
    if "." not in class_path:
        raise ValueError(f"class_path는 'module.Class' 형태여야 합니다: {class_path}")
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return validate_agent_class(cls)


def _instantiate_agent(cls: Type[Any], name: str, config: Dict[str, Any]) -> Any:
    args, kwargs = _constructor_call(inspect.signature(cls), name, config)
    return cls(*args, **kwargs)


def resolve_agents(
    config: Dict[str, Any],
    *,
    plugins_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """설정을 바탕으로 에이전트 인스턴스를 생성.

    Args:
        config: Pipeline 설정 dict (steps, agent_configs 포함).
        plugins_dir: 추가 에이전트 플러그인 폴터.

    Returns:
        이름 -> Agent 인스턴스 매핑.
    """
    # 1. 플러그인 디렉토리에서 클래스 발견
    discovered: Dict[str, Type[Any]] = {}
    if plugins_dir:
        discovered = discover_agents_from_dir(Path(plugins_dir))

    # 2. 내장 에이전트도 등록 (직접 import)
    from .agents import (
        SimpleCoderAgent, SimpleReviewerAgent, LLMCoderAgent, LLMReviewerAgent,
        KimiCLICoder, KimiCLIReviewer, CodexCLICoder, CodexCLIReviewer,
        GeminiCLICoder, GeminiCLIReviewer, ConfigurableCLICoder, ConfigurableCLIReviewer,
        AntigravityCLICoder, AntigravityCLIReviewer,
    )

    _builtin_classes: list[Type[Any]] = [
        SimpleCoderAgent, SimpleReviewerAgent,
        LLMCoderAgent, LLMReviewerAgent,
        KimiCLICoder, KimiCLIReviewer,
        CodexCLICoder, CodexCLIReviewer,
        GeminiCLICoder, GeminiCLIReviewer,
        ConfigurableCLICoder, ConfigurableCLIReviewer,
        AntigravityCLICoder, AntigravityCLIReviewer,
    ]

    # 직관적 별칭 (config에서 사용)
    _aliases: Dict[str, Type[Agent]] = {
        "simple_coder": SimpleCoderAgent,
        "simple_reviewer": SimpleReviewerAgent,
        "llm_coder": LLMCoderAgent,
        "llm_reviewer": LLMReviewerAgent,
        "kimi_coder": KimiCLICoder,
        "kimi_reviewer": KimiCLIReviewer,
        "codex_coder": CodexCLICoder,
        "codex_reviewer": CodexCLIReviewer,
        "gemini_coder": GeminiCLICoder,
        "gemini_reviewer": GeminiCLIReviewer,
        "cli_coder": ConfigurableCLICoder,
        "cli_reviewer": ConfigurableCLIReviewer,
        "generic_cli_coder": ConfigurableCLICoder,
        "generic_cli_reviewer": ConfigurableCLIReviewer,
        "antigravity_coder": AntigravityCLICoder,
        "antigravity_reviewer": AntigravityCLIReviewer,
    }

    builtin: Dict[str, Type[Any]] = {**_aliases}
    for cls in _builtin_classes:
        builtin[cls.__name__] = cls
        builtin[_pascal_to_snake(cls.__name__)] = cls

    agent_cfgs = config.get("agent_configs", {})
    agents: Dict[str, Any] = {}

    # steps에 등장한 에이전트 정의 수집
    agent_defs: Dict[str, Dict[str, Any]] = {}
    for step in config.get("steps", []):
        name = step["agent"]
        if name not in agent_defs:
            agent_defs[name] = {"role": step.get("role"), "class": step.get("class")}

    for name, meta in agent_defs.items():
        cfg = agent_cfgs.get(name, {})
        cls: Optional[Type[Any]] = None

        # 2-1. 설정에 class가 명시되어 있으면 동적 로드
        if meta.get("class"):
            cls = load_agent_from_class_path(meta["class"])

        # 2-2. 발견된 플러그인에서 클래스 이름으로 검색
        if cls is None and name in discovered:
            cls = discovered[name]

        # 2-3. 내장 에이전트에서 검색
        if cls is None:
            # 설정의 agent_configs 안에 class 키가 있으면 사용
            explicit_class = cfg.get("class")
            if explicit_class:
                cls = load_agent_from_class_path(explicit_class)
            if cls is None:
                # 이름 매핑 시도
                cls = builtin.get(name)

        # 2-4. role 기본값 추론
        if cls is None:
            role = meta["role"]
            if role == "coder":
                cls = SimpleCoderAgent
            elif role == "reviewer":
                cls = SimpleReviewerAgent

        if cls is None:
            raise ValueError(f"에이전트 '{name}'의 클래스를 결정할 수 없습니다.")

        cls = validate_agent_class(cls, expected_role=meta.get("role"))
        agent = _instantiate_agent(cls, name, cfg)
        if not hasattr(agent, "name"):
            try:
                agent.name = name
            except Exception:
                pass
        if not hasattr(agent, "config"):
            try:
                agent.config = cfg
            except Exception:
                pass
        agents[name] = agent

    return agents
