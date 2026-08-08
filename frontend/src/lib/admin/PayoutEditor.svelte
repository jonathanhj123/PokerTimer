<script>
  import { conn, send } from '../connection.svelte.js';
  import { ordinal } from '../format.js';

  const s = $derived(conn.state);
  let draft = $state([]);
  let seeded = false;

  $effect(() => {
    if (s && !seeded) {
      seeded = true;
      draft = [...s.payout_percentages];
    }
  });

  const total = $derived(draft.reduce((sum, p) => sum + (parseInt(p, 10) || 0), 0));
  // Preview only — authoritative exact amounts come back from the server.
  const pool = $derived(Number(s?.computed.prize_pool ?? 0));

  function apply() {
    send('set_payouts', { percentages: draft.map((p) => parseInt(p, 10)) });
  }
</script>

<section class="panel">
  <h3>Payouts ({draft.length} paid)</h3>
  {#each draft as pct, i}
    <div class="row">
      <span class="place">{ordinal(i + 1)}</span>
      <input type="number" min="1" max="100" bind:value={draft[i]} class="pct" />%
      <span class="preview">≈ {s.currency}{((pool * (parseInt(pct, 10) || 0)) / 100).toFixed(2)}</span>
      <button onclick={() => (draft = draft.filter((_, j) => j !== i))}
              disabled={draft.length === 1}>✕</button>
    </div>
  {/each}
  <div class="row">
    <button onclick={() => (draft = [...draft, 1])}>+ Add place</button>
    <span class="total" class:bad={total !== 100}>Total: {total}%</span>
    <button disabled={total !== 100} onclick={apply}>Apply</button>
  </div>
</section>

<style>
  .place { min-width: 2.5rem; color: #9ca3af; }
  .pct { width: 4.5rem; }
  .preview { color: #7b8794; font-size: 0.85rem; }
  .total { margin-left: auto; color: #86efac; }
  .total.bad { color: #f87171; }
</style>
