---
name: agent-chain
description: Use the installed agent-chain binary to review code produced by the current Codex session, or run paired CLI agents such as Codex, Kimi, and Antigravity.
---

# AgentChain

Use this skill when the current Codex session should implement code and an external reviewer CLI should review it.

The `agc` executable must be available on `PATH`. `agent-chain` remains a long-form alias.

## Preferred Host-Session Flow

When running inside Codex, do not spawn another Codex coder by default. First edit the files yourself, then ask Kimi to review the result:

```powershell
agc review "USER REQUEST" -R kimi -t src/generated.py -w . --json .agent-chain-review.json
```

After the command finishes, read `.agent-chain-review.json`.

- If `status` is `approved`, stop.
- If `status` is `changes_requested`, apply `message` and `suggestions`, then run `agc review` again.

Use this pattern for any host CLI:

```powershell
agc review "USER REQUEST" -R <REVIEWER_CLI> -t <TARGET_FILE> -w . --json .agent-chain-review.json
```

Use challenge mode when the user asks for an adversarial review, design pressure test, or risk-focused critique:

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

## Fully Delegated Pair Commands

Use these only when the user explicitly wants AgentChain to spawn both coder and reviewer CLIs.

Codex as subprocess coder, Kimi as reviewer:

```powershell
agc delegate "USER REQUEST" -C codex -R kimi -t src/generated.py -w .
```

Kimi as coder, Codex as reviewer:

```powershell
agc p "USER REQUEST" -C kimi -R codex -t src/generated.py -w .
```

Antigravity as reviewer:

```powershell
agc p "USER REQUEST" -C codex -R antigravity -t src/generated.py -w .
```

Profiles are available when the user does not need custom options:

```powershell
agc p "USER REQUEST" -P codex-kimi -t src/generated.py -w .
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
agc p "USER REQUEST" -C codex -R antigravity --reviewer-command <ANTIGRAVITY_EXE>
```

The reviewer should return JSON with `status`, `message`, and `suggestions`.
