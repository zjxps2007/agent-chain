---
name: agent-chain
description: Use the installed agent-chain binary to run paired CLI agents such as Codex, Kimi, and Antigravity in a code-review-revise loop.
---

# AgentChain

Use this skill when the user wants a coder CLI and reviewer CLI to work together.

The `agent-chain` executable must be available on `PATH`.

## Preferred Commands

Codex as coder, Kimi as reviewer:

```powershell
agent-chain run "USER REQUEST" --coder-cli codex --reviewer-cli kimi --target-file src/generated.py --workspace .
```

Kimi as coder, Codex as reviewer:

```powershell
agent-chain run "USER REQUEST" --coder-cli kimi --reviewer-cli codex --target-file src/generated.py --workspace .
```

Antigravity as reviewer:

```powershell
agent-chain run "USER REQUEST" --coder-cli codex --reviewer-cli antigravity --target-file src/generated.py --workspace .
```

Profiles are available when the user does not need custom options:

```powershell
agent-chain run "USER REQUEST" --profile codex-kimi --target-file src/generated.py --workspace .
```

Supported profile names:

- `codex-antigravity`
- `codex-kimi`
- `kimi-codex`
- `kimi-antigravity`
- `antigravity-codex`
- `antigravity-kimi`

## Notes

If a CLI executable is not named `codex`, `kimi`, or `antigravity`, pass its path:

```powershell
agent-chain run "USER REQUEST" --coder-cli codex --reviewer-cli antigravity --reviewer-command C:\Tools\antigravity.exe
```

The reviewer should return JSON with `status`, `message`, and `suggestions`.
