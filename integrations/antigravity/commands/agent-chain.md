# AgentChain Command

Use this command definition if Antigravity supports custom Markdown commands.

Run AgentChain reviewer-only mode after the current Antigravity session edits files:

```powershell
agc review "$ARGUMENTS" -R kimi -t src/generated.py -w . --json .agent-chain-review.json
```

Read `.agent-chain-review.json`, apply `changes_requested` feedback, then run the review again until it returns `approved`.

Alternative reviewers:

```powershell
agc review "$ARGUMENTS" -R codex -t src/generated.py -w . --json .agent-chain-review.json
agc review "$ARGUMENTS" -R antigravity -t src/generated.py -w . --json .agent-chain-review.json
```

For adversarial review:

```powershell
agc challenge "$ARGUMENTS" -R kimi -t src/generated.py -w . --focus "security and race conditions"
```

The `agc` executable must be on `PATH`. `agent-chain` remains a long-form alias.
