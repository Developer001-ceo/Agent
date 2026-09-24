@echo off
REM ================================================================
REM  run.bat -- THE one runner for the Win Agent folder.
REM
REM  Double-click (no arguments) = everything:
REM    installs deps if missing, swaps agent_new.py if present,
REM    starts the agent AND opens the Cloudflare tunnel window.
REM
REM  All modes:
REM    run.bat start             same as double-click
REM    run.bat restart           kill agent, swap agent_new.py (compile-gated), start, SELF-VERIFY
REM    run.bat stop              kill the agent (tunnel untouched)
REM    run.bat status            is the agent answering on 127.0.0.1:8787 ?
REM    run.bat tunnel            open a fresh cloudflared window
REM    run.bat chrome            restart Chrome with CDP port 9222 (for /web/* endpoints)
REM    run.bat bar               start ONLY the thin indicator bar (top of screen)
REM    run.bat deps              (re)install requirements.txt
REM    run.bat watchdog-install  auto-restart agent within 1 min if it dies (scheduled task)
REM    run.bat watchdog-remove   remove that scheduled task
REM    run.bat watchdog-status   show the task state
REM    run.bat log               show upgrade.log (trace of the last restart/swap)
REM
REM  NOTE: never use timeout.exe here -- it fails instantly when stdin is
REM  not a real console (the remote-restart case). Use ping-based sleeps.
REM ================================================================
setlocal enableextensions
title Win Agent runner
cd /d "%~dp0"

set "MODE=%~1"
if "%MODE%"=="" set "MODE=start"

if /i "%MODE%"=="start"            goto do_start
if /i "%MODE%"=="restart"          goto do_restart
if /i "%MODE%"=="stop"             goto do_stop
if /i "%MODE%"=="status"           goto do_status
if /i "%MODE%"=="tunnel"           goto do_tunnel
if /i "%MODE%"=="chrome"           goto do_chrome
if /i "%MODE%"=="bar"              goto do_bar
if /i "%MODE%"=="deps"             goto do_deps
if /i "%MODE%"=="watchdog-install" goto do_wd_install
if /i "%MODE%"=="watchdog-remove"  goto do_wd_remove
if /i "%MODE%"=="watchdog-status"  goto do_wd_status
if /i "%MODE%"=="watchdog-check"   goto do_wd_check
if /i "%MODE%"=="log"              goto do_log

echo Usage: run.bat [start^|restart^|stop^|status^|tunnel^|chrome^|bar^|deps^|watchdog-install^|watchdog-remove^|watchdog-status^|log]
exit /b 1

REM ------------------------------------------------------------- start ----
:do_start
call :check_python || exit /b 1
call :ensure_deps
call :swap_new
call :kill_port
call :tunnel_if_needed
echo [*] Starting agent on http://127.0.0.1:8787  (KEEP THIS WINDOW OPEN)
python agent.py
echo.
echo [*] Agent stopped. You can close this window.
pause
exit /b 0

REM ----------------------------------------------------------- restart ----
:do_restart
call :trace "RESTART entered (mode=restart)"
call :check_python || (call :trace "no python - abort" & exit /b 1)
call :swap_new
call :kill_port
call :trace "old agent killed, waiting for socket release"
ping -n 4 127.0.0.1 >nul
start "Win Agent" /min cmd /k python agent.py
call :trace "start issued (minimized window), verifying..."
ping -n 6 127.0.0.1 >nul
call :port_up
if errorlevel 1 (
    ping -n 5 127.0.0.1 >nul
    call :port_up
    if errorlevel 1 (
        call :trace "RESTART FAILED - agent not listening after 2 checks. Watchdog will retry within 1 min."
        echo [!!] Agent did not come up - see upgrade.log. A minimized window may show the error.
        exit /b 1
    )
)
call :trace "RESTART OK - agent is listening on 8787"
echo [OK] agent restarted and verified listening on 8787.
exit /b 0

:do_stop
call :kill_port
echo stop> "%~dp0indicator.stop"
taskkill /F /FI "WINDOWTITLE eq WinAgent Indicator*" >nul 2>nul
echo [OK] agent stopped (tunnel untouched). Indicator bar closed too.
exit /b 0

:do_status
call :port_up
if errorlevel 1 (
    echo [!!] nothing LISTENING on 127.0.0.1:8787 -- agent is DOWN. Run: run.bat
) else (
    echo [OK] port 8787 is LISTENING.
)
curl -s -m 3 http://127.0.0.1:8787/ping 2>nul
echo.
exit /b 0

:do_tunnel
call :tunnel_if_needed
echo     Copy the https://xxxx.trycloudflare.com URL from that window and
echo     paste it to the AI in chat.
exit /b 0

:do_chrome
set "CHROME="
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set "CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe"
if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set "CHROME=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "CHROME=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
if "%CHROME%"=="" (
    echo [!] Chrome not found in the usual locations.
    exit /b 1
)
echo [*] Closing all Chrome windows (needed for the debug port)...
taskkill /IM chrome.exe /F >nul 2>nul
ping -n 3 127.0.0.1 >nul
start "" "%CHROME%" --remote-debugging-port=9222 --restore-last-session
echo [OK] Chrome restarted with CDP on port 9222. The agent can now
echo      drive it: /web/open /web/click /web/fill /web/eval /web/snapshot
exit /b 0

:do_bar
call :check_python || exit /b 1
call :start_indicator
echo [OK] indicator bar running (thin strip at the top of the screen).
echo      Close it with its X button, or stop everything with: run.bat stop
exit /b 0

:do_deps
call :check_python || exit /b 1
python -m pip install --disable-pip-version-check -r "%~dp0requirements.txt"
echo [OK] dependencies installed.
exit /b 0

REM ---------------------------------------------------------- watchdog ----
:do_wd_install
REM Task action is MINIMAL (no parens/braces/double-quotes inside):
REM a hidden powershell that relaunches THIS bat in watchdog-check mode.
REM All logic lives in :do_wd_check so it is traceable via upgrade.log.
schtasks /Create /F /TN "WinAgentWatchdog" /TR "powershell -NoProfile -WindowStyle Hidden -Command Start-Process -FilePath '%~f0' -ArgumentList 'watchdog-check' -WindowStyle Hidden" /SC MINUTE /MO 1
if errorlevel 1 (
    echo [!] Could not create the scheduled task.
    exit /b 1
)
echo [OK] watchdog installed: agent auto-restarts within 1 min if it dies.
echo      Remove anytime with: run.bat watchdog-remove
exit /b 0

:do_wd_check
call :port_up
if not errorlevel 1 exit /b 0
call :trace "WATCHDOG: port 8787 dead - starting agent"
start "Win Agent (watchdog)" /min cmd /k python agent.py
ping -n 6 127.0.0.1 >nul
call :port_up
if errorlevel 1 (
    call :trace "WATCHDOG: start attempt failed - will retry next minute"
) else (
    call :trace "WATCHDOG: agent revived OK"
)
exit /b 0

:do_wd_remove
schtasks /Delete /F /TN "WinAgentWatchdog" >nul 2>nul
if errorlevel 1 (
    echo [=] No watchdog task present.
) else (
    echo [OK] watchdog removed.
)
exit /b 0

:do_wd_status
schtasks /Query /TN "WinAgentWatchdog" >nul 2>nul
if errorlevel 1 (
    echo [=] Watchdog NOT installed. Install with: run.bat watchdog-install
) else (
    echo [OK] watchdog task is installed and scheduled every 1 minute.
)
exit /b 0

:do_log
if exist "%~dp0upgrade.log" (
    type "%~dp0upgrade.log"
) else (
    echo No upgrade.log yet -- no restart or swap has happened.
)
exit /b 0

REM ------------------------------------------------------- subroutines ----
:check_python
where python >nul 2>nul
if errorlevel 1 (
    echo [!] Python not found. Install from python.org and CHECK "Add python.exe to PATH".
    exit /b 1
)
exit /b 0

:ensure_deps
python -c "import fastapi,uvicorn,pyautogui,PIL,pywinauto" >nul 2>nul
if errorlevel 1 (
    echo [*] First run: installing dependencies -- this takes a minute...
    python -m pip install --quiet --disable-pip-version-check -r "%~dp0requirements.txt"
)
exit /b 0

:swap_new
if not exist "%~dp0agent_new.py" exit /b 0
call :trace "agent_new.py found - compile check..."
python -m py_compile "%~dp0agent_new.py" >nul 2>"%~dp0pycompile_err.txt"
if errorlevel 1 (
    call :trace "COMPILE FAILED - old agent.py kept (see pycompile_err.txt)"
    exit /b 0
)
del "%~dp0pycompile_err.txt" >nul 2>nul
move /y "%~dp0agent_new.py" "%~dp0agent.py" >nul
call :trace "swapped agent_new.py into agent.py OK"
echo [OK] agent_new.py swapped into agent.py.
exit /b 0

:kill_port
set KILLED=0
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":8787" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%p >nul 2>nul && set KILLED=1
)
if "%KILLED%"=="1" echo [*] Killed previous agent on port 8787.
exit /b 0

:port_up
netstat -aon | findstr ":8787" | findstr "LISTENING" >nul 2>nul
if errorlevel 1 exit /b 1
exit /b 0

:tunnel_if_needed
tasklist /FI "IMAGENAME eq cloudflared.exe" 2>nul | findstr /I "cloudflared" >nul
if errorlevel 1 (
    echo [*] Starting Cloudflare Tunnel window...
    start "Cloudflare Tunnel" cmd /k cloudflared tunnel --url http://127.0.0.1:8787
) else (
    echo [=] cloudflared is already running -- keeping it.
)
exit /b 0

:start_indicator
REM The agent also spawns the bar on every start; this is the manual way.
REM A second copy exits at once (port-8799 singleton inside indicator.py).
del "%~dp0indicator.stop" >nul 2>nul
where pythonw >nul 2>nul
if errorlevel 1 (
    start "WinAgent Indicator" /min cmd /c python "%~dp0indicator.py"
) else (
    start "" pythonw "%~dp0indicator.py"
)
exit /b 0

:trace
REM The watchdog task and a restart can fire in the same second; two `>>`
REM opens on the same log can collide (sharing violation) and silently drop
REM the line. Retry a few times before giving up.
set /a TRACE_TRY=0
:trace_retry
echo [%date% %time%] %~1 >> "%~dp0upgrade.log" 2>nul && goto trace_done
set /a TRACE_TRY+=1
if %TRACE_TRY% lss 4 (
    ping -n 2 127.0.0.1 >nul
    goto trace_retry
)
:trace_done
exit /b 0
