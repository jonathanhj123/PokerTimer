<script>
  import { onMount } from 'svelte';
  import { conn } from '../connection.svelte.js';

  const s = $derived(conn.state);
  let templates = $state([]);
  let name = $state('');
  let selected = $state('');
  let message = $state('');

  async function refresh() {
    const response = await fetch('/api/templates');
    if (!response.ok) {
      templates = [];
      message = 'Failed to load templates';
      return;
    }
    templates = await response.json();
  }
  onMount(refresh);

  async function saveTemplate() {
    if (!name.trim()) return;
    const response = await fetch('/api/templates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim(), structure: s.structure }),
    });
    message = response.ok ? `Saved "${name.trim()}"` : (await response.json()).detail;
    if (response.ok) {
      name = '';
      refresh();
    }
  }

  async function loadTemplate() {
    if (!selected) return;
    const response = await fetch(`/api/templates/${selected}/load`, { method: 'POST' });
    message = response.ok ? 'Template loaded' : (await response.json()).detail;
  }

  async function removeTemplate() {
    if (!selected) return;
    const response = await fetch(`/api/templates/${selected}`, { method: 'DELETE' });
    if (!response.ok) {
      message = (await response.json()).detail || 'Failed to delete template';
      return;
    }
    selected = '';
    refresh();
  }
</script>

<section class="panel">
  <h3>Templates</h3>
  <div class="row">
    <input placeholder="Template name" bind:value={name} />
    <button onclick={saveTemplate} disabled={!name.trim() || s.structure.length === 0}>
      Save current structure
    </button>
  </div>
  <div class="row">
    <select bind:value={selected}>
      <option value="">— pick a template —</option>
      {#each templates as template}
        <option value={template.id}>{template.name}</option>
      {/each}
    </select>
    <button onclick={loadTemplate} disabled={!selected || s.status !== 'setup'}>
      Load
    </button>
    <button onclick={removeTemplate} disabled={!selected}>Delete</button>
  </div>
  {#if s.status !== 'setup'}
    <p class="hint">Templates can only be loaded during setup.</p>
  {/if}
  {#if message}<p class="hint">{message}</p>{/if}
</section>

<style>
  .hint { color: #7b8794; font-size: 0.85rem; margin: 0.2rem 0 0; }
</style>
