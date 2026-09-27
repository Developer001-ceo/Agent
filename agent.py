"""
agent.py -- Remote Test Agent for Windows  (v1.6.1)
====================================================
v1.6.1 VISION SYSTEM PROMPT (stateless local eyes):
  Every /vision call now opens with a proper SYSTEM message instead of a
  prompt prefix glued onto the question. The default system prompt declares
  the STATELESS contract: each request is a brand-new context with exactly
  ONE image and ONE question -- no history comes in, nothing is kept after
  (the cloud AI owns the conversation; the local model's one job is to
  describe). Together with the agent never sending chat history to Ollama,
  the vision context starts at ZERO tokens on every call -- the "request
  exceeds the available context size" failure of an interactive REPL
  session cannot happen through the agent.
  Configurable: env VISION_SYSTEM_PROMPT (PC-wide default) and an optional
  "system_prompt" field on /vision, /visionclick and the macro visionclick
  step (one-call override -- keep the JSON+box reply contract in any custom
  prompt or boxes stop being clickable). The response says which ran:
  "system_prompt": "default" | "env" | "custom".

v1.6.0 LOCAL VISION TIER (Ollama on the PC -- fast eyes, no rate limits):
  The cloud AI's own vision on screenshots stays the LAST resort: it costs
  30-120s per look and trips provider rate limits. Tier 3 is now a small
  VLM served by Ollama on 127.0.0.1:11434 (localhost only, never exposed
  through the tunnel; default model qwen2.5vl:7b-q8_0):
  POST /vision        -> ask the local model about a bar-free screenshot:
                         {"prompt":"where is the Download button?"} -> JSON
                         with desc + boxes in FULL-screen pixel coordinates
                         (captured image is downscaled to max_size=1280 for
                         inference, coordinates mapped back afterwards).
                         ~2-8s on a modern GPU. Zero rate limits.
  POST /visionclick   -> /vision + click boxes[index] in one atomic call
                         (same contract as /clickfind: found:false +
                         clicked:null when nothing matched).
  /macro "visionclick" step -> the same inside a whole-flow macro.
  GET  /health        -> new "vision" block: is Ollama up, which model
                         resolved, what is installed.
  Config via env: OLLAMA_URL, VISION_MODEL, VISION_MAX_SIZE,
                  VISION_TIMEOUT, VISION_NUM_CTX, VISION_KEEP_ALIVE,
                  VISION_SYSTEM_PROMPT.
  Speed doctrine is now four tiers: UIA semantic tree -> template matching
  (/find) -> LOCAL VLM (/vision) -> cloud vision (last resort).

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
VERSION = "1.6.1"
AGENT_ROOT = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.path.join(AGENT_ROOT, "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

MACRO_TIME_CAP = 30.0       # seconds per /macro call (tunnel friendly)
MACRO_SLEEP_CAP = 10.0      # max seconds per sleep step
MACRO_RUN_CAP = 25          # max timeout per run step inside a macro

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
    screenshot_q: int = 80


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
        "vision": _vision_health(),          # v1.6.0: local VLM tier (Ollama)
        "agent_version": VERSION,
    }


@app.get("/screenshot")
def screenshot(request: Request, fmt: str = "jpeg", q: int = 85, region: Optional[str] = None):
    guard(request)
    img = _capture_screen()        # bar hidden/cloaked, always restored after
    if region:
        try:
            x, y, w, h = [int(v) for v in region.split(",")]
            img = img.crop((x, y, x + w, y + h))
        except Exception:
            raise HTTPException(status_code=400, detail="region must be x,y,w,h")
    buf = io.BytesIO()
    if fmt == "png":
        img.save(buf, "PNG")
        media = "image/png"
    else:
        img.convert("RGB").save(buf, "JPEG", quality=max(1, min(q, 95)))
        media = "image/jpeg"
    return Response(content=buf.getvalue(), media_type=media)


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


# -------------------------------------------- v1.6.0: LOCAL vision tier ----
# The speed doctrine gets a third tier of eyes: a small VLM served by Ollama
# on the SAME PC (127.0.0.1:11434, localhost only -- never exposed through
# the tunnel). The cloud AI sends a question, the agent grabs a bar-free
# screenshot, downscales it (default 1280px longest edge -- roughly halves
# latency with no real accuracy loss on UI shots), asks the local model and
# returns JSON whose bounding boxes are already mapped back to FULL-screen
# pixel coordinates -- the same {x,y,left,top,w,h} shape /find returns, so
# the boxes are immediately clickable.
#   tier 1: UIA semantic tree (/screen, /ui, /uiclick)      ~1-3s, exact
#   tier 2: template matching (/find, /clickfind)           pixel-exact
#   tier 3: LOCAL VLM (/vision, /visionclick)               ~2-8s on GPU
#   tier 4: the cloud AI's own vision on /screenshot        last resort
# Setup on the PC (once): install Ollama from https://ollama.com, then
#   ollama pull qwen2.5vl:7b-q8_0
# Config via environment variables (all optional):
#   OLLAMA_URL        default http://127.0.0.1:11434
#   VISION_MODEL      default qwen2.5vl:7b-q8_0 (any installed qwen2.5vl tag
#                     is auto-picked when the default is missing)
#   VISION_MAX_SIZE   default 1280    (longest edge sent for inference)
#   VISION_TIMEOUT    default 90      (first call loads weights: 10-30s)
#   VISION_NUM_CTX    default 8192    (the image alone eats ~1-2k tokens)
#   VISION_KEEP_ALIVE default 30m     (model stays warm between calls)
#   VISION_SYSTEM_PROMPT  replaces the default STATELESS system message
#                     sent with every /vision call (one job: describe;
#                     fresh context per request); the per-request
#                     "system_prompt" field overrides it for ONE call

VISION_URL = (os.environ.get("OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")
VISION_DEFAULT_MODEL = (os.environ.get("VISION_MODEL") or "qwen2.5vl:7b-q8_0").strip()
VISION_MAX_SIZE_DEFAULT = int(os.environ.get("VISION_MAX_SIZE") or 1280)
VISION_TIMEOUT_DEFAULT = int(os.environ.get("VISION_TIMEOUT") or 90)
VISION_NUM_CTX = int(os.environ.get("VISION_NUM_CTX") or 8192)
VISION_KEEP_ALIVE = os.environ.get("VISION_KEEP_ALIVE") or "30m"

_VISION_LOCK = threading.Lock()   # one capture + one Ollama call at a time

_VISION_SYSTEM_PROMPT_DEFAULT = (
    "You are the vision unit of a desktop automation agent, running locally "
    "on the operator's PC.\n"
    "STATELESS SERVICE: your context is cleared before and after EVERY "
    "request. Each request is a brand-new, independent context containing "
    "exactly ONE screenshot and ONE question -- no conversation history "
    "comes in and nothing is kept afterwards. You have NO memory of earlier "
    "images or questions; the conversation lives in the operator's cloud "
    "model, not in you. Never refer to previous requests; answer only from "
    "THIS image.\n"
    "Your one job is to describe. Reply with ONE JSON object, nothing else:\n"
    '{"desc": "short answer to the question", "boxes": '
    '[{"label": "what this is", "box": [x1, y1, x2, y2]}]}\n'
    "Rules:\n"
    "- box = [left, top, right, bottom], ABSOLUTE PIXEL coordinates of THIS "
    "image, origin at the top-left corner.\n"
    "- One box for every element the operator might need to act on (max 10); "
    "boxes tight around each element.\n"
    '- If nothing matches, reply {"desc": "...", "boxes": []}.\n'
)
# v1.6.1: the system message every /vision call opens with. Replace the
# default PC-wide via env VISION_SYSTEM_PROMPT, or for ONE call via the
# "system_prompt" field on /vision, /visionclick and the macro visionclick
# step. Keep the JSON+box reply contract in any custom prompt -- the agent
# parses it into clickable full-screen boxes.
_VISION_SP_FROM_ENV = bool((os.environ.get("VISION_SYSTEM_PROMPT") or "").strip())
VISION_SYSTEM_PROMPT = ((os.environ.get("VISION_SYSTEM_PROMPT") or "").strip()
                        or _VISION_SYSTEM_PROMPT_DEFAULT)


def _ollama_models():
    """Installed model names from GET /api/tags, or None when Ollama is not
    reachable (a refused localhost connection is instant, so this is cheap
    enough to call on every /health)."""
    try:
        with urllib.request.urlopen(VISION_URL + "/api/tags", timeout=2) as r:
            data = json.loads(r.read().decode("utf-8"))
        return [m.get("name") or m.get("model") for m in data.get("models", [])
                if (m.get("name") or m.get("model"))]
    except Exception:
        return None


def _vision_pick_model(explicit=None):
    """-> (model, error_dict_or_None). Resolution order: an explicit request
    wins; otherwise the configured default when installed; otherwise ANY
    installed qwen2.5vl tag (a 7b one preferred); otherwise any *vl*/*vision*
    model; otherwise the default with a pull hint."""
    want = (explicit or VISION_DEFAULT_MODEL).strip()
    if explicit:
        return want, None                      # caller knows best
    models = _ollama_models()
    if models is None:
        return want, {"ok": False,
                      "error": "Ollama is not reachable at %s" % VISION_URL,
                      "hint": "start the Ollama app (system tray) on the PC, "
                              "then: ollama pull %s" % want}
    if want in models:
        return want, None
    vl = [m for m in models if "qwen2.5vl" in m]
    if vl:
        best = [m for m in vl if "7b" in m] or vl
        return sorted(best)[0], None
    anyvl = [m for m in models if "vl" in m.lower() or "vision" in m.lower()]
    if anyvl:
        return sorted(anyvl)[0], None
    return want, {"ok": False, "error": "no vision model installed in Ollama",
                  "hint": "on the PC run: ollama pull %s" % want,
                  "installed": models[:20]}


def _vision_health():
    """Block for GET /health: is the local vision tier usable right now?"""
    models = _ollama_models()
    if models is None:
        return {"ok": False, "url": VISION_URL,
                "hint": "install/start Ollama, then: ollama pull %s"
                        % VISION_DEFAULT_MODEL}
    model, _err = _vision_pick_model()
    return {"ok": True, "url": VISION_URL, "model": model,
            "installed": models[:20]}


def _vision_json_obj(text):
    """Model output -> JSON dict, or None. Handles plain JSON, markdown
    fences and JSON buried in prose (first '{' .. last '}')."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    try:
        v = json.loads(t)
        if isinstance(v, dict):
            return v
    except Exception:
        pass
    a, b = t.find("{"), t.rfind("}")
    if a >= 0 and b > a:
        try:
            v = json.loads(t[a:b + 1])
            if isinstance(v, dict):
                return v
        except Exception:
            pass
    return None


def _vision_nums(v):
    """A box value in list/tuple/string form -> [x1, y1, x2, y2], or None."""
    if isinstance(v, (list, tuple)):
        vals = []
        for x in list(v)[:4]:
            try:
                vals.append(float(x))
            except Exception:
                return None
        return vals if len(vals) == 4 else None
    if isinstance(v, str):
        nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", v)[:4]]
        return nums if len(nums) == 4 else None
    return None


def _vision_box_from_dict(d):
    """A box given as a dict of named fields -> [x1, y1, x2, y2], or None."""
    try:
        if all(k in d for k in ("x1", "y1", "x2", "y2")):
            return [float(d["x1"]), float(d["y1"]), float(d["x2"]), float(d["y2"])]
        if all(k in d for k in ("left", "top", "right", "bottom")):
            return [float(d["left"]), float(d["top"]),
                    float(d["right"]), float(d["bottom"])]
        x, y = d.get("x", d.get("left")), d.get("y", d.get("top"))
        w, h = d.get("w", d.get("width")), d.get("h", d.get("height"))
        if None not in (x, y, w, h):
            return [float(x), float(y), float(x) + float(w), float(y) + float(h)]
        cx, cy = d.get("cx", d.get("center_x")), d.get("cy", d.get("center_y"))
        if None not in (cx, cy, w, h):
            return [float(cx) - float(w) / 2.0, float(cy) - float(h) / 2.0,
                    float(cx) + float(w) / 2.0, float(cy) + float(h) / 2.0]
    except Exception:
        pass
    return None


def _vision_box_norm(entry):
    """One box entry in ANY of the shapes VLMs like to emit -> (box, label)."""
    label = ""
    if isinstance(entry, dict):
        label = str(entry.get("label") or entry.get("name") or
                    entry.get("text") or "")
        for k in ("box", "box_2d", "bbox", "coords", "coord", "rect", "rectangle"):
            if k in entry:
                r = _vision_nums(entry[k])
                if r:
                    return r, label
        r = _vision_box_from_dict(entry)
        if r:
            return r, label
        return None, label
    r = _vision_nums(entry)
    return (r, label) if r else (None, label)


_VISION_PAIR_RE = re.compile(
    r"\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*,\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)")


def _vision_to_screen(bx, label, sx, sy, ox, oy, sw, sh):
    """[x1,y1,x2,y2] in inference-image pixels -> full-screen box dict (the
    /find match shape), or None when it degenerates after clamping."""
    x1, y1, x2, y2 = bx
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    X1 = int(round(ox + x1 * sx))
    Y1 = int(round(oy + y1 * sy))
    X2 = int(round(ox + x2 * sx))
    Y2 = int(round(oy + y2 * sy))
    X1, X2 = max(0, min(X1, sw)), max(0, min(X2, sw))
    Y1, Y2 = max(0, min(Y1, sh)), max(0, min(Y2, sh))
    if X2 - X1 < 3 or Y2 - Y1 < 3:      # sub-3px boxes are noise, not targets
        return None
    return {"label": (label or "")[:80], "left": X1, "top": Y1,
            "w": X2 - X1, "h": Y2 - Y1, "x": (X1 + X2) // 2, "y": (Y1 + Y2) // 2}


def _vision_parse(text, sx, sy, ox, oy, sw, sh):
    """Model reply -> (desc, boxes) where every box is already in FULL-screen
    pixels with the /find match shape {label,x,y,left,top,w,h}. Defensive by
    design: JSON first (Ollama's format:'json' makes this the normal path),
    Qwen's native '(x1,y1),(x2,y2)' grounding text as the fallback."""
    boxes = []
    obj = _vision_json_obj(text)
    desc = ""
    if obj is not None:
        d = obj.get("desc", obj.get("description", obj.get("answer", "")))
        if isinstance(d, str):
            desc = d
        elif d:
            desc = json.dumps(d)[:300]
        entries = []
        for k in ("boxes", "box", "elements", "targets", "items", "results"):
            v = obj.get(k)
            if isinstance(v, list) and v:
                entries = v
                break
        if entries and _vision_nums(entries):
            entries = [obj]              # flat [x1,y1,x2,y2] under one key
        if not entries:
            bx, _lab = _vision_box_norm(obj)
            if bx:
                entries = [obj]          # the whole object IS one box
        for entry in entries[:10]:
            bx, label = _vision_box_norm(entry)
            if not bx:
                continue
            out = _vision_to_screen(bx, label, sx, sy, ox, oy, sw, sh)
            if out:
                boxes.append(out)
    if not boxes:                        # native grounding text fallback
        for i, m in enumerate(_VISION_PAIR_RE.findall(text or "")[:10]):
            bx = [float(m[0]), float(m[1]), float(m[2]), float(m[3])]
            out = _vision_to_screen(bx, "item %d" % (i + 1), sx, sy, ox, oy, sw, sh)
            if out:
                boxes.append(out)
    if not desc:
        desc = (text or "").strip()[:300]
    return desc, boxes


class VisionIn(BaseModel):
    prompt: str                               # the question for the local VLM
    region: Optional[str] = None              # "x,y,w,h" crop of the screen
    max_size: int = VISION_MAX_SIZE_DEFAULT   # longest edge sent to the model
    model: Optional[str] = None               # override the resolved model
    timeout: int = VISION_TIMEOUT_DEFAULT     # Ollama call timeout (seconds)
    detail: bool = False                      # include the raw model text
    system_prompt: Optional[str] = None       # v1.6.1: one-call override of
                                              # the stateless system message


class VisionClickIn(VisionIn):
    button: str = "left"
    clicks: int = 1
    index: int = 0                            # which box to click


def _vision_analyze(prompt, region, max_size, model, timeout, detail=False,
                    system_prompt=None):
    """Shared core of /vision, /visionclick and the macro visionclick step:
    capture (bar-free) -> optional region crop -> downscale -> local VLM ->
    boxes mapped back to full-screen pixels. Returns the response dict.
    v1.6.1: the call opens with a SYSTEM message (stateless describe-only
    contract; configurable via env VISION_SYSTEM_PROMPT or the per-call
    system_prompt argument) and sends NO history -- every request is a
    fresh context, so the model can never accumulate tokens the way an
    interactive REPL session does."""
    t0 = time.time()
    prompt = (prompt or "").strip()[:2000]
    if not prompt:
        return {"ok": False, "error": "prompt required"}
    model, merr = _vision_pick_model(model)
    if merr:
        merr["elapsed"] = round(time.time() - t0, 2)
        return merr
    sp_src = "env" if _VISION_SP_FROM_ENV else "default"
    sp = VISION_SYSTEM_PROMPT
    if system_prompt and str(system_prompt).strip():
        sp = str(system_prompt).strip()[:4000]      # one-call override wins
        sp_src = "custom"
    try:
        max_size = max(320, min(int(max_size or VISION_MAX_SIZE_DEFAULT), 2560))
        timeout = max(10, min(int(timeout or VISION_TIMEOUT_DEFAULT), 300))
    except (TypeError, ValueError):
        return {"ok": False, "error": "max_size/timeout must be integers"}
    with _VISION_LOCK:                   # one capture + one Ollama call at a time
        img = _capture_screen()          # bar hidden/cloaked, always restored
        sw, sh = pyautogui.size()
        ox = oy = 0
        if region:
            x, y, w, h = region
            ox, oy = x, y
            img = img.crop((x, y, x + w, y + h))
        orig_w, orig_h = img.size
        scale = min(1.0, float(max_size) / float(max(orig_w, orig_h)))
        if scale < 1.0:
            infer_w = max(1, int(round(orig_w * scale)))
            infer_h = max(1, int(round(orig_h * scale)))
            img = img.resize((infer_w, infer_h), Image.LANCZOS)
        else:
            infer_w, infer_h = orig_w, orig_h
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=90)
        b64 = base64.b64encode(buf.getvalue()).decode()
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": sp},
                          {"role": "user", "content": prompt,
                           "images": [b64]}],
            "stream": False,
            "format": "json",
            "keep_alive": VISION_KEEP_ALIVE,
            "options": {"temperature": 0, "num_ctx": VISION_NUM_CTX},
        }
        req = urllib.request.Request(
            VISION_URL + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            code = getattr(e, "code", None)
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:200]  # HTTPError body
            except Exception:
                pass
            if code == 404:
                return {"ok": False, "model": model,
                        "error": "model %r is not installed in Ollama" % model,
                        "hint": "on the PC run: ollama pull %s" % model,
                        "elapsed": round(time.time() - t0, 2)}
            if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                return {"ok": False, "model": model,
                        "error": "vision call timed out after %ss" % timeout,
                        "hint": "the FIRST call after a restart loads the model "
                                "into VRAM (10-30s) -- just retry; if it persists, "
                                "lower max_size or pull a smaller quant",
                        "elapsed": round(time.time() - t0, 2)}
            if code is not None:
                return {"ok": False, "model": model,
                        "error": "ollama HTTP %s: %s" % (code, body),
                        "elapsed": round(time.time() - t0, 2)}
            return {"ok": False, "model": model,
                    "error": "Ollama is not reachable at %s (%s)"
                             % (VISION_URL, str(e)[:120]),
                    "hint": "start the Ollama app on the PC (system tray); the "
                            "agent talks to it on localhost only",
                    "elapsed": round(time.time() - t0, 2)}
        text = ((out.get("message") or {}).get("content")) or ""
        sx = orig_w / float(infer_w)
        sy = orig_h / float(infer_h)
        desc, boxes = _vision_parse(text, sx, sy, ox, oy, sw, sh)
        resp = {"ok": True, "model": model,
                "elapsed": round(time.time() - t0, 2),
                "system_prompt": sp_src,
                "image": {"sent": [infer_w, infer_h],
                          "captured": [orig_w, orig_h],
                          "region": [ox, oy, orig_w, orig_h]},
                "desc": desc, "count": len(boxes), "boxes": boxes}
        if out.get("prompt_eval_count") is not None:
            resp["tokens"] = {"prompt": out.get("prompt_eval_count"),
                              "eval": out.get("eval_count")}
        if detail or not boxes:
            resp["raw"] = (text or "")[:1500]
        return resp


@app.post("/vision")
def vision(inp: VisionIn, request: Request):
    """Ask the LOCAL VLM (Ollama, same PC) about the current screen: one
    round trip, ~2-8s on a modern GPU, no cloud rate limits. Boxes come back
    in FULL-screen pixel coordinates -- the same shape /find returns -- so
    they can be clicked directly. Use it for non-UIA targets and milestone
    verification; the semantic tree (/screen, /ui) is still the first tier.
    v1.6.1: an optional "system_prompt" field replaces the default
    stateless system message for THIS call (the response's
    "system_prompt": "default|env|custom" says which one ran)."""
    guard(request)
    region = _parse_region(inp.region)
    return _vision_analyze(inp.prompt, region, inp.max_size, inp.model,
                           inp.timeout, inp.detail, inp.system_prompt)


@app.post("/visionclick")
def visionclick(inp: VisionClickIn, request: Request):
    """/vision + click boxes[index] in one atomic call. found:false +
    clicked:null when the model saw no matching element -- never click
    blindly after that. The click moves the REAL mouse (visible-operation
    mandate), same as /clickfind."""
    guard(request)
    if inp.button not in ("left", "right", "middle"):
        raise HTTPException(status_code=400, detail="button must be left|right|middle")
    region = _parse_region(inp.region)
    out = _vision_analyze(inp.prompt, region, inp.max_size, inp.model,
                          inp.timeout, inp.detail, inp.system_prompt)
    if not out.get("ok"):
        return out
    boxes = out.get("boxes") or []
    if not boxes:
        return {"ok": True, "found": False, "count": 0, "boxes": [],
                "desc": out.get("desc"), "model": out.get("model"),
                "elapsed": out.get("elapsed"), "system_prompt": out.get("system_prompt"),
                "clicked": None}
    if inp.index >= len(boxes):
        return {"ok": False,
                "error": "only %d boxes (index %d too high)" % (len(boxes), inp.index),
                "boxes": boxes, "elapsed": out.get("elapsed"),
                "system_prompt": out.get("system_prompt")}
    b = boxes[inp.index]
    with _input_lock:
        pyautogui.click(x=b["x"], y=b["y"], clicks=max(1, inp.clicks),
                        button=inp.button)
    return {"ok": True, "found": True, "count": len(boxes), "boxes": boxes,
            "clicked": {"x": b["x"], "y": b["y"], "label": b.get("label")},
            "desc": out.get("desc"), "model": out.get("model"),
            "elapsed": out.get("elapsed"), "system_prompt": out.get("system_prompt")}


def _s_visionclick(s):
    """v1.6.0: local-VLM guided click inside a macro (see /visionclick).
    v1.6.1: optional "system_prompt" step field overrides the vision system
    message for this one call.
    NOTE: deliberately NOT in the macro dispatcher's _input_lock list -- the
    vision call itself must not block other input actions; this helper takes
    the lock for the click only. timeout is capped at 25s to respect the 30s
    macro budget."""
    region = _parse_region(s.get("region")) if s.get("region") else None
    out = _vision_analyze(s["prompt"], region,
                          int(s.get("max_size", VISION_MAX_SIZE_DEFAULT)),
                          s.get("model"),
                          min(int(s.get("timeout", 25)), 25),
                          system_prompt=s.get("system_prompt"))
    if not out.get("ok"):
        raise RuntimeError("visionclick: %s" % out.get("error"))
    boxes = out.get("boxes") or []
    if not boxes:
        raise RuntimeError("visionclick: the local vision model saw nothing "
                           "matching %r" % s["prompt"])
    idx = int(s.get("index", 0))
    if idx >= len(boxes):
        raise RuntimeError("visionclick: only %d boxes" % len(boxes))
    b = boxes[idx]
    with _input_lock:
        pyautogui.click(x=b["x"], y=b["y"], clicks=int(s.get("clicks", 1)),
                        button=s.get("button", "left"))
    return {"clicked": b, "desc": out.get("desc"), "method": "local-vlm"}


MACRO_ACTIONS["visionclick"] = _s_visionclick   # v1.6.0 (the dispatcher's
                                                 # error list picks it up too)

# ------------------------------- end v1.6.0: LOCAL vision tier -----------------


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
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=max(1, min(inp.screenshot_q, 95)))
            shot_b64 = base64.b64encode(buf.getvalue()).decode()
        except Exception:
            pass
    return {"ok": all(r["ok"] for r in results), "elapsed": round(time.time() - t0, 2),
            "results": results, "screenshot": shot_b64}


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


if __name__ == "__main__":
    import uvicorn
    print("=" * 64)
    print(" win-agent v%s  on  http://%s:%d  (localhost only)" % (VERSION, HOST, PORT))
    print(" Token starts with   :  %s..." % TOKEN[:8])
    print(" Jobs log dir        :  %s" % JOBS_DIR)
    _spawn_indicator()
    print(" KEEP THIS WINDOW OPEN. KEEP THE CLOUDFLARED WINDOW OPEN.")
    print("=" * 64)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
