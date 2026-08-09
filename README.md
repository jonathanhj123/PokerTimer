# PokerTimer

Self-hosted poker tournament clock for home games. One machine on your WiFi runs it;
the TV shows the fullscreen timer at `/`, the tournament admin controls everything
live from a phone at `/admin`.

Spec: `docs/superpowers/specs/2026-08-08-poker-timer-design.md`

## One-time setup

Requires Python 3.11+ and Node 18+.

    cd backend
    python -m venv .venv
    .venv\Scripts\activate          # PowerShell: .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    python scripts/setup_env.py     # choose your admin password

    cd ../frontend
    npm install
    npm run build

## Poker night

    npm start

or, manually:

    cd backend
    .venv\Scripts\activate           # PowerShell: .venv\Scripts\Activate.ps1
    uvicorn app.main:app --host 0.0.0.0 --port 8000

Run as a single process (do not add `--workers`) — the tournament state lives in
one process's memory, so multiple workers would each run their own disagreeing
tournament.

Find this machine's LAN IP with `ipconfig` (IPv4 Address), then:

- **TV / display:** `http://<ip>:8000/` — fullscreen it (F11), tap the 🔊 chip once
- **Admin (your phone):** `http://<ip>:8000/admin`

First run: allow Python through the Windows Firewall prompt (private networks).
If the server restarts mid-game it comes back **paused** at the right level — hit
Resume when ready.

## Development

    # terminal 1 (PowerShell: .venv\Scripts\Activate.ps1 instead of activate)
    cd backend && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000
    # terminal 2
    cd frontend && npm run dev      # → http://localhost:5173

## Tests

    cd backend && python -m pytest tests -v
    cd frontend && npm test
