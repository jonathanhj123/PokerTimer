<script>
  import Admin from './lib/Admin.svelte';
  import Display from './lib/Display.svelte';

  const isAdminRoute = window.location.pathname.startsWith('/admin');
</script>

{#if isAdminRoute}
  <Admin />
{:else}
  <Display />
{/if}
