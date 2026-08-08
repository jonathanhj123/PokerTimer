<script>
  import { conn, send } from '../connection.svelte.js';
  import { formatClock } from '../format.js';

  const s = $derived(conn.state);
  const active = $derived(s.status === 'running' || s.status === 'paused');
  let exact = $state('');

  function setExact() {
    const match = exact.trim().match(/^(\d{1,3}):([0-5]\d)$/);
    if (!match) return;
    send('set_time', { seconds: Number(match[1]) * 60 + Number(match[2]) });
    exact = '';
  }
</script>

<section class="panel">
  <h3>Clock</h3>
  <div class="row clock-row">
    <span class="clock-preview">{formatClock(s.seconds_remaining)}</span>
    <span class="status-tag">{s.status}</span>
  </div>
  <div class="row">
    {#if s.status === 'setup'}
      <button onclick={() => send('start')} disabled={s.structure.length === 0}>
        Start tournament
      </button>
    {/if}
    {#if s.status === 'running'}<button onclick={() => send('pause')}>Pause</button>{/if}
    {#if s.status === 'paused'}<button onclick={() => send('resume')}>Resume</button>{/if}
    {#if active}<button onclick={() => send('end')}>End</button>{/if}
    {#if s.status === 'finished'}
      <button onclick={() => send('reset')}>Reset for next game</button>
    {/if}
  </div>
  {#if active}
    <div class="row">
      <button onclick={() => send('prev_level')}>◀ Prev</button>
      <button onclick={() => send('next_level')}>Next ▶</button>
      <button onclick={() => send('adjust_time', { delta_seconds: -60 })}>−1 min</button>
      <button onclick={() => send('adjust_time', { delta_seconds: 60 })}>+1 min</button>
    </div>
    <div class="row">
      <input placeholder="mm:ss" bind:value={exact} size="6" />
      <button onclick={setExact}>Set clock</button>
    </div>
  {/if}
</section>

<style>
  .clock-preview {
    font-size: 2rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
  .status-tag {
    background: #1f2937;
    border-radius: 999px;
    padding: 0.15rem 0.7rem;
    font-size: 0.8rem;
    color: #9ca3af;
    text-transform: uppercase;
  }
</style>
