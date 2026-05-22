from pathlib import Path
import sys

from agent_chain.agents import (
    AntigravityCLICoder,
    AntigravityCLIReviewer,
    ConfigurableCLIReviewer,
    LLMCoderAgent,
    LLMReviewerAgent,
    SimpleCoderAgent,
    SimpleReviewerAgent,
)
from agent_chain.core import Context, Pipeline
from agent_chain.tools import Environment
from agent_chain.registry import (
    discover_agents_from_dir,
    resolve_agents,
)


def test_resolve_agents_falls_back_to_role_defaults() -> None:
    agents = resolve_agents(
        {
            "steps": [
                {"role": "coder", "agent": "primary_coder"},
                {"role": "reviewer", "agent": "strict_reviewer"},
            ],
        }
    )

    assert isinstance(agents["primary_coder"], SimpleCoderAgent)
    assert isinstance(agents["strict_reviewer"], SimpleReviewerAgent)


def test_resolve_agents_supports_llm_aliases() -> None:
    agents = resolve_agents(
        {
            "steps": [
                {"role": "coder", "agent": "llm_coder"},
                {"role": "reviewer", "agent": "llm_reviewer"},
            ],
            "agent_configs": {
                "llm_coder": {"client": object()},
                "llm_reviewer": {"client": object()},
            },
        }
    )

    assert isinstance(agents["llm_coder"], LLMCoderAgent)
    assert isinstance(agents["llm_reviewer"], LLMReviewerAgent)


def test_resolve_agents_supports_generic_cli_reviewer_alias() -> None:
    agents = resolve_agents(
        {
            "steps": [
                {"role": "reviewer", "agent": "generic_cli_reviewer"},
            ],
            "agent_configs": {
                "generic_cli_reviewer": {
                    "command": [
                        sys.executable,
                        "-c",
                        "print('{\"status\":\"approved\",\"message\":\"ok\",\"suggestions\":[]}')",
                    ],
                },
            },
        }
    )

    assert isinstance(agents["generic_cli_reviewer"], ConfigurableCLIReviewer)


def test_resolve_agents_supports_antigravity_aliases() -> None:
    agents = resolve_agents(
        {
            "steps": [
                {"role": "coder", "agent": "antigravity_coder"},
                {"role": "reviewer", "agent": "antigravity_reviewer"},
            ],
        }
    )

    assert isinstance(agents["antigravity_coder"], AntigravityCLICoder)
    assert isinstance(agents["antigravity_reviewer"], AntigravityCLIReviewer)


def test_antigravity_agents_default_to_agy_command(tmp_path: Path) -> None:
    context = Context(request="review", workspace=tmp_path)

    coder = AntigravityCLICoder("antigravity_coder")
    reviewer = AntigravityCLIReviewer("antigravity_reviewer")

    assert coder.build_command(context)[0] == "agy"
    assert reviewer.build_command(context)[0] == "agy"


def test_discover_agents_loads_valid_plugin_with_snake_case_alias(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "agents"
    plugins_dir.mkdir()
    (plugins_dir / "plugin.py").write_text(
        """
from agent_chain.agents.base import BaseCoderAgent
from agent_chain.core import Context


class PluginCoderAgent(BaseCoderAgent):
    def generate_code(self, context: Context) -> str:
        return "def plugin():\\n    return 1\\n"
""".strip(),
        encoding="utf-8",
    )

    discovered = discover_agents_from_dir(plugins_dir)

    assert "PluginCoderAgent" in discovered
    assert "plugin_coder_agent" in discovered


def test_resolve_agents_does_not_require_role_specific_base_class(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "agents"
    plugins_dir.mkdir()
    (plugins_dir / "reviewer_plugin.py").write_text(
        """
from agent_chain.agents.base import BaseReviewerAgent
from agent_chain.core import Context, ReviewResult


class PluginReviewer(BaseReviewerAgent):
    def review_code(self, context: Context) -> ReviewResult:
        return ReviewResult(status="approved", message="ok")
""".strip(),
        encoding="utf-8",
    )

    agents = resolve_agents(
        {
            "steps": [
                {"role": "coder", "agent": "PluginReviewer"},
            ],
        },
        plugins_dir=plugins_dir,
    )

    assert agents["PluginReviewer"].__class__.__name__ == "PluginReviewer"


def test_plain_run_context_agent_can_be_discovered_and_executed(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "agents"
    plugins_dir.mkdir()
    (plugins_dir / "plain_plugin.py").write_text(
        """
from agent_chain.core import Context


class PlainAgent:
    def __init__(self, name: str, config: dict | None = None) -> None:
        self.name = name
        self.config = config or {}

    def run(self, context: Context) -> Context:
        context.metadata["plain"] = self.config["value"]
        return context
""".strip(),
        encoding="utf-8",
    )

    config = {
        "steps": [
            {"role": "planner", "agent": "PlainAgent"},
        ],
        "agent_configs": {
            "PlainAgent": {"value": "ok"},
        },
    }

    agents = resolve_agents(config, plugins_dir=plugins_dir)
    context = Pipeline(config).execute(agents, request="plan", workspace=tmp_path)

    assert context.metadata["plain"] == "ok"


def test_resolve_agents_supports_looser_agent_constructors(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "agents"
    plugins_dir.mkdir()
    (plugins_dir / "constructors.py").write_text(
        """
from agent_chain.core import Context


class NoArgAgent:
    def run(self, context: Context) -> Context:
        context.metadata["no_arg_name"] = self.name
        return context


class ConfigOnlyAgent:
    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

    def run(self, context: Context) -> Context:
        context.metadata["config_value"] = self.config["value"]
        return context
""".strip(),
        encoding="utf-8",
    )

    config = {
        "steps": [
            {"role": "first", "agent": "NoArgAgent"},
            {"role": "second", "agent": "ConfigOnlyAgent"},
        ],
        "agent_configs": {
            "ConfigOnlyAgent": {"value": "from-config"},
        },
    }

    agents = resolve_agents(config, plugins_dir=plugins_dir)
    context = Pipeline(config).execute(agents, request="run", workspace=tmp_path)

    assert context.metadata["no_arg_name"] == "NoArgAgent"
    assert context.metadata["config_value"] == "from-config"


def test_pipeline_can_bind_generic_agent_outputs_and_review_gates(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "agents"
    plugins_dir.mkdir()
    (plugins_dir / "generic_plugin.py").write_text(
        """
from agent_chain.core import Context


class StringCoder:
    def __init__(self, name: str, config: dict | None = None) -> None:
        self.name = name
        self.config = config or {}

    def run(self, context: Context) -> str:
        return "def generated():\\n    return 1\\n"


class DictGate:
    def __init__(self, name: str, config: dict | None = None) -> None:
        self.name = name
        self.config = config or {}

    def run(self, context: Context) -> dict:
        if context.iteration == 1:
            return {
                "status": "changes_requested",
                "message": "retry once",
                "suggestions": ["try again"],
            }
        return {"status": "approved", "message": "ok", "suggestions": []}
""".strip(),
        encoding="utf-8",
    )

    config = {
        "max_iterations": 2,
        "steps": [
            {"role": "producer", "agent": "StringCoder", "output": "code"},
            {"role": "quality_gate", "agent": "DictGate", "output": "review"},
        ],
    }

    agents = resolve_agents(config, plugins_dir=plugins_dir)
    context = Pipeline(config).execute(agents, request="build", workspace=tmp_path)

    assert context.code == "def generated():\n    return 1\n"
    assert [review.status for review in context.reviews] == ["changes_requested", "approved"]


def test_configurable_cli_reviewer_command_outputs_review(tmp_path: Path) -> None:
    config = {
        "max_iterations": 1,
        "steps": [
            {"role": "reviewer", "agent": "generic_cli_reviewer"},
        ],
        "agent_configs": {
            "generic_cli_reviewer": {
                "command": [
                    sys.executable,
                    "-c",
                    "print('{\"status\":\"approved\",\"message\":\"ok\",\"suggestions\":[]}')",
                ],
            },
        },
    }

    agents = resolve_agents(config)
    context = Pipeline(config).execute(
        agents,
        request="review",
        workspace=tmp_path,
        env=Environment(tmp_path),
    )

    assert context.review is not None
    assert context.review.status == "approved"


def test_configurable_cli_reviewer_extracts_fenced_json() -> None:
    reviewer = ConfigurableCLIReviewer("reviewer")

    review = reviewer.parse_review(
        """
Review result:
```json
{"status":"changes_requested","message":"fix it","suggestions":["one"]}
```
""".strip()
    )

    assert review.status == "changes_requested"
    assert review.message == "fix it"
    assert review.suggestions == ["one"]


def test_kimi_reviewer_prompt_includes_original_request(tmp_path: Path) -> None:
    from agent_chain.agents.cli.kimi import KimiCLIReviewer

    reviewer = KimiCLIReviewer("kimi_reviewer", {"target_file": "src/generated.py"})
    context = Context(
        request="implement email validation",
        workspace=tmp_path,
        language="python",
    )

    command = reviewer.build_command(context)
    prompt = command[command.index("--prompt") + 1]

    assert "implement email validation" in prompt
    assert "src/generated.py" in prompt


def test_kimi_reviewer_prompt_supports_challenge_mode(tmp_path: Path) -> None:
    from agent_chain.agents.cli.kimi import KimiCLIReviewer

    reviewer = KimiCLIReviewer(
        "kimi_reviewer",
        {
            "target_file": "src/generated.py",
            "review_mode": "challenge",
            "review_focus": "race conditions",
        },
    )
    context = Context(request="implement queue worker", workspace=tmp_path, language="python")

    command = reviewer.build_command(context)
    prompt = command[command.index("--prompt") + 1]

    assert "adversarial review" in prompt
    assert "race conditions" in prompt


def test_discover_agents_skips_plugins_with_incompatible_constructor(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "agents"
    plugins_dir.mkdir()
    (plugins_dir / "bad_plugin.py").write_text(
        """
from agent_chain.core import Agent, Context


class BadAgent(Agent):
    def __init__(self, name: str, config: dict | None, extra: str) -> None:
        super().__init__(name, config)

    def run(self, context: Context) -> Context:
        return context
""".strip(),
        encoding="utf-8",
    )

    discovered = discover_agents_from_dir(plugins_dir)

    assert "BadAgent" not in discovered
