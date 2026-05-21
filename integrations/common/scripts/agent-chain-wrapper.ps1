param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Request,

    [ValidateSet("codex-antigravity", "codex-kimi", "kimi-codex", "kimi-antigravity", "antigravity-codex", "antigravity-kimi")]
    [string]$Profile,
    [ValidateSet("codex", "kimi", "antigravity")]
    [string]$CoderCli,
    [ValidateSet("codex", "kimi", "antigravity")]
    [string]$ReviewerCli,
    [string]$TargetFile,
    [string]$Workspace = ".",
    [int]$MaxIterations = 0
)

$Args = @("run", $Request, "--workspace", $Workspace)

if ($Profile) { $Args += @("--profile", $Profile) }
if ($CoderCli) { $Args += @("--coder-cli", $CoderCli) }
if ($ReviewerCli) { $Args += @("--reviewer-cli", $ReviewerCli) }
if ($TargetFile) { $Args += @("--target-file", $TargetFile) }
if ($MaxIterations -gt 0) { $Args += @("--max-iterations", [string]$MaxIterations) }

agent-chain @Args
exit $LASTEXITCODE
