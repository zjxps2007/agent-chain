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
    [int]$MaxIterations = 0,
    [string]$Focus,
    [switch]$Pair,
    [switch]$Challenge,
    [switch]$Background
)

if ($Pair -or $Profile -or $CoderCli) {
    $Args = @("p", $Request, "-w", $Workspace)
} elseif ($Challenge) {
    $Args = @("challenge", $Request, "-w", $Workspace)
} else {
    $Args = @("review", $Request, "-w", $Workspace)
}

if ($Profile) { $Args += @("-P", $Profile) }
if ($CoderCli) { $Args += @("-C", $CoderCli) }
if ($ReviewerCli) { $Args += @("-R", $ReviewerCli) }
if ($TargetFile) { $Args += @("-t", $TargetFile) }
if ($Focus) { $Args += @("--focus", $Focus) }
if ($Background -and $Args[0] -ne "p") { $Args += "--background" }
if ($MaxIterations -gt 0 -and $Args[0] -eq "p") { $Args += @("-m", [string]$MaxIterations) }

agc @Args
exit $LASTEXITCODE
