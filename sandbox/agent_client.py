"""
agent_client.py -- semantic-first client for the Win Agent  (v1.5.2, AI-side)
=============================================================================
OPTIONAL helper for the AI sandbox (NOT part of the six Windows agent files).

Why it exists (the v1.5.2 speed doctrine, machine-enforced):
  * ONE persistent HTTP session for the whole chat session -- no TLS
    re-handshake per call (~0.5-1s saved on every request through the
    Cloudflare tunnel), gzip handled automatically.
  * The fast path wrapped in one-liners so the natural thing is also the
    fast thing:

        SEE (screen / ui)  ->  PLAN (names + rects)  ->
        ACT (one macro)    ->  VERIFY (scaled jpeg, milestones only)

  * Screenshots are for VERIFYING, never for planning (see the VISION BAN
    in Prompt.md). verify() defaults to q=60 & scale=0.5 -- the standard
    cheap verification shot (~3-6x smaller than a full-quality grab).

Usage:
    export TUNNEL_URL=https://xxxx.trycloudflare.com
    export TOKEN=...
    from agent_client import Agent
    a = Agent()                          # or Agent(TUNNEL_URL, TOKEN)

    a.ping(); a.health()                 # connectivity
    a.screen()                           # semantic desktop, ONE call
    a.screen(query="Text Document")      # where is that element? (any window)
    a.ui(title="Notepad", query="Save")  # tiny filtered element list
    a.uiclick("OK", wait_ms=1500)        # real click by element name
    a.uiset("Filename", "report.txt")    # set text on a control
    a.macro([                            # a WHOLE flow in ONE call
        {"action": "uiclick", "name": "New"},
        {"action": "uiset",  "name": "Filename", "value": "x.txt"},
        {"action": "key",    "keys": ["ctrl", "s"], "combo": True},
    ])
    a.verify("shot.jpg")                 # milestone screenshot (q=60, scale=0.5)
    a.find("crop.png")                   # pixel fallback (non-UIA targets only)
    a.clickfind("crop.png")              # find + click, atomic
    a.run("Get-Date")                    # powershell (explicitly allowed cases)
    a.task("Opening Notepad", "start")   # announce to the indicator bar

Needs: `requests` if available; falls back to stdlib urllib (manual gzip).
"""

import base64
import gzip
import json as _json
import os
import urllib.error
import urllib.request

try:
    import requests as _requests
except ImportError:          # stdlib fallback path below
    _requests = None


class AgentError(RuntimeError):
    """Any non-2xx reply or transport problem, with the body snippet."""


class Agent:
    """Persistent-session client for the Win Agent (v1.5.x API)."""

    def __init__(self, base_url=None, token=None, timeout=90):
        self.base = (base_url or os.environ.get("TUNNEL_URL", "")).rstrip("/")
        self.token = token or os.environ.get("TOKEN", "")
        self.timeout = timeout
        if not self.base or not self.token:
            raise AgentError("need TUNNEL_URL and TOKEN (env vars or constructor args)")
        self._sess = _requests.Session() if _requests else None
        if self._sess is not None:
            self._sess.headers.update({
                "Authorization": "Bearer %s" % self.token,
                "Accept-Encoding": "gzip",
                "Accept": "application/json",
            })

    # ------------------------------------------------------------- core ----
    def _request(self, method, path, params=None, body=None, raw=False):
        url = self.base + path
        if self._sess is not None:
            r = self._sess.request(method, url, params=params, json=body,
                                    timeout=self.timeout)
            if r.status_code >= 400:
                raise AgentError("%s %s -> HTTP %d: %s"
                                 % (method, path, r.status_code, r.text[:300]))
            return (r.content, dict(r.headers)) if raw else r.json()
        # ---- stdlib fallback (manual gzip) ----
        if params:
            from urllib.parse import urlencode
            url += "?" + urlencode(params)
        data = None
        hdrs = {"Authorization": "Bearer %s" % self.token,
                "Accept-Encoding": "gzip"}
        if body is not None:
            data = _json.dumps(body).encode()
            hdrs["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = resp.read()
                if resp.headers.get("Content-Encoding", "") == "gzip":
                    payload = gzip.decompress(payload)
                if raw:
                    return payload, dict(resp.headers)
                return _json.loads(payload)
        except urllib.error.HTTPError as e:
            raise AgentError("%s %s -> HTTP %d: %s"
                             % (method, path, e.code, e.read()[:300]))

    def _get(self, path, params=None, raw=False):
        return self._request("GET", path, params=params, raw=raw)

    def _post(self, path, body=None):
        return self._request("POST", path, body=body)

    # -------------------------------------------------------- fast path ----
    def ping(self):
        return self._get("/ping")

    def health(self):
        return self._get("/health")

    def screen(self, query=None, elements=True, depth=3, per_window=30):
        """The semantic desktop in ONE call. With query= it searches EVERY
        window (including open context menus) for that element name."""
        params = {"elements": "true" if elements else "false",
                  "depth": depth, "per_window": per_window}
        if query:
            params["query"] = query
        return self._get("/screen", params)

    def ui(self, title=None, query=None, max_depth=10, max_nodes=500):
        """UIA elements of one window; query= filters server-side (tiny)."""
        params = {"max_depth": max_depth, "max_nodes": max_nodes}
        if title:
            params["title"] = title
        if query:
            params["query"] = query
        return self._get("/ui", params)

    def windows(self):
        return self._get("/windows")

    def uiclick(self, name, title=None, control_type=None, index=0,
                button="left", double=False, wait_ms=1500):
        """Real-mouse click on the element whose name CONTAINS `name`.
        Omit title to search ALL windows (context-menu items)."""
        body = {"name": name, "index": index, "button": button,
                "double": double, "wait_ms": wait_ms}
        if title:
            body["title"] = title
        if control_type:
            body["control_type"] = control_type
        return self._post("/uiclick", body)

    def uiset(self, name, value, title=None, index=0, wait_ms=1500):
        body = {"name": name, "value": value, "index": index, "wait_ms": wait_ms}
        if title:
            body["title"] = title
        return self._post("/uiset", body)

    def macro(self, steps, capture=False, screenshot_q=60,
              screenshot_scale=0.5, stop_on_error=True):
        """ONE call for a whole flow (uiclick/uiset/type/key/... steps).
        capture=True attaches a cheap end-of-flow verification shot."""
        return self._post("/macro", {
            "steps": steps, "stop_on_error": stop_on_error,
            "capture": capture, "screenshot_q": screenshot_q,
            "screenshot_scale": screenshot_scale})

    def verify(self, path="verify.jpg", q=60, scale=0.5, region=None):
        """MILESTONE verification shot -- small by default (q=60, scale=0.5).
        Saves to `path`; returns (path, width, height). Remember: coords in a
        scaled shot map back to the screen by 1/scale -- or use find()."""
        params = {"fmt": "jpeg", "q": q, "scale": scale}
        if region:
            params["region"] = region
        data, headers = self._get("/screenshot", params, raw=True)
        with open(path, "wb") as f:
            f.write(data)
        w = int(headers.get("X-Screen-W", 0) or 0)
        h = int(headers.get("X-Screen-H", 0) or 0)
        return path, w, h

    # ------------------------------------------- pixel fallback (non-UIA) ----
    def find(self, image, confidence=0.9, region=None, grayscale=True):
        """image = path to a PNG/JPEG crop of the target from a PREVIOUS
        shot. Server-side template match; returns exact centers."""
        with open(image, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        body = {"image_b64": b64, "confidence": confidence,
                "grayscale": grayscale}
        if region:
            body["region"] = region
        return self._post("/find", body)

    def clickfind(self, image, confidence=0.9, region=None,
                  button="left", clicks=1):
        with open(image, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        body = {"image_b64": b64, "confidence": confidence,
                "button": button, "clicks": clicks}
        if region:
            body["region"] = region
        return self._post("/clickfind", body)

    # --------------------------------------------------- raw input / ops ----
    def click(self, x, y, button="left", clicks=1):
        return self._post("/click", {"x": x, "y": y, "button": button,
                                     "clicks": clicks})

    def type(self, text, interval=0.01, paste=False):
        return self._post("/type", {"text": text, "interval": interval,
                                    "paste": paste})

    def key(self, keys, combo=False):
        return self._post("/key", {"keys": keys, "combo": combo})

    def window(self, title, action="activate"):
        return self._post("/window", {"title": title, "action": action})

    def run(self, command, shell="powershell", timeout=120):
        return self._post("/run", {"command": command, "shell": shell,
                                   "timeout": timeout})

    def task(self, label, state="start", reason=None):
        """Announce to the indicator bar: start | thinking | done | fail | clear."""
        body = {"task": label, "state": state}
        if reason:
            body["reason"] = reason
        return self._post("/task", body)


if __name__ == "__main__":
    # quick connectivity check:  python agent_client.py
    a = Agent()
    print("ping  :", a.ping())
    print("health:", a.health())
