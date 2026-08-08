# PokerTimer — Separate Rebuy Pricing — Design Spec

**Date:** 2026-08-08
**Status:** Approved
**Amends:** `2026-08-08-poker-timer-design.md` (the original PokerTimer spec, already implemented and merged)

## What this is

Today the admin panel tracks a single "Entries (incl. rebuys)" count, and the prize
pool is `entries × buy_in` — every entry, original or rebuy, is priced the same.
In practice a rebuy is often cheaper than the original buy-in (e.g. 50kr original,
25kr rebuy) and can hand out a different starting stack. This spec splits entries
into two priced, stacked categories so the prize pool and chip count reflect that.

## Data model changes

Extends `TournamentState` (backend `app/engine.py`) with two new config fields and
one new count field, and renames one existing field:

- `total_entries` → **renamed to `entries`**, and its meaning narrows: today it
  counts every buy-in including rebuys (there's only one counter); after this
  change it counts ONLY original buy-ins. Rebuys move to the new `rebuy_count`
  field below. This is a real behavior change, not just a rename — it's driven
  by the admin UI splitting one "+" button into two ("Entries" and "Rebuys").
- **New:** `rebuy_count: int = 0` — count of rebuys. Mirrors `early_bird_count`.
- **New:** `rebuy_price: Decimal = Decimal("0")` — price per rebuy, exact decimal
  like `buy_in`. Never a float; serialized as a string, same rule as every other
  money field.
- **New:** `rebuy_stack: int = 0` — starting chips per rebuy. Mirrors
  `starting_stack`.

There is no existing production data to migrate — this is a pre-release local app,
so the rename is a clean break, not a compatibility concern.

## Money math changes (`app/engine.py`)

- `compute_prize_pool` becomes a function of both entry types:
  `pool = entries × buy_in + rebuy_count × rebuy_price`.
- `compute_chips_in_play` becomes:
  `chips = entries × starting_stack + rebuy_count × rebuy_stack + early_bird_count × early_bird_bonus`.
- Both new numeric inputs (`rebuy_price`, `rebuy_stack`) get the same validation
  already applied to their siblings: `rebuy_price` goes through the same
  non-negative + magnitude-bounded check as `buy_in` (the exact guard added during
  Task 9's hardening, which exists specifically to stop a huge/malformed value from
  breaking the money math); `rebuy_stack` and `rebuy_count` go through the same
  bounded non-negative integer check already applied to `starting_stack` and
  `total_entries`.

## Reset behavior (`TournamentState.reset()`)

Extends the existing split cleanly — no new categories, just two more fields
slotting into the existing two buckets:

- **Zeroed on reset** (a count, like `early_bird_count`): `rebuy_count`.
- **Preserved across reset** (config, like `buy_in`/`starting_stack`):
  `rebuy_price`, `rebuy_stack`.

## WebSocket protocol changes

- `set_counts` command gains `rebuy_count` as a settable field, alongside the
  existing `total_entries`→`entries` (renamed), `players_remaining`,
  `early_bird_count`.
- `set_config` command gains `rebuy_price` and `rebuy_stack` as settable fields,
  alongside the existing `buy_in`, `currency`, `starting_stack`,
  `early_bird_bonus`.
- `to_dict()`'s top-level state and `computed` block change field names/add
  fields as described above; no other computed field (`payouts`,
  `average_stack`, `level_number`, etc.) changes shape.

## Admin UI changes (`MoneyPanel.svelte`)

- The config grid (currently Buy-in / Currency / Starting stack / Early-bird
  chips) gains two more fields: **Rebuy price** and **Rebuy stack**, applied via
  the same "Apply" button and `set_config` call as the existing fields.
- The counter rows (currently "Entries (incl. rebuys)" / "Players remaining" /
  "Early birds") change to four rows: **Entries** / **Rebuys** / **Players
  remaining** / **Early birds** — each with its own `+`/`−`, following the exact
  pattern already used (`bump(field, delta)` sending `set_counts` with the new
  absolute value, clamped at 0).
- The pool/avg-stack summary line at the bottom is unchanged — it already reads
  `computed.prize_pool`/`computed.average_stack`, which now reflect the combined
  math automatically.

## What does NOT change

- The public display page (`Display.svelte`) — it only ever showed the combined
  pool and payouts, never a raw entry count, so nothing there needs to change.
  Confirmed with the user: the combined pool total is enough, no entries/rebuys
  breakdown needs to surface on the TV display.
- `PayoutEditor.svelte`, `StructureEditor.svelte`, `TemplateBar.svelte`,
  `ClockControls.svelte` — untouched.
- Payout computation itself (`compute_payouts`) — unaffected; it only ever
  consumed the already-computed `pool` value, not the entry counts directly.

## Testing

Same bar as the original implementation: unit tests for the two updated money
functions (mixed entries+rebuys at different prices/stacks, zero-rebuy case
behaving identically to today, exact-decimal payouts still summing to the
pool), a `set_config`/`set_counts` validation test for the two new fields
(reusing the existing magnitude-bound test pattern), and a reset test
confirming `rebuy_count` zeroes while `rebuy_price`/`rebuy_stack` survive.
Frontend: no new automated tests required (matches the project's existing
frontend testing bar — `MoneyPanel.svelte` has none today either); verified via
build + a live check against the running app, same as the original admin panel
tasks.
