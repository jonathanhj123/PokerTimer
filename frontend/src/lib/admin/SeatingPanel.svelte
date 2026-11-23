<script>
  import { conn, send } from '../connection.svelte.js';

  const s = $derived(conn.state);

  let tables = $state('');
  let seats = $state('');
  let newName = $state('');
  let seeded = false;

  $effect(() => {
    if (s && !seeded) {
      seeded = true;
      tables = String(s.table_count);
      seats = String(s.seats_per_table);
    }
  });

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
    send('draw_seats', {
      table_count: parseInt(tables, 10) || 0,
      seats_per_table: parseInt(seats, 10) || 0,
    });
  }
</script>

<section class="panel">
  <h3>Seating</h3>
  <div class="grid2">
    <label>Tables <input bind:value={tables} inputmode="numeric" /></label>
    <label>Seats per table <input bind:value={seats} inputmode="numeric" /></label>
  </div>

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
</style>
