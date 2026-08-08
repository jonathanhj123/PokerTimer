# PokerTimer — Design Spec

**Date:** 2026-08-08
**Status:** Approved pending final review

## What this is

A self-hosted tournament clock for a friend group's poker nights, in the spirit of the
defunct bullets.poker. One screen (a TV or monitor, fullscreened) shows the countdown,
blinds, and payouts to everyone; an admin logs in from a phone or laptop to control the
clock and change settings while the game runs.

## Deployment

- **Phase 1 (this spec):** runs on one host machine on the local network. The TV opens
  `http://<host-ip>:<port>/`, the admin opens `/admin` from any device on the same WiFi.
- **Phase 2 (later, out of scope):** expose the same running app through a free
  Cloudflare Tunnel so the admin panel works from anywhere. Nothing in Phase 1 may
  assume localhost-only (e.g. cookies must not be `Secure`-only-localhost hacks) so the
  tunnel can be added without rework.

## Stack

- **Backend:** Python, FastAPI. One process. REST for auth/setup, WebSocket for live sync.
- **Frontend:** Svelte. Two routes: `/` (display) and `/admin` (control panel).
- **Persistence:** SQLite via SQLAlchemy, so a later switch to hosted Postgres (user has
  a Neon account) is a connection-string change. Snapshots written atomically.
- **Auth:** single shared admin password, stored as a hash in config/env (not the DB).
  Login sets a signed session cookie; WebSocket admin commands are only accepted from
  authenticated connections. The display page requires no auth.

## Data model

### Blind structure templates (SQLite table)

Reusable named structures (e.g. "Friday Night"). Each is an ordered list of entries:

- **Level:** small blind, big blind, ante (integer, 0 = no ante), duration (minutes)
- **Break:** duration (minutes)

### Live tournament state (singleton snapshot, persisted on every change)

- `status` — `setup` | `running` | `paused` | `finished`
- `structure` — the entry list, **copied** from a template at start. Mid-game edits
  change the copy only; templates change only via explicit "save as template".
- `current_level_index`, `seconds_remaining`
- `buy_in` (amount), `currency` (display symbol, e.g. `$`, `€`, `kr`; no exchange logic)
- `total_entries` (buy-ins + rebuys), `players_remaining`
- `starting_stack` — chips per entry (rebuys get the same stack)
- `early_bird_bonus` — extra chips for showing up on time (e.g. 1,000)
- `early_bird_count` — how many players received the bonus (rebuys never touch it)
- `payout_percentages` — ordered list (e.g. `[50, 30, 20]`); its length is the number
  of paid places; must sum to 100 (server-validated)

### Computed (never stored)

- Prize pool = `total_entries × buy_in`
- Payout per place = `pool × percentage / 100` — **exact, no rounding.** Decimal
  arithmetic (not floats). Displayed with decimals when present ($112.50), clean when
  not ($110).
- Chips in play = `total_entries × starting_stack + early_bird_count × early_bird_bonus`
- Average stack = chips in play ÷ players remaining, rounded to whole chips
- Next level = the entry after `current_level_index`

## Timer engine

A background task in the server ticks once per second, decrements `seconds_remaining`,
and advances `current_level_index` when it hits zero. The server is the sole source of
truth; clients only render broadcast state.

Edge cases:

- **Editing the current level's duration:** elapsed time stays elapsed. 15→20 min with
  3:00 left shows 8:00 left. If the new duration ≤ elapsed, the level ends now.
- **Deleting the current level:** clock jumps to the start of the next entry.
- **Structure exhausted:** the last level holds — blinds stay, clock parks at 0:00 with
  a "final level" indicator. No crash, no loop.
- **Concurrent admins:** last write wins; all clients re-sync immediately. No locking.
- **Restart mid-game:** state reloads from the snapshot and resumes **paused** — wall
  time that passed during the outage is not counted. Admin resumes manually.

## Display page (`/`)

Layout locked via mockups (see `.superpowers/brainstorm/` session, final: `layout-a-v6`):

- Vertically centered main stack: `LEVEL n` label, giant clock, current blinds, ante
  (only if nonzero), "Next: SB / BB" below.
- Vertically centered right-side block: players left, average stack, prize pool,
  payouts as tight `1st $110` rows.
- Large typography throughout — designed for a fullscreened TV read from across a room.

Behavior:

- **Level change:** alert sound + screen flash highlighting the new blinds ~5 s.
  Browsers block audio before first interaction, so the page shows a one-time
  "tap to enable sound" prompt on load; the flash works regardless.
- **Ante = 0:** ante is not rendered at all (never shown as "0").
- **No starting stack set:** the average-stack line is not rendered.
- **Break:** clock counts down, "BREAK" replaces the blinds, next level's blinds shown
  below ("Back at: 200/400").
- **Paused:** unmistakable "PAUSED" indicator over the clock.
- **Connection loss:** "reconnecting…" badge, auto-retry every few seconds, full
  re-sync on reconnect. The display extrapolates between one-second ticks for
  smoothness but never runs its own countdown as truth.
- **Finished:** end screen with final payouts until the admin resets.

## Admin panel (`/admin`)

All actions work live, mid-game; every change broadcasts to all screens within a second.

**Clock:** start / pause / resume / end; previous/next level; add/subtract minutes;
set clock to an exact time.

**Structure:** full table editor (add/remove/reorder levels and breaks, edit any
field, including the current level); save current structure as a named template; load
a template (setup only — loading mid-game is ambiguous about the current level).

**Money & players:** buy-in amount; currency symbol; starting stack; early-bird bonus
amount; `+/−` entries (rebuys, with decrement for misclicks); `+/−` players remaining;
`+/−` early-bird count; payout editor — add/remove paid places, set percentages, live
sum-to-100 validation, live preview of computed amounts.

## Error handling

- All validation server-side (percentages sum to 100, positive blinds, non-negative
  counts). Invalid commands are rejected with an inline UI error; state never corrupts.
- Snapshot writes are atomic — a crash mid-write cannot half-save a tournament.
- Restart-resumes-paused (see Timer engine).

## Testing

- **Unit (thorough):** timer engine and money math — level advancement, mid-level
  duration edits, exact payout decimals, chips in play, average stack. Pure logic,
  no I/O; this is where a silent bug ruins a game night.
- **API/WebSocket:** login flow; admin command → broadcast state reflects it.
- **Frontend (light):** components render state and send commands; no heavy coverage.

## Explicitly out of scope (Phase 1)

- Cloudflare Tunnel / remote access (Phase 2)
- Named player roster, eliminations by name, "who got early-bird" tracking — headcount
  only; the math needs only counts
- Multiple admin accounts (single shared password now; nothing blocks adding accounts
  later)
- Multiple simultaneous tournaments (one live tournament, singleton state)
- Exchange rates / multi-currency math (currency is a display symbol)
