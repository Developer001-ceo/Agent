# Swap agent_new.py -> agent.py and restart, portably (works from ANY folder).
$dir = $PSScriptRoot
$p = (Get-NetTCPConnection -LocalPort 8787 -State Listen | Select-Object -First 1).OwningProcess
if ($p) { Stop-Process -Id $p -Force }
Start-Sleep -Milliseconds 1500
Move-Item -Force (Join-Path $dir 'agent_new.py') (Join-Path $dir 'agent.py')
Start-Process python -ArgumentList (Join-Path $dir 'agent.py') -WorkingDirectory $dir
Write-Output 'RESTART_SCRIPT_DONE'
