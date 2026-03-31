// ============================================================
// App Main — Router + Lifecycle
// ============================================================
import { $, clearChildren } from './utils/dom.js';
import { api } from './api.js';
import { checkAuth } from './components/auth-modal.js';
import { renderSidebar, updateActiveNav } from './components/sidebar.js';
import { renderHeader, updateHeaderStatus } from './components/header.js';
import { showToast } from './components/toast.js';

class App {
  constructor() {
    this.currentPage = null;
    this.refreshTimer = null;
    this.refreshInterval = 30000;
  }

  async init() {
    // Auth check
    const authed = await checkAuth();
    if (!authed) return;

    // Render shell
    this.renderShell();

    // Listen for hash changes
    window.addEventListener('hashchange', () => this.navigate());

    // Initial navigation
    this.navigate();

    // Start auto-refresh
    this.startAutoRefresh();
  }

  renderShell() {
    const appRoot = $('#app-root');
    clearChildren(appRoot);

    appRoot.className = 'app-layout';

    // Sidebar
    const sidebarEl = document.createElement('div');
    sidebarEl.className = 'app-sidebar';
    renderSidebar(sidebarEl);
    appRoot.appendChild(sidebarEl);

    // Main area
    const mainArea = document.createElement('div');
    mainArea.className = 'app-main';

    // Header
    const headerEl = document.createElement('div');
    headerEl.className = 'app-header';
    renderHeader(headerEl, {
      onRefresh: () => this.refreshCurrentPage(),
      onIntervalChange: (ms) => {
        this.refreshInterval = ms;
        this.startAutoRefresh();
      },
    });
    mainArea.appendChild(headerEl);

    // Content
    const contentEl = document.createElement('div');
    contentEl.className = 'app-content';
    contentEl.id = 'page-content';
    mainArea.appendChild(contentEl);

    appRoot.appendChild(mainArea);
  }

  async navigate() {
    const hash = window.location.hash || '#/';
    const route = hash.replace('#', '') || '/';
    updateActiveNav();

    const content = $('#page-content');
    if (!content) return;

    try {
      switch (route) {
        case '/':
          const { renderDashboard } = await import('./pages/dashboard.js');
          await renderDashboard(content);
          this.currentPage = 'dashboard';
          break;
        case '/channels':
          const { renderChannels } = await import('./pages/channels.js');
          await renderChannels(content);
          this.currentPage = 'channels';
          break;
        case '/models':
          const { renderModels } = await import('./pages/models.js');
          await renderModels(content);
          this.currentPage = 'models';
          break;
        case '/stats':
          const { renderStats } = await import('./pages/stats.js');
          await renderStats(content);
          this.currentPage = 'stats';
          break;
        default:
          clearChildren(content);
          content.innerHTML = `<div class="page-error"><h3>页面未找到</h3><p class="text-muted">路由 "${route}" 不存在</p></div>`;
          break;
      }
      updateHeaderStatus('已连接', true);
    } catch (err) {
      console.error('Navigation error:', err);
      updateHeaderStatus('连接错误', false);
      showToast('页面加载失败', 'error');
    }
  }

  async refreshCurrentPage() {
    const content = $('#page-content');
    if (!content) return;

    try {
      switch (this.currentPage) {
        case 'dashboard':
          const { renderDashboard } = await import('./pages/dashboard.js');
          await renderDashboard(content);
          break;
        case 'channels':
          const { renderChannels } = await import('./pages/channels.js');
          await renderChannels(content);
          break;
        case 'models':
          const { renderModels } = await import('./pages/models.js');
          await renderModels(content);
          break;
        case 'stats':
          const { renderStats } = await import('./pages/stats.js');
          await renderStats(content);
          break;
      }
    } catch (err) {
      console.error('Refresh error:', err);
    }
  }

  startAutoRefresh() {
    this.stopAutoRefresh();
    if (this.refreshInterval > 0) {
      this.refreshTimer = setInterval(() => this.refreshCurrentPage(), this.refreshInterval);
    }
  }

  stopAutoRefresh() {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer);
      this.refreshTimer = null;
    }
  }
}

// Boot
document.addEventListener('DOMContentLoaded', () => {
  const app = new App();
  app.init().catch(console.error);
});
