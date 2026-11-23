# Seat drawing — short design

## Context
Poker nights sometimes run on two or more tables. The host wants the app to randomly
draw seats and show them on the TV, so people can find their seat. The seating view
can be toggled on and off from the admin panel: on at the start of the night, back to
the clock afterwards, and on again whenever a late joiner is seated. Today the app has
no player names at all. Players are only counters (`entries`, `players_remaining`) in
`backend/app/engine.py`.

## Goals / non-goals
- **Goals:** a named player list, a random even draw across N tables × M seats, late
  joiners placed in a random empty seat at the shortest table, and a TV seating view the
  admin toggles.
- **Non-goals:** table balancing, bust tracking by name, suggestions to move players,
  breaking or merging tables. Players are moved by hand, which was the user's choice.
- **Anti-goals:** reshuffling people who are already seated when someone joins late.
  The seating view must never get stuck covering the clock.

## Approaches (user picked A)
- **A. Seating inside `TournamentState` (chosen):** reuses the existing persist and
  WebSocket broadcast, survives restarts, and keeps names and entries in step in one
  place.
- B. A separate seating module with its own storage. Rejected: it doubles the
  save/broadcast plumbing and makes it awkward to keep names and entries in step.
- (Frontend-only was ruled out: the TV is a separate device.)

## Design
**State (engine.py `TournamentState`, plus `to_dict`/`from_dict`):**
- `players: list[{name, table, seat}]`, where table/seat are `None` until drawn
- `table_count: int` (default 1) and `seats_per_table: int` (default 9). These are kept on reset, like buy-in.
- `show_seating: bool` (default False)
- `reset()` clears `players` and sets `show_seating = False`.

**Engine commands** (plain methods raising `EngineError`, following the existing pattern):
- `add_player(name)`: name trimmed, 1–30 chars, unique (case-insensitive). It bumps
  `entries` and `players_remaining` by 1, like the Entries `+` does today. If a draw has
  already happened, the player gets a random empty seat at the table with the fewest
  players right away. If every seat is full, it raises "No empty seats".
- `remove_player(name)`: decrements `entries`/`players_remaining` (floored at 0). It is meant for typos.
- `draw_seats()`: shuffles all players and deals them round-robin across tables, so
  sizes differ by at most 1, then assigns random seat numbers within each table. It
  requires players ≤ table_count × seats_per_table. Running it again redraws everyone
  (the admin UI confirms first if anyone is already seated).
- `set_seating_config(table_count, seats_per_table)`: both ≥ 1. It is rejected if it would leave
  existing seat assignments out of range.
- `set_show_seating(bool)`.
- Randomness: `random.SystemRandom`, injectable for tests.

**Manager (`backend/app/manager.py`):** wire the new command names into `handle_command`
with the same payload validation as the existing commands (`_require_int`, string checks).

**Admin (new `frontend/src/lib/admin/SeatingPanel.svelte`, added in `Admin.svelte`):**
the tables and seats-per-table inputs, a name input with an Add button, a player list with
table/seat and a remove ×, a **Draw seats** button, and a **Show seating on TV** toggle.
The Entries `+` in `MoneyPanel` stays for unnamed entries.

**TV (`frontend/src/lib/Display.svelte`):** when `show_seating` is true, the seating
view replaces whatever is showing. This includes the `setup` status, since the draw
happens before the clock starts. It shows one column per table, with seats in order,
empty seats as "—", and large readable names. The clock keeps running in the backend.
A small corner clock in the seating view is the builder's call.

```
            SEATING
  Table 1              Table 2
  1  Anna              1  Mads
  2  Jonas             2  Sofie
  3  —                 3  Kasper
```

## Calls I made (user to check)
- Adding a name counts as an entry. Rebuys and the Entries `+` are unchanged.
- Default is 9 seats per table.
- A late joiner goes to a random empty seat at the shortest table.
- Removing a player also reduces the entry count.

## After approval
1. Commit this as `docs/superpowers/specs/2026-11-23-seat-drawing-design.md`.
2. Invoke superpowers:writing-plans for the implementation plan.

## Verification
- Backend pytest, with new tests in `backend/tests/test_engine_seating.py`: draw evenness
  (e.g. 14 players on 2×9 gives 7/7), unique seats, late-joiner placement, full-table
  error, entries kept in step, reset behaviour, and a serialize round-trip. Also manager
  command tests in `test_manager.py`.
- Manual: `npm start`, add about 10 names on `/admin`, draw on 2 tables, toggle the TV view on `/`,
  add a late joiner and check that only they get a new seat, then toggle back to the clock.
