// ============================================================
// Dashboard Page — 仪表盘总览
// ============================================================
import { h, clearChildren, icon } from '../utils/dom.js';
import { api } from '../api.js';
import { formatNumber, formatTokens, formatCost } from '../utils/format.js';
import { StatCard, ChannelCard, RouteChain } from '../components/ui.js';
import { showToast } from '../components/toast.js';

/**
 * Extract aggregated model stats for a provider from quota stats
 */
function extractModelStats(providerData) {
  const modelMap = {};
  if (!providerData.credentials) return [];
  for (const cred of providerData.credentials) {
    if (!cred.models) continue;
    for (const [modelName, modelData] of Object.entries(cred.models)) {
      if (!modelMap[modelName]) {
        modelMap[modelName] = { name: modelName.split('/').pop(), used: 0, total: 0 };
      }
      modelMap[modelName].used += modelData.requests || 0;
      if (modelData.quota_max_requests) {
        modelMap[modelName].total = Math.max(modelMap[modelName].total, modelData.quota_max_requests);
      }
    }
  }
  return Object.values(modelMap).filter(m => m.total > 0 || m.used > 0);
}

/**
 * Parse virtual model info from quota stats (or from /v1/models)
 */
function extractVirtualModels(quotaStats) {
  // Virtual models are in the stats under a special section or we can infer from provider names
  // For now, we'll fetch from the models endpoint separately
  return [];
}

export async function renderDashboard(container) {
  clearChildren(container);
  container.appendChild(h('div', { className: 'page-loading' }, '加载中...'));

  try {
    const [quotaStats, modelsResp] = await Promise.all([
      api.getQuotaStats(),
      api.getModels(true).catch(() => ({ data: [] })),
    ]);

    clearChildren(container);
    const page = h('div', { className: 'page', id: 'page-dashboard' });

    // --- Summary Stats ---
    const summary = quotaStats.summary || {};
    const providers = quotaStats.providers || {};
    const providerCount = Object.keys(providers).length;
    const totalCreds = summary.total_credentials || Object.values(providers).reduce((s, p) => s + (p.credential_count || 0), 0);
    const activeCreds = summary.total_active || Object.values(providers).reduce((s, p) => s + (p.active_count || 0), 0);
    const cooldownCreds = summary.total_cooldown || Object.values(providers).reduce((s, p) => s + (p.on_cooldown_count || 0), 0);
    const exhaustedCreds = summary.total_exhausted || Object.values(providers).reduce((s, p) => s + (p.exhausted_count || 0), 0);
    const totalRequests = summary.total_requests || Object.values(providers).reduce((s, p) => s + (p.total_requests || 0), 0);
    const totalCost = summary.total_cost || Object.values(providers).reduce((s, p) => s + (p.approx_cost || 0), 0);
    const totalTokens = Object.values(providers).reduce((s, p) => {
      const t = p.tokens || {};
      return s + (t.total_input || 0) + (t.total_output || 0);
    }, 0);

    const statsGrid = h('div', { className: 'stat-grid' },
      StatCard({
        title: '系统状态',
        value: '运行中',
        subtitle: `${providerCount} 个渠道在线`,
        icon: icon('bolt', 20),
        accentColor: 'var(--secondary)',
      }),
      StatCard({
        title: '活跃渠道',
        value: `${providerCount}`,
        subtitle: '全部在线',
        icon: icon('link', 20),
        accentColor: 'var(--primary)',
      }),
      StatCard({
        title: 'Key 状态',
        value: `${totalCreds}`,
        subtitle: `${activeCreds} 活跃 · ${cooldownCreds} 冷却 · ${exhaustedCreds} 耗尽`,
        icon: icon('key', 20),
        accentColor: exhaustedCreds > 0 ? 'var(--tertiary)' : 'var(--secondary)',
      }),
      StatCard({
        title: '请求总数',
        value: formatNumber(totalRequests),
        subtitle: `${formatCost(totalCost)} 估算费用`,
        icon: icon('chart', 20),
        accentColor: 'var(--primary)',
      })
    );

    // --- Channel Health ---
    const channelSection = h('div', { className: 'section' },
      h('div', { className: 'section-title' },
        h('span', { className: 'section-title-icon' }, icon('diamond', 20)),
        '渠道健康'
      )
    );

    const channelGrid = h('div', { className: 'card-grid' });
    for (const [provName, provData] of Object.entries(providers)) {
      const models = extractModelStats(provData);
      const tokens = provData.tokens || {};
      const card = ChannelCard({
        name: provName,
        endpoint: '',
        credentials: (provData.credentials || []).map(c => ({
          status: c.cooldown_until && c.cooldown_until > Date.now() / 1000 ? 'cooldown' :
            (c.exhausted ? 'exhausted' : 'active'),
          ...c,
        })),
        totalRequests: provData.total_requests || 0,
        totalTokens: (tokens.total_input || 0) + (tokens.total_output || 0),
        models,
      });
      channelGrid.appendChild(card);
    }
    channelSection.appendChild(channelGrid);

    // --- Virtual Model Routes ---
    const virtualSection = h('div', { className: 'section' },
      h('div', { className: 'section-title' },
        h('span', { className: 'section-title-icon' }, icon('route', 20)),
        '虚拟模型路由'
      )
    );

    // Virtual models from the models list
    const virtualModels = (modelsResp.data || []).filter(m =>
      !m.id.includes('/') || m.owned_by === 'Mirro-Proxy'
    );

    // We'll show route info if available from quota stats or model data
    const routeContainer = h('div', { className: 'card-grid-2' });

    // Try to find virtual model route info — look for models that appear across multiple providers
    const modelProviderMap = {};
    for (const [provName, provData] of Object.entries(providers)) {
      for (const cred of (provData.credentials || [])) {
        if (!cred.models) continue;
        for (const modelName of Object.keys(cred.models)) {
          const shortName = modelName.split('/').pop();
          if (!modelProviderMap[shortName]) modelProviderMap[shortName] = new Set();
          modelProviderMap[shortName].add(provName);
        }
      }
    }

    // Show models that exist across multiple providers as "virtual-like" routes
    const multiProviderModels = Object.entries(modelProviderMap).filter(([_, pSet]) => pSet.size > 1);
    if (multiProviderModels.length > 0) {
      for (const [modelName, provSet] of multiProviderModels) {
        const targets = [...provSet].map(p => ({
          model: `${p}/${modelName}`,
          enabled: true,
          weight: 100,
        }));
        routeContainer.appendChild(RouteChain({
          name: modelName,
          strategy: 'sequential',
          targets,
        }));
      }
    } else {
      routeContainer.appendChild(h('div', { className: 'text-muted' }, '未配置虚拟模型路由'));
    }

    virtualSection.appendChild(routeContainer);

    // Assemble page
    page.appendChild(statsGrid);
    page.appendChild(channelSection);
    page.appendChild(virtualSection);
    container.appendChild(page);

  } catch (err) {
    clearChildren(container);
    container.appendChild(h('div', { className: 'page-error' },
      h('h3', {}, '加载失败'),
      h('p', { className: 'text-muted' }, err.message),
      h('button', { className: 'btn btn-primary mt-lg', onClick: () => renderDashboard(container) }, '重试')
    ));
    showToast('仪表盘加载失败: ' + err.message, 'error');
  }
}
