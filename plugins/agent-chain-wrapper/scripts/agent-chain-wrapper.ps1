param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Request,

    [string]$Config,
    [ValidateSet("codex-antigravity", "codex-kimi", "kimi-codex", "kimi-antigravity", "antigravity-codex", "antigravity-kimi")]
    [string]$Profile,
    [ValidateSet("codex", "kimi", "antigravity")]
    [string]$CoderCli,
    [ValidateSet("codex", "kimi", "antigravity")]
    [string]$ReviewerCli,
    [string]$TargetFile,
    [string]$CoderModel,
    [string]$ReviewerModel,
    [string]$CoderCommand,
    [string]$ReviewerCommand,
    [string]$Workspace = ".",
    [string]$Language = "python",
    [int]$MaxIterations = 0,
    [string]$Output,
    [string]$Json,
    [string]$PluginsDir,
    [switch]$Pair,
    [switch]$DryRun
)

$Script = Join-Path $PSScriptRoot "agent_chain_wrapper.py"
$Args = @($Script, $Request, "--workspace", $Workspace, "--language", $Language)

if ($Config) { $Args += @("--config", $Config) }
if ($Profile) { $Args += @("--profile", $Profile) }
if ($CoderCli) { $Args += @("--coder-cli", $CoderCli) }
if ($ReviewerCli) { $Args += @("--reviewer-cli", $ReviewerCli) }
if ($TargetFile) { $Args += @("--target-file", $TargetFile) }
if ($CoderModel) { $Args += @("--coder-model", $CoderModel) }
if ($ReviewerModel) { $Args += @("--reviewer-model", $ReviewerModel) }
if ($CoderCommand) { $Args += @("--coder-command", $CoderCommand) }
if ($ReviewerCommand) { $Args += @("--reviewer-command", $ReviewerCommand) }
if ($MaxIterations -gt 0) { $Args += @("--max-iterations", [string]$MaxIterations) }
if ($Output) { $Args += @("--output", $Output) }
if ($Json) { $Args += @("--json", $Json) }
if ($PluginsDir) { $Args += @("--plugins-dir", $PluginsDir) }
if ($Pair) { $Args += "--pair" }
if ($DryRun) { $Args += "--dry-run" }

uv run python @Args
exit $LASTEXITCODE
