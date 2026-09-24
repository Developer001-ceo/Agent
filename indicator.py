"""
indicator.py -- Win Agent indicator bar  (v1.3.1)
=================================================
A THIN always-on-top horizontal strip at the top of the screen:

  [ * ]  AI is working  |  Opening Notepad to draft the report   [ 01:24 ]  win-agent v1.3.1  [x]

Items (left to right):
  1. status light   -- GREEN while the AI is connected (pulsing while a task
                       is running), RED when the AI went idle beyond the
                       threshold or the agent is down.
  2. status text    -- a short human sentence: "AI is working",
                       "AI connected — waiting for a task",
                       "AI disconnected — task paused", "Finished",
                       "Could not finish", "Agent offline — run run.bat to
                       bring it back".
  3. current task   -- whatever the AI announced via POST /task, shown in
                       plain human words (auto-capitalized, truncated).
  4. task timer     -- ACTIVE time on the current task, computed by the
                       agent (GET /indicator -> task.elapsed). It FREEZES at
                       the moment the AI disconnects and resumes where it
                       froze when the AI comes back; done/fail freeze it at
                       the final duration ("took 01:24" / "after 00:07").

v1.3.1 changes:
  - timer freezes on AI disconnect (the bar renders the server-provided
    elapsed; no more local wall-clock math), duration excludes paused time
  - THE BAR NEVER APPEARS IN SCREENSHOTS: on Windows 10 2004+ it
    capture-cloaks itself (SetWindowDisplayAffinity WDA_EXCLUDEFROMCAPTURE
    -- still visible on the physical screen, absent from BitBlt/DXGI
    captures). Older systems fall back to hide -> capture -> show via this
    file's tiny control server (see below). A screenshot can never fail
    because of it.
  - clearer, human-understandable status texts (see item 2)
  - stale indicator.stop sentinels are deleted at startup, so a fresh bar
    never insta-exits because the previous bar was killed before consuming
    an old "stop" file

Live updates: polls GET /indicator on the agent every second, repaints 4x/sec.
The bar is draggable (click + drag vertically) and closable via its [x].

Auth : reads the per-boot secret from indicator.key (rewritten by agent.py at
       every start) so only the local bar (or the real Bearer token) can read
       /indicator through the tunnel.
Single instance : the first bar binds 127.0.0.1:8799 with its CONTROL SERVER
       (http.server.ThreadingHTTPServer); later copies exit at once.
Control server (agent -> bar, for clean screenshots):
       POST/GET /hide   -> bar gets out of the way for a capture
                          (cloaked bars are a no-op, others hide + auto-
                          reappear after 3s even if the agent dies mid-shot)
       POST/GET /show   -> bring it back / cancel a pending auto-reappear
       POST/GET /status -> {"cloaked":bool,"hidden":bool}
Stop  : `run.bat stop` writes indicator.stop (sentinel) -- the bar exits on it.
"""

import http.server
import json
import os
import queue
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

BAR_VERSION = "1.4.0"
AGENT_URL = os.environ.get("AGENT_URL", "http://127.0.0.1:8787").rstrip("/")
SINGLETON_PORT = int(os.environ.get("INDICATOR_PORT", "8799"))
KEY_FILE = os.path.join(HERE, "indicator.key")
STOP_FILE = os.path.join(HERE, "indicator.stop")
LOG_FILE = os.path.join(HERE, "indicator.log")
SNAPSHOT_FILE = os.environ.get("INDICATOR_SNAPSHOT", "")   # debug/test hook

POLL_SECONDS = 1.0        # how often the bar asks the agent for state
TICK_MS = 250             # UI repaint interval (smooth timer + pulse)
FETCH_TIMEOUT = 2.5
BAR_HEIGHT = 30           # logical pixels; scaled by DPI on Windows
OFFLINE_AFTER_FAILS = 3   # polls failing in a row before crying AGENT OFFLINE

AI_IDLE_RED_SECONDS = float(os.environ.get("AGENT_IDLE_RED_SECONDS", "45") or 45)
CTL_POLL_MS = 20          # control-queue poll interval (runs on the tk thread)
RESHOW_MS = 3000          # auto-restore after /hide if the agent died mid-shot
CLOAK_DELAY_MS = 150      # cloak right after the window has been shown
LABEL_MAX = 48            # display cap for task labels ("…" beyond that)
STATUS_MAX = 64           # display cap for status sentences

# ---------------------------------------------------------------- palette ----
BG = "#15171c"
CHIP = "#252b38"
SEP = "#2c313d"
TEXT = "#e8eaed"
MUTED = "#8b93a1"
GREEN = "#22c55e"
GREEN_DIM = "#157f43"
RED = "#ef4444"
RED_TEXT = "#f87171"
GREEN_TEXT = "#4ade80"
THINK_TEXT = "#fbbf24"      # v1.4.0: amber for the thinking task slot
HOVER = "#2a303c"

FONT = "Segoe UI"         # falls back to the system default elsewhere
MONO = "Consolas"

# texts (v1.4.0: status = PURE CONNECTION state; what the AI is doing
# lives in the task slot, never in the light)
TXT_CONNECTED = "AI connected — controlling your PC"
TXT_DISCONNECTED = "AI disconnected — no access"
TXT_OFFLINE = "Agent offline — run run.bat to bring it back"
TXT_CONNECTING = "Connecting to agent…"
# task-slot prefixes
TSK_DOING = "Doing:"
TSK_THINKING = "Thinking:"
TSK_DONE = "Done:"
TSK_FAILED = "Failed:"
TSK_PAUSED = "Paused:"


def log(msg: str) -> None:
    line = "[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        if os.path.isfile(LOG_FILE) and os.path.getsize(LOG_FILE) > 262144:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                tail = f.read()[-131072:]
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write(tail)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


# --------------------------------------------------------- pure view logic ----
def fmt_clock(seconds) -> str:
    try:
        sec = max(0, int(round(float(seconds))))
    except (TypeError, ValueError):
        return "--:--"
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%02d:%02d" % (m, s)


def fmt_idle(seconds) -> str:
    try:
        sec = max(0, int(float(seconds)))
    except (TypeError, ValueError):
        return ""
    if sec < 90:
        return "%ds ago" % sec
    if sec < 5400:
        return "%dm ago" % round(sec / 60)
    return "%dh ago" % round(sec / 3600)


def display_label(label, limit: int = LABEL_MAX) -> str:
    """Cosmetics: capitalize the first letter and keep it short enough that
    the strip never overflows."""
    text = str(label or "").strip()
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    return ellipsize(text, limit)


def compute_view(payload, now: float, offset: float = 0.0, blink: bool = False,
                 fetched: float = None) -> dict:
    """Pure: /indicator payload -> what the bar shows. No tkinter involved,
    so this is unit-testable headless.

    v1.4.0 SEMANTICS (user-specified):
      * the LIGHT + status sentence are PURE CONNECTION STATE:
          green  = AI connected / has access (pulsing while it is actively
                   working or thinking)
          red    = AI disconnected / no access
        Task outcomes (done/failed) NEVER touch the light -- they live in
        the task slot text only.
      * the TASK SLOT says what the AI is doing:
          Doing: <label>            + live timer
          Thinking: <reason>        + live timer (amber, timer keeps running)
          Paused: <label>           + frozen dim timer (AI went away)
          Done: <label>   took MM:SS
          Failed: <label> — <reason>   after MM:SS
      * task.elapsed (v1.3.1+) is rendered directly; while working AND
        connected we advance it locally between 1s polls so the chip stays
        smooth. `blink` accepted for signature compatibility; the pulse
        phase is owned by the bar (see _apply)."""
    if not isinstance(payload, dict):
        return {"color": "red", "pulse": False, "status": TXT_OFFLINE,
                "task": None, "timer": None, "task_kind": "offline",
                "chip_prefix": "", "dim_timer": False, "task_think": False}
    ai = payload.get("ai") or {}
    task = payload.get("task") or {}
    last_action = payload.get("last_action") or {}
    now_s = now + offset

    connected = bool(ai.get("connected"))
    label = task.get("label")
    reason = task.get("reason")
    tstate = task.get("state") or "idle"
    started = task.get("started")
    ended = task.get("ended")
    elapsed = task.get("elapsed")                       # seconds (v1.3.1+ agents)

    def _elapsed_or(fallback_final=None):
        """Server-computed elapsed when available; wall-clock math only as a
        fallback for older agents that do not send task.elapsed yet."""
        if isinstance(elapsed, (int, float)):
            return float(elapsed)
        if fallback_final is not None and isinstance(started, (int, float)):
            return fallback_final - started
        if isinstance(started, (int, float)):
            return now_s - started
        return None

    view = {"task": None, "timer": None, "chip_prefix": "", "dim_timer": False,
            "task_think": False}

    # ---- 1. the light + status: PURE connection state ---------------------
    if connected:
        view["color"] = "green"
        view["status"] = TXT_CONNECTED
        view["pulse"] = tstate in ("working", "thinking")
    else:
        view["color"] = "red"
        view["status"] = TXT_DISCONNECTED
        view["pulse"] = False

    # ---- 2. the task slot: what the AI is doing ---------------------------
    if label and tstate in ("working", "thinking"):
        if tstate == "thinking":
            view["task_kind"] = "thinking"
            view["task_think"] = True
        else:
            view["task_kind"] = "working"
        if connected:
            if tstate == "thinking":
                body = display_label(reason or label, LABEL_MAX + 14)
                view["task"] = TSK_THINKING + " " + body
            else:
                view["task"] = TSK_DOING + " " + display_label(label)
            # live: advance the server's value between polls
            if isinstance(elapsed, (int, float)) and fetched is not None:
                base = float(elapsed) + max(0.0, now - fetched)
            else:
                base = _elapsed_or(now_s)
        else:
            # AI went away mid-task: timer frozen at the disconnect moment
            view["dim_timer"] = True
            view["task_kind"] = "paused"
            view["task_think"] = False            # paused renders muted, not amber
            view["task"] = TSK_PAUSED + " " + display_label(label, LABEL_MAX + 14)
            frozen = _elapsed_or((ai.get("last_seen") + AI_IDLE_RED_SECONDS)
                                 if isinstance(ai.get("last_seen"), (int, float)) else None)
            base = frozen
        view["timer"] = fmt_clock(base) if base is not None else "--:--"
    elif label and tstate in ("done", "fail"):
        # outcome lives ONLY here -- the light stays whatever connection is
        view["pulse"] = False
        if tstate == "done":
            view["task_kind"] = "done"
            view["chip_prefix"] = "took "
            text = TSK_DONE + " " + display_label(label, LABEL_MAX + 8)
        else:
            view["task_kind"] = "fail"
            view["chip_prefix"] = "after "
            text = TSK_FAILED + " " + display_label(label, LABEL_MAX + 8)
            if reason:
                text += " — " + display_label(reason, 46)
        view["task"] = text
        fin = ended if isinstance(ended, (int, float)) else now_s
        base = _elapsed_or(fin)
        view["timer"] = fmt_clock(base) if base is not None else "--:--"
    else:
        # idle (or no label): the task slot just rests
        view["pulse"] = False
        what = last_action.get("what")
        if what:
            view["task"] = "Last: %s" % display_label(what)
            view["task_kind"] = "fallback"
        else:
            view["task_kind"] = "none"
    return view


def ellipsize(text: str, limit: int = 110) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "\u2026"


# ------------------------------------------------------------ state feeder ----
class Feeder(threading.Thread):
    """Polls GET /indicator once a second; keeps the latest result."""

    def __init__(self):
        super().__init__(daemon=True)
        self.url = AGENT_URL + "/indicator"
        self.latest = None            # {"ok":bool, "data":dict|None, "fetched":ts, "offset":float}
        self._lock = threading.Lock()
        self._stop_evt = threading.Event()

    # -- auth: fresh per-boot secret from indicator.key on EVERY poll, so a
    #    restarted agent (new key) is picked up without restarting the bar.
    def _bearer(self) -> str:
        try:
            with open(KEY_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""

    def _fetch_once(self):
        headers = {}
        tok = self._bearer()
        if tok:
            headers["Authorization"] = "Bearer " + tok
        req = urllib.request.Request(self.url, headers=headers)
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))

    def run(self):
        while not self._stop_evt.is_set():
            t0 = time.time()
            try:
                data = self._fetch_once()
                with self._lock:
                    self.latest = {"ok": True, "data": data, "fetched": t0,
                                   "offset": float(data.get("now", t0)) - t0}
            except Exception as e:
                with self._lock:
                    self.latest = {"ok": False, "data": None, "fetched": t0,
                                   "offset": 0.0, "error": repr(e)[:180]}
            self._stop_evt.wait(max(0.2, POLL_SECONDS - (time.time() - t0)))

    def snapshot(self):
        with self._lock:
            return self.latest


# ----------------------------------------------------- control server (v1.3.1) --
# Doubles as the SINGLETON: binding 127.0.0.1:8799 is what proves "I am the
# only bar". The HTTP threads NEVER touch tkinter -- they only flip plain
# attributes and enqueue; the tk thread executes via root.after callbacks.
class ControlHandler(http.server.BaseHTTPRequestHandler):
    bar = None                      # set in main() once the Bar exists
    server_version = "WinAgentBar/1.3.1"

    def _reply(self, obj, code: int = 200) -> None:
        try:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass                     # client hung up -- nothing to do

    def do_GET(self):               # noqa: N802 (http.server naming)
        self._dispatch()

    def do_POST(self):              # noqa: N802
        self._dispatch()

    def _dispatch(self):
        try:                        # drain any body so the reply is not reset
            n = int(self.headers.get("Content-Length") or 0)
            if n > 0:
                self.rfile.read(min(n, 65536))
        except Exception:
            pass
        path = (self.path or "/").split("?")[0].rstrip("/") or "/"
        bar = ControlHandler.bar
        if bar is None:
            self._reply({"ok": False, "error": "bar not ready yet"}, 503)
            return
        try:
            if path == "/hide":
                self._reply(bar.http_hide())
            elif path == "/show":
                self._reply(bar.http_show())
            elif path == "/status":
                self._reply(bar.http_status())
            else:
                self._reply({"ok": False, "error": "unknown endpoint",
                             "endpoints": ["/hide", "/show", "/status"]}, 404)
        except Exception as e:      # never 500 the agent mid-screenshot
            self._reply({"ok": False, "error": repr(e)[:120]})

    def log_message(self, fmt, *args):   # keep stderr clean (pythonw!)
        return


def make_control_server():
    """Bind the control port = claim the singleton. OSError -> another bar."""
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", SINGLETON_PORT),
                                          ControlHandler)
    srv.daemon_threads = True
    return srv


def clear_stale_stop() -> None:
    """v1.3.1 fix: `run.bat stop` writes indicator.stop and THEN kills the
    bar -- if the bar died before its next tick, a stale sentinel survives
    and would insta-exit the NEXT bar. A fresh start voids it (an agent
    start clears it too; this is the belt to that suspenders)."""
    try:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
            log("stale stop sentinel removed at startup")
    except OSError:
        pass


# ------------------------------------------------------------------- the bar --
class Bar:
    def __init__(self, tk):
        self.tk = tk
        self._setup_dpi_awareness()
        self.root = tk.Tk()
        self.root.configure(bg=BG)
        self.root.title("WinAgent Indicator")          # taskkill /FI WINDOWTITLE
        self.root.overrideredirect(True)               # borderless thin strip
        try:
            self.root.attributes("-topmost", True)
        except Exception:
            pass

        try:
            self.dpi = float(self.root.winfo_fpixels("1i"))
        except Exception:
            self.dpi = 96.0
        self.scale = max(1.0, self.dpi / 96.0)
        try:
            self.root.tk.call("tk", "scaling", self.dpi / 72.0)
        except Exception:
            pass

        self.screen_w = self.root.winfo_screenwidth()
        self.h = max(26, round(BAR_HEIGHT * self.scale))
        self.y = 0
        self.root.geometry("%dx%d+0+0" % (self.screen_w, self.h))

        self.dot_px = max(10, round(12 * self.scale))
        self._blink = False
        self._fails = 0
        self._last_key = None
        self._last_snap_write = 0.0
        self._drag = None
        self._tick_n = 0

        # --- screenshot hygiene (v1.3.1) ---
        self.cloaked = False        # True once WDA_EXCLUDEFROMCAPTURE applied
        self._hidden = False        # plain bool -- read by the HTTP threads
        self._hide_gen = 0          # bump = "everything pending is cancelled"
        self._ctl_lock = threading.Lock()
        self._ctl_q = queue.Queue() # HTTP threads -> tk thread commands

        self.feeder = Feeder()
        self._build()
        self._bind()

    # -- Windows DPI awareness so the bar is crisp, not blurry, at 125/150% --
    def _setup_dpi_awareness(self):
        if os.name != "nt":
            return
        try:
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)   # per-monitor v2
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    def _font(self, fam, size, bold=False):
        # negative size = points; tk scaling (set to real DPI) renders them crisp
        return (fam, -size, "bold" if bold else "normal")

    def _build(self):
        tk = self.tk
        pad = max(5, round(6 * self.scale))

        self.dot = tk.Canvas(self.root, width=self.dot_px, height=self.dot_px,
                             bg=BG, highlightthickness=0, bd=0)
        self._dot_id = self.dot.create_oval(1, 1, self.dot_px - 1, self.dot_px - 1,
                                            fill=RED, outline="")
        self.dot.pack(side="left", padx=(pad + pad, pad), pady=0)

        self.status = tk.Label(self.root, text=TXT_CONNECTING, bg=BG, fg=RED_TEXT,
                               font=self._font(FONT, 9, bold=True))
        self.status.pack(side="left", padx=(0, pad))

        self._sep().pack(side="left")

        self.task = tk.Label(self.root, text="", bg=BG, fg=TEXT, anchor="w",
                             font=self._font(FONT, 9))
        self.task.pack(side="left", fill="x", expand=True, padx=(pad, 0))

        self._sep().pack(side="left", padx=(pad, pad))

        chip = tk.Frame(self.root, bg=CHIP)
        self.timer = tk.Label(chip, text="--:--", bg=CHIP, fg=TEXT,
                              font=self._font(MONO, 10, bold=True))
        self.timer.pack(padx=pad, pady=max(1, round(2 * self.scale)))
        chip.pack(side="left", pady=max(2, round(3 * self.scale)))

        # pack right side first: close stays outermost-right, version inside it
        self.close = tk.Label(self.root, text="\u2715", bg=BG, fg=MUTED,
                              font=self._font(FONT, 9, bold=True))
        self.close.pack(side="right", padx=(0, pad + pad))
        for evt, fn in (("<Enter>", lambda e: self.close.config(bg=HOVER, fg=TEXT)),
                        ("<Leave>", lambda e: self.close.config(bg=BG, fg=MUTED)),
                        ("<Button-1>", lambda e: self._quit("closed by user"))):
            self.close.bind(evt, fn)

        self.version = tk.Label(self.root, text="win-agent", bg=BG, fg=MUTED,
                                font=self._font(FONT, 8))
        self.version.pack(side="right", padx=(pad, pad))

    def _sep(self):
        return self.tk.Label(self.root, text="\u2502", bg=BG, fg=SEP,
                             font=self._font(FONT, 9))

    def _bind(self):
        r = self.root
        r.bind("<Button-1>", self._press)
        r.bind("<B1-Motion>", self._motion)
        r.bind("<ButtonRelease-1>", self._release)

    # ------------------------------------------------------------ dragging ----
    def _press(self, e):
        if e.widget is self.close:
            return
        self._drag = (e.x_root, e.y_root, self.y)

    def _motion(self, e):
        if not self._drag:
            return
        _, y0, base = self._drag
        new_y = base + (e.y_root - y0)
        max_y = self.root.winfo_screenheight() - self.h
        self.y = max(0, min(new_y, max(0, max_y)))
        self.root.geometry("+0+%d" % self.y)

    def _release(self, _e):
        self._drag = None

    # ------------------------------------------- screenshot hygiene (v1.3.1) ----
    # PRIMARY mechanism: capture-cloak (Windows 10 2004+). The window stays
    # visible on the physical display but is excluded from BitBlt/DXGI
    # captures (pyautogui / PIL.ImageGrab), so the AI sees the whole screen
    # without any hide/show dance. Must degrade silently elsewhere (Linux,
    # Xvfb, older Windows) -> cloaked stays False and the hide/show fallback
    # below is used instead.
    def _try_cloak(self):
        if os.name != "nt":
            self.cloaked = False
            return
        try:
            import ctypes
            WDA_EXCLUDEFROMCAPTURE = 0x11
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if hwnd and ctypes.windll.user32.SetWindowDisplayAffinity(
                    hwnd, WDA_EXCLUDEFROMCAPTURE):
                self.cloaked = True
                log("capture-cloak ON (WDA_EXCLUDEFROMCAPTURE) -- bar stays "
                    "on screen but never appears in screenshots")
            else:
                self.cloaked = False
                log("capture-cloak unavailable -- using hide/show fallback "
                    "for screenshots")
        except Exception as e:
            self.cloaked = False
            log("capture-cloak failed (%r) -- using hide/show fallback" % e)

    # FALLBACK mechanism: hide-during-screenshot. The HTTP threads only flip
    # plain attributes + enqueue; every tkinter call happens on the tk thread
    # inside root.after callbacks. A hide always schedules its own auto-reshow
    # (3s) so the bar can never stay invisible even if the agent dies mid-shot.
    def http_hide(self):
        """Called from a control-server thread. Never touches tkinter."""
        if self.cloaked:
            return {"ok": True, "cloaked": True, "hidden": False}
        with self._ctl_lock:
            self._hide_gen += 1
            gen = self._hide_gen
        self._ctl_q.put(("hide", gen))
        return {"ok": True, "cloaked": False, "hidden": True}

    def http_show(self):
        """Called from a control-server thread. Never touches tkinter."""
        with self._ctl_lock:
            self._hide_gen += 1       # cancels any pending hide AND auto-reshow
        if not self.cloaked:
            with self._ctl_lock:
                gen = self._hide_gen
            self._ctl_q.put(("show", gen))
        return {"ok": True, "visible": True}

    def http_status(self):
        """Called from a control-server thread. Never touches tkinter."""
        return {"ok": True, "cloaked": bool(self.cloaked),
                "hidden": bool(self._hidden)}

    def _ctl_poll(self):
        """Runs on the tk thread every CTL_POLL_MS: drains the control queue."""
        try:
            while True:
                try:
                    kind, gen = self._ctl_q.get_nowait()
                except queue.Empty:
                    break
                if gen != self._hide_gen:
                    continue          # superseded by a newer hide/show request
                if kind == "hide":
                    try:
                        self.root.withdraw()
                    except Exception:
                        pass
                    self._hidden = True
                    self.root.after(RESHOW_MS, lambda g=gen: self._ctl_reshow(g))
                elif kind == "show":
                    self._ctl_reshow_now()
        except Exception as e:
            log("ctl poll error: %r" % e)
        self.root.after(CTL_POLL_MS, self._ctl_poll)

    def _ctl_reshow(self, gen):
        if gen != self._hide_gen:     # a newer request already took over
            return
        self._ctl_reshow_now()

    def _ctl_reshow_now(self):
        try:
            self.root.deiconify()
            self.root.overrideredirect(True)   # deiconify can re-add a title bar
            self.root.geometry("+0+%d" % self.y)
            self.root.lift()
            try:
                self.root.attributes("-topmost", True)
            except Exception:
                pass
            self._hidden = False
        except Exception as e:
            log("reshow failed: %r" % e)

    # --------------------------------------------------------------- tick ----
    def _tick(self):
        try:
            if os.path.exists(STOP_FILE):                 # run.bat stop sentinel
                self._quit("stop sentinel seen")
                return

            snap = self.feeder.snapshot()
            if snap and snap.get("ok"):
                self._fails = 0
                self._last_good = snap
                view = compute_view(snap["data"], time.time(), snap.get("offset", 0.0),
                                     fetched=snap.get("fetched"))
                ver = (snap["data"] or {}).get("agent_version")
                if ver:
                    self.version.config(text="win-agent v%s" % ver)
            else:
                self._fails += 1
                base = getattr(self, "_last_good", None)
                if base and base.get("ok"):
                    # freeze the timer at the moment the agent went away
                    view = compute_view(base["data"], base["fetched"],
                                        base.get("offset", 0.0),
                                        fetched=base.get("fetched"))
                else:
                    view = compute_view(None, time.time())
                view["color"] = "red"
                view["pulse"] = False
                if self._fails >= OFFLINE_AFTER_FAILS:
                    view["status"] = TXT_OFFLINE
                    view["task_kind"] = "offline"
                else:
                    view["status"] = TXT_CONNECTING

            self._apply(view)
            self._write_snapshot(view)

            self._blink = not self._blink
            self._tick_n += 1
            if self._tick_n % 8 == 0:                    # re-assert topmost 2x/s
                try:
                    self.root.attributes("-topmost", True)
                except Exception:
                    pass
        except Exception as e:                           # never let the bar die
            log("tick error: %r" % e)
        self.root.after(TICK_MS, self._tick)

    def _apply(self, view):
        key = (view["color"], view["status"], view["task"], view["timer"],
               view.get("pulse"), view.get("task_kind"), view.get("chip_prefix"),
               view.get("dim_timer"), view.get("task_think"))
        if key == self._last_key:
            return
        self._last_key = key

        # light -- PURE connection state (v1.4.0); pulse = actively
        # working/thinking while connected
        if view["color"] == "green":
            fill = GREEN if not view.get("pulse") else (GREEN if self._blink else GREEN_DIM)
        else:
            fill = RED
        self.dot.itemconfig(self._dot_id, fill=fill)

        # status text (also connection only)
        self.status.config(text=ellipsize(view["status"], STATUS_MAX),
                           fg=GREEN_TEXT if view["color"] == "green" else RED_TEXT)

        # task text + color by kind (the task slot carries the meaning:
        # doing = plain, thinking = amber, done = green, failed = red,
        # paused = dimmed -- it is not the AI's fault)
        kind = view.get("task_kind")
        if view.get("task_think"):
            fg = THINK_TEXT
        elif kind == "working":
            fg = TEXT
        elif kind == "done":
            fg = GREEN_TEXT
        elif kind == "fail":
            fg = RED_TEXT
        else:
            fg = MUTED
        self.task.config(text=ellipsize(view["task"] or "", LABEL_MAX + 22), fg=fg)

        # timer chip: "01:24" live / frozen, "took 01:24", "after 00:07";
        # grey it out while the task is paused (AI disconnected)
        chip = (view.get("chip_prefix") or "") + (view["timer"] or "--:--")
        self.timer.config(text=chip,
                          fg=MUTED if view.get("dim_timer") else TEXT)

    def _write_snapshot(self, view):
        if not SNAPSHOT_FILE:
            return
        now = time.time()
        if now - self._last_snap_write < 0.2 and self._last_key:
            return
        self._last_snap_write = now
        try:
            with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
                json.dump({"ts": now, **view}, f)
        except Exception:
            pass

    def _quit(self, why):
        log("exiting: %s" % why)
        try:
            if os.path.exists(STOP_FILE):
                os.remove(STOP_FILE)      # consume the sentinel we acted on
        except OSError:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.feeder.start()
        # cloak right after the window is shown (mainloop below maps it)
        self.root.after(CLOAK_DELAY_MS, self._try_cloak)
        # fast control-queue pump (hide/show requests from the agent)
        self.root.after(CTL_POLL_MS, self._ctl_poll)
        self.root.after(TICK_MS, self._tick)
        self.root.mainloop()


def main() -> int:
    log("indicator bar v%s starting (pid %d, agent %s)"
        % (BAR_VERSION, os.getpid(), AGENT_URL))

    # 1) bind the control port = claim the singleton (a second copy exits)
    try:
        server = make_control_server()
    except OSError:
        log("another indicator bar already holds port %d -- exiting" % SINGLETON_PORT)
        return 0

    # 2) a fresh bar must not insta-exit on a stale indicator.stop written by
    #    a previous `run.bat stop` (that stop already killed the old bar --
    #    this one is brand new). Deleted BEFORE the main loop starts; the
    #    tick loop then only ever sees freshly written sentinels.
    clear_stale_stop()

    try:
        import tkinter as tk
    except Exception as e:
        log("tkinter unavailable (%r) -- pip-install python with tcl/tk" % e)
        return 1

    try:
        bar = Bar(tk)
    except Exception as e:
        log("bar construction failed: %r" % e)
        return 1
    ControlHandler.bar = bar

    # 3) serve /hide /show /status (the singleton bind already happened)
    threading.Thread(target=server.serve_forever,
                     kwargs={"poll_interval": 0.25}, daemon=True).start()

    log("bar up: %dx%d px at top of screen, polling %s/indicator "
        "(control server on 127.0.0.1:%d)" % (bar.screen_w, bar.h, AGENT_URL,
                                              SINGLETON_PORT))
    bar.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
