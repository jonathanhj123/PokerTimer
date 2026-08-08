<script>
  import { conn, send } from '../connection.svelte.js';

  const s = $derived(conn.state);

  // Local editable copies. Reseed ONLY when the server structure itself
  // changes — every-second tick broadcasts must not wipe in-progress edits.
  let rows = $state([]);
  let serverKey = $state('');

  $effect(() => {
    if (!s) return;
    const key = JSON.stringify(s.structure);
    if (key !== serverKey) {
      serverKey = key;
      rows = s.structure.map((entry) => ({ ...entry }));
    }
  });

  function toEntry(row) {
    return row.type === 'break'
      ? { type: 'break', minutes: Number(row.minutes) }
      : { type: 'level', sb: Number(row.sb), bb: Number(row.bb),
          ante: Number(row.ante) || 0, minutes: Number(row.minutes) };
  }

  function isDirty(i) {
    return JSON.stringify(toEntry(rows[i])) !== JSON.stringify(s.structure[i]);
  }

  function saveRow(i) {
    send('update_entry', { index: i, entry: toEntry(rows[i]) });
  }

  function addLevel() {
    const last = [...s.structure].reverse().find((e) => e.type === 'level');
    const entry = last
      ? { type: 'level', sb: last.sb * 2, bb: last.bb * 2, ante: last.ante,
          minutes: last.minutes }
      : { type: 'level', sb: 25, bb: 50, ante: 0, minutes: 15 };
    send('insert_entry', { index: s.structure.length, entry });
  }

  function addBreak() {
    send('insert_entry',
         { index: s.structure.length, entry: { type: 'break', minutes: 10 } });
  }
</script>

<section class="panel wide">
  <h3>Blind structure</h3>
  <div class="table">
    <div class="thead">
      <span></span><span>SB</span><span>BB</span><span>Ante</span><span>Min</span><span></span>
    </div>
    {#each rows as row, i}
      <div class="trow" class:current={i === s.current_index && s.status !== 'setup'}>
        <span class="num">{i + 1}</span>
        {#if row.type === 'level'}
          <input inputmode="numeric" bind:value={row.sb} />
          <input inputmode="numeric" bind:value={row.bb} />
          <input inputmode="numeric" bind:value={row.ante} />
          <input inputmode="numeric" bind:value={row.minutes} />
        {:else}
          <span class="break-cell">BREAK</span>
          <span></span><span></span>
          <input inputmode="numeric" bind:value={row.minutes} />
        {/if}
        <span class="actions">
          {#if isDirty(i)}<button class="save" onclick={() => saveRow(i)}>Save</button>{/if}
          <button onclick={() => send('move_entry', { from_index: i, to_index: i - 1 })}
                  disabled={i === 0}>↑</button>
          <button onclick={() => send('move_entry', { from_index: i, to_index: i + 1 })}
                  disabled={i === rows.length - 1}>↓</button>
          <button onclick={() => send('delete_entry', { index: i })}
                  disabled={rows.length === 1}>✕</button>
        </span>
      </div>
    {/each}
  </div>
  <div class="row">
    <button onclick={addLevel}>+ Add level</button>
    <button onclick={addBreak}>+ Add break</button>
  </div>
</section>

<style>
  .wide { grid-column: 1 / -1; }
  .table { display: flex; flex-direction: column; gap: 0.3rem; margin-bottom: 0.8rem; }
  .thead, .trow {
    display: grid;
    grid-template-columns: 2rem 1fr 1fr 1fr 1fr auto;
    gap: 0.4rem;
    align-items: center;
  }
  .thead { color: #7b8794; font-size: 0.8rem; }
  .trow.current { outline: 1px solid #166534; border-radius: 8px; }
  .trow input { width: 100%; min-width: 3rem; }
  .num { color: #7b8794; text-align: right; }
  .break-cell { color: #fbbf24; font-size: 0.85rem; }
  .actions { display: flex; gap: 0.25rem; }
  .actions .save { background: #166534; border-color: #166534; }
</style>
