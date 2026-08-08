<script>
  import { onMount } from 'svelte';
  import { conn, connect, enableSound } from './connection.svelte.js';
  import { formatChips, formatClock, formatMoney, ordinal } from './format.js';

  let flashing = $state(false);
  let flashTimer;

  $effect(() => {
    if (conn.levelChangeAt > 0) {
      flashing = true;
      clearTimeout(flashTimer);
      flashTimer = setTimeout(() => (flashing = false), 5000);
    }
  });

  onMount(() => {
    connect();
  });

  const s = $derived(conn.state);
  const c = $derived(conn.state?.computed);
  const entry = $derived(conn.state?.computed?.current_entry);
</script>

{#if !s}
  <main class="screen center"><p class="muted">Connecting…</p></main>
{:else if s.status === 'setup'}
  <main class="screen center">
    <h1 class="waiting-title">PokerTimer</h1>
    <p class="muted">Waiting for the tournament to start…</p>
  </main>
{:else if s.status === 'finished'}
  <main class="screen center">
    <p class="label">FINAL RESULT</p>
    <p class="pool-final">Pool {formatMoney(c.prize_pool, s.currency)}</p>
    <div class="payouts-final">
      {#each c.payouts as amount, i}
        <div class="payout-row final-row">
          <span class="place">{ordinal(i + 1)}</span>
          <span class="accent">{formatMoney(amount, s.currency)}</span>
        </div>
      {/each}
    </div>
  </main>
{:else}
  <main class="screen" class:flashing>
    <div class="main-stack">
      <div class="level-label">
        {#if entry.type === 'break'}BREAK{:else}LEVEL {c.level_number}{/if}
        {#if c.is_final_entry}&nbsp;· FINAL LEVEL{/if}
      </div>
      <div class="clock-wrap">
        <div class="clock">{formatClock(s.seconds_remaining)}</div>
        {#if s.status === 'paused'}<div class="paused-badge">PAUSED</div>{/if}
      </div>
      {#if entry.type === 'level'}
        <div class="blinds">
          {formatChips(entry.sb)} / {formatChips(entry.bb)}
          {#if entry.ante > 0}<span class="dim">ante {formatChips(entry.ante)}</span>{/if}
        </div>
      {:else}
        <div class="blinds">Break — {entry.minutes} min</div>
      {/if}
      <div class="next">
        {#if entry.type === 'break'}
          {#if c.next_blinds}Back at: {formatChips(c.next_blinds.sb)} / {formatChips(c.next_blinds.bb)}{/if}
        {:else if c.next_entry?.type === 'break'}
          Next: Break ({c.next_entry.minutes} min)
        {:else if c.next_entry}
          Next: {formatChips(c.next_entry.sb)} / {formatChips(c.next_entry.bb)}
        {/if}
      </div>
    </div>

    <aside class="side-block">
      <div class="side-line">{s.players_remaining} players left</div>
      {#if s.starting_stack > 0 && c.average_stack !== null}
        <div class="side-line">Avg stack <span class="side-strong">{formatChips(c.average_stack)}</span></div>
      {/if}
      <div class="side-line">Pool <span class="side-strong accent">{formatMoney(c.prize_pool, s.currency)}</span></div>
      <div class="payouts-label">PAYOUTS</div>
      {#each c.payouts as amount, i}
        <div class="payout-row">
          <span class="place">{ordinal(i + 1)}</span>
          <span class="accent">{formatMoney(amount, s.currency)}</span>
        </div>
      {/each}
    </aside>
  </main>
{/if}

{#if !conn.connected}
  <div class="reconnect-badge">reconnecting…</div>
{/if}
{#if !conn.soundEnabled}
  <button class="sound-chip" onclick={enableSound}>🔊 Tap to enable sound</button>
{/if}

<style>
  .screen {
    height: 100dvh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    position: relative;
    overflow: hidden;
    background: #0b0f14;
  }
  .screen.center { align-items: center; }
  .flashing { animation: flash 0.8s ease-in-out 4; }
  @keyframes flash {
    0%, 100% { background: #0b0f14; }
    50% { background: #14532d; }
  }

  .main-stack { text-align: center; }
  .level-label {
    font-size: 2.2vw;
    letter-spacing: 0.12em;
    color: #7b8794;
    font-weight: 600;
  }
  .clock-wrap { position: relative; display: inline-block; }
  .clock {
    font-size: 17vw;
    font-weight: 800;
    line-height: 1.05;
    font-variant-numeric: tabular-nums;
  }
  .paused-badge {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 4vw;
    font-weight: 800;
    letter-spacing: 0.2em;
    color: #fbbf24;
    background: rgba(11, 15, 20, 0.75);
    border-radius: 1vw;
  }
  .blinds { font-size: 5.5vw; font-weight: 700; }
  .next { font-size: 2.3vw; color: #7b8794; margin-top: 0.4em; font-weight: 500; }

  .side-block {
    position: absolute;
    top: 50%;
    right: 3vw;
    transform: translateY(-50%);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.45em;
    font-size: 1.9vw;
    text-align: center;
    min-width: 20vw;
  }
  .side-line { color: #7b8794; }
  .side-strong { color: #e8edf2; font-weight: 700; font-size: 1.2em; }
  .payouts-label {
    color: #7b8794;
    border-top: 1px solid #1f2937;
    padding-top: 0.45em;
    margin-top: 0.3em;
    width: 100%;
    letter-spacing: 0.06em;
    font-size: 0.85em;
    font-weight: 600;
  }
  .payout-row { display: flex; justify-content: center; gap: 0.5em; font-weight: 600; }
  .payout-row .place { color: #cbd5e1; font-weight: 400; }

  .accent { color: #4ade80; }
  .dim { color: #7b8794; }
  .muted { color: #7b8794; font-size: 2vw; }
  .label { color: #7b8794; letter-spacing: 0.12em; font-size: 2vw; }
  .waiting-title { font-size: 5vw; margin: 0 0 0.2em; }
  .pool-final { font-size: 3.5vw; font-weight: 700; margin: 0.2em 0 0.6em; }
  .payouts-final { display: flex; flex-direction: column; gap: 0.4em; }
  .final-row { font-size: 3vw; }

  .reconnect-badge {
    position: fixed;
    top: 1rem;
    left: 1rem;
    background: #7f1d1d;
    color: #fecaca;
    padding: 0.35rem 0.8rem;
    border-radius: 999px;
    font-size: 0.9rem;
  }
  .sound-chip {
    position: fixed;
    bottom: 1rem;
    left: 1rem;
    background: #1f2937;
    color: #e8edf2;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 999px;
    font-size: 0.95rem;
  }
</style>
