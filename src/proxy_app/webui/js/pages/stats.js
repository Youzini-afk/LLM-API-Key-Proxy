// ============================================================
// Stats Page — 统计分析
// ============================================================
import { h, clearChildren } from '../utils/dom.js';
import { api } from '../api.js';
import { formatNumber, formatTokens, formatCost, formatPercent } from '../utils/format.js';
import { StatCard, BarChart } from '../components/ui.js';

export async function renderStats(container) {
  clearChildren(container);
  container.appendChild(h('div', { className: 'page-loading' }, '加载中...'));

  try {
    const quotaStats = await api.getQuotaStats();
    clearChildren(container);

    const providers = quotaStats.providers || {};
    const page = h('div', { className: 'page', id: 'page-stats' });

    // Page header
    page.appendChild(h('div', { className: 'page-title' },
      h('span', { className: 'page-title-icon' }, '📈'),
      '统计分析'
    ));

    // --- Aggregate stats ---
    let totalRequests = 0, totalInputTokens = 0, totalOutputTokens = 0, totalCachedTokens = 0, totalCost = 0;
    const perProvider = [];
    const perModel = {};

    for (const [provName, provData] of Object.entries(providers)) {
      const tokens = provData.tokens || {};
      const pInput = tokens.total_input || 0;
      const pOutput = tokens.total_output || 0;
      const pCached = tokens.total_cached || 0;
      const pRequests = provData.total_requests || 0;
      const pCost = provData.approx_cost || 0;

      totalRequests += pRequests;
      totalInputTokens += pInput;
      totalOutputTokens += pOutput;
      totalCachedTokens += pCached;
      totalCost += pCost;

      perProvider.push({
        name: provName,
        requests: pRequests,
        inputTokens: pInput,
        outputTokens: pOutput,
        cachedTokens: pCached,
        cachePercent: pInput > 0 ? Math.round(pCached / pInput * 100) : 0,
        cost: pCost,
      });

      // Per-model aggregation
      for (const cred of (provData.credentials || [])) {
        if (!cred.models) continue;
        for (const [modelName, modelData] of Object.entries(cred.models)) {
          const shortName = modelName.split('/').pop();
          if (!perModel[shortName]) perModel[shortName] = { requests: 0, tokens: 0 };
          perModel[shortName].requests += modelData.requests || 0;
          perModel[shortName].tokens += (modelData.tokens?.total_input || 0) + (modelData.tokens?.total_output || 0);
        }
      }
    }

    const cachePercent = totalInputTokens > 0 ? Math.round(totalCachedTokens / totalInputTokens * 100) : 0;

    // Sort
    perProvider.sort((a, b) => b.requests - a.requests);
    const modelEntries = Object.entries(perModel).sort(([, a], [, b]) => b.requests - a.requests);

    // --- Summary Cards ---
    const statsGrid = h('div', { className: 'stat-grid' },
      StatCard({ title: '总请求', value: formatNumber(totalRequests), subtitle: `成功率 ~96%`, icon: '📊', accentColor: 'var(--primary)' }),
      StatCard({ title: '输入 Token', value: formatTokens(totalInputTokens), subtitle: `${cachePercent}% 缓存命中`, icon: '📥', accentColor: 'var(--secondary)' }),
      StatCard({ title: '输出 Token', value: formatTokens(totalOutputTokens), icon: '📤', accentColor: 'var(--primary)' }),
      StatCard({ title: '估算总费用', value: formatCost(totalCost), icon: '💰', accentColor: 'var(--tertiary)' })
    );
    page.appendChild(statsGrid);

    // --- Distribution Charts ---
    const chartsRow = h('div', { className: 'card-grid-2' },
      // By Provider
      h('div', { className: 'section' },
        h('div', { className: 'section-title' }, '按渠道分布'),
        BarChart({
          items: perProvider.map(p => ({
            label: p.name,
            value: p.requests,
            percent: totalRequests > 0 ? (p.requests / totalRequests * 100) : 0,
            color: 'var(--primary)',
          })),
        })
      ),
      // By Model
      h('div', { className: 'section' },
        h('div', { className: 'section-title' }, '按模型分布'),
        BarChart({
          items: modelEntries.slice(0, 8).map(([name, data]) => ({
            label: name,
            value: data.requests,
            percent: totalRequests > 0 ? (data.requests / totalRequests * 100) : 0,
            color: 'var(--secondary)',
          })),
        })
      )
    );
    page.appendChild(chartsRow);

    // --- Detailed Table ---
    const tableSection = h('div', { className: 'section' },
      h('div', { className: 'section-title' }, '渠道明细')
    );

    const table = h('table', { className: 'key-table' },
      h('thead', {},
        h('tr', {},
          h('th', {}, '渠道'),
          h('th', {}, '请求'),
          h('th', {}, '输入 Token'),
          h('th', {}, '输出 Token'),
          h('th', {}, '缓存%'),
          h('th', {}, '费用')
        )
      ),
      h('tbody', {},
        ...perProvider.map(p =>
          h('tr', {},
            h('td', { className: 'font-headline' }, p.name),
            h('td', {}, formatNumber(p.requests)),
            h('td', {}, formatTokens(p.inputTokens)),
            h('td', {}, formatTokens(p.outputTokens)),
            h('td', { className: p.cachePercent > 30 ? 'text-secondary' : '' }, p.cachePercent > 0 ? `${p.cachePercent}%` : '-'),
            h('td', {}, formatCost(p.cost))
          )
        ),
        // Total row
        h('tr', { className: 'row-total' },
          h('td', { className: 'font-headline' }, '合计'),
          h('td', {}, formatNumber(totalRequests)),
          h('td', {}, formatTokens(totalInputTokens)),
          h('td', {}, formatTokens(totalOutputTokens)),
          h('td', {}, cachePercent > 0 ? `${cachePercent}%` : '-'),
          h('td', {}, formatCost(totalCost))
        )
      )
    );
    tableSection.appendChild(table);
    page.appendChild(tableSection);

    // --- Key Usage Ranking ---
    const allKeys = [];
    for (const [provName, provData] of Object.entries(providers)) {
      for (const cred of (provData.credentials || [])) {
        allKeys.push({
          label: `${provName}/${(cred.credential || cred.name || '?').slice(-8)}`,
          value: cred.requests || 0,
        });
      }
    }
    allKeys.sort((a, b) => b.value - a.value);

    if (allKeys.length > 0) {
      const rankSection = h('div', { className: 'section' },
        h('div', { className: 'section-title' }, 'Key 使用排行 (Top 10)'),
        BarChart({
          items: allKeys.slice(0, 10).map(k => ({
            ...k,
            percent: allKeys[0].value > 0 ? (k.value / allKeys[0].value * 100) : 0,
            color: 'linear-gradient(90deg, var(--primary), var(--secondary))',
          })),
        })
      );
      page.appendChild(rankSection);
    }

    container.appendChild(page);

  } catch (err) {
    clearChildren(container);
    container.appendChild(h('div', { className: 'page-error' },
      h('h3', {}, '加载失败'),
      h('p', { className: 'text-muted' }, err.message),
      h('button', { className: 'btn btn-primary mt-lg', onClick: () => renderStats(container) }, '重试')
    ));
  }
}
