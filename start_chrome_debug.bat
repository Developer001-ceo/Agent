@echo off
REM ============================================================
REM  Starts Chrome with a CDP debug port (9222) so the agent's
REM  /web/* endpoints (Playwright bridge) can drive it.
REM  Chrome must be FULLY closed first -- this script does that.
REM ============================================================
set CHROME=
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe
if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set CHROME=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set CHROME=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe
if "%CHROME%"=="" (
    echo [!] Chrome not found in the usual locations.
    pause & exit /b 1
)
echo [*] Closing all Chrome windows (needed for the debug port)...
taskkill /IM chrome.exe /F >nul 2>nul
timeout /t 2 >nul
start "" "%CHROME%" --remote-debugging-port=9222 --restore-last-session
echo [*] Chrome restarted with CDP on port 9222.
echo     The agent can now drive it: /web/open /web/click /web/fill /web/eval ...
pause
