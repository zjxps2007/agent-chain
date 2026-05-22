---
name: agent-chain
description: Run this repository's AgentChain orchestrator as a Codex/Kimi/Antigravity skill-style wrapper, preferring reviewer-only checks for code produced by the current CLI session.
---

# AgentChain Wrapper

Use this skill when the user wants the current CLI session to code and another CLI to review the result.

## What This Skill Does

AgentChain is the orchestrator. External CLIs such as Codex, Kimi, Antigravity, Claude,
Aider, or custom tools are workers configured in YAML.

When the current host CLI session is already editing files, prefer reviewer-only mode:

```powershell
agc review "USER REQUEST" -R kimi -t src/generated.py -w . --json .agent-chain-review.json
```

Read `.agent-chain-review.json`. If `status` is `changes_requested`, apply `message` and
`suggestions`, then run `agc review` again. If `status` is `approved`, stop.

The host-session loop is:

1. current CLI session generates or edits code.
2. `agc review` calls the selected reviewer CLI.
3. if review status is `changes_requested`, the current CLI applies the feedback.
4. run `agc review` again until it returns `approved`.

## Wrapper Command

If AgentChain is installed, prefer the short `agc` command:

```powershell
agc review "USER REQUEST" -R kimi -t src/generated.py -w . --json .agent-chain-review.json
```

For adversarial review, use:

```powershell
agc challenge "USER REQUEST" -R kimi -t src/generated.py -w . --focus "security and rollback risk"
```

For long reviews, use background job commands:

```powershell
agc review "USER REQUEST" -R kimi -t src/generated.py -w . --background
agc status
agc result <job-id>
agc cancel <job-id>
```

For fully delegated paired CLI runs, use `agc p` only when explicitly requested:

```powershell
agc delegate "USER REQUEST" -C codex -R kimi -t src/generated.py -w .
```

If the package entrypoint is not installed yet, use the repository wrapper script and pass the
project workspace explicitly:

```powershell
uv run python <AGENT_CHAIN_ROOT>\plugins\agent-chain-wrapper\scripts\agent_chain_wrapper.py "USER REQUEST" --reviewer-cli kimi --target-file src/generated.py --workspace <PROJECT_ROOT> --json .agent-chain-review.json
```

The wrapper sets `PYTHONPATH` to this repository, runs AgentChain from the target workspace, and defaults to reviewer-only mode unless `--pair`, `--config`, `--profile`, or `--coder-cli` is supplied.

Useful options:

- `--config PATH`: YAML config. Supplying this runs full AgentChain config mode.
- `--pair`: run a delegated coder/reviewer pair.
- `--workspace PATH`: target workspace. Defaults to the current directory.
- `--max-iterations N`: override `max_iterations`.
- `--language NAME`: pass language metadata to agents.
- `--output PATH`: write final code.
- `--json PATH`: write final result JSON.
- `--plugins-dir PATH`: load additional AgentChain Python agent plugins.

## Supported Built-In CLI Workers

Use these options when the user wants a quick Codex/Kimi/Antigravity pair without writing config:

```powershell
agc p "USER REQUEST" -C codex -R antigravity -t src/generated.py
```

Supported values:

- `codex`
- `kimi`
- `antigravity`

Pair any coder/reviewer:

```powershell
agc p "USER REQUEST" -C kimi -R codex -t src/generated.py
agc p "USER REQUEST" -C antigravity -R kimi -t src/generated.py
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
kimi plugin install <AGENT_CHAIN_ROOT>\integrations\kimi
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
      - agy
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
