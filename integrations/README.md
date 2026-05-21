# AgentChain Integration Packs

These directories are prebuilt files for registering AgentChain with external
CLI hosts.

The `agent-chain` executable must be installed and available on `PATH`.

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
