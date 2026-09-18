# watchdog_task.ps1 -- called every minute by the WinAgentWatchdog scheduled task.
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$listening = Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue
if (-not $listening) {
    Start-Process python -ArgumentList (Join-Path $dir 'agent.py') -WorkingDirectory $dir -WindowStyle Hidden
}
