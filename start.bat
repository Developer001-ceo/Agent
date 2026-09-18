@echo off
title Win Agent v1.1
cd /d C:\agent
where python >nul 2>nul
if errorlevel 1 (
    echo [!] Python not found. Install from python.org with "Add to PATH".
    pause & exit /b 1
)
python -m pip install --quiet --disable-pip-version-check -r C:\agent\requirements.txt
echo [*] Starting agent v1.1 on http://127.0.0.1:8787
python C:\agent\agent.py
pause
