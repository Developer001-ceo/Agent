$p = (Get-NetTCPConnection -LocalPort 8787 -State Listen | Select-Object -First 1).OwningProcess
if ($p) { Stop-Process -Id $p -Force }
Start-Sleep -Milliseconds 900
Move-Item -Force 'C:\agent\agent_new.py' 'C:\agent\agent.py'
Start-Process python -ArgumentList 'C:\agent\agent.py' -WorkingDirectory 'C:\agent'
Write-Output 'RESTART_SCRIPT_DONE'
