<script>
  import { onMount } from 'svelte';
  import { conn, send } from '../connection.svelte.js';
  import { isRegular, regularChips } from '../seating.js';

  const s = $derived(conn.state);

  let tables = $state('');
  let seats = $state('');
  let newName = $state('');
  // Plain (non-reactive) flag: while an input has focus, don't overwrite
  // what the admin is typing with the server's value.
  let editing = false;

  // Follow the server's layout (another admin may change it), and snap back
  // to it when a change is rejected (lastError).
  $effect(() => {
    const tableCount = s.table_count;
    const seatCount = s.seats_per_table;
    conn.lastError;
    if (!editing) {
      tables = String(tableCount);
      seats = String(seatCount);
    }
  });

  function layout() {
    return {
      table_count: parseInt(tables, 10) || 0,
      seats_per_table: parseInt(seats, 10) || 0,
    };
  }

  // Lets a host add a table mid-game for late joiners without a redraw.
  function applyLayout() {
    editing = false;
    send('set_seating_config', layout());
  }

  const anySeated = $derived(s.players.some((p) => p.table !== null));

  function addPlayer(event) {
    event.preventDefault();
    const name = newName.trim();
    if (!name) return;
    send('add_player', { name });
    newName = '';
  }

  function draw() {
    if (anySeated && !confirm("Redraw everyone's seats?")) return;
    send('draw_seats', layout());
  }

  // --- saved regulars (REST, outside the game state so Reset keeps them) ---
  let regulars = $state([]);
  let editRegulars = $state(false);
  let regularsMessage = $state('');
  const chips = $derived(regularChips(regulars, s.players));

  async function refreshRegulars() {
    const response = await fetch('/api/regulars');
    if (response.ok) {
      regulars = await response.json();
      regularsMessage = '';
    } else {
      regularsMessage = 'Failed to load regulars';
    }
  }
  onMount(refreshRegulars);

  async function saveRegular(name) {
    const response = await fetch('/api/regulars', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!response.ok) {
      regularsMessage = (await response.json()).detail || 'Failed to save regular';
      return;
    }
    refreshRegulars();
  }

  async function deleteRegular(regular) {
    const response = await fetch(`/api/regulars/${regular.id}`, { method: 'DELETE' });
    if (!response.ok) {
      regularsMessage = 'Failed to delete regular';
      return;
    }
    refreshRegulars();
  }
</script>

<section class="panel">
  <h3>Seating</h3>
  <div class="grid2">
    <label>Tables
      <input bind:value={tables} inputmode="numeric"
             onfocus={() => (editing = true)} onchange={applyLayout}
             onblur={() => (editing = false)} />
    </label>
    <label>Seats per table
      <input bind:value={seats} inputmode="numeric"
             onfocus={() => (editing = true)} onchange={applyLayout}
             onblur={() => (editing = false)} />
    </label>
  </div>

  <div class="regulars-head">
    <span>Regulars <span class="hint">— tap to add tonight</span></span>
    {#if regulars.length > 0}
      <button class="link" onclick={() => (editRegulars = !editRegulars)}>
        {editRegulars ? 'Done' : 'Edit'}
      </button>
    {/if}
  </div>
  {#if regulars.length > 0}
    <div class="chips">
      {#each chips as chip (chip.id)}
        {#if editRegulars}
          <button class="chip editing" aria-label="Delete regular {chip.name}"
                  onclick={() => deleteRegular(chip)}>{chip.name} ×</button>
        {:else}
          <button class="chip" class:playing={chip.playing} disabled={chip.playing}
                  onclick={() => send('add_player', { name: chip.name })}>
            {chip.playing ? '✓ ' : ''}{chip.name}
          </button>
        {/if}
      {/each}
    </div>
  {:else}
    <p class="muted">No regulars saved yet. Tap ☆ next to a player to save them.</p>
  {/if}
  {#if regularsMessage}<p class="error">{regularsMessage}</p>{/if}

  <form class="row" onsubmit={addPlayer}>
    <input class="name-input" bind:value={newName} placeholder="Player name" maxlength="30" />
    <button type="submit">Add</button>
  </form>

  {#if s.players.length > 0}
    <ul class="players">
      {#each s.players as player (player.name)}
        <li>
          <span class="pname">{player.name}</span>
          <span class="pseat">
            {player.table === null ? 'not seated' : `T${player.table} · S${player.seat}`}
          </span>
          {#if !isRegular(player.name, regulars)}
            <button class="remove" aria-label="Save {player.name} as a regular"
                    title="Save as regular" onclick={() => saveRegular(player.name)}>☆</button>
          {/if}
          <button class="remove" aria-label="Remove {player.name}"
                  onclick={() => send('remove_player', { name: player.name })}>×</button>
        </li>
      {/each}
    </ul>
  {:else}
    <p class="muted">No players yet. Adding a name counts as an entry.</p>
  {/if}

  <div class="row">
    <button onclick={draw} disabled={s.players.length === 0}>
      {anySeated ? 'Redraw seats' : 'Draw seats'}
    </button>
    <button class:on={s.show_seating}
            onclick={() => send('set_show_seating', { show: !s.show_seating })}>
      {s.show_seating ? 'Back to clock' : 'Show seating on TV'}
    </button>
  </div>
</section>

<style>
  .grid2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.6rem;
    margin-bottom: 0.8rem;
  }
  .grid2 label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.85rem;
    color: #9ca3af;
    min-width: 0;
  }
  .grid2 input { width: 100%; min-width: 0; }
  .name-input { flex: 1; min-width: 0; }
  .players {
    list-style: none;
    margin: 0 0 0.6rem;
    padding: 0;
    max-height: 16rem;
    overflow-y: auto;
  }
  .players li {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.25rem 0;
    border-bottom: 1px solid #1f2937;
  }
  .pname { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pseat { color: #9ca3af; font-size: 0.85rem; font-variant-numeric: tabular-nums; }
  .remove { padding: 0.1rem 0.55rem; }
  .muted { color: #7b8794; margin: 0 0 0.6rem; font-size: 0.9rem; }
  .on { background: #166534; border-color: #166534; }
  .regulars-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.85rem;
    color: #9ca3af;
    margin-bottom: 0.4rem;
  }
  .hint { color: #6b7280; }
  .link { background: none !important; border: none !important; color: #60a5fa !important; padding: 0 !important; }
  .chips { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 0.8rem; }
  .chip { padding: 0.3rem 0.65rem !important; font-size: 0.85rem !important; border-radius: 999px !important; }
  .chip.playing { opacity: 0.45; }
  .chip.editing { border-color: #7f1d1d !important; color: #fecaca !important; }
  .error { color: #f87171; margin: 0 0 0.6rem; font-size: 0.85rem; }
</style>
