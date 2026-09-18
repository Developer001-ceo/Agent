"""
agent.py -- Remote Test Agent for Windows  (v1.1.0)
====================================================
v1.1 additions:
  GET  /ui        -> element tree of a window (pywinauto / UIA)      [fix #1]
  POST /uiclick   -> click element BY NAME inside a window           [fix #1]
  POST /uidump    -> Android UI hierarchy as JSON (uiautomator dump) [fix #1]
  POST /macro     -> execute a sequence of steps in ONE round trip   [fix #2]
  POST /upload    -> write files (b64, append-able, sandboxed)       [fix #2 support]
  POST /download  -> read files as b64 (sandboxed)                   [fix #2 support]

All v1.0 endpoints unchanged: /ping /health /screenshot /windows
  /click /drag /move /scroll /type /key /window /run /adb
v1.1.1 fix: /uidump now PULLS the xml instead of `adb shell cat` -- cat output
  was truncated to the last 20KB, corrupting the XML on complex screens.
"""

import base64
import io
import os
import re
import shutil
import socket
import subprocess
import time
import xml.etree.ElementTree as ET
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel
from PIL import Image

import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

# ------------------------------------------------------------------------------
TOKEN = "Czj3u9HadjO-PkEMw9X9VR_S02v_ZXKMD9CcFT1WADs"
HOST = "127.0.0.1"          # localhost only -- never change to 0.0.0.0
PORT = 8787
VERSION = "1.1.1"
AGENT_ROOT = os.path.dirname(os.path.abspath(__file__))

MACRO_TIME_CAP = 30.0       # seconds per /macro call (tunnel friendly)
MACRO_SLEEP_CAP = 10.0      # max seconds per sleep step
MACRO_RUN_CAP = 25          # max timeout per run step inside a macro

app = FastAPI(title="win-agent", docs_url=None, redoc_url=None, openapi_url=None)


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


class UiIn(BaseModel):
    title: str
    max_depth: int = 10
    max_nodes: int = 500


class UiClickIn(BaseModel):
    title: str
    name: str
    control_type: Optional[str] = None
    index: int = 0


class UiDumpIn(BaseModel):
    serial: Optional[str] = None


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
    pyautogui.write(s["text"], interval=float(s.get("interval", 0.01)))
    return None


def _s_key(s):
    keys = s["keys"]
    if s.get("combo"):
        pyautogui.hotkey(*keys)
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


MACRO_ACTIONS = {
    "click": _s_click, "move": _s_move, "drag": _s_drag, "scroll": _s_scroll,
    "type": _s_type, "key": _s_key, "sleep": _s_sleep, "window": _s_window,
    "run": _s_run, "adb": _s_adb,
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
        "agent_version": VERSION,
    }


@app.get("/screenshot")
def screenshot(request: Request, fmt: str = "jpeg", q: int = 85, region: Optional[str] = None):
    guard(request)
    img = pyautogui.screenshot()
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
    return {"ok": True, "titles": titles[:200]}


@app.post("/click")
def click(inp: ClickIn, request: Request):
    guard(request)
    if inp.button not in ("left", "right", "middle"):
        raise HTTPException(status_code=400, detail="button must be left|right|middle")
    pyautogui.click(x=inp.x, y=inp.y, clicks=inp.clicks, button=inp.button)
    return {"ok": True}


@app.post("/drag")
def drag(inp: DragIn, request: Request):
    guard(request)
    pyautogui.moveTo(inp.x1, inp.y1)
    pyautogui.dragTo(inp.x2, inp.y2, duration=max(0.05, inp.duration))
    return {"ok": True}


@app.post("/move")
def move(inp: MoveIn, request: Request):
    guard(request)
    pyautogui.moveTo(inp.x, inp.y, duration=max(0.0, inp.duration))
    return {"ok": True, "pos": pyautogui.position()}


@app.post("/scroll")
def scroll(inp: ScrollIn, request: Request):
    guard(request)
    if inp.dy:
        pyautogui.scroll(inp.dy)
    elif inp.dx:
        pyautogui.hscroll(inp.dx)
    return {"ok": True}


@app.post("/type")
def type_text(inp: TypeIn, request: Request):
    guard(request)
    pyautogui.write(inp.text, interval=max(0, inp.interval))
    return {"ok": True}


@app.post("/key")
def key(inp: KeyIn, request: Request):
    guard(request)
    if not inp.keys:
        raise HTTPException(status_code=400, detail="keys required")
    if inp.combo:
        pyautogui.hotkey(*inp.keys)
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
def ui_tree(request: Request, title: str, max_depth: int = 10, max_nodes: int = 500):
    guard(request)
    win = _find_window_uia(title)
    if win is None:
        return {"ok": False, "error": "no top-level window matching %r" % title}
    nodes, truncated = [], False
    try:
        wrappers = _collect_wrappers(win, min(max_depth, 12), min(max_nodes, 800))
    except Exception as e:
        return {"ok": False, "error": "tree walk failed: %s" % e}
    for ctrl in wrappers[1:]:        # skip the top window itself
        if len(nodes) >= min(max_nodes, 800):
            truncated = True
            break
        nodes.append(_wrap_info(ctrl))
    return {"ok": True, "window": win.window_text(), "count": len(nodes),
            "truncated": truncated, "elements": nodes}


@app.post("/uiclick")
def uiclick(inp: UiClickIn, request: Request):
    guard(request)
    win = _find_window_uia(inp.title)
    if win is None:
        return {"ok": False, "error": "no top-level window matching %r" % inp.title}
    wrappers = _collect_wrappers(win, 12, 800)
    matches = []
    for ctrl in wrappers[1:]:
        info = _wrap_info(ctrl)
        if inp.name.lower() in (info.get("name") or "").lower():
            if inp.control_type and (info.get("type") or "") != inp.control_type:
                continue
            matches.append((ctrl, info))
    if not matches:
        return {"ok": False, "error": "no element named ~%r" % inp.name}
    if inp.index >= len(matches):
        return {"ok": False, "error": "only %d matches" % len(matches)}
    ctrl, info = matches[inp.index]
    try:
        ctrl.click_input()
        return {"ok": True, "clicked": info}
    except Exception as e:
        return {"ok": False, "error": "click failed: %s" % e, "element": info}


@app.post("/uidump")
def uidump(inp: UiDumpIn, request: Request):
    guard(request)
    path = adb_path()
    if not path:
        return {"ok": False, "error": "adb not found"}
    pre = [path] + (["-s", inp.serial] if inp.serial else [])
    dump = run_process(pre + ["shell", "uiautomator", "dump", "/sdcard/aidump.xml"], 30)
    if dump["exit"] != 0:
        return {"ok": False, "error": "dump failed", "stderr": dump["stderr"]}
    # v1.1.1: pull the file instead of `adb shell cat` -- run_process truncates
    # stdout to the LAST 20KB, which cuts off the XML root on complex screens.
    local_xml = os.path.join(AGENT_ROOT, "aidump.xml")
    pull = run_process(pre + ["pull", "/sdcard/aidump.xml", local_xml], 30)
    run_process(pre + ["shell", "rm", "/sdcard/aidump.xml"], 10)
    if pull["exit"] != 0 or not os.path.isfile(local_xml):
        return {"ok": False, "error": "pull failed", "stderr": pull["stderr"]}
    try:
        with open(local_xml, "r", encoding="utf-8", errors="replace") as f:
            xml_text = f.read()
        root = ET.fromstring(xml_text)
    except Exception as e:
        return {"ok": False, "error": "xml parse failed: %s" % e}
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
            detail = MACRO_ACTIONS[action](s)
            results.append({"i": i, "action": action, "ok": True, "detail": detail})
        except Exception as e:
            results.append({"i": i, "action": action, "ok": False, "error": str(e)[:500]})
            if inp.stop_on_error:
                break
    shot_b64 = None
    if inp.capture:
        try:
            img = pyautogui.screenshot()
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


if __name__ == "__main__":
    import uvicorn
    print("=" * 64)
    print(" win-agent v%s  on  http://%s:%d  (localhost only)" % (VERSION, HOST, PORT))
    print(" Token starts with   :  %s..." % TOKEN[:8])
    print(" KEEP THIS WINDOW OPEN. KEEP THE CLOUDFLARED WINDOW OPEN.")
    print("=" * 64)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
