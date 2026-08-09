<script>
  import { conn, send } from '../connection.svelte.js';
  import { formatChips, formatMoney } from '../format.js';

  const s = $derived(conn.state);

  let buyIn = $state('');
  let currency = $state('');
  let stack = $state('');
  let bonus = $state('');
  let rebuyPrice = $state('');
  let rebuyStack = $state('');
  let seeded = false;

  $effect(() => {
    if (s && !seeded) {
      seeded = true;
      buyIn = s.buy_in;
      currency = s.currency;
      stack = String(s.starting_stack);
      bonus = String(s.early_bird_bonus);
      rebuyPrice = s.rebuy_price;
      rebuyStack = String(s.rebuy_stack);
    }
  });

  function applyConfig() {
    send('set_config', {
      buy_in: buyIn,
      currency,
      starting_stack: parseInt(stack, 10) || 0,
      early_bird_bonus: parseInt(bonus, 10) || 0,
      rebuy_price: rebuyPrice,
      rebuy_stack: parseInt(rebuyStack, 10) || 0,
    });
  }

  function bump(field, delta) {
    const updates = { [field]: Math.max(0, s[field] + delta) };
    if (field === 'entries') {
      // A new entry is a new player at the table; a rebuy isn't. Keep
      // players_remaining in lockstep with entries so the admin only has
      // to track it manually for the one event entries can't see: busts.
      updates.players_remaining = Math.max(0, s.players_remaining + delta);
    }
    send('set_counts', updates);
  }

  const countRows = [
    ['entries', 'Entries'],
    ['rebuy_count', 'Rebuys'],
    ['players_remaining', 'Players remaining'],
    ['early_bird_count', 'Early birds'],
  ];
</script>

<section class="panel">
  <h3>Money & players</h3>
  <div class="grid2">
    <label>Buy-in <input bind:value={buyIn} inputmode="decimal" /></label>
    <label>Currency <input bind:value={currency} size="4" /></label>
    <label>Starting stack <input bind:value={stack} inputmode="numeric" /></label>
    <label>Early-bird chips <input bind:value={bonus} inputmode="numeric" /></label>
    <label>Rebuy price <input bind:value={rebuyPrice} inputmode="decimal" /></label>
    <label>Rebuy stack <input bind:value={rebuyStack} inputmode="numeric" /></label>
  </div>
  <div class="row"><button onclick={applyConfig}>Apply</button></div>

  {#each countRows as [field, label]}
    <div class="row count-row">
      <span class="count-label">{label}</span>
      <button onclick={() => bump(field, -1)}>−</button>
      <strong class="count-value">{s[field]}</strong>
      <button onclick={() => bump(field, 1)}>+</button>
    </div>
  {/each}

  <p class="summary">
    Pool <strong>{formatMoney(s.computed.prize_pool, s.currency)}</strong>
    · Avg stack
    <strong>
      {s.computed.average_stack === null ? '—' : formatChips(s.computed.average_stack)}
    </strong>
  </p>
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
  .grid2 input {
    width: 100%;
    min-width: 0;
  }
  .count-row { justify-content: space-between; }
  .count-label { flex: 1; color: #9ca3af; }
  .count-value { min-width: 2ch; text-align: center; font-size: 1.1rem; }
  .summary { color: #9ca3af; margin: 0.6rem 0 0; }
</style>
