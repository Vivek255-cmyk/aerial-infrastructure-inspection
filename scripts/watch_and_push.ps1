param(
    [int]$DebounceSeconds = 20
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$git = "C:\Program Files\Git\cmd\git.exe"

if (-not (Test-Path $git)) {
    $git = (Get-Command git -ErrorAction Stop).Source
}

Set-Location $repoRoot

function Get-WorkingTreeState {
    return (& $git status --porcelain)
}

Write-Host "Watching $repoRoot for changes. Press Ctrl+C to stop."
$lastState = (Get-WorkingTreeState | Out-String)
$pendingSince = $null

while ($true) {
    Start-Sleep -Seconds 2
    $currentState = (Get-WorkingTreeState | Out-String)

    if ($currentState -ne $lastState) {
        $lastState = $currentState
        $pendingSince = Get-Date
        Write-Host "Changes detected; waiting $DebounceSeconds seconds for edits to settle..."
    }

    if ($null -ne $pendingSince -and ((Get-Date) - $pendingSince).TotalSeconds -ge $DebounceSeconds) {
        if (Get-WorkingTreeState) {
            & $git add --all
            $stagedChanges = & $git diff --cached --quiet
            if ($LASTEXITCODE -ne 0) {
                $message = "Auto-update $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
                & $git commit -m $message
                & $git push
                Write-Host "Pushed changes to GitHub. Render should deploy automatically."
            }
        }
        $pendingSince = $null
        $lastState = (Get-WorkingTreeState | Out-String)
    }
}