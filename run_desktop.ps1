# PostFinder PowerShell Launcher
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "             Starting PostFinder Desktop           " -ForegroundColor Yellow
Write-Host "===================================================" -ForegroundColor Cyan

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3.11 desktop.py
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python desktop.py
} else {
    Write-Error "Python was not found in PATH."
}
