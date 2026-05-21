---
name: agent-chain
description: Run this repository's AgentChain orchestrator as a Codex/Kimi/Antigravity skill-style wrapper when the user wants two CLI agents to code, review, revise, and repeat.
---

# AgentChain Wrapper

Use this skill when the user wants to run AgentChain like a CLI plugin/skill instead of calling
`python -m agent_chain` directly.

## What This Skill Does

AgentChain is the orchestrator. External CLIs such as Codex, Kimi, Antigravity, Claude,
Aider, or custom tools are workers configured in YAML.

The normal loop is:

1. coder step generates or edits code.
2. reviewer step returns a review.
3. if review status is `changes_requested`, AgentChain starts the next iteration from the first step.
4. if review status is `approved`, AgentChain stops.

## Wrapper Command

If AgentChain is installed, prefer the short `ac` command:

```powershell
ac r "USER REQUEST" -c .\config.yaml -w .
```

For quick paired CLI runs, use `ac p`:

```powershell
ac p "USER REQUEST" -C codex -R kimi -t src/generated.py -w .
```

If the package entrypoint is not installed yet, use the repository wrapper script and pass the
project workspace explicitly:

```powershell
uv run python <AGENT_CHAIN_ROOT>\plugins\agent-chain-wrapper\scripts\agent_chain_wrapper.py "USER REQUEST" --config <PROJECT_ROOT>\.agent-chain.yaml --workspace <PROJECT_ROOT>
```

The wrapper sets `PYTHONPATH` to this repository, runs AgentChain from the target workspace, and
passes through common AgentChain options.

Useful options:

- `--config PATH`: YAML config. Defaults to the first of `.agent-chain.yaml`, `agent-chain.yaml`, `config.yaml`, or this repo's `config.yaml`.
- `--workspace PATH`: target workspace. Defaults to the current directory.
- `--max-iterations N`: override `max_iterations`.
- `--language NAME`: pass language metadata to agents.
- `--output PATH`: write final code.
- `--json PATH`: write final result JSON.
- `--plugins-dir PATH`: load additional AgentChain Python agent plugins.

## Supported Built-In CLI Workers

Use these options when the user wants a quick Codex/Kimi/Antigravity pair without writing config:

```powershell
ac p "USER REQUEST" -C codex -R antigravity -t src/generated.py
```

Supported values:

- `codex`
- `kimi`
- `antigravity`

Pair any coder/reviewer:

```powershell
ac p "USER REQUEST" -C kimi -R codex -t src/generated.py
ac p "USER REQUEST" -C antigravity -R kimi -t src/generated.py
```

Optional overrides:

- `--coder-model MODEL`
- `--reviewer-model MODEL`
- `--coder-command PATH_OR_NAME`
- `--reviewer-command PATH_OR_NAME`

Built-in profile configs are also available:

- `--profile codex-antigravity`
- `--profile codex-kimi`
- `--profile kimi-codex`
- `--profile kimi-antigravity`
- `--profile antigravity-codex`
- `--profile antigravity-kimi`

Kimi can load this same skill directory when used as the host CLI:

```powershell
kimi --skills-dir <AGENT_CHAIN_ROOT>\plugins\agent-chain-wrapper\skills --prompt "Use the agent-chain skill to implement this request."
```

## Config For Codex Coder And CLI Reviewer

Use this shape when the user wants Codex to code and another CLI to review:

```yaml
max_iterations: 3

steps:
  - role: coder
    agent: codex_coder
    output: code
  - role: reviewer
    agent: antigravity_reviewer
    output: review

agent_configs:
  codex_coder:
    model: gpt-5.4
    target_file: src/generated.py
  antigravity_reviewer:
    class: agent_chain.agents.cli.ConfigurableCLIReviewer
    target_file: src/generated.py
    command:
      - antigravity
      - --prompt
      - "{prompt}"
```

Adjust `command` to match the actual reviewer CLI. Review CLIs should print JSON:

```json
{"status":"approved","message":"ok","suggestions":[]}
```

or:

```json
{"status":"changes_requested","message":"fix this","suggestions":["specific change"]}
```

If a linter or test runner exits nonzero for findings, wrap it with a small script that converts
the output to this JSON shape and exits 0 so AgentChain can treat it as review feedback rather than
a runner failure.
