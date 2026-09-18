@echo off
title Win Agent v1.2.0
cd /d %~dp0
where python >nul 2>nul
if errorlevel 1 (
    echo [!] Python not found. Install from python.org with "Add to PATH".
    pause & exit /b 1
)
python -m pip install --quiet --disable-pip-version-check -r "%~dp0requirements.txt"
echo [*] Starting agent v1.2.0 on http://127.0.0.1:8787
python "%~dp0agent.py"
pause
