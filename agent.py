"""
agent.py -- Remote Test Agent for Windows  (v1.6.4)
====================================================
v1.6.4 TUNNEL WATCHDOG + POLISH:
  Quick tunnels kept dying mid-session (4 deaths in one day of live
  testing). The agent now supervises cloudflared itself: a background
  thread checks every 20s; if cloudflared was up once and then died, the
  agent restarts it (hidden, output to cloudflared-watchdog.log), waits
  for the NEW trycloudflare URL, writes it to tunnel_url.txt, shows a
  small toast with the URL so the user can relay it to the AI, and logs
  every event to tunnel_watchdog.log. Restart rate is capped (max 6 per
  hour, then a 10-minute backoff) so a broken network cannot loop.
  GET /tunnel reports {running, url, restarts}. Quick tunnels still
  rotate URLs on restart -- for a PERMANENT URL see
  NAMED-TUNNEL-SETUP.md (5 minutes, free Cloudflare account).
  Also: the timeout flash now pulses 6x130ms (was 5x110) -- clearly
  visible, still inside the 1.5s grace re-wait; and the free-text entry
  got brighter text + a lighter field so typed answers read easily.

v1.6.3 iOS-STYLE MOTION FOR THE /ASK POPUP:
  The ask card now moves like an iPhone modal: rounded corners (DWM round
  on Win11 + system shadow, window-region fallback elsewhere), a spring
  entrance (fade + rise with a subtle ease-out-back overshoot), a spring
  exit (fade + drop), a breathing accent dot, color-tweened hover/press
  states on every button, a bright pick-flash on the chosen option, a
  five-pulse highlight of the recommended option when time runs out (the
  "AI is going with this one" moment), and a smoothly depleting progress
  bar (50 ms interpolation instead of 1 Hz steps). All motion is ~16 ms
  after() tweens in pure tkinter -- no new dependencies.

v1.6.2 BLOCKING-RESPONSE RACE FIX (found in live test):
  When the block window ended at the same moment the popup timed out, the
  wait timer could beat the resolve by a few ms and the blocking POST /ask
  returned still-waiting for a question resolved microseconds later. The
  caller now does a 1.5s grace re-wait, so the blocking call returns the
  FINAL result (answer / default / hint) whenever it exists at all.
  Also: stale timeout_sec or-300 fallback -> 90; asks.jsonl now records
  "proceeded_with" on timeout+default so the audit trail shows what the
  AI actually continued with.

v1.6.1 ASK UI REDESIGN + 90-SECOND AUTO-PROCEED:
  The popup is now a proper dark card: "AI PAUSED -- NEEDS YOUR ANSWER"
  header, bigger question, hover quick-reply buttons (the option matching
  "default" -- the AI's best recommendation -- is star-marked and amber),
  focused free-text entry (Enter submits, Esc cancels), and a depleting
  progress bar with an "auto-continue m:ss" clock (amber at 30s left, red
  at 10s). A plain-language line under it says exactly what happens if
  the user does not answer. Gentle re-beep + re-front every 30s so a
  buried popup is not missed.
  NEW RULE: timeout_sec DEFAULT 300 -> 90. If the user does not respond
  within 1:30 the AI PROCEEDS WITH ITS BEST RECOMMENDATION: pass it as
  "default" and it auto-applies at timeout (the response says so); if no
  default was passed the timeout response carries a hint telling the AI
  to decide immediately and never re-ask. Doctrine (Prompt.md v1.6.1):
  ALWAYS pass "default" -- it is the recommendation, shown in the popup.

v1.6.0 ASK THE HUMAN (MCP-style elicitation, zero extra infra):
  The AI can now STOP and ASK the user a question mid-task. A blocking
  HTTP call opens a popup ON THE USER'S SCREEN and the tool result is
  simply... the human's answer. The AI's tool call naturally suspends
  until the popup is answered (or times out).
  POST /ask  {"question":"Which file?","options":["a.docx","b.docx"],
              "timeout_sec":300,"default":"a.docx","wait":true}
              -> {ok, answered:true, answer:"a.docx", elapsed_sec}
              wait=true blocks up to 90s (tunnel-safe); if still pending:
                 {ok, answered:false, reason:"still-waiting", ask_id} --
                 then poll GET /ask?id=... every ~5s. wait=false returns
                 the ask_id at once (long waits / fire-and-forget).
              -> {ok, answered:false, reason:"timeout", default:"a.docx"}
              (timeout auto-applies "default" so the task never stalls)
              -> {ok, answered:false, reason:"cancelled"}  (user closed it)
  GET  /ask?id=...  -> status of that question (poll while waiting)
  GET  /ask         -> {pending:{question,options,opened_sec_ago}} or none
  The dialog: topmost tkinter window + system beep + quick-reply buttons
  for "options" + free-text entry + countdown + auto-close. The bar
  shows "Thinking: waiting for your answer..." while pending. One
  question at a time (409 + the pending question if busy). Every Q&A is
  appended to asks.jsonl (ts, question, answer, outcome).

v1.5.3 THE TURBO LOOP (one round trip per iteration, local vision):
  The v1.5.2 demo showed where the remaining seconds hide: conservative
  fixed sleeps while waiting for apps to appear, a second round trip to
  re-SEE after acting, and remote vision calls for content reads. Fix:
  MACRO STEP
    "waitfor"       -> {"action":"waitfor","title":"Notepad"} or
                        {"action":"waitfor","name":"File name"} blocks
                        SERVER-SIDE, polling every 150ms (window titles via
                        pygetwindow) / 300ms (UIA element names), and the
                        macro resumes the INSTANT the target shows up
                        (timeout_ms default 5000, cap 15000). Fixed sleep
                        steps are dead: app-launch waits become actual
                        ~800-1200ms instead of a guessed 3000ms.
  POST /macro
    screen_after     -> true: the macro RESPONSE carries a fresh window
                        overview (title+rect+pid/exe) -- ACT and re-SEE in
                        ONE round trip.
    screen_query     -> "Text Document": response carries /screen query
                        matches instead (exact rects right after the flow)
                        -- ACT + semantic VERIFY in ONE round trip.
  POST /vdescribe    -> the LOCAL vision LLM (Ollama) reads the screen and
                        answers in TEXT. Capture + LANCZOS scale + JPEG q
                        all happen ON the PC; only the answer text crosses
                        the tunnel (pixels never leave). RTX-class GPU:
                        ~0.3-1s total vs ~3-5s for a remote vision call.
                        Model: "model" field or OLLAMA_VLM env, auto-pick
                        falls back to qwen2.5vl:3b. Pull once:
                        ollama pull qwen2.5vl:3b   (or qwen2.5vl:7b).
  GET  /health       -> now reports "ollama": bool and "vlm":
                        {"default", "installed":[...]} so the AI knows
                        before the first /vdescribe.
  VERIFY DOCTRINE: verify STRUCTURE semantically first (/macro
  screen_query, /screen?query=, /ui). /vdescribe only to READ rendered
  content the tree does not expose (canvas, images, PDF text). 
  /screenshot only when a human-eye artifact is genuinely required.

v1.5.2 VISION-COST CONTROL (screenshot analysis is the #1 time sink):
  The #1 slowdown reported in live sessions is still the AI analyzing
  full-size screenshots through a vision model. This release makes the
  cheap path cheaper and the expensive path disciplined:
  GET  /screenshot  new "scale" param (0.1-1.0, LANCZOS downscale BEFORE
                     encoding) + default quality 85 -> 60. A 2560x1600
                     screen at scale=0.5 & q=60 is ~3-6x smaller: faster
                     through the tunnel, cheaper to analyze. Response
                     headers X-Screen-W / X-Screen-H / X-Screen-Scale give
                     the ACTUAL image size (map coords back by 1/scale if
                     you must -- or use /find, which matches FULL-screen).
  POST /macro        new "screenshot_scale" param (default 1.0); default
                     screenshot_q 80 -> 60 for the end-of-flow capture.
  The doctrine (enforced by Prompt.md v1.5.2): plan and act semantically
  (/screen, /ui, /uiclick, /macro); screenshots only VERIFY milestones.

v1.5.0 SPEED REDESIGN ("semantic-first" control -- 10-20x faster, fewer errors):
  ROOT CAUSE of the 1-2 minute pauses in v1.4.0 sessions: the AI looked at
  the screen with screenshots + external vision-model analysis before every
  click (30-120s per action) and the guessed coordinates caused retries.
  THE FIX: the UIA semantic tree IS the eyes -- exact names + rects, no vision
  in the control loop. Screenshots (jpeg q=60) only to VERIFY milestones.
  GET  /screen          -> whole semantic desktop in ONE call:
                           overview mode: every top-level window + rect (+ a
                           shallow element list per window)
                           query mode: /screen?query=Text+Document finds that
                           element across ALL windows -- including open context
                           menus / submenus, which have no title -- and returns
                           its exact rect. First matching window wins.
  GET  /ui?query=       -> server-side name filter: return ONLY the matching
                           elements (tiny response, one round trip)
  POST /uiclick         -> title now OPTIONAL: omit it to search every window
                           (that is how you click context-menu items); new
                           button / double / wait_ms (retries until the element
                           appears -- menus animate in); rect-center pyautogui
                           click as fallback when click_input fails.
  POST /uiset           -> title optional too.
  /macro                -> new step actions "uiclick" and "uiset" so a WHOLE
                           flow (right-click -> New -> Text Document -> type)
                           runs in ONE server-side call, zero round trips.
  GZip middleware       -> JSON responses compressed (5-10x smaller through
                           the tunnel: /ui, /screen, /windows, ...)

v1.3.1 fixes (all three user-reported):
  TIMER FREEZES WHEN THE AI DISCONNECTS
    GET /indicator now returns task.elapsed = ACTIVE seconds on the task
    (paused time excluded). While the AI is away the clock stops at the
    disconnect moment; if the AI comes back the SAME task resumes where it
    froze. POST /task done/fail record ended = now - paused_total, so the
    final duration is active-trying time only.
  THE BAR NEVER APPEARS IN SCREENSHOTS (the AI needs a clean view)
    /screenshot and /macro captures first ask the bar to vacate: it
    capture-cloaks itself on Windows 10 2004+ (SetWindowDisplayAffinity
    WDA_EXCLUDEFROMCAPTURE -- visible on screen, absent from captures) and
    falls back to hide -> capture -> show via the bar's control server
    (127.0.0.1:8799 /hide /show /status). Bar trouble can NEVER fail a
    capture; a hidden bar auto-reappears after 3s as a safety net.
  CLEARER STATUS TEXTS
    the bar now speaks plain human sentences ("AI is working",
    "AI disconnected — task paused", "Finished ... took 01:24",
    "Agent offline — run run.bat to bring it back"); stale indicator.stop
    sentinels are deleted at bar startup so a fresh bar never insta-exits.

v1.3 additions (INDICATOR BAR):
  indicator.py   -> thin always-on-top bar at the top of the screen:
                    [light] AI is working | Opening Notepad | 00:42  (live, 4 fps)
                    green light while AI requests flow, red when the AI went
                    idle > AGENT_IDLE_RED_SECONDS or the agent is down.
  GET  /indicator -> live JSON state for the bar (auth: Bearer TOKEN or the
                     per-boot secret in indicator.key -- never counts as AI activity)
  POST /task      -> the AI announces what it is doing:
                     {"task":"opening Notepad","state":"start"} then
                     {"state":"done"} or {"state":"fail"}. The bar's task
                     timer resets whenever the task label changes.
  the agent spawns the bar automatically on start (Windows only); single
  instance is enforced by the bar itself (port 8799). run.bat bar restarts it,
  run.bat stop also closes it (indicator.stop sentinel).

v1.2 additions:
  POST /uiset        -> set text on a UIA control by name (desktop forms)
  POST /clipboard    -> get/set clipboard; /type auto-pastes unicode
  GET  /windows      -> now includes pid + exe per window
  GET  /proc         -> process list;  POST /kill -> kill by pid/name
  POST /awake        -> keep PC awake during long test runs
  POST /job/start    -> background jobs with log files (builds/installs)
  POST /job/status   -> running/exit state + output tail; /job/list /job/stop
  GET  /devscreen    -> ANDROID screen as PNG (adb exec-out screencap)
  POST /uiclick_android -> tap node by text / resource-id / content-desc
  POST /logcat       -> logcat tail or clear
  POST /adbapp       -> install/uninstall/launch/stop/clear/packages/devices
  POST /web/*        -> drive real Chrome via CDP with Playwright
  run.bat is the SINGLE runner in this folder: start/restart/stop/status,
  tunnel, chrome (CDP), watchdog (scheduled task) -- see README.md

v1.1: /ui /uiclick /uidump /macro /upload /download
      /uidump PULLS the xml (v1.1.1 fix: `adb shell cat` truncated at 20KB)
v1.0: /ping /health /screenshot /windows /click /drag /move /scroll
      /type /key /window /run /adb
"""

import base64
import csv
import ctypes
import io
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import weakref
import xml.etree.ElementTree as ET
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from PIL import Image

import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

# ------------------------------------------------------------------------------
TOKEN = "Czj3u9HadjO-PkEMw9X9VR_S02v_ZXKMD9CcFT1WADs"
HOST = "127.0.0.1"          # localhost only -- never change to 0.0.0.0
PORT = 8787
VERSION = "1.6.4"
AGENT_ROOT = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.path.join(AGENT_ROOT, "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

MACRO_TIME_CAP = 30.0       # seconds per /macro call (tunnel friendly)
MACRO_SLEEP_CAP = 10.0      # max seconds per sleep step
MACRO_RUN_CAP = 25          # max timeout per run step inside a macro
MACRO_WAITFOR_CAP_MS = 15000  # v1.5.3: max wait per waitfor step
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_VLM = os.environ.get("OLLAMA_VLM", "")  # v1.5.3: force a vision model

app = FastAPI(title="win-agent", docs_url=None, redoc_url=None, openapi_url=None)
# v1.5.0: compress JSON responses (5-10x smaller through the tunnel: /ui,
# /screen, /windows ...). Only kicks in when the client sends Accept-Encoding.
app.add_middleware(GZipMiddleware, minimum_size=1024)

_input_lock = threading.Lock()      # serialize mouse/keyboard/UI actions
JOBS = {}                           # id -> job dict
JOB_SEQ = [0]
JOB_LOCK = threading.Lock()
AWAKE_FLAG = {"on": False}
_PID_CACHE = {}
_WEB = {"pw": None, "ctx": None, "console": [], "errors": []}
_WEB_LOCK = threading.Lock()
_WEB_HOOKED = weakref.WeakSet()


# --------------------------------------------- v1.3: indicator bar plumbing ----
# The indicator bar (indicator.py) is a thin always-on-top strip at the top of
# the screen: [light] [AI CONTROLLING] [TASK: ...] [00:42].
#   light  : GREEN while authorized AI requests are flowing (or one is
#            executing right now), RED once the AI has been idle longer than
#            AI_IDLE_RED_SECONDS -- or the agent itself is down.
#   task   : what the AI announced via POST /task (fallback: last API action).
#   timer  : seconds on the CURRENT task; resets when the label changes.
INDICATOR_KEY_FILE = os.path.join(AGENT_ROOT, "indicator.key")    # per-boot bar secret
INDICATOR_STOP_FILE = os.path.join(AGENT_ROOT, "indicator.stop")  # stop sentinel
INDICATOR_PORT = int(os.environ.get("INDICATOR_PORT", "8799"))    # bar singleton port
AI_IDLE_RED_SECONDS = float(os.environ.get("AGENT_IDLE_RED_SECONDS", "45") or 45)

_TRACK = {"last_seen": None, "last_what": None, "in_flight": 0}
_TRACK_LOCK = threading.Lock()
# v1.3.1 internal freeze accounting (never part of the public contract):
#   paused_total -- seconds accumulated while the AI was disconnected
#   frozen_at    -- wall-clock moment the current freeze began (None = live)
# v1.4.0: "reason" -- optional plain-words note the AI attaches to a task
# state (why it is thinking / why it failed). Rendered on the indicator bar.
_TASK = {"label": None, "state": "idle", "started": None, "ended": None,
         "paused_total": 0.0, "frozen_at": None, "reason": None}

# states where the AI is actively on the task (timer runs / freezes apply)
_ACTIVE_STATES = ("working", "thinking")
_TASK_LOCK = threading.Lock()
_BAR_SECRET = secrets.token_hex(16)   # fresh every agent start; bar re-reads it


def _indicator_write_key() -> None:
    try:
        with open(INDICATOR_KEY_FILE, "w", encoding="utf-8") as f:
            f.write(_BAR_SECRET)
    except OSError:
        pass


try:
    if os.path.exists(INDICATOR_STOP_FILE):
        os.remove(INDICATOR_STOP_FILE)    # a fresh agent start voids an old stop
except OSError:
    pass
_indicator_write_key()


@app.middleware("http")
async def _ai_activity_tracker(request: Request, call_next):
    """Counts authorized AI requests so the bar can tell connected from idle.
    /ping and /indicator never count -- neither means the AI is controlling.
    last_seen is stamped when a request COMPLETES, so a long /macro or /run
    stays green afterwards instead of instantly flipping red."""
    path = request.url.path
    if path not in ("/ping", "/indicator"):
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer ") and auth[7:] == TOKEN:
            with _TRACK_LOCK:
                _TRACK["in_flight"] += 1
                _TRACK["last_what"] = "%s %s" % (request.method, path)
            try:
                return await call_next(request)
            finally:
                with _TRACK_LOCK:
                    _TRACK["in_flight"] -= 1
                    _TRACK["last_seen"] = time.time()
    return await call_next(request)


def _indicator_auth(request: Request) -> None:
    """/indicator accepts the real Bearer TOKEN or the bar's per-boot secret
    from indicator.key (so the local bar can poll, but a random tunnel
    visitor who only knows the URL gets nothing)."""
    auth = request.headers.get("authorization", "")
    tok = auth[7:] if auth.startswith("Bearer ") else ""
    if tok and (tok == TOKEN or tok == _BAR_SECRET):
        return
    raise HTTPException(status_code=401, detail="unauthorized")


def _port_listening(port: int) -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=0.3)
        s.close()
        return True
    except Exception:
        return False


# --------------------------------------- v1.3.1: bar-safe pixel captures ----
# The bar paints itself always-on-top at the very top of the screen -- exactly
# where the AI looks. Before ANY pixel capture we ask the bar (control server
# on 127.0.0.1:8799, added in indicator.py v1.3.1) to get out of the way:
# capture-cloaked bars are already invisible to captures (no-op), everything
# else hides for the duration of the shot. Bar problems must NEVER make a
# screenshot fail, so every error is swallowed.

def _bar_call(path: str):
    """One tiny HTTP call to the bar's control server. Returns the parsed
    JSON dict, or None when there is no bar / it does not answer / anything
    at all goes wrong."""
    try:
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (INDICATOR_PORT, path),
                                     method="POST")
        with urllib.request.urlopen(req, timeout=0.5) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _bar_hide():
    """Ask the bar to vacate the screen for a capture. Reply (or None):
      {"cloaked": true}            -> nothing to do, it never shows in shots
      {"hidden": true}             -> it is hiding; caller MUST _bar_show()
      None / unreachable           -> no bar, capture straight away
    """
    return _bar_call("/hide")


def _bar_show():
    """Let the bar come back after _bar_hide(). Errors always ignored."""
    return _bar_call("/show")


def _capture_screen():
    """pyautogui.screenshot with the indicator bar removed from the frame.
    If the bar actually hides we give it 0.15s to withdraw first; /show is
    sent in a finally, and a hidden bar also auto-reappears after 3s on its
    own, so a crash between hide and show can never leave it invisible."""
    hid = _bar_hide()
    try:
        if isinstance(hid, dict) and hid.get("hidden"):
            time.sleep(0.15)          # let the withdraw actually happen
        return pyautogui.screenshot()
    finally:
        _bar_show()


def _task_freeze_update(connected: bool, last_seen, now: float) -> None:
    """v1.3.1: advance the task FREEZE accounting. _TASK_LOCK must be held.
      AI went away while working -> frozen_at = the moment it went away
        (last completed request + idle threshold; task start if the AI
        never showed up at all)
      AI came back while frozen  -> fold the pause into paused_total so the
        timer resumes exactly where it froze
    v1.4.0: "thinking" counts as an active state too -- the AI is still on
    the task, it is just figuring out what to do next."""
    if _TASK["state"] not in _ACTIVE_STATES:
        return
    if connected:
        if _TASK["frozen_at"] is not None:
            _TASK["paused_total"] += max(0.0, now - _TASK["frozen_at"])
            _TASK["frozen_at"] = None
    else:
        if _TASK["frozen_at"] is None:
            if last_seen is not None:
                _TASK["frozen_at"] = last_seen + AI_IDLE_RED_SECONDS
            else:
                _TASK["frozen_at"] = _TASK["started"]


def _task_elapsed(connected: bool, now: float):
    """v1.3.1: ACTIVE seconds on the task (paused time excluded), or the
    final duration once done/fail. None when there is nothing to measure.
    _TASK_LOCK must be held; call _task_freeze_update first."""
    started = _TASK["started"]
    if _TASK["state"] not in _ACTIVE_STATES:
        if isinstance(started, (int, float)) and isinstance(_TASK["ended"], (int, float)):
            return max(0.0, _TASK["ended"] - started)
        return None
    if not isinstance(started, (int, float)):
        return None
    if connected:
        return max(0.0, now - started - _TASK["paused_total"])
    if _TASK["frozen_at"] is None:
        return 0.0        # disconnected, not yet frozen by an /indicator poll
    return max(0.0, _TASK["frozen_at"] - started - _TASK["paused_total"])


def _finish_task(state: str, label, now: float) -> bool:
    """Mark the current task done/fail. Assumes _TASK_LOCK is held.
    v1.3.1: the recorded duration EXCLUDES paused time -- an open freeze is
    folded into paused_total first, then ended = now - paused_total, so
    ended - started is pure active-trying time.
    v1.4.0: finishing from "thinking" behaves exactly like from "working"."""
    if _TASK["state"] in _ACTIVE_STATES:
        if label:
            _TASK["label"] = label          # finished a task it forgot to announce
        if _TASK["frozen_at"] is not None:  # still frozen -> close the pause now
            _TASK["paused_total"] += max(0.0, now - _TASK["frozen_at"])
            _TASK["frozen_at"] = None
        _TASK["state"] = state
        _TASK["ended"] = now - _TASK["paused_total"]
        _TASK["paused_total"] = 0.0
        _TASK["frozen_at"] = None
        return True
    if label:                               # done for a never-announced task
        _TASK["label"] = label              # duration unknown -> show 0, do not
        _TASK["state"] = state              # inherit the previous task's timer
        _TASK["started"] = now
        _TASK["ended"] = now
        _TASK["paused_total"] = 0.0
        _TASK["frozen_at"] = None
        return True
    return False


def guard(request: Request) -> None:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or auth[7:] != TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


def in_agent_root(path: str) -> str:
    full = os.path.normpath(os.path.join(AGENT_ROOT, path))
    low = full.lower()
    if not (low == AGENT_ROOT.lower() or low.startswith(AGENT_ROOT.lower() + os.sep)):
        raise HTTPException(status_code=400, detail="path must stay inside the agent folder")
    return full


# ----------------------------------------------------------------- models ----
class ClickIn(BaseModel):
    x: int
    y: int
    button: str = "left"
    clicks: int = 1


class DragIn(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    duration: float = 0.5


class MoveIn(BaseModel):
    x: int
    y: int
    duration: float = 0.2


class ScrollIn(BaseModel):
    dx: int = 0
    dy: int = 0


class TypeIn(BaseModel):
    text: str
    interval: float = 0.01
    paste: bool = False


class KeyIn(BaseModel):
    keys: List[str]
    combo: bool = False


class WindowIn(BaseModel):
    title: str
    action: str = "activate"


class RunIn(BaseModel):
    command: str
    shell: str = "powershell"
    timeout: int = 120


class AdbIn(BaseModel):
    args: List[str]
    timeout: int = 120


class UiClickIn(BaseModel):
    title: Optional[str] = None        # v1.5.0: None/omitted = search ALL windows
    name: str
    control_type: Optional[str] = None
    index: int = 0
    button: str = "left"               # v1.5.0: left|right|middle
    double: bool = False               # v1.5.0: double-click
    wait_ms: int = 0                   # v1.5.0: retry until the element appears


class UiSetIn(BaseModel):
    title: Optional[str] = None        # v1.5.0: None/omitted = search ALL windows
    name: str
    value: str
    control_type: Optional[str] = None
    index: int = 0
    wait_ms: int = 0                   # v1.5.0: retry until the element appears


class UiDumpIn(BaseModel):
    serial: Optional[str] = None


class ClipIn(BaseModel):
    action: str = "get"          # get | set
    text: str = ""


class KillIn(BaseModel):
    pid: Optional[int] = None
    name: Optional[str] = None
    force: bool = True


class AwakeIn(BaseModel):
    on: bool = True


class JobIn(BaseModel):
    command: str
    shell: str = "powershell"
    name: Optional[str] = None


class JobIdIn(BaseModel):
    id: str


class UiClickAIn(BaseModel):
    text: Optional[str] = None
    res: Optional[str] = None    # resource-id
    desc: Optional[str] = None   # content-desc
    index: int = 0
    serial: Optional[str] = None
    long_press: bool = False


class LogcatIn(BaseModel):
    lines: int = 200
    filter: Optional[str] = None  # e.g. "*:E" or "MyApp:D"
    clear: bool = False
    serial: Optional[str] = None


class AppIn(BaseModel):
    action: str                  # install|uninstall|launch|stop|clear|packages|devices
    package: Optional[str] = None
    apk: Optional[str] = None    # path INSIDE the agent folder
    serial: Optional[str] = None


class WebOpenIn(BaseModel):
    url: str
    new_tab: bool = False
    timeout: int = 30


class WebSelIn(BaseModel):
    selector: str
    timeout: int = 10


class WebFillIn(BaseModel):
    selector: str
    text: str
    timeout: int = 10


class WebEvalIn(BaseModel):
    expression: str


class MacroIn(BaseModel):
    steps: List[dict]
    stop_on_error: bool = True
    capture: bool = True
    screenshot_q: int = 60          # v1.5.2: 80 -> 60 (verification quality)
    screenshot_scale: float = 1.0   # v1.5.2: <1.0 downscales the capture
    screen_after: bool = False      # v1.5.3: window overview in the response
    screen_query: str = ""         # v1.5.3: query-mode matches in the response


class VDescribeIn(BaseModel):
    """v1.5.3: LOCAL vision LLM (Ollama) reads the screen, answers in text."""
    prompt: str = "Describe the screen briefly. Be concise."
    model: str = ""               # "" -> OLLAMA_VLM env > installed vlm > qwen2.5vl:3b
    q: int = 60
    scale: float = 0.5
    region: Optional[str] = None   # x,y,w,h -- read just that part
    max_tokens: int = 400
    timeout: int = 45


class UploadIn(BaseModel):
    path: str
    data: str
    append: bool = False


class DownloadIn(BaseModel):
    path: str


class TaskIn(BaseModel):
    task: Optional[str] = None          # label; required for state=start
    state: str = "start"                # start | thinking | done | fail | clear
    reason: Optional[str] = None        # v1.4.0: why thinking / why it failed


class AskIn(BaseModel):
    question: Optional[str] = None      # REQUIRED: short, human-readable
    options: Optional[List[str]] = None # quick-reply buttons (max 6)
    timeout_sec: int = 90               # popup lifetime (10-1800). v1.6.1:
                                        # 1:30 default -- no answer -> the
                                        # AI proceeds with "default"
    default: Optional[str] = None       # best recommendation; auto-applies
                                        # at timeout so the task never stalls
    wait: bool = True                   # false = return ask_id at once


# ------------------------------------------------------------- adb helper ----
def adb_path() -> Optional[str]:
    p = os.environ.get("ADB_PATH", "")
    if p and os.path.isfile(p):
        return p
    found = shutil.which("adb")
    if found:
        return found
    candidates = [
        os.path.join(AGENT_ROOT, "platform-tools", "adb.exe"),
        os.path.join(AGENT_ROOT, "adb.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _adb_pre(serial: Optional[str]):
    path = adb_path()
    if not path:
        return None, None
    return [path] + (["-s", serial] if serial else []), path


def run_process(cmd: List[str], timeout: int) -> dict:
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"exit": None, "timeout": True, "stdout": "", "stderr": "timed out after %ss" % timeout}
    return {
        "exit": p.returncode,
        "stdout": p.stdout.decode("utf-8", "replace")[-20000:],
        "stderr": p.stderr.decode("utf-8", "replace")[-20000:],
    }


def run_process_bytes(cmd: List[str], timeout: int):
    """Raw-byte variant (for screencap PNGs). Returns (returncode|None, stdout_bytes)."""
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, b""
    return p.returncode, p.stdout


# --------------------------------------------------------- clipboard (win) ----
def _clip_api():
    """ctypes with CORRECT argtypes/restypes -- without these, 64-bit HANDLEs
    get truncated to 32-bit ints and GlobalLock/SetClipboardData silently fail."""
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    u32.OpenClipboard.argtypes = [ctypes.c_void_p]
    u32.OpenClipboard.restype = ctypes.c_bool
    u32.EmptyClipboard.restype = ctypes.c_bool
    u32.GetClipboardData.argtypes = [ctypes.c_uint]
    u32.GetClipboardData.restype = ctypes.c_void_p
    u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    u32.SetClipboardData.restype = ctypes.c_void_p
    k32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.restype = ctypes.c_bool
    return u32, k32


def _clipboard_get() -> str:
    u32, k32 = _clip_api()
    CF_UNICODETEXT = 13
    for _ in range(6):
        if u32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("could not open clipboard")
    try:
        h = u32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = k32.GlobalLock(h)
        if not p:
            return ""
        try:
            return ctypes.wstring_at(p)
        finally:
            k32.GlobalUnlock(h)
    finally:
        u32.CloseClipboard()


def _clipboard_set(text: str) -> None:
    u32, k32 = _clip_api()
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    for _ in range(6):
        if u32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("could not open clipboard")
    try:
        u32.EmptyClipboard()
        buf = ctypes.create_unicode_buffer(text)
        h = k32.GlobalAlloc(GMEM_MOVEABLE, ctypes.sizeof(buf))
        if not h:
            raise RuntimeError("GlobalAlloc failed")
        p = k32.GlobalLock(h)
        if not p:
            raise RuntimeError("GlobalLock failed")
        try:
            ctypes.memmove(p, buf, ctypes.sizeof(buf))
        finally:
            k32.GlobalUnlock(h)
        if not u32.SetClipboardData(CF_UNICODETEXT, h):
            raise RuntimeError("SetClipboardData failed")
    finally:
        u32.CloseClipboard()


# ------------------------------------------------------------- proc / awake ----
def _pid_exe(pid) -> str:
    if not pid:
        return "?"
    try:
        pid = int(pid)
    except Exception:
        return "?"
    if pid in _PID_CACHE:
        return _PID_CACHE[pid]
    exe = "?"
    try:
        out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/FO", "CSV", "/NH"],
                             capture_output=True, timeout=10).stdout.decode("utf-8", "replace")
        line = out.strip().splitlines()[0] if out.strip() else ""
        row = next(csv.reader([line])) if line else []
        if row and row[0].upper() != "INFO":
            exe = row[0]
    except Exception:
        pass
    _PID_CACHE[pid] = exe
    return exe


def _awake_loop():
    prev = False
    while True:
        on = AWAKE_FLAG["on"]
        try:
            if on:
                # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000003)
            elif prev:
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)  # reset
        except Exception:
            pass
        prev = on
        time.sleep(15)


threading.Thread(target=_awake_loop, daemon=True).start()

# ------------------------------------------------- pywinauto (UIA) helpers ----
def _uia_desktop():
    try:
        from pywinauto import Desktop
    except ImportError:
        raise HTTPException(
            status_code=400,
            detail="pywinauto not installed. Run: pip install pywinauto",
        )
    return Desktop(backend="uia")


def _find_window_uia(title: str):
    for w in _uia_desktop().windows():
        try:
            t = w.window_text() or ""
        except Exception:
            continue
        if title.lower() in t.lower():
            return w
    return None


def _collect_wrappers(win, max_depth: int, max_nodes: int) -> List:
    out = []

    def walk(ctrl, depth):
        if len(out) >= max_nodes or depth > max_depth:
            return
        out.append(ctrl)
        try:
            kids = ctrl.children()
        except Exception:
            return
        for k in kids:
            if len(out) >= max_nodes:
                return
            walk(k, depth + 1)

    walk(win, 0)
    return out


def _wrap_info(ctrl) -> dict:
    try:
        info = ctrl.element_info
        r = info.rectangle
        return {
            "type": info.control_type,
            "name": (info.name or "")[:120],
            "auto_id": getattr(info, "automation_id", "") or "",
            "rect": [r.left, r.top, r.right, r.bottom],
            "center": [(r.left + r.right) // 2, (r.top + r.bottom) // 2],
            "enabled": bool(info.enabled),
        }
    except Exception:
        return {"type": "?", "name": "<unreadable>", "rect": None, "center": None, "enabled": False}


def _uia_match(win, name: str, control_type: Optional[str] = None,
               max_depth: int = 12, max_nodes: int = 800):
    wrappers = _collect_wrappers(win, max_depth, max_nodes)
    matches = []
    for ctrl in wrappers[1:]:
        info = _wrap_info(ctrl)
        if name.lower() in (info.get("name") or "").lower():
            if control_type and (info.get("type") or "") != control_type:
                continue
            matches.append((ctrl, info))
    return matches


def _find_in_window(title, name, control_type=None, timeout_ms=0):
    """v1.5.0: search ONE titled window for an element, retrying until
    timeout_ms (windows and elements can appear a beat late). Returns
    (window_title, matches) -- matches empty when not found."""
    deadline = time.time() + max(0.0, min(int(timeout_ms), 15000)) / 1000.0
    while True:
        win = _find_window_uia(title)
        matches, wt = [], ""
        if win is not None:
            try:
                wt = win.window_text() or ""
            except Exception:
                wt = ""
            try:
                matches = _uia_match(win, name, control_type)
            except Exception:
                matches = []
        if matches or time.time() >= deadline:
            return wt, matches
        time.sleep(0.12)


def _uia_find_any(name, control_type=None, timeout_ms=0):
    """v1.5.0: search EVERY top-level window (z-order: menus are on top, so
    they are hit first) for an element by name; retry until timeout_ms.
    This is how you click items of open context menus / submenus -- they
    live in untitled windows. Returns (window_title, matches)."""
    deadline = time.time() + max(0.0, min(int(timeout_ms), 15000)) / 1000.0
    while True:
        try:
            wins = _uia_desktop().windows()
        except HTTPException:
            raise
        except Exception:
            wins = []
        for w in wins:
            try:
                matches = _uia_match(w, name, control_type,
                                     max_depth=10, max_nodes=400)
            except Exception:
                continue
            if matches:
                try:
                    wt = w.window_text() or ""
                except Exception:
                    wt = ""
                return wt, matches
        if time.time() >= deadline:
            return "", []
        time.sleep(0.12)


def _uia_click_it(ctrl, info, button="left", double=False):
    """v1.5.0: real click on a UIA wrapper with a rect-center pyautogui
    fallback. Returns the method used. Raises when both paths fail."""
    try:
        ctrl.click_input(button=button, double=double)
        return "click_input"
    except Exception:
        c = info.get("center")
        if not c:
            raise
        pyautogui.click(x=c[0], y=c[1], clicks=2 if double else 1, button=button)
        return "rect-center-fallback"


def _uia_readback(ctrl):
    """v1.5.1: best-effort read of an element's current text (Value pattern
    first, then window text). None when the control cannot be read."""
    for how in ("get_value", "window_text"):
        try:
            v = getattr(ctrl, how)()
            if isinstance(v, str) and v:
                return v
        except Exception:
            pass
    return None


def _uia_paste_into(ctrl, info, value):
    """v1.5.1: bulletproof paste for edit controls that reject set_edit_text
    (the Win11 Store Notepad 'Text Editor' does). Clicks the element's rect
    center for a REAL focus, pastes, verifies via readback when possible and
    retries once. Returns the method string; raises when a readable readback
    proves the paste did not land."""
    probe = (value.splitlines() or [value])[0][:60] if value else ""
    last_rb = None
    for _attempt in (1, 2):
        try:
            c = info.get("center")
            if c:
                pyautogui.click(x=c[0], y=c[1])
            else:
                ctrl.set_focus()
        except Exception:
            ctrl.set_focus()
        time.sleep(0.15)
        _clipboard_set(value)
        pyautogui.hotkey("ctrl", "v", interval=0.05)
        time.sleep(0.12)
        rb = _uia_readback(ctrl)
        if rb is None:
            return "click+paste (unverified)"
        last_rb = rb
        if not probe or probe in rb:
            return "click+paste+verified"
    raise RuntimeError("paste verification failed: readback %r does not "
                       "contain %r" % (last_rb[:80], probe))


# ------------------------------------------------- android ui dump helper ----
def _aidump_nodes(serial: Optional[str]):
    """uiautomator dump -> (nodes, error_or_None). Pulls the XML file locally
    (v1.1.1 fix) so large hierarchies are never truncated."""
    pre, path = _adb_pre(serial)
    if not path:
        return [], {"ok": False, "error": "adb not found"}
    dump = run_process(pre + ["shell", "uiautomator", "dump", "/sdcard/aidump.xml"], 30)
    if dump["exit"] != 0:
        return [], {"ok": False, "error": "dump failed (is a device connected + authorized?)",
                    "stderr": dump["stderr"][:300]}
    local_xml = os.path.join(AGENT_ROOT, "aidump.xml")
    pull = run_process(pre + ["pull", "/sdcard/aidump.xml", local_xml], 30)
    run_process(pre + ["shell", "rm", "/sdcard/aidump.xml"], 10)
    if pull["exit"] != 0 or not os.path.isfile(local_xml):
        return [], {"ok": False, "error": "pull failed", "stderr": pull["stderr"][:300]}
    try:
        with open(local_xml, "r", encoding="utf-8", errors="replace") as f:
            xml_text = f.read()
        root = ET.fromstring(xml_text)
    except Exception as e:
        return [], {"ok": False, "error": "xml parse failed: %s" % e}
    finally:
        try:
            os.remove(local_xml)
        except OSError:
            pass
    nodes = []
    for node in root.iter("node"):
        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
        if not m:
            continue
        x1, y1, x2, y2 = [int(v) for v in m.groups()]
        nodes.append({
            "text": node.get("text") or "",
            "desc": node.get("content-desc") or "",
            "res": node.get("resource-id") or "",
            "class": node.get("class") or "",
            "clickable": node.get("clickable") == "true",
            "bounds": [x1, y1, x2, y2],
            "center": [(x1 + x2) // 2, (y1 + y2) // 2],
        })
        if len(nodes) >= 400:
            break
    return nodes, None


# ------------------------------------------------------- macro dispatcher ----
def _s_click(s):
    pyautogui.click(x=int(s["x"]), y=int(s["y"]),
                    clicks=int(s.get("clicks", 1)), button=s.get("button", "left"))
    return None


def _s_move(s):
    pyautogui.moveTo(int(s["x"]), int(s["y"]), duration=float(s.get("duration", 0.2)))
    return None


def _s_drag(s):
    pyautogui.moveTo(int(s["x1"]), int(s["y1"]))
    pyautogui.dragTo(int(s["x2"]), int(s["y2"]), duration=max(0.05, float(s.get("duration", 0.5))))
    return None


def _s_scroll(s):
    if s.get("dy"):
        pyautogui.scroll(int(s["dy"]))
    if s.get("dx"):
        pyautogui.hscroll(int(s["dx"]))
    return None


def _s_type(s):
    if s.get("paste") or any(ord(c) > 127 for c in s.get("text", "")):
        _clipboard_set(s["text"])
        pyautogui.hotkey("ctrl", "v")
        return {"method": "clipboard-paste"}
    pyautogui.write(s["text"], interval=float(s.get("interval", 0.01)))
    return {"method": "write"}


def _s_key(s):
    keys = s["keys"]
    if s.get("combo"):
        # v1.5.1: interval=0.05 -- Store apps (Win11 Notepad etc.) drop
        # ultra-fast synthetic combos; 50ms between keys is still instant
        # for a human observer but registers reliably everywhere.
        pyautogui.hotkey(*keys, interval=0.05)
    else:
        for k in keys:
            pyautogui.press(k)
    return None


def _s_sleep(s):
    time.sleep(min(float(s.get("ms", 500)), MACRO_SLEEP_CAP * 1000) / 1000.0)
    return None


def _s_window(s):
    import pygetwindow as gw
    matches = [w for w in gw.getAllWindows() if s["title"].lower() in (w.title or "").lower()]
    if not matches:
        raise RuntimeError("no window matching %r" % s["title"])
    w = matches[0]
    op = s.get("op", "activate")
    if op == "activate":
        if w.isMinimized:
            w.restore()
        w.activate()
    elif op == "minimize":
        w.minimize()
    elif op == "close":
        w.close()
    else:
        raise RuntimeError("op must be activate|minimize|close")
    return {"title": w.title}


def _s_waitfor(s):
    """v1.5.3: block server-side until a window title (pygetwindow, fast)
    or a UIA element name appears, then return the instant it does.
    Replaces conservative fixed sleeps -- the macro resumes the moment
    the app is actually there. Raises on timeout so stop_on_error sees
    a failed launch cleanly."""
    title = s.get("title")
    name = s.get("name")
    if not title and not name:
        raise RuntimeError("waitfor: needs title= and/or name=")
    timeout_ms = min(int(s.get("timeout_ms", 5000)), MACRO_WAITFOR_CAP_MS)
    poll_ms = max(50, int(s.get("poll_ms", 150 if title else 300)))
    t0 = time.time()
    while (time.time() - t0) * 1000 < timeout_ms:
        if title:
            import pygetwindow as gw
            if any(title.lower() in (w.title or "").lower()
                   for w in gw.getAllWindows()):
                return {"waited_ms": round((time.time() - t0) * 1000),
                        "found": "title:%s" % title}
        if name:
            _, matches = _uia_find_any(name, None, 0)
            if matches:
                return {"waited_ms": round((time.time() - t0) * 1000),
                        "found": "name:%s" % name}
        time.sleep(poll_ms / 1000.0)
    raise RuntimeError("waitfor: timed out after %dms waiting for %s"
                       % (timeout_ms, title or name))


def _s_run(s):
    shell = s.get("shell", "powershell")
    cmd = s["command"]
    timeout = min(int(s.get("timeout", 25)), MACRO_RUN_CAP)
    if shell == "cmd":
        argv = ["cmd", "/c", cmd]
    else:
        argv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd]
    return run_process(argv, timeout)


def _s_adb(s):
    path = adb_path()
    if not path:
        return {"ok": False, "error": "adb not found"}
    return run_process([path] + s["args"], min(int(s.get("timeout", 25)), MACRO_RUN_CAP))


def _s_uiclick(s):
    """v1.5.0: semantic click inside a macro (see /uiclick). Whole flows --
    right-click, menu, submenu, rename, save -- run in ONE server-side call
    with zero tunnel round trips between the clicks."""
    name = s["name"]
    title = s.get("title")
    control_type = s.get("control_type")
    index = int(s.get("index", 0))
    button = s.get("button", "left")
    double = bool(s.get("double", False))
    wait_ms = int(s.get("wait_ms", 0))
    if button not in ("left", "right", "middle"):
        raise RuntimeError("uiclick: button must be left|right|middle")
    if title:
        wt, matches = _find_in_window(title, name, control_type, wait_ms)
    else:
        wt, matches = _uia_find_any(name, control_type, wait_ms)
    if not matches:
        raise RuntimeError("uiclick: no element named ~%r" % name)
    if index >= len(matches):
        raise RuntimeError("uiclick: only %d matches for ~%r" % (len(matches), name))
    ctrl, info = matches[index]
    method = _uia_click_it(ctrl, info, button, double)
    return {"window": wt, "clicked": info, "method": method}


def _s_uiset(s):
    """v1.5.0: semantic set-text inside a macro (see /uiset)."""
    name, value = s["name"], s["value"]
    title = s.get("title")
    control_type = s.get("control_type")
    index = int(s.get("index", 0))
    wait_ms = int(s.get("wait_ms", 0))
    if title:
        wt, matches = _find_in_window(title, name, control_type, wait_ms)
    else:
        wt, matches = _uia_find_any(name, control_type, wait_ms)
    if not matches:
        raise RuntimeError("uiset: no element named ~%r" % name)
    if index >= len(matches):
        raise RuntimeError("uiset: only %d matches for ~%r" % (len(matches), name))
    ctrl, info = matches[index]
    try:
        ctrl.set_edit_text(value)
        return {"window": wt, "element": info, "method": "set_edit_text"}
    except Exception:
        # v1.5.1: click+paste+verify (see _uia_paste_into)
        method = _uia_paste_into(ctrl, info, value)
        return {"window": wt, "element": info, "method": method}


MACRO_ACTIONS = {
    "click": _s_click, "move": _s_move, "drag": _s_drag, "scroll": _s_scroll,
    "type": _s_type, "key": _s_key, "sleep": _s_sleep, "window": _s_window,
    "run": _s_run, "adb": _s_adb,
    "uiclick": _s_uiclick, "uiset": _s_uiset,      # v1.5.0 semantic steps
    "waitfor": _s_waitfor,                         # v1.5.3: event-driven waits
}


# -------------------------------------------------------------- endpoints ----
@app.get("/ping")
def ping():
    return {"ok": True, "ts": int(time.time())}


@app.get("/health")
def health(request: Request):
    guard(request)
    w, h = pyautogui.size()
    import importlib.util
    return {
        "ok": True,
        "host": socket.gethostname(),
        "screen": {"width": w, "height": h},
        "adb": adb_path(),
        "pywinauto": importlib.util.find_spec("pywinauto") is not None,
        "playwright": importlib.util.find_spec("playwright") is not None,
        "awake": AWAKE_FLAG["on"],
        "indicator": _port_listening(INDICATOR_PORT),
        "ollama": bool(_ollama_models()),                    # v1.5.3
        "vlm": {"default": _ollama_pick_vlm(),              # v1.5.3
                "installed": [m for m in _ollama_models()
                              if any(h in m.lower() for h in _VLM_HINTS)]},
        "agent_version": VERSION,
    }


@app.get("/tunnel")
def tunnel_status(request: Request):
    """v1.6.4: cloudflared watchdog status. 'running' reflects a live
    cloudflared process; 'url' is the last URL the watchdog captured (or
    the one in tunnel_url.txt). Quick-tunnel URLs rotate on every restart
    -- if this url differs from the one you are calling through, the one
    you are using is stale."""
    guard(request)
    with _TUNNEL_LOCK:
        restarts = _TUNNEL["restarts"]
        url = _TUNNEL["url"] or _tunnel_url_from_file()
        seen_up = _TUNNEL["seen_up"]
    return {"ok": True, "running": _cloudflared_running(), "url": url,
            "restarts": restarts, "watchdog_armed": seen_up,
            "note": "quick tunnels rotate URLs; for a permanent URL see "
                    "NAMED-TUNNEL-SETUP.md"}


@app.get("/screenshot")
def screenshot(request: Request, fmt: str = "jpeg", q: int = 60, region: Optional[str] = None,
               scale: float = 1.0):
    guard(request)
    img = _capture_screen()        # bar hidden/cloaked, always restored after
    if region:
        try:
            x, y, w, h = [int(v) for v in region.split(",")]
            img = img.crop((x, y, x + w, y + h))
        except Exception:
            raise HTTPException(status_code=400, detail="region must be x,y,w,h")
    # v1.5.2: downscale BEFORE encoding -- scale=0.5 & q=60 is the standard
    # verification shot: 3-6x smaller through the tunnel and much cheaper
    # to analyze on the rare occasion a vision check is genuinely needed.
    scale = max(0.1, min(float(scale or 1.0), 1.0))
    if scale < 1.0:
        resample = getattr(Image, "Resampling", Image).LANCZOS
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                         resample)
    buf = io.BytesIO()
    if fmt == "png":
        img.save(buf, "PNG")
        media = "image/png"
    else:
        img.convert("RGB").save(buf, "JPEG", quality=max(1, min(q, 95)))
        media = "image/jpeg"
    # v1.5.2: tell the caller the ACTUAL pixel size of the returned image
    # (coords seen in a scaled shot must be multiplied by 1/scale to map
    # back to the real screen -- or just use /find, which matches the
    # FULL-resolution screen and returns exact centers).
    return Response(content=buf.getvalue(), media_type=media,
                    headers={"X-Screen-W": str(img.width), "X-Screen-H": str(img.height),
                             "X-Screen-Scale": "%.3f" % scale})


@app.get("/windows")
def windows(request: Request):
    guard(request)
    import pygetwindow as gw
    titles = [t for t in gw.getAllTitles() if t.strip()]
    detailed = []
    try:
        for w in _uia_desktop().windows():
            try:
                info = w.element_info
                detailed.append({"title": (info.name or "")[:120],
                                 "pid": info.process_id,
                                 "exe": _pid_exe(info.process_id)})
            except Exception:
                continue
    except Exception:
        pass
    return {"ok": True, "titles": titles[:200], "windows": detailed[:200]}


@app.get("/proc")
def proc(request: Request, name: str = "", limit: int = 60):
    guard(request)
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                             timeout=20).stdout.decode("utf-8", "replace")
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
    procs = []
    for row in csv.reader(io.StringIO(out)):
        if len(row) >= 5 and name.lower() in row[0].lower():
            procs.append({"name": row[0], "pid": row[1], "mem": row[4]})
            if len(procs) >= max(1, min(limit, 300)):
                break
    return {"ok": True, "count": len(procs), "processes": procs}


@app.post("/kill")
def kill(inp: KillIn, request: Request):
    guard(request)
    if inp.pid == os.getpid():
        return {"ok": False, "error": "refusing to kill the agent itself"}
    if inp.pid:
        argv = ["taskkill", "/PID", str(inp.pid)] + (["/F"] if inp.force else [])
    elif inp.name:
        argv = ["taskkill", "/IM", inp.name] + (["/F"] if inp.force else [])
    else:
        return {"ok": False, "error": "pid or name required"}
    r = run_process(argv, 20)
    r["ok"] = r.get("exit") == 0
    return r


class FindIn(BaseModel):
    image_b64: str                      # PNG/JPEG of the thing to find
    confidence: float = 0.9             # needs opencv; falls back to exact
    region: Optional[str] = None        # "x,y,w,h" to narrow the search
    grayscale: bool = True
    button: str = "left"                # /clickfind only
    clicks: int = 1                     # /clickfind only


@app.post("/click")
def click(inp: ClickIn, request: Request):
    guard(request)
    if inp.button not in ("left", "right", "middle"):
        raise HTTPException(status_code=400, detail="button must be left|right|middle")
    with _input_lock:
        pyautogui.click(x=inp.x, y=inp.y, clicks=inp.clicks, button=inp.button)
    return {"ok": True}


# ------------------------------------------------ v1.4.0: vision workflow ----
# The default way the AI operates the PC is now EYES + HANDS: look with
# /screenshot, decide, act with /click /type /key /macro -- never by running
# commands. /find and /clickfind close the precision gap: the AI sees a
# target in its screenshot, crops it, and asks the agent to locate that
# exact patch of pixels on the live screen (template matching), getting
# back pixel-perfect coordinates it can click.

def _decode_template(image_b64: str):
    """base64 -> PIL Image, or raises ValueError with a friendly message."""
    try:
        raw = base64.b64decode(image_b64, validate=True)
        img = Image.open(io.BytesIO(raw))
        img.load()
        return img
    except Exception as e:
        raise HTTPException(status_code=400,
                            detail="image_b64 is not a valid PNG/JPEG: %s" % e)


def _parse_region(region: Optional[str]):
    """'x,y,w,h' -> tuple, or raises 400."""
    if not region:
        return None
    try:
        x, y, w, h = [int(v) for v in region.split(",")]
        if w <= 0 or h <= 0:
            raise ValueError
        return (x, y, w, h)
    except Exception:
        raise HTTPException(status_code=400, detail="region must be x,y,w,h")


def _locate_matches(template, region, confidence: float, grayscale: bool):
    """Template-match the template against a bar-free grab of the screen.
    Returns a list of {'x','y','left','top','w','h'} center boxes (max 10).
    confidence needs opencv; without it we fall back to an exact match."""
    screen = _capture_screen()                 # bar excluded from the grab
    if region:
        x, y, w, h = region
        screen = screen.crop((x, y, x + w, y + h))
    kwargs = {"grayscale": grayscale}
    try:
        boxes = list(pyautogui.locateAll(template, screen, confidence=confidence, **kwargs))
    except Exception:
        # no opencv (or it disliked the args) -> exact matching, best effort
        try:
            boxes = list(pyautogui.locateAll(template, screen, **kwargs))
        except Exception:
            boxes = []
    out = []
    for b in boxes[:10]:
        left = b.left + (region[0] if region else 0)
        top = b.top + (region[1] if region else 0)
        out.append({"x": left + b.width // 2, "y": top + b.height // 2,
                    "left": left, "top": top, "w": b.width, "h": b.height})
    return out


@app.post("/find")
def find(inp: FindIn, request: Request):
    """Locate a piece of the screen by picture. Send a small crop from your
    last /screenshot (the button/icon/field you want), get back the pixel
    coordinates where it currently sits on screen. {} when not found."""
    guard(request)
    template = _decode_template(inp.image_b64)
    region = _parse_region(inp.region)
    matches = _locate_matches(template, region, inp.confidence, inp.grayscale)
    return {"ok": True, "found": bool(matches), "count": len(matches),
            "matches": matches}


@app.post("/clickfind")
def clickfind(inp: FindIn, request: Request):
    """Find (see /find) then click the first match in one atomic call.
    Use this instead of eyeballing coordinates from a screenshot."""
    guard(request)
    if inp.button not in ("left", "right", "middle"):
        raise HTTPException(status_code=400, detail="button must be left|right|middle")
    template = _decode_template(inp.image_b64)
    region = _parse_region(inp.region)
    matches = _locate_matches(template, region, inp.confidence, inp.grayscale)
    if not matches:
        return {"ok": True, "found": False, "count": 0, "matches": [],
                "clicked": None}
    m = matches[0]
    with _input_lock:
        pyautogui.click(x=m["x"], y=m["y"], clicks=inp.clicks, button=inp.button)
    return {"ok": True, "found": True, "count": len(matches), "matches": matches,
            "clicked": {"x": m["x"], "y": m["y"]}}


@app.post("/drag")
def drag(inp: DragIn, request: Request):
    guard(request)
    with _input_lock:
        pyautogui.moveTo(inp.x1, inp.y1)
        pyautogui.dragTo(inp.x2, inp.y2, duration=max(0.05, inp.duration))
    return {"ok": True}


@app.post("/move")
def move(inp: MoveIn, request: Request):
    guard(request)
    with _input_lock:
        pyautogui.moveTo(inp.x, inp.y, duration=max(0.0, inp.duration))
    return {"ok": True, "pos": pyautogui.position()}


@app.post("/scroll")
def scroll(inp: ScrollIn, request: Request):
    guard(request)
    with _input_lock:
        if inp.dy:
            pyautogui.scroll(inp.dy)
        elif inp.dx:
            pyautogui.hscroll(inp.dx)
    return {"ok": True}


@app.post("/type")
def type_text(inp: TypeIn, request: Request):
    guard(request)
    with _input_lock:
        if inp.paste or any(ord(c) > 127 for c in inp.text):
            _clipboard_set(inp.text)
            pyautogui.hotkey("ctrl", "v")
            return {"ok": True, "method": "clipboard-paste"}
        pyautogui.write(inp.text, interval=max(0, inp.interval))
    return {"ok": True, "method": "write"}


@app.post("/key")
def key(inp: KeyIn, request: Request):
    guard(request)
    if not inp.keys:
        raise HTTPException(status_code=400, detail="keys required")
    with _input_lock:
        if inp.combo:
            pyautogui.hotkey(*inp.keys, interval=0.05)   # v1.5.1: reliable vs Store apps
        else:
            for k in inp.keys:
                pyautogui.press(k)
    return {"ok": True}


@app.post("/window")
def window(inp: WindowIn, request: Request):
    guard(request)
    r = _s_window({"title": inp.title, "op": inp.action})
    return {"ok": True, **r}


@app.post("/run")
def run(inp: RunIn, request: Request):
    guard(request)
    r = _s_run({"command": inp.command, "shell": inp.shell, "timeout": inp.timeout})
    r["ok"] = r.get("exit") == 0
    return r


@app.post("/adb")
def adb(inp: AdbIn, request: Request):
    guard(request)
    path = adb_path()
    if not path:
        return {"ok": False, "error": "adb not found",
                "hint": "Download Android platform-tools into the agent folder or set ADB_PATH."}
    result = run_process([path] + inp.args, inp.timeout)
    result["ok"] = result["exit"] == 0
    return result


# --------------------------------------------------- v1.1: element tree ----
@app.get("/ui")
def ui_tree(request: Request, title: str, max_depth: int = 10, max_nodes: int = 500,
            query: str = ""):
    guard(request)
    win = _find_window_uia(title)
    if win is None:
        return {"ok": False, "error": "no top-level window matching %r" % title}
    nodes, truncated = [], False
    try:
        wrappers = _collect_wrappers(win, min(max_depth, 12), min(max_nodes, 800))
    except Exception as e:
        return {"ok": False, "error": "tree walk failed: %s" % e}
    q = (query or "").strip().lower()
    for ctrl in wrappers[1:]:        # skip the top window itself
        if len(nodes) >= min(max_nodes, 800):
            truncated = True
            break
        info = _wrap_info(ctrl)
        if q and q not in (info.get("name") or "").lower():
            continue                 # v1.5.0: server-side name filter
        nodes.append(info)
    try:
        win_title = win.window_text()
    except Exception:
        win_title = "?"
    return {"ok": True, "window": win_title, "count": len(nodes),
            "truncated": truncated, "elements": nodes}


def _screen_query_impl(query):
    """v1.5.3: /screen query mode, shared by the endpoint and /macro
    screen_query (ACT + semantic VERIFY in one round trip)."""
    for w in _uia_desktop().windows():
        try:
            matches = _uia_match(w, query, None, max_depth=10, max_nodes=400)
        except Exception:
            continue
        if matches:
            try:
                wt = w.window_text() or ""
            except Exception:
                wt = ""
            return {"ok": True, "query": query, "window": wt,
                    "matches": [info for _, info in matches[:20]]}
    return {"ok": True, "query": query, "window": None, "matches": []}


def _screen_overview_impl(elements=True, depth=3, per_window=30):
    """v1.5.3: /screen overview mode, shared by the endpoint and /macro
    screen_after (ACT + re-SEE in one round trip)."""
    depth = max(1, min(depth, 8))
    per_window = max(1, min(per_window, 120))
    out = []
    for w in _uia_desktop().windows():
        info = _wrap_info(w)
        entry = {"title": (info.get("name") or "")[:120],
                 "type": info.get("type"), "rect": info.get("rect"),
                 "center": info.get("center")}
        try:
            entry["pid"] = w.element_info.process_id
            entry["exe"] = _pid_exe(entry["pid"])
        except Exception:
            pass
        if elements:
            els = []
            try:
                wrappers = _collect_wrappers(w, depth, per_window + 1)
            except Exception:
                wrappers = []
            for ctrl in wrappers[1:]:          # skip the window itself
                if len(els) >= per_window:
                    break
                ei = _wrap_info(ctrl)
                els.append({"type": ei.get("type"), "name": ei.get("name"),
                            "rect": ei.get("rect"), "center": ei.get("center")})
            entry["elements"] = els
        out.append(entry)
    return {"ok": True, "count": len(out), "windows": out}


@app.get("/screen")
def screen(request: Request, query: str = "", elements: bool = True,
           depth: int = 3, per_window: int = 30):
    """v1.5.0: the semantic screen -- ONE call instead of screenshot + vision
    analysis. Overview mode (no query): every top-level window + rect (+ a
    shallow element list each). Query mode: /screen?query=Text+Document
    finds that element in ANY window (open context menus / submenus included
    -- they have no title) and returns exact rects; first matching window
    wins. This is the fast way to answer where-is-X-on-screen-right-now
    without any screenshot."""
    guard(request)
    if (query or "").strip():
        return _screen_query_impl(query)
    return _screen_overview_impl(elements, depth, per_window)


@app.post("/uiclick")
def uiclick(inp: UiClickIn, request: Request):
    """v1.5.0: click a UIA element by name. Omit title/null to search ALL
    top-level windows -- that is how you click context-menu / submenu items
    (they live in untitled windows on top of the z-order). button / double /
    wait_ms are new; a rect-center pyautogui click is the fallback if
    click_input fails. Real mouse click either way -- the user sees it."""
    guard(request)
    if inp.button not in ("left", "right", "middle"):
        return {"ok": False, "error": "button must be left|right|middle"}
    if inp.title:
        wt, matches = _find_in_window(inp.title, inp.name, inp.control_type,
                                      inp.wait_ms)
    else:
        wt, matches = _uia_find_any(inp.name, inp.control_type, inp.wait_ms)
    if not matches:
        return {"ok": False, "error": "no element named ~%r%s" % (
            inp.name, " (waited %dms)" % inp.wait_ms if inp.wait_ms else "")}
    if inp.index >= len(matches):
        return {"ok": False, "error": "only %d matches" % len(matches)}
    ctrl, info = matches[inp.index]
    with _input_lock:
        try:
            method = _uia_click_it(ctrl, info, inp.button, inp.double)
            return {"ok": True, "window": wt, "clicked": info, "method": method}
        except Exception as e:
            return {"ok": False, "error": "click failed: %s" % e, "element": info}


@app.post("/uidump")
def uidump(inp: UiDumpIn, request: Request):
    guard(request)
    nodes, err = _aidump_nodes(inp.serial)
    if err:
        return err
    return {"ok": True, "count": len(nodes), "elements": nodes}


# ------------------------------------------------------- v1.1: macro ----
@app.post("/macro")
def macro(inp: MacroIn, request: Request):
    guard(request)
    t0 = time.time()
    results = []
    for i, s in enumerate(inp.steps):
        action = s.get("action", "")
        if action not in MACRO_ACTIONS:
            results.append({"i": i, "action": action, "ok": False,
                            "error": "unknown action; valid: %s" % ", ".join(sorted(MACRO_ACTIONS))})
            if inp.stop_on_error:
                break
            continue
        if time.time() - t0 > MACRO_TIME_CAP:
            results.append({"i": i, "action": action, "ok": False,
                            "error": "macro time cap (%.0fs) reached" % MACRO_TIME_CAP})
            break
        try:
            if action in ("click", "move", "drag", "scroll", "type", "key", "window",
                          "uiclick", "uiset"):
                with _input_lock:
                    detail = MACRO_ACTIONS[action](s)
            else:
                detail = MACRO_ACTIONS[action](s)
            results.append({"i": i, "action": action, "ok": True, "detail": detail})
        except Exception as e:
            results.append({"i": i, "action": action, "ok": False, "error": str(e)[:500]})
            if inp.stop_on_error:
                break
    shot_b64 = None
    if inp.capture:
        try:
            img = _capture_screen()   # bar hidden/cloaked, always restored after
            # v1.5.2: optional downscale of the end-of-flow capture
            if inp.screenshot_scale and inp.screenshot_scale < 1.0:
                sc = max(0.1, min(float(inp.screenshot_scale), 1.0))
                resample = getattr(Image, "Resampling", Image).LANCZOS
                img = img.resize((max(1, int(img.width * sc)), max(1, int(img.height * sc))),
                                 resample)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=max(1, min(inp.screenshot_q, 95)))
            shot_b64 = base64.b64encode(buf.getvalue()).decode()
        except Exception:
            pass
    # v1.5.3: ACT + re-SEE / ACT + VERIFY in this same round trip
    screen = None
    try:
        if (inp.screen_query or "").strip():
            screen = _screen_query_impl(inp.screen_query)
        elif inp.screen_after:
            screen = _screen_overview_impl(elements=False)   # windows+rects: fast
    except Exception as e:
        screen = {"ok": False, "error": str(e)[:200]}
    return {"ok": all(r["ok"] for r in results), "elapsed": round(time.time() - t0, 2),
            "results": results, "screenshot": shot_b64, "screen": screen}


# ------------------------------------- v1.5.3: local vision LLM ----
_OLLAMA_CACHE = {"t": 0.0, "data": None}     # /health: don't hammer ollama
_VLM_HINTS = ("vl", "vision", "llava", "moondream", "minicpm-v", "gemma3")
# localhost opener with proxies DISABLED: on Windows, urllib honors the
# registry proxy (VPN/Clash/etc.) and would misroute 127.0.0.1 calls.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _ollama_models(timeout=1.0):
    """Installed ollama model names ([] when ollama is down). Cached 30s."""
    now = time.time()
    if _OLLAMA_CACHE["data"] is not None and now - _OLLAMA_CACHE["t"] < 30:
        return _OLLAMA_CACHE["data"]
    names = []
    try:
        req = urllib.request.Request(OLLAMA_URL + "/api/tags", method="GET")
        with _OPENER.open(req, timeout=timeout) as r:
            for m in json.loads(r.read().decode() or "{}").get("models", []):
                n = m.get("name") or m.get("model") or ""
                if n:
                    names.append(n)
    except Exception:
        names = []
    _OLLAMA_CACHE["t"], _OLLAMA_CACHE["data"] = now, names
    return names


def _ollama_pick_vlm():
    """Default vision model: OLLAMA_VLM env > first installed model whose
    name looks vision-capable > qwen2.5vl:3b (the recommended pull)."""
    if OLLAMA_VLM:
        return OLLAMA_VLM
    for n in _ollama_models():
        if any(h in n.lower() for h in _VLM_HINTS):
            return n
    return "qwen2.5vl:3b"


@app.post("/vdescribe")
def vdescribe(inp: VDescribeIn, request: Request):
    """v1.5.3: the LOCAL vision LLM (Ollama) reads the screen and answers in
    TEXT. Capture + LANCZOS downscale + JPEG encode happen ON the PC; only
    the model's answer crosses the tunnel -- pixels never leave. Use it to
    read rendered content the UIA tree does not expose (canvas, images,
    PDF text, game state); verify STRUCTURE semantically (/screen, /ui)
    first -- that is still cheaper."""
    guard(request)
    model = (inp.model or "").strip() or _ollama_pick_vlm()
    t0 = time.time()
    img = _capture_screen()        # bar hidden/cloaked, always restored after
    if inp.region:
        try:
            x, y, w, h = [int(v) for v in inp.region.split(",")]
            img = img.crop((x, y, x + w, y + h))
        except Exception:
            return {"ok": False, "error": "region must be x,y,w,h integers"}
    sc = max(0.1, min(float(inp.scale or 0.5), 1.0))
    if sc < 1.0:
        resample = getattr(Image, "Resampling", Image).LANCZOS
        img = img.resize((max(1, int(img.width * sc)), max(1, int(img.height * sc))),
                         resample)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=max(1, min(inp.q, 95)))
    b64 = base64.b64encode(buf.getvalue()).decode()
    ms_capture = round((time.time() - t0) * 1000)
    payload = {"model": model, "stream": False,
               "messages": [{"role": "user", "content": inp.prompt,
                             "images": [b64]}],
               "options": {"temperature": 0.1,
                           "num_predict": max(50, min(inp.max_tokens, 2000))}}
    t1 = time.time()
    try:
        req = urllib.request.Request(
            OLLAMA_URL + "/api/chat", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with _OPENER.open(req, timeout=max(5, min(inp.timeout, 120))) as r:
            data = json.loads(r.read().decode() or "{}")
    except Exception as e:
        hint = ""
        low = str(e).lower()
        if "refused" in low or "connect" in low or "timed out" in low:
            hint = "ollama is not running on the PC? start it, then retry"
        elif "404" in low or "not found" in low:
            hint = "model not pulled?  ollama pull %s" % model
        return {"ok": False, "error": str(e)[:300], "hint": hint}
    err = data.get("error")
    if err:
        return {"ok": False, "error": str(err)[:300],
                "hint": "model not pulled?  ollama pull %s" % model}
    text = ((data.get("message") or {}).get("content") or "").strip()
    if not text:
        return {"ok": False, "error": "empty answer from %s" % model,
                "raw": str(data)[:300]}
    return {"ok": True, "model": model, "text": text,
            "image": {"w": img.width, "h": img.height, "scale": sc, "q": inp.q},
            "ms_capture": ms_capture,
            "ms_vlm": round((time.time() - t1) * 1000),
            "total_ms": round((time.time() - t0) * 1000)}


# --------------------------------------------- v1.1: file transfer ----
@app.post("/upload")
def upload(inp: UploadIn, request: Request):
    guard(request)
    full = in_agent_root(inp.path)
    try:
        raw = base64.b64decode(inp.data)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid base64")
    mode = "ab" if inp.append else "wb"
    with open(full, mode) as f:
        f.write(raw)
    return {"ok": True, "path": full, "wrote": len(raw), "total": os.path.getsize(full)}


@app.post("/download")
def download(inp: DownloadIn, request: Request):
    guard(request)
    full = in_agent_root(inp.path)
    if not os.path.isfile(full):
        return {"ok": False, "error": "not a file: %s" % inp.path}
    size = os.path.getsize(full)
    if size > 80 * 1024 * 1024:
        return {"ok": False, "error": "file too large (>80MB)"}
    with open(full, "rb") as f:
        data = f.read()
    return {"ok": True, "path": full, "bytes": size,
            "data": base64.b64encode(data).decode()}


# =========================================================== v1.2 endpoints ====
# ------------------------------------------------- desktop: forms + ops ----
@app.post("/uiset")
def uiset(inp: UiSetIn, request: Request):
    guard(request)
    if inp.title:
        wt, matches = _find_in_window(inp.title, inp.name, inp.control_type,
                                      inp.wait_ms)
    else:
        wt, matches = _uia_find_any(inp.name, inp.control_type, inp.wait_ms)
    if not matches:
        return {"ok": False, "error": "no element named ~%r" % inp.name}
    if inp.index >= len(matches):
        return {"ok": False, "error": "only %d matches" % len(matches)}
    ctrl, info = matches[inp.index]
    with _input_lock:
        try:
            try:
                ctrl.set_edit_text(inp.value)
                return {"ok": True, "method": "set_edit_text", "element": info}
            except Exception:
                # v1.5.1: click+paste+verify (see _uia_paste_into)
                method = _uia_paste_into(ctrl, info, inp.value)
                return {"ok": True, "method": method, "element": info}
        except Exception as e:
            return {"ok": False, "error": "set failed: %s" % str(e)[:200], "element": info}


@app.post("/clipboard")
def clipboard_ep(inp: ClipIn, request: Request):
    guard(request)
    if inp.action == "set":
        _clipboard_set(inp.text)
        return {"ok": True, "set": len(inp.text)}
    return {"ok": True, "text": _clipboard_get()}


@app.post("/awake")
def awake(inp: AwakeIn, request: Request):
    guard(request)
    AWAKE_FLAG["on"] = bool(inp.on)
    return {"ok": True, "awake": AWAKE_FLAG["on"],
            "hint": "display+system sleep suppressed while on; turn off after testing"}


# --------------------------------------------------------- background jobs ----
@app.post("/job/start")
def job_start(inp: JobIn, request: Request):
    guard(request)
    with JOB_LOCK:
        JOB_SEQ[0] += 1
        jid = "j%04d" % JOB_SEQ[0]
    log_path = os.path.join(JOBS_DIR, jid + ".log")
    if inp.shell == "cmd":
        argv = ["cmd", "/c", inp.command]
    else:
        argv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", inp.command]
    job = {"id": jid, "name": (inp.name or inp.command)[:80], "command": inp.command[:300],
           "running": True, "started": time.time(), "log": log_path, "exit": None}
    JOBS[jid] = job

    def _run():
        try:
            with open(log_path, "wb") as f:
                p = subprocess.Popen(argv, stdout=f, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, cwd=AGENT_ROOT)
                job["pid"] = p.pid
                rc = p.wait()
            job["running"] = False
            job["exit"] = rc
            job["ended"] = time.time()
        except Exception as e:
            job["running"] = False
            job["exit"] = -1
            job["error"] = str(e)[:300]

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "job": {"id": jid, "name": job["name"], "started": job["started"]}}


@app.post("/job/status")
def job_status(inp: JobIdIn, request: Request):
    guard(request)
    job = JOBS.get(inp.id)
    if job is None:
        return {"ok": False, "error": "unknown job id (try /job/list)"}
    tail = ""
    try:
        size = os.path.getsize(job["log"])
        with open(job["log"], "rb") as f:
            if size > 16000:
                f.seek(-16000, 2)
            tail = f.read().decode("utf-8", "replace")
    except Exception:
        pass
    return {"ok": True, "id": job["id"], "name": job["name"], "running": job["running"],
            "exit": job.get("exit"), "started": job["started"], "ended": job.get("ended"),
            "pid": job.get("pid"), "tail": tail[-8000:]}


@app.post("/job/list")
def job_list(request: Request):
    guard(request)
    out = [{"id": j["id"], "name": j["name"], "running": j["running"], "exit": j.get("exit")}
           for j in sorted(JOBS.values(), key=lambda x: x.get("started", 0), reverse=True)]
    return {"ok": True, "jobs": out[:50]}


@app.post("/job/stop")
def job_stop(inp: JobIdIn, request: Request):
    guard(request)
    job = JOBS.get(inp.id)
    if job is None:
        return {"ok": False, "error": "unknown job id"}
    pid = job.get("pid")
    if not pid or not job.get("running"):
        return {"ok": False, "error": "job not running"}
    r = run_process(["taskkill", "/PID", str(pid), "/T", "/F"], 15)
    return {"ok": r.get("exit") == 0, "kill": r}


# --------------------------------------------------------- android: v1.2 ----
@app.get("/devscreen")
def devscreen(request: Request, serial: Optional[str] = None):
    guard(request)
    pre, path = _adb_pre(serial)
    if not path:
        return JSONResponse({"ok": False, "error": "adb not found"})
    rc, png = run_process_bytes(pre + ["exec-out", "screencap", "-p"], 30)
    if rc != 0 or not png or len(png) < 100:
        return JSONResponse({"ok": False,
                             "error": "screencap failed (is a device connected + authorized?)"})
    return Response(content=png, media_type="image/png")


@app.post("/uiclick_android")
def uiclick_android(inp: UiClickAIn, request: Request):
    guard(request)
    nodes, err = _aidump_nodes(inp.serial)
    if err:
        return err

    def _hit(n):
        if inp.text and inp.text.lower() in (n["text"] or "").lower():
            return True
        if inp.res and inp.res.lower() in (n["res"] or "").lower():
            return True
        if inp.desc and inp.desc.lower() in (n["desc"] or "").lower():
            return True
        return False

    matches = [n for n in nodes if _hit(n)]
    if not matches:
        return {"ok": False, "error": "no node matching", "hint": "call /uidump and inspect elements"}
    if inp.index >= len(matches):
        return {"ok": False, "error": "only %d matches" % len(matches),
                "candidates": [{"text": n["text"], "res": n["res"], "center": n["center"]}
                               for n in matches[:10]]}
    n = matches[inp.index]
    cx, cy = n["center"]
    pre, path = _adb_pre(inp.serial)
    if inp.long_press:
        argv = pre + ["shell", "input", "swipe", str(cx), str(cy), str(cx), str(cy), "900"]
    else:
        argv = pre + ["shell", "input", "tap", str(cx), str(cy)]
    r = run_process(argv, 15)
    return {"ok": r.get("exit") == 0,
            "tapped": {"center": [cx, cy], "text": n["text"], "res": n["res"]},
            "match_count": len(matches)}


@app.post("/logcat")
def logcat_ep(inp: LogcatIn, request: Request):
    guard(request)
    pre, path = _adb_pre(inp.serial)
    if not path:
        return {"ok": False, "error": "adb not found"}
    if inp.clear:
        r = run_process(pre + ["logcat", "-c"], 15)
        return {"ok": r.get("exit") == 0, "cleared": True}
    argv = pre + ["logcat", "-d", "-t", str(max(1, min(inp.lines, 2000)))]
    if inp.filter:
        argv.append(inp.filter)
    r = run_process(argv, 30)
    r["ok"] = r.get("exit") == 0
    r["lines"] = len((r.get("stdout") or "").splitlines())
    return r


@app.post("/adbapp")
def adbapp_ep(inp: AppIn, request: Request):
    guard(request)
    path = adb_path()
    if not path:
        return {"ok": False, "error": "adb not found"}
    a = inp.action
    pre = [path] + (["-s", inp.serial] if inp.serial else [])
    if a == "devices":
        argv, timeout = [path, "devices", "-l"], 15
    elif a == "install":
        if not inp.apk:
            return {"ok": False, "error": "apk path required (upload it into the agent folder first)"}
        try:
            full = in_agent_root(inp.apk)
        except HTTPException:
            return {"ok": False, "error": "apk must stay inside the agent folder"}
        if not os.path.isfile(full):
            return {"ok": False, "error": "apk not found: %s" % inp.apk}
        argv, timeout = pre + ["install", "-r", full], 300
    elif a == "uninstall":
        if not inp.package:
            return {"ok": False, "error": "package required"}
        argv, timeout = pre + ["uninstall", inp.package], 60
    elif a == "launch":
        if not inp.package:
            return {"ok": False, "error": "package required"}
        argv, timeout = pre + ["shell", "monkey", "-p", inp.package,
                               "-c", "android.intent.category.LAUNCHER", "1"], 30
    elif a == "stop":
        if not inp.package:
            return {"ok": False, "error": "package required"}
        argv, timeout = pre + ["shell", "am", "force-stop", inp.package], 30
    elif a == "clear":
        if not inp.package:
            return {"ok": False, "error": "package required"}
        argv, timeout = pre + ["shell", "pm", "clear", inp.package], 30
    elif a == "packages":
        argv, timeout = pre + ["shell", "pm", "list", "packages", "-3"], 30
    else:
        return {"ok": False, "error": "action must be install|uninstall|launch|stop|clear|packages|devices"}
    r = run_process(argv, timeout)
    r["ok"] = r.get("exit") == 0
    return r


# --------------------------------------------- web: Playwright CDP bridge ----
_SNAPSHOT_JS = """
() => ({
  title: document.title,
  text: (document.body ? document.body.innerText : '').slice(0, 1500),
  elements: Array.from(document.querySelectorAll('a,button,input,select,textarea,[role=button]')).slice(0, 120).map(e => ({
    tag: e.tagName.toLowerCase(),
    text: ((e.innerText || e.value || e.placeholder || e.getAttribute('aria-label') || '') + '').trim().slice(0, 60),
    id: e.id || undefined,
    name: e.getAttribute('name') || undefined,
    type: e.getAttribute('type') || undefined
  }))
})
"""


def _web_ctx():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise HTTPException(status_code=400,
                            detail="playwright not installed. Run: pip install playwright "
                                   "(browser download NOT needed for CDP attach)")
    with _WEB_LOCK:
        if _WEB["pw"] is None:
            try:
                pw = sync_playwright().start()
                ctx = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
            except Exception as e:
                try:
                    pw.stop()
                except Exception:
                    pass
                raise HTTPException(status_code=400,
                                    detail="cannot reach Chrome CDP on 127.0.0.1:9222 (%s). "
                                           "Close Chrome fully, then run: run.bat chrome (in the agent folder)"
                                           % str(e)[:140])
            _WEB["pw"], _WEB["ctx"] = pw, ctx
    return _WEB["ctx"]


def _hook_page(page):
    with _WEB_LOCK:
        if page in _WEB_HOOKED:
            return
        try:
            def on_console(m):
                _WEB["console"].append({"type": m.type, "text": (m.text or "")[:300]})
                if len(_WEB["console"]) > 200:
                    del _WEB["console"][:100]

            def on_error(e):
                _WEB["errors"].append(str(e)[:300])
                if len(_WEB["errors"]) > 100:
                    del _WEB["errors"][:50]

            page.on("console", on_console)
            page.on("pageerror", on_error)
            _WEB_HOOKED.add(page)
        except Exception:
            pass


def _web_page(new_tab: bool = False):
    ctx = _web_ctx()
    with _WEB_LOCK:
        if new_tab or not ctx.pages:
            page = ctx.new_page()
        else:
            page = ctx.pages[-1]
    _hook_page(page)
    return page


@app.post("/web/open")
def web_open(inp: WebOpenIn, request: Request):
    guard(request)
    page = _web_page(inp.new_tab)
    page.goto(inp.url, timeout=max(5, inp.timeout) * 1000, wait_until="domcontentloaded")
    return {"ok": True, "title": page.title(), "url": page.url}


@app.post("/web/click")
def web_click(inp: WebSelIn, request: Request):
    guard(request)
    page = _web_page()
    page.click(inp.selector, timeout=max(2, inp.timeout) * 1000)
    return {"ok": True, "clicked": inp.selector}


@app.post("/web/fill")
def web_fill(inp: WebFillIn, request: Request):
    guard(request)
    page = _web_page()
    page.fill(inp.selector, inp.text, timeout=max(2, inp.timeout) * 1000)
    return {"ok": True, "filled": inp.selector}


@app.post("/web/eval")
def web_eval(inp: WebEvalIn, request: Request):
    guard(request)
    page = _web_page()
    try:
        result = page.evaluate(inp.expression)
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}
    try:
        json.dumps(result)
        return {"ok": True, "result": result}
    except Exception:
        return {"ok": True, "result": repr(result)[:2000]}


@app.get("/web/state")
def web_state(request: Request):
    guard(request)
    page = _web_page()
    return {"ok": True, "title": page.title(), "url": page.url}


@app.get("/web/console")
def web_console(request: Request, clear: bool = False):
    guard(request)
    with _WEB_LOCK:
        out = {"ok": True, "console": list(_WEB["console"][-100:]),
               "errors": list(_WEB["errors"][-50:])}
        if clear:
            _WEB["console"].clear()
            _WEB["errors"].clear()
    return out


@app.get("/web/snapshot")
def web_snapshot(request: Request):
    guard(request)
    page = _web_page()
    try:
        data = page.evaluate(_SNAPSHOT_JS)
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}
    return {"ok": True, **data}


# =========================================================== v1.3 endpoints ====
@app.get("/indicator")
def indicator_state(request: Request):
    """Live state for the indicator bar. Bar secret or TOKEN auth. Never
    counted as AI activity (see _ai_activity_tracker), so the bar's own
    polling can never keep the light green.
    v1.3.1: this endpoint also advances the task FREEZE accounting -- while
    the AI is disconnected the task timer stops (frozen_at), when it
    reconnects the pause is folded into paused_total and the timer resumes.
    task.elapsed is always ACTIVE time (paused seconds excluded)."""
    _indicator_auth(request)
    now = time.time()
    with _TRACK_LOCK:
        last_seen = _TRACK["last_seen"]
        last_what = _TRACK["last_what"]
        in_flight = _TRACK["in_flight"]
    connected = bool(in_flight > 0 or
                     (last_seen is not None and now - last_seen <= AI_IDLE_RED_SECONDS))
    with _TASK_LOCK:
        _task_freeze_update(connected, last_seen, now)     # freeze / resume
        elapsed = _task_elapsed(connected, now)            # active seconds
        task = {"label": _TASK["label"], "state": _TASK["state"],
                "started": _TASK["started"], "ended": _TASK["ended"],
                "reason": _TASK["reason"],
                "elapsed": (round(elapsed, 1) if elapsed is not None else None)}
    return {
        "ok": True,
        "now": now,
        "agent_version": VERSION,
        "ai": {
            "connected": connected,
            "in_flight": in_flight,
            "last_seen": last_seen,
            "idle_seconds": (round(now - last_seen, 1) if last_seen is not None else None),
        },
        "task": task,
        "last_action": {"what": last_what, "ts": last_seen},
    }


@app.post("/task")
def task_ep(inp: TaskIn, request: Request):
    """AI announces what it is doing -- drives the indicator bar.
      {"task":"Opening Notepad to draft the report","state":"start"}
                                  -> bar: Doing: Opening Notepad... + timer from 0
      {"state":"thinking","reason":"window did not open, looking for it"}
                                  -> bar: Thinking: <reason>, timer KEEPS RUNNING
                                    (use whenever you pause to analyze the
                                    screen or recover from a failure)
      {"state":"done"} / {"state":"fail","reason":"menu item was greyed out"}
                                  -> bar: Done/Failed (+reason), timer frozen
      {"state":"clear"}           -> bar: idle
    Timer RESETS whenever the label changes (or a new task starts after done).
    Labels/reasons must be SHORT HUMAN-READABLE phrases (see Prompt.md).
    v1.3.1: timer FREEZES while the AI is disconnected, resumes on reconnect;
    done/fail record ACTIVE time only (paused seconds excluded).
    v1.4.0: thinking state + reason on any announcement. The red/green light
    is pure CONNECTION state -- done/fail never change it."""
    guard(request)
    st = (inp.state or "").strip().lower()
    label = (inp.task or "").strip()[:200] or None
    reason = (inp.reason or "").strip()[:200] or None
    now = time.time()
    with _TASK_LOCK:
        if st in ("", "start", "working"):
            if not label:
                return {"ok": False, "error": "task label required for state=start"}
            if _TASK["label"] != label or _TASK["state"] not in _ACTIVE_STATES:
                _TASK["started"] = now          # new task (or restart) -> timer resets
                _TASK["paused_total"] = 0.0     # v1.3.1: fresh freeze accounting
                _TASK["frozen_at"] = None
                # same label while still active: NOT touched -- the task
                # continues, so an open freeze stays open and keeps counting.
            _TASK["label"] = label
            _TASK["state"] = "working"
            _TASK["ended"] = None
            _TASK["reason"] = None              # fresh start clears old reasons
        elif st in ("think", "thinking", "analyze", "analyzing"):
            if _TASK["state"] in _ACTIVE_STATES and (label is None or label == _TASK["label"]):
                # same task: timer keeps running, just flip to thinking
                if label:
                    _TASK["label"] = label
            else:
                # thinking announced with a NEW label (or nothing running):
                # it becomes the current task, timer from zero
                if not label:
                    return {"ok": False,
                            "error": "no active task; pass task=<label> with state=thinking"}
                _TASK["label"] = label
                _TASK["started"] = now
                _TASK["ended"] = None
                _TASK["paused_total"] = 0.0
                _TASK["frozen_at"] = None
            _TASK["state"] = "thinking"
            _TASK["reason"] = reason
        elif st in ("done", "ok", "success"):
            if not _finish_task("done", label, now):
                return {"ok": False, "error": "no active task (POST /task state=start first)"}
            _TASK["reason"] = reason
        elif st in ("fail", "failed", "error"):
            if not _finish_task("fail", label, now):
                return {"ok": False, "error": "no active task (POST /task state=start first)"}
            _TASK["reason"] = reason
        elif st == "clear":
            _TASK["label"] = None
            _TASK["state"] = "idle"
            _TASK["started"] = None
            _TASK["ended"] = None
            _TASK["paused_total"] = 0.0
            _TASK["frozen_at"] = None
            _TASK["reason"] = None
        else:
            return {"ok": False,
                    "error": "state must be start|thinking|done|fail|clear"}
        snap = dict(_TASK)
    return {"ok": True, "task": snap}


# =========================================================================
# v1.6.0 -- /ask : the AI stops and asks the human (MCP-style elicitation)
# =========================================================================
# One question at a time. The popup runs in its own thread (it owns its Tk
# instance exclusively -- the only safe way to use tkinter off the main
# thread). The HTTP handler blocks on a threading.Event, capped at 90s so
# the Cloudflare tunnel can never 524; longer waits degrade gracefully into
# polling GET /ask?id=... . Every resolved question is appended to
# asks.jsonl next to agent.py.

ASK_BLOCK_CAP_SEC = 90          # longest a POST /ask will block (tunnel-safe)
ASK_LOG_FILE = os.path.join(AGENT_ROOT, "asks.jsonl")

_ASK_LOCK = threading.Lock()
_ASK = None            # live record while a question is up (see _ask_new)
_ASK_DONE = {}         # ask_id -> resolved record (bounded history)
_ASK_HIST_MAX = 20


def _ask_new(question, options, timeout_sec, default):
    rec = {
        "id": secrets.token_hex(6),
        "question": question,
        "options": options or [],
        "timeout_sec": timeout_sec,
        "default": default,
        "opened_ts": time.time(),
        "event": threading.Event(),
        "resolved": False,
        "outcome": None,       # answered | timeout | cancelled | error
        "answer": None,
        "error": None,
    }
    return rec


def _ask_resolve(rec, outcome, answer=None, error=None):
    """Mark a question resolved exactly once, log it, tidy the bar."""
    with _ASK_LOCK:
        if rec["resolved"]:
            return
        rec["resolved"] = True
        rec["outcome"] = outcome
        rec["answer"] = answer
        rec["error"] = error
        global _ASK
        if _ASK is rec:
            _ASK = None
        _ASK_DONE[rec["id"]] = rec
        while len(_ASK_DONE) > _ASK_HIST_MAX:
            _ASK_DONE.pop(next(iter(_ASK_DONE)))
        try:
            with open(ASK_LOG_FILE, "a", encoding="utf-8") as f:
                entry = {"ts": time.time(),
                         "question": rec["question"],
                         "options": rec["options"],
                         "outcome": outcome,
                         "answer": answer,
                         "elapsed_sec": round(time.time() - rec["opened_ts"], 1)}
                # v1.6.2: on timeout+default record what the AI actually
                # proceeded with, so the audit trail tells the full story.
                if outcome == "timeout" and rec["default"] is not None:
                    entry["proceeded_with"] = rec["default"]
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass
    rec["event"].set()
    # bar: brief, outcome-aware note so the user sees how it continued
    try:
        with _TASK_LOCK:
            if _TASK["state"] in _ACTIVE_STATES:
                _TASK["state"] = "thinking"
                _TASK["reason"] = {
                    "answered": "answer received -- resuming",
                    "timeout": "no answer -- continuing with the plan",
                    "cancelled": "question skipped -- resuming",
                }.get(outcome, "question closed -- resuming")
    except Exception:
        pass


def _ask_dialog(rec):
    """The popup (v1.6.3 iOS-motion redesign). Runs alone in its own
    thread; every Tk call happens here. A dark rounded card: spring
    entrance (fade + rise, ease-out-back overshoot), spring exit (fade +
    drop), breathing accent dot, color-tweened hover/press buttons, a
    bright pick-flash on the chosen option, a five-pulse highlight of the
    recommended option at timeout, and a smoothly depleting progress bar
    with an "auto-continue m:ss" clock (amber at 30s left, red at 10s).
    The line under it states exactly what happens if the user does not
    answer. On any close path the record is resolved
    (answered/timeout/cancelled)."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception as e:                       # no GUI session / no tkinter
        _ask_resolve(rec, "error", error="cannot open dialog: %s" % e)
        return

    # ---- palette ------------------------------------------------------
    BG = "#0b1220"; PANEL = "#1e293b"; ACCENT = "#38bdf8"
    AMBER = "#f59e0b"; RED = "#ef4444"; TEXT = "#f1f5f9"; MUTED = "#94a3b8"
    BTN = "#155e75"; BTN_H = "#0e7490"           # quick-reply idle / hover
    REC_C = "#b45309"; REC_H = "#d97706"         # recommended idle / hover
    GREEN = "#34d399"; FLASH = "#e0f2fe"         # answered / pick-flash tints

    def _rgb(c):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))

    def _hex_lerp(c1, c2, t):
        a, b = _rgb(c1), _rgb(c2)
        return "#%02x%02x%02x" % tuple(
            max(0, min(255, round(a[i] + (b[i] - a[i]) * t)))
            for i in range(3))

    def _col_dist(c1, c2):
        a, b = _rgb(c1), _rgb(c2)
        return sum(abs(a[i] - b[i]) for i in range(3))

    def beep():
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

    beep()

    root = tk.Tk()
    root.title("AI question -- win-agent")
    root.attributes("-topmost", True)
    root.configure(bg=BG)
    root.resizable(False, False)

    ALPHA_OK = True                              # fades need -alpha support
    try:
        root.attributes("-alpha", 1.0)
    except Exception:
        ALPHA_OK = False

    def _round_corners(win, w, h):
        """iOS-style rounded card. DWMWCP_ROUND on Win11 (adds the system
        shadow too); CreateRoundRectRgn window region as the fallback."""
        if os.name != "nt":
            return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
            pref = ctypes.c_int(2)               # DWMWCP_ROUND
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 33, ctypes.byref(pref), 4) == 0:
                return
        except Exception:
            pass
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
            rgn = ctypes.windll.gdi32.CreateRoundRectRgn(
                0, 0, w + 1, h + 1, 16, 16)
            ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)
        except Exception:
            pass

    result = {"value": None}
    total = max(1, int(rec["timeout_sec"]))
    remain = {"sec": total}

    # ---- animated close: status line swap + fade/drop exit -------------
    def close(outcome, answer=None):
        if result["value"] is not None:
            return
        result["value"] = (outcome, answer)
        try:
            if outcome == "answered":
                auto_lbl.config(text="\u2713 Got it \u2014 continuing\u2026",
                                fg=GREEN)
            elif outcome == "cancelled":
                auto_lbl.config(text="Skipped \u2014 the AI will proceed",
                                fg=MUTED)
        except Exception:
            pass
        t0 = time.time()
        y0 = root.winfo_y()

        def _exit_step():
            t = (time.time() - t0) / 0.26
            if t >= 1.0:
                try:
                    root.destroy()
                except Exception:
                    pass
                return
            try:
                root.geometry("+%d+%d" % (root.winfo_x(),
                                          y0 + round(26 * t * t)))
            except Exception:
                pass
            if ALPHA_OK:
                try:
                    root.attributes("-alpha", max(0.0, 1.0 - t))
                except Exception:
                    pass
            root.after(16, _exit_step)
        _exit_step()

    def submit_free(_e=None):
        txt = entry.get().strip()
        if txt and result["value"] is None:
            try:
                entry.config(bg="#052e16", fg=GREEN)
            except Exception:
                pass
            close("answered", txt)

    # ---- hover/press color-tween engine (one loop drives all buttons) --
    _BTN_FX = []          # {btn, idle, hover, press, cur, target}

    def _fx_target(it, color, snap=False):
        it["target"] = color
        if snap:
            it["cur"] = color
            try:
                it["btn"].config(bg=color)
            except Exception:
                pass

    def _fx_step():
        if result["value"] is not None:
            return
        for it in _BTN_FX:
            try:
                if it["cur"] != it["target"]:
                    nc = _hex_lerp(it["cur"], it["target"], 0.45)
                    if _col_dist(nc, it["target"]) <= 12:
                        nc = it["target"]
                    it["cur"] = nc
                    it["btn"].config(bg=nc)
            except Exception:
                pass
        root.after(20, _fx_step)

    def mk_btn(parent, text, cmd, idle, hover, font, padx=12, pady=7):
        """Flat button wired into the color-tween engine (hover/press)."""
        press = _hex_lerp(idle, "#000000", 0.38)
        it = {"idle": idle, "hover": hover, "press": press,
              "cur": idle, "target": idle, "btn": None}
        b = tk.Button(parent, text=text, command=cmd, bg=idle, fg="white",
                      activebackground=hover, activeforeground="white",
                      relief="flat", font=font, padx=padx, pady=pady,
                      cursor="hand2")
        it["btn"] = b
        b.bind("<Enter>", lambda e, i=it: _fx_target(i, i["hover"]))
        b.bind("<Leave>", lambda e, i=it: _fx_target(i, i["idle"]))
        b.bind("<ButtonPress-1>", lambda e, i=it: _fx_target(
            i, i["press"], snap=True))
        _BTN_FX.append(it)
        return b, it

    # ---- header (breathing accent dot) ---------------------------------
    head = tk.Frame(root, bg=BG)
    head.pack(fill="x", padx=22, pady=(16, 6))
    dot = tk.Label(head, text="\u25cf", bg=BG, fg=ACCENT,
                   font=("Segoe UI", 10, "bold"))
    dot.pack(side="left")
    tk.Label(head, text="  AI PAUSED -- NEEDS YOUR ANSWER", bg=BG, fg=ACCENT,
             font=("Segoe UI", 9, "bold")).pack(side="left")

    def _breathe():
        if result["value"] is not None:
            return
        import math
        k = 0.5 - 0.5 * math.cos(2 * math.pi * ((time.time() % 2.6) / 2.6))
        try:
            dot.config(fg=_hex_lerp("#0e5a73", ACCENT, k))
        except Exception:
            pass
        root.after(70, _breathe)

    # ---- question ------------------------------------------------------
    tk.Label(root, text=rec["question"], bg=BG, fg=TEXT, wraplength=432,
             justify="left", font=("Segoe UI", 12)).pack(
                 anchor="w", padx=22, pady=(0, 12))

    # ---- quick replies (recommended star-marked; click = flash + close) -
    rec_fx = [None]                               # fx item of the default
    if rec["options"]:
        grid = tk.Frame(root, bg=BG)
        grid.pack(fill="x", padx=22)
        ncols = 2 if len(rec["options"]) <= 4 else 3
        for i, opt in enumerate(rec["options"]):
            is_rec = rec["default"] is not None and opt == rec["default"]
            idle_c = REC_C if is_rec else BTN
            hover_c = REC_H if is_rec else BTN_H
            it = {"idle": idle_c, "hover": hover_c,
                  "press": _hex_lerp(idle_c, "#000000", 0.38),
                  "cur": idle_c, "target": idle_c, "btn": None}

            def _pick(o=opt, i2=it):
                if result["value"] is not None:
                    return
                _fx_target(i2, FLASH, snap=True)   # bright pick flash
                try:
                    i2["btn"].config(fg="#0b1220")
                except Exception:
                    pass
                root.after(150, lambda: close("answered", o))

            b = tk.Button(grid,
                          text=("\u2605  " + opt) if is_rec else opt,
                          command=_pick, bg=idle_c, fg="white",
                          activebackground=hover_c, activeforeground="white",
                          relief="flat",
                          font=("Segoe UI", 10, "bold" if is_rec else "normal"),
                          padx=12, pady=7, cursor="hand2")
            it["btn"] = b
            b.bind("<Enter>", lambda e, i2=it: _fx_target(i2, i2["hover"]))
            b.bind("<Leave>", lambda e, i2=it: _fx_target(i2, i2["idle"]))
            b.bind("<ButtonPress-1>", lambda e, i2=it: _fx_target(
                i2, i2["press"], snap=True))
            _BTN_FX.append(it)
            if is_rec:
                rec_fx[0] = it
            b.grid(row=i // ncols, column=i % ncols, sticky="ew",
                   padx=3, pady=3)
        for c in range(ncols):
            grid.columnconfigure(c, weight=1)
        tk.Label(root, text="...or type your own answer:", bg=BG, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=22, pady=(8, 0))

    # ---- free text -----------------------------------------------------
    entry = tk.Entry(root, font=("Segoe UI", 11), width=54, bg="#101b2e",
                     fg="#f8fafc", insertbackground="#f8fafc",
                     relief="solid", bd=1,
                     highlightthickness=1, highlightbackground=PANEL,
                     highlightcolor=ACCENT)
    entry.pack(fill="x", padx=22, pady=(5, 10))
    entry.bind("<Return>", submit_free)
    entry.focus_set()
    root.bind("<Escape>", lambda e: close("cancelled"))

    # ---- footer buttons --------------------------------------------------
    foot = tk.Frame(root, bg=BG)
    foot.pack(fill="x", padx=22)
    mk_btn(foot, "Submit answer", submit_free, "#0e7490", "#155e75",
           ("Segoe UI", 10, "bold"), padx=18, pady=6)[0].pack(side="right")
    mk_btn(foot, "Cancel", lambda: close("cancelled"), PANEL, "#334155",
           ("Segoe UI", 9), padx=14, pady=6)[0].pack(side="right",
                                                     padx=(0, 8))

    # ---- countdown strip: depleting bar + what happens on timeout -------
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    # NOTE: ttk style names MUST carry the orientation ("Horizontal.") --
    # without it the layout lookup fails (Layout Horizontal.X not found).
    PB = "ask.Horizontal.TProgressbar"
    style.configure(PB, troughcolor=PANEL, background=ACCENT,
                    bordercolor=BG, lightcolor=ACCENT, darkcolor=ACCENT,
                    thickness=6)
    strip = tk.Frame(root, bg=BG)
    strip.pack(fill="x", padx=22, pady=(16, 2))
    bar = ttk.Progressbar(strip, style=PB, maximum=total, value=total,
                          mode="determinate")
    bar.pack(side="left", fill="x", expand=True)
    clock = tk.Label(strip, text="", bg=BG, fg=MUTED,
                     font=("Segoe UI", 9, "bold"), width=18, anchor="e")
    clock.pack(side="left", padx=(10, 0))

    auto_txt = ("No answer? The AI will go with \u201c%s\u201d"
                % rec["default"][:40]) if rec["default"] else \
               "No answer? The AI will use its best judgment"
    auto_lbl = tk.Label(root, text=auto_txt, bg=BG, fg=MUTED,
                        font=("Segoe UI", 8), wraplength=432, justify="left")
    auto_lbl.pack(anchor="w", padx=22, pady=(0, 16))

    # ---- smooth depletion (50 ms) + 1 Hz heartbeat + timeout flash ------
    t_start = {"t": time.time()}

    def _bar_step():
        if result["value"] is not None:
            return
        try:
            bar["value"] = max(0, total - (time.time() - t_start["t"]))
        except Exception:
            pass
        root.after(50, _bar_step)

    def timeout_flash():
        """Time is up: swap the status line, pulse the recommended option
        (the 'AI is going with this one' moment), then close."""
        if result["value"] is not None:
            return
        try:
            if rec["default"]:
                auto_lbl.config(
                    text="Time\u2019s up \u2014 the AI is going with "
                         "\u201c%s\u201d" % rec["default"][:40], fg=AMBER)
            else:
                auto_lbl.config(
                    text="Time\u2019s up \u2014 the AI will use its best "
                         "judgment", fg=AMBER)
        except Exception:
            pass
        state = {"n": 0}

        def pulse():
            if result["value"] is not None:
                return
            if rec_fx[0] is not None and state["n"] < 6:
                bright = (state["n"] % 2 == 0)
                _fx_target(rec_fx[0], "#fbbf24" if bright else REC_C,
                           snap=True)
                state["n"] += 1
                root.after(130, pulse)
            else:
                close("timeout")
        pulse()

    def tick():
        if result["value"] is not None:
            return
        remain["sec"] -= 1
        if remain["sec"] <= 0:
            timeout_flash()
            return
        m, s = divmod(remain["sec"], 60)
        clock.config(text="auto-continue %d:%02d" % (m, s))
        if remain["sec"] <= 10:
            clock.config(fg=RED)
            style.configure(PB, background=RED, lightcolor=RED, darkcolor=RED)
        elif remain["sec"] <= 30:
            clock.config(fg=AMBER)
            style.configure(PB, background=AMBER, lightcolor=AMBER,
                            darkcolor=AMBER)
        if remain["sec"] % 30 == 0:            # gentle reminder; re-front it
            beep()
            try:
                root.attributes("-topmost", True)
                root.focus_force()
            except Exception:
                pass
        root.after(1000, tick)

    root.protocol("WM_DELETE_WINDOW", lambda: close("cancelled"))
    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    cx = (root.winfo_screenwidth() - w) // 2
    ty = (root.winfo_screenheight() - h) // 2 - 80
    _round_corners(root, w, h)

    # ---- iOS-style entrance: fade + rise with a gentle overshoot --------
    y0 = ty + 40
    root.geometry("+%d+%d" % (cx, y0))
    if ALPHA_OK:
        try:
            root.attributes("-alpha", 0.0)
        except Exception:
            pass

    def _entrance():
        c1 = 1.9; c3 = c1 + 1.0
        t0 = time.time()

        def step():
            t = min(1.0, (time.time() - t0) / 0.42)
            p = t - 1.0
            e = 1.0 + c3 * p * p * p + c1 * p * p   # easeOutBack (>1 ok)
            try:
                root.geometry("+%d+%d" % (cx, round(y0 + (ty - y0) * e)))
            except Exception:
                pass
            if ALPHA_OK:
                try:
                    root.attributes("-alpha", 1.0 - (1.0 - t) ** 3)
                except Exception:
                    pass
            if t < 1.0:
                root.after(16, step)
        step()
    _entrance()

    root.after(20, _fx_step)
    root.after(50, _bar_step)
    root.after(70, _breathe)
    root.after(1000, tick)
    try:
        root.focus_force()
    except Exception:
        pass

    try:
        root.mainloop()
    except Exception as e:
        _ask_resolve(rec, "error", error="dialog crashed: %s" % e)
        return

    if result["value"] is None:                 # mainloop exited abnormally
        _ask_resolve(rec, "error", error="dialog closed unexpectedly")
        return
    outcome, answer = result["value"]
    _ask_resolve(rec, outcome, answer=answer)


def _ask_snapshot(rec, include_answer=True):
    snap = {"ask_id": rec["id"],
            "question": rec["question"],
            "options": rec["options"],
            "opened_sec_ago": round(time.time() - rec["opened_ts"], 1),
            "resolved": rec["resolved"],
            "outcome": rec["outcome"]}
    if include_answer:
        snap["answer"] = rec["answer"]
        if rec["default"] is not None:
            snap["default"] = rec["default"]
    return snap


@app.post("/ask")
def ask_ep(inp: AskIn, request: Request):
    """Ask the human a question -- the popup opens on the user's screen and
    this call blocks (<=90s) until answered. The AI's tool call suspends:
    the response IS the human's answer. If still pending at the block cap,
    poll GET /ask?id=<ask_id>. "wait":false returns the id at once for
    long timeouts. One question at a time (409 while one is pending)."""
    guard(request)
    global _ASK
    question = (inp.question or "").strip()
    if not question:
        return {"ok": False, "error": "question is required"}
    question = question[:500]

    options = []
    for o in (inp.options or []):
        o = str(o).strip()
        if o and o not in options:
            options.append(o[:120])
    options = options[:6]

    timeout_sec = min(max(int(inp.timeout_sec or 90), 10), 1800)  # v1.6.2:
    # stale 300 fallback removed -- the never-stall default is 90s
    default = (inp.default or None)
    if default is not None:
        default = str(default).strip()[:300] or None

    with _ASK_LOCK:
        if _ASK is not None:
            raise HTTPException(status_code=409, detail={
                "ok": False,
                "error": "a question is already pending on the user's screen",
                "pending": _ask_snapshot(_ASK, include_answer=False)})
        rec = _ask_new(question, options, timeout_sec, default)
        _ASK = rec

    t = threading.Thread(target=_ask_dialog, args=(rec,), daemon=True)
    t.start()

    # bar: tell the user a question is up
    try:
        with _TASK_LOCK:
            if _TASK["state"] in _ACTIVE_STATES or _TASK["state"] == "idle":
                _TASK["state"] = "thinking"
                _TASK["reason"] = "waiting for your answer (dialog on screen)"
    except Exception:
        pass

    if not inp.wait:
        return {"ok": True, "answered": False, "reason": "waiting",
                "ask_id": rec["id"],
                "hint": "poll GET /ask?id=%s every few seconds" % rec["id"]}

    rec["event"].wait(min(timeout_sec, ASK_BLOCK_CAP_SEC))

    # v1.6.2 race fix: when the block window ends at the same moment the
    # popup times out, the wait timer can fire a few ms BEFORE the resolve
    # lands -- the caller would get still-waiting for a question that is
    # resolved microseconds later. A short grace re-wait closes that window
    # so the blocking call returns the FINAL result (answer / default / hint)
    # whenever it is available at all.
    if not rec["resolved"]:
        rec["event"].wait(1.5)

    if rec["resolved"]:
        return _ask_response(rec)
    return {"ok": True, "answered": False, "reason": "still-waiting",
            "ask_id": rec["id"],
            "hint": "poll GET /ask?id=%s every ~5s until answered" % rec["id"]}


def _ask_response(rec):
    """Uniform response for a resolved question."""
    out = {"ok": True, "answered": rec["outcome"] == "answered",
           "reason": rec["outcome"],
           "elapsed_sec": round(time.time() - rec["opened_ts"], 1)}
    if rec["outcome"] == "answered":
        out["answer"] = rec["answer"]
    elif rec["outcome"] == "timeout" and rec["default"] is not None:
        out["answer"] = rec["default"]      # never stall: best recommendation
        out["note"] = "timeout -- proceeding with your recommended default"
    elif rec["outcome"] == "timeout":
        out["hint"] = ("no default was given -- proceed NOW with your best "
                       "judgment; do not re-ask the same question")
    elif rec["outcome"] == "cancelled":
        out["hint"] = ("user skipped the question -- proceed with a safe "
                       "choice or ask differently")
    elif rec["outcome"] == "error":
        out["error"] = rec["error"]
    return out


@app.get("/ask")
def ask_status(request: Request, id: Optional[str] = None):
    """Poll a question's status (GET /ask?id=...) or see what is pending
    (GET /ask with no id)."""
    guard(request)
    if id:
        with _ASK_LOCK:
            rec = _ASK if (_ASK is not None and _ASK["id"] == id) else _ASK_DONE.get(id)
        if rec is None:
            raise HTTPException(status_code=404, detail={
                "ok": False, "error": "unknown ask_id (history keeps the last 20)"})
        if rec["resolved"]:
            return _ask_response(rec)
        return {"ok": True, "answered": False, "reason": "waiting",
                **_ask_snapshot(rec, include_answer=False)}
    with _ASK_LOCK:
        if _ASK is None:
            return {"ok": True, "pending": None}
        return {"ok": True, "pending": _ask_snapshot(_ASK, include_answer=False)}


def _spawn_indicator() -> None:
    """Start the thin indicator bar (Windows only). It lives as a separate
    detached process: it survives agent restarts, reconnects using the fresh
    indicator.key, and a second copy exits at once (port-8799 singleton)."""
    if os.environ.get("AGENT_NO_INDICATOR") == "1":
        return
    if os.name != "nt":
        return
    script = os.path.join(AGENT_ROOT, "indicator.py")
    if not os.path.isfile(script):
        return
    try:
        subprocess.Popen(
            [sys.executable, script], cwd=AGENT_ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        print(" Indicator bar     : spawned (thin strip at the top of the screen)")
    except Exception as e:
        print(" Indicator bar     : spawn failed (%s)" % e)


# ----------------------------------------------------------------------
# v1.6.4: cloudflared tunnel watchdog. Quick tunnels die without warning
# (no uptime guarantee); when one dies mid-session the agent becomes
# unreachable until the user manually restarts run.bat. This thread keeps
# a tunnel up on its own: it only acts if cloudflared was seen running at
# least once (so local-only runs are never hijacked), restarts it hidden,
# extracts the new URL from its output and surfaces it to the user.
# ----------------------------------------------------------------------
_TUNNEL = {"seen_up": False, "url": None, "restarts": 0,
           "restart_times": [], "proc": None}
_TUNNEL_LOCK = threading.Lock()
_TUNNEL_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def _tunnel_log(msg: str) -> None:
    try:
        with open(os.path.join(AGENT_ROOT, "tunnel_watchdog.log"), "a",
                  encoding="utf-8", errors="replace") as f:
            f.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def _cloudflared_running() -> bool:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq cloudflared.exe"],
            capture_output=True, text=True, timeout=10).stdout or ""
        return "cloudflared" in out.lower()
    except Exception:
        return False                    # tasklist missing (non-Windows) -> no


def _tunnel_url_from_file() -> Optional[str]:
    try:
        with open(os.path.join(AGENT_ROOT, "tunnel_url.txt"),
                  encoding="ascii", errors="replace") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _tunnel_toast(url: str) -> None:
    """Small self-closing popup with the NEW tunnel URL -- the user must
    relay it to the AI (quick tunnels rotate URLs on every restart)."""
    def run():
        try:
            import tkinter as tk               # local: agent may run headless
            r = tk.Tk()
            r.withdraw()
            box = tk.Toplevel(r)
            box.title("win-agent: tunnel restarted")
            box.configure(bg="#0f172a")
            box.attributes("-topmost", True)
            box.resizable(False, False)
            tk.Label(box, text="The Cloudflare tunnel died and was restarted.",
                     bg="#0f172a", fg="#e2e8f0",
                     font=("Segoe UI", 10, "bold")).pack(padx=18, pady=(14, 4))
            tk.Label(box, text="New URL (send this to your AI):", bg="#0f172a",
                     fg="#94a3b8", font=("Segoe UI", 9)).pack(padx=18)
            tk.Label(box, text=url, bg="#0f172a", fg="#38bdf8", wraplength=420,
                     font=("Consolas", 9)).pack(padx=18, pady=(2, 10))
            tk.Label(box, text="also saved to tunnel_url.txt  --  closes in 20s",
                     bg="#0f172a", fg="#64748b",
                     font=("Segoe UI", 8)).pack(padx=18, pady=(0, 12))
            box.geometry("+%d+%d" % (max(0, r.winfo_screenwidth() - 520), 60))
            try:
                import winsound
                winsound.MessageBeep()
            except Exception:
                pass
            box.after(20000, lambda: (box.destroy(), r.destroy()))
            r.mainloop()
        except Exception:
            pass                       # toast is best-effort, never fatal
    threading.Thread(target=run, daemon=True).start()


def _tunnel_restart() -> bool:
    """Start a fresh hidden cloudflared, wait for its URL, persist it and
    toast the user. Returns True if a URL was captured."""
    exe = shutil.which("cloudflared")
    if not exe:
        _tunnel_log("restart aborted: cloudflared not on PATH")
        return False
    log_path = os.path.join(AGENT_ROOT, "cloudflared-watchdog.log")
    try:
        logf = open(log_path, "ab")
    except OSError:
        return False
    try:
        _TUNNEL["proc"] = subprocess.Popen(
            [exe, "tunnel", "--url", "http://127.0.0.1:%d" % PORT,
             "--no-autoupdate"],
            stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as e:
        _tunnel_log("restart failed: %s" % e)
        logf.close()
        return False
    with _TUNNEL_LOCK:
        _TUNNEL["restarts"] += 1
        _TUNNEL["restart_times"].append(time.time())
        _TUNNEL["restart_times"] = _TUNNEL["restart_times"][-20:]
    _tunnel_log("cloudflared restarted (pid %s), waiting for URL..."
                % _TUNNEL["proc"].pid)
    deadline = time.time() + 30
    while time.time() < deadline:
        time.sleep(1.5)
        if _TUNNEL["proc"].poll() is not None:
            _tunnel_log("restarted cloudflared exited early (rc=%s)"
                        % _TUNNEL["proc"].returncode)
            return False
        try:
            with open(log_path, "rb") as f:
                f.seek(max(0, f.seek(0, 2) - 16384))     # last 16 KB
                txt = f.read().decode("utf-8", "replace")
        except OSError:
            continue
        m = _TUNNEL_URL_RE.search(txt)
        if m:
            url = m.group(0)
            with _TUNNEL_LOCK:
                _TUNNEL["url"] = url
            try:
                with open(os.path.join(AGENT_ROOT, "tunnel_url.txt"), "w",
                          encoding="ascii") as f:
                    f.write(url + "\n")
            except OSError:
                pass
            _tunnel_log("tunnel up: %s" % url)
            _tunnel_toast(url)
            return True
    _tunnel_log("no URL found in cloudflared output after 30s")
    return False


def _tunnel_watch_loop() -> None:
    if os.name != "nt":
        return
    while True:
        time.sleep(20)
        if _cloudflared_running():
            if not _TUNNEL["seen_up"]:
                _TUNNEL["seen_up"] = True
                _tunnel_log("cloudflared detected running (watchdog armed)")
            continue
        if not _TUNNEL["seen_up"]:
            continue            # user never started a tunnel this session
        # it was up, now it is dead -> restart, rate-capped
        with _TUNNEL_LOCK:
            hour_ago = time.time() - 3600
            recent = [t for t in _TUNNEL["restart_times"] if t > hour_ago]
            _TUNNEL["restart_times"] = recent
            capped = len(recent) >= 6
        if capped:
            _tunnel_log("rate cap hit (6 restarts/hour) -- backing off 10 min")
            time.sleep(600)               # OUTSIDE the lock (never block /tunnel)
            continue
        _tunnel_log("cloudflared DIED -- restarting it")
        _tunnel_restart()


if __name__ == "__main__":
    import uvicorn
    print("=" * 64)
    print(" win-agent v%s  on  http://%s:%d  (localhost only)" % (VERSION, HOST, PORT))
    print(" Token starts with   :  %s..." % TOKEN[:8])
    print(" Jobs log dir        :  %s" % JOBS_DIR)
    _spawn_indicator()
    threading.Thread(target=_tunnel_watch_loop, daemon=True,
                     name="tunnel-watchdog").start()
    print(" Tunnel watchdog     : armed (auto-restarts cloudflared if it dies)")
    print(" KEEP THIS WINDOW OPEN. KEEP THE CLOUDFLARED WINDOW OPEN.")
    print("=" * 64)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
