// ============================================================
// App Main — Router + Lifecycle
// ============================================================
import { $, clearChildren } from './utils/dom.js';
import { api, APIError } from './api.js';
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

    // Header (direct grid child)
    const headerEl = document.createElement('div');
    headerEl.className = 'app-header';
    renderHeader(headerEl, {
      onRefresh: () => this.refreshCurrentPage(),
      onIntervalChange: (ms) => {
        this.refreshInterval = ms;
        this.startAutoRefresh();
      },
    });
    appRoot.appendChild(headerEl);

    // Content (direct grid child)
    const contentEl = document.createElement('div');
    contentEl.className = 'app-content';
    contentEl.id = 'page-content';
    appRoot.appendChild(contentEl);
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
        case '/settings':
          this.renderSettings(content);
          this.currentPage = 'settings';
          break;
        default:
          clearChildren(content);
          content.innerHTML = `<div class="page-error"><h3>页面未找到</h3><p class="text-muted">路由 "${route}" 不存在</p></div>`;
          break;
      }
      updateHeaderStatus('已连接', true);
    } catch (err) {
      console.error('Navigation error:', err);
      if (err instanceof APIError && err.status === 401) {
        showToast('认证已失效，请重新登录', 'error');
        api.logout();
        return;
      }
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
      if (err instanceof APIError && err.status === 401) {
        showToast('认证已失效，请重新登录', 'error');
        api.logout();
      }
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

  renderSettings(container) {
    const render = async () => {
      clearChildren(container);
      const keyDisplay = api.getApiKey()
        ? `${api.getApiKey().slice(0, 4)}••••${api.getApiKey().slice(-4)}`
        : '未设置';

      let runtime = null;
      let validate = null;
      try {
        runtime = await api.getRuntimeStatus();
      } catch (e) {
        runtime = { message: `获取运行时状态失败: ${e.message}` };
      }

      container.innerHTML = `
        <div class="page-header">
          <h2 class="page-title">设置 / 运行时管理</h2>
        </div>
        <div class="card" style="max-width:760px">
          <div class="card-body">
            <div style="margin-bottom:12px">
              <span class="text-muted">当前密钥：</span>
              <code style="background:var(--surface-2);padding:4px 8px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:13px">${keyDisplay}</code>
            </div>
            <div style="margin-bottom:8px"><span class="text-muted">配置版本：</span> <strong>${runtime?.config_version ?? '-'}</strong></div>
            <div style="margin-bottom:8px"><span class="text-muted">最后更新：</span> <code>${runtime?.updated_at ?? '-'}</code></div>
            <div style="margin-bottom:8px"><span class="text-muted">最后重载：</span> <code>${runtime?.last_reload_at ?? '-'}</code></div>
            <div style="margin-bottom:16px"><span class="text-muted">状态：</span> ${runtime?.message ?? '-'}</div>

            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <button class="btn btn-ghost" id="admin-validate-btn">校验配置</button>
              <button class="btn btn-primary" id="admin-reload-btn">重载运行时</button>
              <button class="btn btn-danger" id="logout-btn">退出登录</button>
            </div>
            <pre id="settings-output" style="margin-top:12px;background:var(--surface-container);padding:12px;border-radius:8px;white-space:pre-wrap">${runtime ? JSON.stringify(runtime, null, 2) : ''}</pre>
          </div>
        </div>
      `;

      container.querySelector('#logout-btn')?.addEventListener('click', () => api.logout());
      container.querySelector('#admin-validate-btn')?.addEventListener('click', async () => {
        try {
          const v = await api.validateAdminConfig();
          container.querySelector('#settings-output').textContent = JSON.stringify(v, null, 2);
          if (v.ok) showToast('配置校验通过', 'success');
          else showToast('配置校验失败', 'error');
        } catch (e) {
          showToast(`校验失败: ${e.message}`, 'error');
        }
      });

      container.querySelector('#admin-reload-btn')?.addEventListener('click', async () => {
        try {
          const r = await api.reloadRuntime();
          container.querySelector('#settings-output').textContent = JSON.stringify(r, null, 2);
          showToast('运行时重载完成', 'success');
          await render();
        } catch (e) {
          showToast(`重载失败: ${e.message}`, 'error');
        }
      });
    };

    render().catch((e) => {
      container.innerHTML = `<div class="page-error"><h3>设置页面加载失败</h3><p class="text-muted">${e.message}</p></div>`;
    });
  }
}

// Boot
document.addEventListener('DOMContentLoaded', () => {
  const app = new App();
  app.init().catch(console.error);
});
