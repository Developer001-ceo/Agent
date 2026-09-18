@echo off
title Launcher
cd /d %~dp0

where python >nul 2>nul
if errorlevel 1 (
    echo [!] Python not found. Install it from python.org and CHECK "Add python.exe to PATH".
    pause
    exit /b 1
)

echo [*] First run: installing dependencies (later runs are fast)...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt

echo [*] Opening Cloudflare Tunnel window...
start "Cloudflare Tunnel" cmd /k cloudflared tunnel --url http://127.0.0.1:8787

echo [*] Opening Agent window...
start "Win Agent" cmd /k python agent.py

echo.
echo ==================================================
echo  BOTH WINDOWS ARE LAUNCHING.
echo  1. Find the line  "Visit it at:  https://....trycloudflare.com"
echo     in the "Cloudflare Tunnel" window.
echo  2. Copy that URL and paste it to the AI in chat.
echo  3. KEEP BOTH WINDOWS OPEN while testing.
echo ==================================================
pause