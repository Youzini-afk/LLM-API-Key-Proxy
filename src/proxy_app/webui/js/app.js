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
      let policies = null;
      try {
        [runtime, policies] = await Promise.all([
          api.getRuntimeStatus(),
          api.getPolicies(),
        ]);
      } catch (e) {
        runtime = { message: `获取运行时状态失败: ${e.message}` };
        policies = null;
      }

      const safePolicies = {
        global_timeout: policies?.global_timeout ?? '',
        virtual_scheduler_mode: policies?.virtual_scheduler_mode ?? 'global_pool',
        key_busy_wait_interval_seconds: policies?.key_busy_wait_interval_seconds ?? 0.2,
        key_busy_wait_max_attempts: policies?.key_busy_wait_max_attempts ?? 5,
        scarcity_probe_budget_ratio: policies?.scarcity_probe_budget_ratio ?? 0.01,
        scarcity_probe_burst: policies?.scarcity_probe_burst ?? 3,
      };

      container.innerHTML = `
        <div class="page-header">
          <h2 class="page-title">设置 / 运行时管理</h2>
        </div>
        <div class="card" style="max-width:960px">
          <div class="card-body">
            <div style="margin-bottom:12px">
              <span class="text-muted">当前密钥：</span>
              <code style="background:var(--surface-2);padding:4px 8px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:13px">${keyDisplay}</code>
            </div>
            <div style="margin-bottom:8px"><span class="text-muted">配置版本：</span> <strong>${runtime?.config_version ?? '-'}</strong></div>
            <div style="margin-bottom:8px"><span class="text-muted">最后更新：</span> <code>${runtime?.updated_at ?? '-'}</code></div>
            <div style="margin-bottom:8px"><span class="text-muted">最后重载：</span> <code>${runtime?.last_reload_at ?? '-'}</code></div>
            <div style="margin-bottom:16px"><span class="text-muted">状态：</span> ${runtime?.message ?? '-'}</div>

            <div style="border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px;background:var(--surface-2)">
              <div style="font-weight:700;margin-bottom:12px">Scheduler Policies</div>
              <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px">
                <label class="input-label">虚拟调度模式
                  <select id="policy-virtual-scheduler-mode" class="select-field">
                    <option value="global_pool" ${safePolicies.virtual_scheduler_mode === 'global_pool' ? 'selected' : ''}>global_pool</option>
                    <option value="legacy" ${safePolicies.virtual_scheduler_mode === 'legacy' ? 'selected' : ''}>legacy</option>
                  </select>
                </label>
                <label class="input-label">总超时 Global Timeout
                  <input id="policy-global-timeout" class="input-field" type="number" min="1" step="1" value="${safePolicies.global_timeout}">
                </label>
                <label class="input-label">Busy Wait 间隔(秒)
                  <input id="policy-busy-wait-interval" class="input-field" type="number" min="0" step="0.1" value="${safePolicies.key_busy_wait_interval_seconds}">
                </label>
                <label class="input-label">Busy Wait 次数
                  <input id="policy-busy-wait-attempts" class="input-field" type="number" min="0" step="1" value="${safePolicies.key_busy_wait_max_attempts}">
                </label>
                <label class="input-label">Probe Budget 比例
                  <input id="policy-probe-ratio" class="input-field" type="number" min="0" step="0.001" value="${safePolicies.scarcity_probe_budget_ratio}">
                </label>
                <label class="input-label">Probe Burst
                  <input id="policy-probe-burst" class="input-field" type="number" min="1" step="1" value="${safePolicies.scarcity_probe_burst}">
                </label>
              </div>
              <div class="text-muted" style="margin-top:10px">
                `global_pool` 会启用跨 provider 全局 key 候选池；probe 预算越低，恢复试探越保守。
              </div>
            </div>

            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <button class="btn btn-primary" id="admin-save-policies-btn">保存调度策略</button>
              <button class="btn btn-ghost" id="admin-save-apply-btn">保存并应用</button>
              <button class="btn btn-ghost" id="admin-validate-btn">校验配置</button>
              <button class="btn btn-primary" id="admin-reload-btn">重载运行时</button>
              <button class="btn btn-danger" id="logout-btn">退出登录</button>
            </div>
            <pre id="settings-output" style="margin-top:12px;background:var(--surface-container);padding:12px;border-radius:8px;white-space:pre-wrap">${runtime ? JSON.stringify(runtime, null, 2) : ''}</pre>
          </div>
        </div>
      `;

      container.querySelector('#logout-btn')?.addEventListener('click', () => api.logout());
      const readPoliciesForm = () => {
        const globalTimeoutRaw = (container.querySelector('#policy-global-timeout')?.value || '').trim();
        return {
          global_timeout: globalTimeoutRaw ? Number.parseInt(globalTimeoutRaw, 10) : null,
          virtual_scheduler_mode: container.querySelector('#policy-virtual-scheduler-mode')?.value || 'global_pool',
          key_busy_wait_interval_seconds: Number.parseFloat(container.querySelector('#policy-busy-wait-interval')?.value || '0.2'),
          key_busy_wait_max_attempts: Number.parseInt(container.querySelector('#policy-busy-wait-attempts')?.value || '5', 10),
          scarcity_probe_budget_ratio: Number.parseFloat(container.querySelector('#policy-probe-ratio')?.value || '0.01'),
          scarcity_probe_burst: Number.parseInt(container.querySelector('#policy-probe-burst')?.value || '3', 10),
        };
      };

      const savePolicies = async (applyAfter = false) => {
        const payload = readPoliciesForm();
        const updated = await api.updatePolicies(payload);
        if (applyAfter) {
          const applied = await api.applyAdminConfig();
          container.querySelector('#settings-output').textContent = JSON.stringify(applied, null, 2);
          showToast('调度策略已保存并应用', 'success');
        } else {
          container.querySelector('#settings-output').textContent = JSON.stringify(updated, null, 2);
          showToast('调度策略已保存', 'success');
        }
        await render();
      };

      container.querySelector('#admin-save-policies-btn')?.addEventListener('click', async () => {
        try {
          await savePolicies(false);
        } catch (e) {
          showToast(`保存策略失败: ${e.message}`, 'error');
        }
      });

      container.querySelector('#admin-save-apply-btn')?.addEventListener('click', async () => {
        try {
          await savePolicies(true);
        } catch (e) {
          showToast(`保存并应用失败: ${e.message}`, 'error');
        }
      });

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
