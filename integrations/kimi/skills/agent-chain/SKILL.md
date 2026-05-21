---
name: agent-chain
description: Use the installed agent-chain binary to orchestrate Codex, Kimi, and Antigravity CLI agents in a code-review-revise loop.
---

# AgentChain

Use this skill when the user wants two CLI agents to alternate:

1. coder CLI implements or edits code.
2. reviewer CLI reviews and returns feedback.
3. AgentChain repeats until the review is approved or max iterations are reached.

The `agent-chain` executable must be available on `PATH`.

## Commands

Kimi as coder, Codex as reviewer:

```powershell
agent-chain run "USER REQUEST" --coder-cli kimi --reviewer-cli codex --target-file src/generated.py --workspace .
```

Codex as coder, Kimi as reviewer:

```powershell
agent-chain run "USER REQUEST" --coder-cli codex --reviewer-cli kimi --target-file src/generated.py --workspace .
```

Antigravity as reviewer:

```powershell
agent-chain run "USER REQUEST" --coder-cli kimi --reviewer-cli antigravity --target-file src/generated.py --workspace .
```

## Profiles

```powershell
agent-chain run "USER REQUEST" --profile kimi-codex --target-file src/generated.py --workspace .
```

Supported profiles:

- `codex-antigravity`
- `codex-kimi`
- `kimi-codex`
- `kimi-antigravity`
- `antigravity-codex`
- `antigravity-kimi`

## Host Setup

Launch Kimi with this directory:

```powershell
kimi --skills-dir <AGENT_CHAIN_ROOT>\integrations\kimi\skills --prompt "Use agent-chain for this request."
```
