# AgentChain Integration Packs

These directories are prebuilt files for registering AgentChain with external
CLI hosts.

The `agc` executable must be installed and available on `PATH`.
`agent-chain` remains available as the long-form command.

## One-command setup helper

From the AgentChain repository, run:

```powershell
agc install codex
agc install kimi
agc install antigravity
agc install all
```

Use `--copy-to DIR` to copy the prebuilt files first and then print setup steps
for the copied location.

## Codex

Register the prebuilt local marketplace:

```powershell
codex plugin marketplace add <AGENT_CHAIN_ROOT>\integrations\codex
codex plugin add agent-chain-wrapper@agent-chain-local
```

## Kimi

Launch Kimi with the prebuilt skills directory:

```powershell
kimi --skills-dir <AGENT_CHAIN_ROOT>\integrations\kimi\skills --prompt "Use agent-chain for this request."
```

## Antigravity

Use the files in `integrations/antigravity/skills` and
`integrations/antigravity/commands` with Antigravity's skill or command
registration mechanism.

If the Antigravity executable is not named `antigravity`, pass the path through
`--coder-command` or `--reviewer-command`.

Common direct runs:

```powershell
agc review "USER REQUEST" -R kimi -t src/generated.py -w . --json .agent-chain-review.json
agc review "USER REQUEST" -R codex -t src/generated.py -w . --json .agent-chain-review.json
agc p "USER REQUEST" -C codex -R kimi -t src/generated.py -w .
```

Use `agc p` only for fully delegated pairs where AgentChain should spawn both
the coder and reviewer CLIs. In the normal skill/plugin flow, the current host
CLI edits files and `agc review` calls only the reviewer.
