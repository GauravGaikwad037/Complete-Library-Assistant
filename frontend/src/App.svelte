<script>
  import { onMount } from 'svelte';
  import { authUser } from './lib/stores/authStore.js';
  import { isDarkMode } from './lib/stores/themeStore.js';
  import { fetchGeminiConfigStatus } from './lib/services/api.js';
  import LoginPage from './lib/components/LoginPage.svelte';
  import AdminPortal from './lib/components/AdminPortal.svelte';
  import UserPortal from './lib/components/UserPortal.svelte';
  import GeminiConfigGate from './lib/components/GeminiConfigGate.svelte';

  let configStatus = null;
  let isCheckingConfig = true;

  // Synchronize documentElement class with theme store
  $: if (typeof document !== 'undefined') {
    if ($isDarkMode) {
      document.documentElement.classList.add('dark');
      document.documentElement.classList.remove('light');
    } else {
      document.documentElement.classList.add('light');
      document.documentElement.classList.remove('dark');
    }
  }

  onMount(async () => {
    await checkConfig();
  });

  async function checkConfig() {
    isCheckingConfig = true;
    try {
      configStatus = await fetchGeminiConfigStatus(false);
    } catch (e) {
      configStatus = {
        status: 'service_unavailable',
        is_valid: false,
        has_key: false,
        message: 'Could not connect to backend server.'
      };
    } finally {
      isCheckingConfig = false;
    }
  }
</script>

<div class="app-container {$isDarkMode ? 'dark' : 'light'}">
  {#if isCheckingConfig}
    <div class="loading-screen">
      <div class="loader-box">
        <div class="spinner"></div>
        <h2>Verifying VidyaAI Core Services</h2>
        <p>Validating Google Gemini LLM API connection & library database...</p>
      </div>
    </div>
  {:else if !configStatus || !configStatus.is_valid}
    <GeminiConfigGate 
      {configStatus} 
      onValidated={(status) => { configStatus = status; }} 
    />
  {:else}
    <!-- Floating or Top Verified Indicator -->
    <div class="gemini-status-bar">
      <span class="status-dot"></span>
      <span class="status-label font-mono">Gemini Connected • {configStatus.model || 'gemini-3.5-flash'}</span>
    </div>

    {#if !$authUser.loggedIn}
      <LoginPage {configStatus} />
    {:else if $authUser.role === 'admin'}
      <AdminPortal {configStatus} />
    {:else if $authUser.role === 'user' || $authUser.role === 'student'}
      <UserPortal {configStatus} />
    {/if}
  {/if}
</div>

<style>
  .app-container {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    position: relative;
  }

  .gemini-status-bar {
    position: fixed;
    bottom: 1rem;
    right: 1rem;
    z-index: 9999;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: rgba(15, 23, 42, 0.92);
    border: 1px solid rgba(16, 185, 129, 0.4);
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
    padding: 0.4rem 0.85rem;
    border-radius: 9999px;
    font-size: 0.8rem;
    color: #34d399;
    backdrop-filter: blur(8px);
    pointer-events: none;
  }

  .status-dot {
    width: 8px;
    height: 8px;
    background: #10b981;
    border-radius: 50%;
    box-shadow: 0 0 8px #10b981;
    animation: pulse-glow 2s infinite;
  }

  @keyframes pulse-glow {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.6; transform: scale(1.2); }
  }

  .loading-screen {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-primary, #0f172a);
    color: var(--text-primary, #f8fafc);
  }

  .loader-box {
    text-align: center;
    max-width: 400px;
    padding: 2rem;
  }

  .spinner {
    width: 2.5rem;
    height: 2.5rem;
    margin: 0 auto 1.25rem;
    border: 3px solid rgba(99, 102, 241, 0.2);
    border-top-color: #6366f1;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .loader-box h2 {
    font-size: 1.25rem;
    margin: 0 0 0.5rem 0;
  }

  .loader-box p {
    font-size: 0.88rem;
    color: var(--text-secondary, #94a3b8);
    margin: 0;
  }
</style>
