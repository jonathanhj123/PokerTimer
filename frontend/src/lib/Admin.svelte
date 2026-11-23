<script>
  import { onMount } from 'svelte';
  import { conn, connect } from './connection.svelte.js';
  import ClockControls from './admin/ClockControls.svelte';
  import MoneyPanel from './admin/MoneyPanel.svelte';
  import SeatingPanel from './admin/SeatingPanel.svelte';
  import PayoutEditor from './admin/PayoutEditor.svelte';
  import StructureEditor from './admin/StructureEditor.svelte';
  import TemplateBar from './admin/TemplateBar.svelte';

  let checked = $state(false);
  let loggedIn = $state(false);
  let password = $state('');
  let loginError = $state('');
  let toast = $state('');
  let toastTimer;

  $effect(() => {
    if (conn.lastError) {
      toast = conn.lastError.message;
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => (toast = ''), 4000);
    }
  });

  onMount(async () => {
    const response = await fetch('/api/me');
    loggedIn = (await response.json()).is_admin;
    checked = true;
    if (loggedIn) connect();
  });

  async function login(event) {
    event.preventDefault();
    loginError = '';
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    });
    if (response.ok) {
      loggedIn = true;
      connect();
    } else {
      loginError = 'Wrong password';
    }
  }
</script>

{#if !checked}
  <p class="muted pad">Loading…</p>
{:else if !loggedIn}
  <main class="login-wrap">
    <form class="login-card" onsubmit={login}>
      <h1>PokerTimer admin</h1>
      <input type="password" placeholder="Admin password" bind:value={password} />
      <button type="submit">Log in</button>
      {#if loginError}<p class="error">{loginError}</p>{/if}
    </form>
  </main>
{:else if !conn.state}
  <p class="muted pad">Connecting…</p>
{:else}
  <main class="admin">
    <header class="topbar">
      <strong>PokerTimer admin</strong>
      {#if !conn.connected}<span class="badge bad">reconnecting…</span>
      {:else}<span class="badge ok">live</span>{/if}
    </header>
    <!-- Packed columns: each column stacks its panels with no gaps. On a
         phone the columns dissolve (display: contents) and `order` puts the
         game-night panels first. -->
    <div class="columns">
      <div class="col">
        <div class="slot" style="order: 1"><ClockControls /></div>
        <div class="slot" style="order: 4"><PayoutEditor /></div>
      </div>
      <div class="col">
        <div class="slot" style="order: 3"><MoneyPanel /></div>
        <div class="slot" style="order: 5"><TemplateBar /></div>
      </div>
      <div class="col">
        <div class="slot" style="order: 2"><SeatingPanel /></div>
      </div>
    </div>
    <div class="full"><StructureEditor /></div>
  </main>
{/if}

{#if toast}<div class="toast">{toast}</div>{/if}

<style>
  .pad { padding: 2rem; }
  .muted { color: #7b8794; }
  .error { color: #f87171; margin: 0.5rem 0 0; }

  .login-wrap { min-height: 100dvh; display: grid; place-items: center; }
  .login-card {
    background: #111827;
    padding: 2rem;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
    width: min(320px, 90vw);
  }
  .login-card h1 { font-size: 1.2rem; margin: 0; }
  .login-card input, .login-card button {
    padding: 0.6rem 0.8rem;
    border-radius: 8px;
    border: 1px solid #374151;
    background: #0b0f14;
    color: #e8edf2;
    font-size: 1rem;
  }
  .login-card button { background: #166534; border-color: #166534; }

  .admin { padding: 1rem; max-width: 1200px; margin: 0 auto; }
  .topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }
  .badge { padding: 0.15rem 0.7rem; border-radius: 999px; font-size: 0.8rem; }
  .badge.ok { background: #14532d; color: #86efac; }
  .badge.bad { background: #7f1d1d; color: #fecaca; }

  .columns {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1rem;
    align-items: start;
  }
  .col { display: flex; flex-direction: column; gap: 1rem; min-width: 0; }
  .full { margin-top: 1rem; }
  @media (max-width: 900px) {
    .columns { display: flex; flex-direction: column; }
    .col { display: contents; }
  }

  .toast {
    position: fixed;
    bottom: 1rem;
    left: 50%;
    transform: translateX(-50%);
    background: #7f1d1d;
    color: #fecaca;
    padding: 0.6rem 1.2rem;
    border-radius: 8px;
    max-width: 90vw;
  }

  :global(.panel) {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 12px;
    padding: 1rem 1.1rem;
  }
  :global(.panel h3) {
    margin: 0 0 0.9rem;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #e5e7eb;
  }
  :global(.panel .row) {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
    margin-bottom: 0.6rem;
  }
  :global(.panel .row:last-child) { margin-bottom: 0; }
  :global(.panel button) {
    background: #1f2937;
    color: #e8edf2;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 0.45rem 0.9rem;
    font-size: 0.9rem;
    cursor: pointer;
    transition: background 0.12s, border-color 0.12s;
  }
  :global(.panel button:hover:not(:disabled)) { background: #273244; border-color: #4b5563; }
  :global(.panel button.primary) { background: #166534; border-color: #15803d; font-weight: 600; }
  :global(.panel button.primary:hover:not(:disabled)) { background: #15803d; }
  :global(.panel button.danger) { border-color: #7f1d1d; color: #fca5a5; }
  :global(.panel button:disabled) { opacity: 0.4; cursor: not-allowed; }
  :global(.panel input), :global(.panel select) {
    background: #0b0f14;
    color: #e8edf2;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 0.45rem 0.6rem;
    font-size: 0.95rem;
  }
  :global(.panel input:focus), :global(.panel select:focus) {
    outline: none;
    border-color: #22c55e;
  }
</style>
