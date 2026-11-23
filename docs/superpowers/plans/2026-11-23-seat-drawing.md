# Seat Drawing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Named players, a random even seat draw across tables, late joiners seated into empty seats, and a seating view on the TV that the admin can toggle.

**Architecture:** Seating lives in `TournamentState` (`backend/app/engine.py`), next to the counts. It is persisted and broadcast through the existing `TournamentManager` command path. A pure JS helper (`frontend/src/lib/seating.js`) turns the flat player list into per-table seat rows for both the admin panel and the TV.

**Tech Stack:** Python/FastAPI and pytest (backend), Svelte 5 runes and vitest (frontend).

**Spec:** `docs/superpowers/specs/2026-11-23-seat-drawing-design.md`

## Global Constraints

- Player names are trimmed, 1–30 chars, and unique case-insensitively.
- Defaults are `table_count = 1`, `seats_per_table = 9` and `show_seating = False`.
- `reset()` clears `players` and sets `show_seating = False`. It keeps `table_count`/`seats_per_table`.
- Adding a player raises `entries` and `players_remaining` by 1. Removing one lowers both by 1, floored at 0.
- A late joiner (added after a draw) gets a random empty seat at the table with the fewest players. Nobody else moves.
- Randomness comes from `random.SystemRandom()`, injectable as `TournamentState.rng`.
- Every engine command validates fully before mutating, and raises `EngineError` with an admin-safe message.
- Backend tests run from `backend/` with `python -m pytest`. Frontend tests run from `frontend/` with `npm test`.

## Plan calls (not in the spec)

- `draw_seats` takes `table_count` and `seats_per_table` and applies them atomically before dealing. Otherwise there's no way to go from 2 tables to 1 after a draw, because `set_seating_config` rejects layouts that strand seated players, as the spec requires.
- "A draw has happened" means at least one player has a non-`None` table.
- `draw_seats` with zero players raises `"Add players before drawing"`.
- The TV seating view shows a small corner clock while status is `running`/`paused`.

## Review Focus

1. **An old snapshot without seating keys** (saved before this feature) must load, using the defaults rather than a `KeyError` on startup. Test in Task 1.
2. **A late joiner when every seat is full** must fail without bumping `entries`/`players_remaining`. Test in Task 2.
3. **A draw with more players than seats** must fail and leave existing seats untouched. Test in Task 2.
4. **Showing seating before any draw** must make the TV list the names as "not seated yet" rather than show blank tables. Test in Task 4.
5. **Names differing only in case or surrounding spaces** ("anna " vs "Anna") count as duplicates, and remove works on the trimmed, case-insensitive name. Test in Task 2.

---

### Task 1: Seating state, config, toggle, serialization

**Files:**
- Modify: `backend/app/engine.py` (`TournamentState` fields, `reset`, new methods, `to_dict`, `from_dict`)
- Test: `backend/tests/test_engine_seating.py` (create)

**Interfaces:**
- Produces: fields `players: list[dict]` (each `{"name": str, "table": int | None, "seat": int | None}`), `table_count: int`, `seats_per_table: int`, `show_seating: bool`, `rng: random.Random` (`field(default_factory=random.SystemRandom, repr=False, compare=False)`, not serialized); `set_seating_config(table_count: int, seats_per_table: int) -> None`; `set_show_seating(show: bool) -> None`; `to_dict()` gains keys `players`, `table_count`, `seats_per_table`, `show_seating`.

- [ ] **Step 1: Write the failing tests**

```python
def test_seating_defaults():
    s = TournamentState()
    assert (s.players, s.table_count, s.seats_per_table, s.show_seating) == ([], 1, 9, False)

def test_set_seating_config_validates():
    s = TournamentState()
    s.set_seating_config(2, 8)
    assert (s.table_count, s.seats_per_table) == (2, 8)
    for bad in [(0, 8), (2, 0), (True, 8)]:
        with pytest.raises(EngineError):
            s.set_seating_config(*bad)

def test_set_seating_config_rejects_stranding_seated_players():
    s = TournamentState(table_count=2, seats_per_table=9,
                        players=[{"name": "Anna", "table": 2, "seat": 9}])
    with pytest.raises(EngineError):
        s.set_seating_config(1, 9)
    with pytest.raises(EngineError):
        s.set_seating_config(2, 8)
    assert (s.table_count, s.seats_per_table) == (2, 9)

def test_set_show_seating():
    s = TournamentState()
    s.set_show_seating(True)
    assert s.show_seating is True
    with pytest.raises(EngineError):
        s.set_show_seating("yes")

def test_reset_clears_players_keeps_layout():
    s = TournamentState(table_count=2, seats_per_table=8, show_seating=True,
                        players=[{"name": "Anna", "table": 1, "seat": 3}])
    s.reset()
    assert s.players == [] and s.show_seating is False
    assert (s.table_count, s.seats_per_table) == (2, 8)

def test_seating_roundtrip():
    s = TournamentState(table_count=2, seats_per_table=8, show_seating=True,
                        players=[{"name": "Anna", "table": 1, "seat": 3}])
    restored = TournamentState.from_dict(s.to_dict())
    assert restored.players == s.players
    assert (restored.table_count, restored.seats_per_table, restored.show_seating) == (2, 8, True)

def test_from_dict_without_seating_keys_uses_defaults():  # Review Focus 1
    data = TournamentState().to_dict()
    for key in ("players", "table_count", "seats_per_table", "show_seating"):
        del data[key]
    restored = TournamentState.from_dict(data)
    assert (restored.players, restored.table_count, restored.seats_per_table,
            restored.show_seating) == ([], 1, 9, False)
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_engine_seating.py -v`
Expected: FAIL (unexpected keyword `players` / missing attributes)

- [ ] **Step 3: Implement**

Add the fields and both methods to `engine.py`. The int checks use the same `isinstance(value, bool) or not isinstance(value, int)` pattern as `set_counts`, with error messages such as `"Tables must be a whole number of at least 1"`. The stranding check looks for any player with `table > table_count or seat > seats_per_table` and raises `"Some players are seated outside that layout — redraw instead"`. `from_dict` reads the four new keys with `.get(key, default)` and copies each player dict. `to_dict` emits copies of the player dicts.

- [ ] **Step 4: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine.py backend/tests/test_engine_seating.py
git commit -m "feat: seating state, layout config and TV toggle in engine"
```

---

### Task 2: Add/remove players and draw seats

**Files:**
- Modify: `backend/app/engine.py`
- Test: `backend/tests/test_engine_seating.py`

**Interfaces:**
- Consumes: the Task 1 fields and `set_seating_config`.
- Produces: `add_player(name: str) -> None`, `remove_player(name: str) -> None`, `draw_seats(table_count: int, seats_per_table: int) -> None`.

- [ ] **Step 1: Write the failing tests** (seed with `s.rng = random.Random(1)` for determinism)

```python
def names(n): return [f"P{i}" for i in range(n)]

def seeded(**kw):
    s = TournamentState(**kw); s.rng = random.Random(1); return s

def test_add_player_counts_as_entry():
    s = seeded(entries=2, players_remaining=2)
    s.add_player("  Anna ")
    assert s.players == [{"name": "Anna", "table": None, "seat": None}]
    assert (s.entries, s.players_remaining) == (3, 3)

def test_add_player_rejects_bad_names():  # Review Focus 5
    s = seeded()
    s.add_player("Anna")
    for bad in ["anna ", "", "   ", "x" * 31, 5]:
        with pytest.raises(EngineError):
            s.add_player(bad)
    assert s.entries == 1

def test_remove_player_case_insensitive_and_floored():
    s = seeded()
    s.add_player("Anna")
    s.set_counts(entries=0, players_remaining=0)
    s.remove_player(" ANNA")
    assert s.players == [] and (s.entries, s.players_remaining) == (0, 0)
    with pytest.raises(EngineError):
        s.remove_player("Nobody")

def test_draw_even_and_unique():
    s = seeded()
    for n in names(14): s.add_player(n)
    s.draw_seats(2, 9)
    per_table = Counter(p["table"] for p in s.players)
    assert per_table == {1: 7, 2: 7}
    spots = {(p["table"], p["seat"]) for p in s.players}
    assert len(spots) == 14 and all(1 <= seat <= 9 for _, seat in spots)
    assert (s.table_count, s.seats_per_table) == (2, 9)

def test_draw_uneven_differs_by_at_most_one():
    s = seeded()
    for n in names(13): s.add_player(n)
    s.draw_seats(3, 9)
    sizes = Counter(p["table"] for p in s.players).values()
    assert max(sizes) - min(sizes) <= 1

def test_draw_rejects_too_many_players_without_mutating():  # Review Focus 3
    s = seeded()
    for n in names(4): s.add_player(n)
    s.draw_seats(1, 9)
    before = [dict(p) for p in s.players]
    with pytest.raises(EngineError):
        s.draw_seats(1, 3)                     # 4 players, 3 seats
    assert s.players == before and s.seats_per_table == 9

def test_draw_requires_players():
    with pytest.raises(EngineError):
        seeded().draw_seats(1, 9)

def test_late_joiner_goes_to_shortest_table_nobody_moves():
    s = seeded()
    for n in names(5): s.add_player(n)
    s.draw_seats(2, 9)            # 3 + 2
    before = [dict(p) for p in s.players]
    s.add_player("Late")
    assert s.players[:5] == before
    late = s.players[-1]
    assert late["table"] == min(Counter(p["table"] for p in before).items(),
                                key=lambda kv: kv[1])[0]
    assert (late["table"], late["seat"]) not in {(p["table"], p["seat"]) for p in before}

def test_late_joiner_when_full_fails_without_counting():  # Review Focus 2
    s = seeded()
    for n in names(2): s.add_player(n)
    s.draw_seats(1, 2)
    with pytest.raises(EngineError, match="No empty seats"):
        s.add_player("Late")
    assert len(s.players) == 2 and s.entries == 2
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_engine_seating.py -v`
Expected: the new tests FAIL with `AttributeError` (no `add_player`)

- [ ] **Step 3: Implement the three methods in `engine.py`**

`add_player`: reject non-str, empty after trim, length over 30, or a casefold duplicate. If a draw has happened, pick the target seat before appending or counting. The candidate tables are those with an empty seat. Choose the one with the fewest players (break ties with `self.rng.choice`), then `self.rng.choice` among its empty seat numbers. If no table has room, raise `"No empty seats — add a table or redraw"`. Then append and bump `entries`/`players_remaining`.

`remove_player`: find by trimmed casefold name, else raise `"No player named …"`. Delete the player and decrement both counts with `max(0, …)`.

`draw_seats`: validate the ints (the same messages as Task 1), require at least 1 player, and require `len(players) <= table_count * seats_per_table`. Only then set the layout and deal:

```python
order = list(range(len(self.players)))
self.rng.shuffle(order)
by_table = {t: [] for t in range(1, table_count + 1)}
for i, idx in enumerate(order):
    by_table[i % table_count + 1].append(idx)
for table, idxs in by_table.items():
    for idx, seat in zip(idxs, self.rng.sample(range(1, seats_per_table + 1), len(idxs))):
        self.players[idx]["table"], self.players[idx]["seat"] = table, seat
```

Test imports: `import random`, `from collections import Counter`, `import pytest`, `from app.engine import EngineError, TournamentState`.

- [ ] **Step 4: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine.py backend/tests/test_engine_seating.py
git commit -m "feat: add/remove players, seat draw and late-joiner seating"
```

---

### Task 3: Manager commands

**Files:**
- Modify: `backend/app/manager.py` (`_apply`)
- Test: `backend/tests/test_manager.py`

**Interfaces:**
- Consumes: the Task 1–2 engine methods.
- Produces these WebSocket actions for the frontend: `add_player {name}`, `remove_player {name}`, `draw_seats {table_count, seats_per_table}`, `set_seating_config {table_count, seats_per_table}`, `set_show_seating {show}`.

- [ ] **Step 1: Write the failing tests** (reuse `make_manager`/`FakeWebSocket`)

```python
def test_seating_commands_roundtrip(clean_db):
    manager = make_manager()
    admin = FakeWebSocket(); manager.clients = [admin]
    for name in ["Anna", "Mads", "Sofie"]:
        asyncio.run(manager.handle_command(admin, "add_player", {"name": name}))
    asyncio.run(manager.handle_command(admin, "draw_seats",
                                       {"table_count": 2, "seats_per_table": 9}))
    asyncio.run(manager.handle_command(admin, "set_show_seating", {"show": True}))
    state = admin.sent[-1]["state"]
    assert admin.sent[-1]["type"] == "state"
    assert state["show_seating"] is True and state["entries"] == 3
    assert all(p["table"] in (1, 2) for p in state["players"])

def test_seating_command_bad_payload_is_error(clean_db):
    manager = make_manager()
    admin = FakeWebSocket()
    asyncio.run(manager.handle_command(admin, "draw_seats", {"table_count": "2"}))
    asyncio.run(manager.handle_command(admin, "set_show_seating", {}))
    assert [m["type"] for m in admin.sent] == ["error", "error"]
    assert manager.state.players == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_manager.py -k seating -v`
Expected: FAIL (`Unknown command`)

- [ ] **Step 3: Add the five `elif` branches to `_apply`**

The ints go through `_require_int`. `name` is passed as-is, since the engine validates the type. For `show`, raise `EngineError("show must be true or false")` unless `isinstance(p.get("show"), bool)`.

- [ ] **Step 4: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/manager.py backend/tests/test_manager.py
git commit -m "feat: websocket commands for seating"
```

---

### Task 4: Seating layout helper

**Files:**
- Create: `frontend/src/lib/seating.js`
- Test: `frontend/tests/seating.test.js` (create)

**Interfaces:**
- Produces: `seatingTables(players, tableCount, seatsPerTable) -> { tables: Array<{ table: number, seats: Array<{ seat: number, name: string | null }> }>, unseated: string[] }`. Tables are numbered 1..tableCount. Each has seats 1..seatsPerTable in order, with `name: null` for empty seats. `unseated` lists the names whose table is null, in insertion order.

- [ ] **Step 1: Write the failing tests**

```js
import { describe, expect, it } from 'vitest';
import { seatingTables } from '../src/lib/seating.js';

describe('seatingTables', () => {
  it('lays out seats per table with empties', () => {
    const { tables, unseated } = seatingTables(
      [{ name: 'Anna', table: 1, seat: 2 }, { name: 'Mads', table: 2, seat: 1 }], 2, 3);
    expect(tables).toEqual([
      { table: 1, seats: [{ seat: 1, name: null }, { seat: 2, name: 'Anna' }, { seat: 3, name: null }] },
      { table: 2, seats: [{ seat: 1, name: 'Mads' }, { seat: 2, name: null }, { seat: 3, name: null }] },
    ]);
    expect(unseated).toEqual([]);
  });

  it('lists players not seated yet', () => {  // Review Focus 4
    const { unseated } = seatingTables(
      [{ name: 'Anna', table: null, seat: null }, { name: 'Mads', table: null, seat: null }], 1, 9);
    expect(unseated).toEqual(['Anna', 'Mads']);
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npm test`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `seatingTables` in `frontend/src/lib/seating.js`**

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/seating.js frontend/tests/seating.test.js
git commit -m "feat: seating layout helper"
```

---

### Task 5: Admin seating panel

**Files:**
- Create: `frontend/src/lib/admin/SeatingPanel.svelte`
- Modify: `frontend/src/lib/Admin.svelte` (import and place `<SeatingPanel />` after `<MoneyPanel />`)

**Interfaces:**
- Consumes: `conn`, `send` from `../connection.svelte.js`; the Task 3 actions; `seatingTables` from Task 4; the state keys `players`, `table_count`, `seats_per_table`, `show_seating`.

- [ ] **Step 1: Build the panel**, following `MoneyPanel.svelte`'s conventions (`<section class="panel">`, `<h3>Seating</h3>`, `.row`, a seed-once `$effect` for the inputs):
  - Inputs for **Tables** and **Seats per table**, seeded from state.
  - A name input and an **Add** button. Enter submits, and the input clears after sending.
  - A player list. Each row shows `name`, `T{table} · S{seat}` or "not seated", and a `×` button that sends `remove_player`.
  - A **Draw seats** button that sends `draw_seats` with the two inputs parsed as ints. If any player is already seated, first run `confirm('Redraw everyone\'s seats?')`.
  - A **Show seating on TV** toggle button. Its label switches to "Back to clock" while `s.show_seating` is on, and it sends `set_show_seating {show: !s.show_seating}`.

- [ ] **Step 2: Build check**

Run: `cd frontend && npm run build`
Expected: the build succeeds with no Svelte errors or warnings from the new file

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/admin/SeatingPanel.svelte frontend/src/lib/Admin.svelte
git commit -m "feat: admin seating panel"
```

---

### Task 6: TV seating view and end-to-end check

**Files:**
- Modify: `frontend/src/lib/Display.svelte`

**Interfaces:**
- Consumes: `seatingTables` from Task 4; `formatClock` from `format.js`; the state key `show_seating`.

- [ ] **Step 1: Add the seating branch** immediately after `{#if !s}` (`{:else if s.show_seating}`), so it wins over the setup, finished and running screens. It shows a "SEATING" title, then one column per table in a CSS grid (`repeat(table_count, 1fr)`) with a "Table N" heading. Each row reads `seat  name`, or `—` when empty. Text is sized in `vw` like the rest of the screen, so 2 tables × 9 seats fit a 1080p TV without scrolling. If `unseated` is non-empty, add a "Not seated yet:" line listing those names. When `s.status` is `running` or `paused`, show `formatClock(s.seconds_remaining)` in a corner.

- [ ] **Step 2: Build check**

Run: `cd frontend && npm run build`
Expected: the build succeeds

- [ ] **Step 3: Manual end-to-end check**

Run `npm start` from the repo root. On `/admin`, add 10 names and draw on 2 tables × 9, then turn on **Show seating on TV**. On `/`, expect two tables of 5 and the remaining seats shown as `—`. Start the clock and toggle back: the clock should be running. Add "Late" and toggle seating on again: only Late is new, everyone else is in the same seat, and Entries is 11. Toggle off, then Reset: the seating view should not reappear.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/Display.svelte
git commit -m "feat: seating view on the TV display"
```
