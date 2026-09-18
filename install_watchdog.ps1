# ================================================================
#  install_watchdog.ps1 -- run ONCE (normal user is fine).
#  Creates a scheduled task that checks the agent every minute and
#  restarts it if port 8787 is dead. Remove anytime with:
#    Unregister-ScheduledTask -TaskName "WinAgentWatchdog" -Confirm:$false
# ================================================================
$dir = $PSScriptRoot
$action  = New-ScheduledTaskAction -Execute 'powershell.exe' `
           -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$dir\watchdog_task.ps1`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "WinAgentWatchdog" -Action $action -Trigger $trigger -Force | Out-Null
Write-Output '[OK] Watchdog installed: agent auto-restarts within 1 min if it dies.'
Write-Output '     Remove with: Unregister-ScheduledTask -TaskName WinAgentWatchdog -Confirm:$false'
