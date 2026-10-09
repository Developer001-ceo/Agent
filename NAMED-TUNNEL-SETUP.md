# Named Tunnel Setup — a PERMANENT URL for your agent (5 minutes)

## Why

Quick tunnels (`trycloudflare.com` URLs from `run.bat`) have **no uptime
guarantee** and **rotate their URL on every restart** — during testing they
died 4 times in a single day, and every death means: paste a new URL to the
AI, update scripts, re-verify. A **named tunnel** fixes both problems:

- the URL NEVER changes (you pick `myagent.example.com`-style, well —
  `<anything>.<your-domain>.trycloudflare...` no — with a named tunnel you
  use your own domain OR the free `*.cfargotunnel.com` hostname),
- cloudflared **auto-reconnects** through network changes and PC reboots,
- it is still FREE (Cloudflare account required, no card).

## Setup (once)

1. **Cloudflare account** (free): https://dash.cloudflare.com/sign-up
2. Go to **Zero Trust** (one-page "get started" is fine, free plan):
   https://one.dash.cloudflare.com/
3. Left menu: **Networks → Tunnels** → **Create a tunnel** →
   choose **Cloudflared** → give it a name (e.g. `win-agent`).
4. **Install and run a connector**: it shows a command with a long
   `--token eyJ...`. Copy that token.
5. On your PC, edit the Cloudflare Tunnel window (or run directly):
   ```
   cloudflared tunnel run --token eyJ....PASTE.YOUR.TOKEN....
   ```
   (Keep the agent itself running as usual — this replaces the
   `cloudflared tunnel --url http://127.0.0.1:8787` command.)
6. Back in the dashboard: **Public hostname** → add one:
   - subdomain: pick anything (e.g. `prasa-agent`)
   - domain: your domain (if you have one on Cloudflare) — or leave the
     tunnel's `*.cfargotunnel.com` try-route if offered
   - service: `HTTP` → `localhost:8787`
7. That hostname is now your PERMANENT agent URL. Give it to the AI once —
   it survives restarts of the agent, cloudflared, and the PC.

## Making it the default

Replace the tunnel line in `run.bat` (`:tunnel_if_needed` section):

    start "Cloudflare Tunnel" cmd /k cloudflared tunnel run --token eyJ.YOUR.TOKEN

Better: keep the token OUT of the bat file —

    set /p CFTOKEN=<tunnel_token.txt
    start "Cloudflare Tunnel" cmd /k cloudflared tunnel run --token %CFTOKEN%

(save the token into `tunnel_token.txt` in the agent folder and add that
file to `.gitignore`).

## Notes

- The agent's v1.6.4 watchdog coexists with a named tunnel: if cloudflared
  dies, the watchdog restarts it in QUICK mode (new URL) — with a named
  tunnel, prefer letting cloudflared's own auto-reconnect handle it; you can
  simply close the watchdog-restarted instance and start the token mode
  again. (A future release may supervise token mode directly.)
- Auth is unchanged: the Bearer token still protects every endpoint.
- Public hostname + Bearer token = fine. Do NOT remove the token check.
