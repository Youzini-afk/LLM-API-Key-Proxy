// ============================================================
// Reusable UI Components (stat-card, quota-bar, channel-card, key-table, route-chain, bar-chart)
// ============================================================
import { h, icon } from '../utils/dom.js';
import { formatNumber, formatTokens, formatCost, formatPercent, formatCooldown, maskKey, getStatusInfo, getStrategyLabel } from '../utils/format.js';

// --- Stat Card ---
export function StatCard({ title, value, subtitle, icon: iconName, accentColor }) {
  return h('div', { className: 'stat-card' },
    h('div', { className: 'stat-card-header' },
      h('span', { className: 'stat-card-title' }, title),
      iconName ? h('span', { className: 'stat-card-icon', style: { color: accentColor || '' } }, iconName) : null
    ),
    h('div', { className: 'stat-card-value font-headline', style: { color: accentColor || '' } }, value),
    subtitle ? h('div', { className: 'stat-card-subtitle text-muted' }, subtitle) : null
  );
}

// --- Quota Bar ---
export function QuotaBar({ label, current, max, showLabel = true }) {
  const pct = max > 0 ? Math.min(100, Math.round((current / max) * 100)) : 0;
  const colorClass = pct >= 90 ? 'quota-bar-danger' : pct >= 70 ? 'quota-bar-warning' : 'quota-bar-ok';

  return h('div', { className: 'quota-bar-wrap' },
    showLabel ? h('div', { className: 'quota-bar-label flex justify-between' },
      h('span', { className: 'text-body-sm' }, label),
      h('span', { className: `text-label-sm ${pct >= 90 ? 'text-error' : pct >= 70 ? 'text-tertiary' : 'text-muted'}` }, `${pct}%`)
    ) : null,
    h('div', { className: 'quota-bar' },
      h('div', { className: `quota-bar-fill ${colorClass}`, style: { width: `${pct}%` } })
    )
  );
}

// --- Status Badge ---
export function StatusBadge(status) {
  const info = getStatusInfo(status);
  return h('span', { className: `badge badge-status badge-${status}` },
    h('span', { className: `status-dot status-${status}` }),
    info.label
  );
}

// --- Channel Card (compact, for dashboard) ---
export function ChannelCard({ name, endpoint, credentials, totalRequests, totalTokens, models }) {
  const active = credentials.filter(c => c.status === 'active').length;
  const cooldown = credentials.filter(c => c.status === 'cooldown').length;
  const exhausted = credentials.filter(c => c.status === 'exhausted').length;
  const total = credentials.length;
  const statusClass = exhausted > 0 ? 'channel-degraded' : cooldown > 0 ? 'channel-partial' : 'channel-healthy';

  return h('div', { className: `channel-card ${statusClass}` },
    h('div', { className: 'channel-card-header' },
      h('div', { className: 'channel-card-name' },
        h('span', { className: 'channel-card-title font-headline' }, name),
        h('span', { className: `badge badge-sm ${statusClass === 'channel-healthy' ? 'badge-success' : statusClass === 'channel-partial' ? 'badge-warning' : 'badge-error'}` },
          statusClass === 'channel-healthy' ? '正常' : statusClass === 'channel-partial' ? '部分' : '降级'
        )
      ),
      h('div', { className: 'channel-card-keys text-muted text-label-sm' },
        `${active} 活跃`,
        cooldown > 0 ? ` · ${cooldown} 冷却` : '',
        exhausted > 0 ? ` · ${exhausted} 耗尽` : '',
        ` / ${total} Keys`
      )
    ),
    // Model quota bars
    models && models.length > 0 ? h('div', { className: 'channel-card-models mt-md' },
      ...models.slice(0, 4).map(m =>
        QuotaBar({ label: m.name, current: m.used, max: m.total, showLabel: true })
      )
    ) : null,
    // Footer stats
    h('div', { className: 'channel-card-footer mt-md' },
      h('span', { className: 'text-label-sm text-muted' }, `请求: ${formatNumber(totalRequests)}`),
      h('span', { className: 'text-label-sm text-muted' }, `Token: ${formatTokens(totalTokens)}`)
    )
  );
}

// --- Key Table ---
export function KeyTable({ credentials, onForceRefresh }) {
  const headerCols = ['API Key', '状态', '请求', '输入 Token', '输出 Token', '缓存%', '费用', '冷却剩余'];

  return h('div', { className: 'key-table-wrap' },
    h('table', { className: 'key-table' },
      h('thead', {},
        h('tr', {},
          ...headerCols.map(col => h('th', {}, col))
        )
      ),
      h('tbody', {},
        ...credentials.map(cred => {
          const info = getStatusInfo(cred.status);
          const cd = formatCooldown(cred.cooldown_until);
          const tokens = cred.tokens || {};
          const cacheP = tokens.total_input > 0 ? Math.round((tokens.total_cached || 0) / tokens.total_input * 100) : 0;

          return h('tr', { className: cred.status === 'exhausted' ? 'row-exhausted' : cred.status === 'cooldown' ? 'row-cooldown' : '' },
            h('td', { className: 'text-mono' }, maskKey(cred.credential)),
            h('td', {}, StatusBadge(cred.status)),
            h('td', {}, String(cred.requests || 0)),
            h('td', {}, formatTokens(tokens.total_input)),
            h('td', {}, formatTokens(tokens.total_output)),
            h('td', { className: cacheP > 30 ? 'text-secondary' : 'text-muted' }, cacheP > 0 ? `${cacheP}%` : '-'),
            h('td', {}, formatCost(cred.approx_cost)),
            h('td', { className: cd.isActive ? (cd.seconds > 3600 ? 'text-error' : 'text-tertiary') : '' },
              cd.text
            )
          );
        })
      )
    ),
    onForceRefresh ? h('div', { className: 'key-table-actions mt-md' },
      h('button', { className: 'btn btn-ghost btn-sm', onClick: onForceRefresh },
        icon('refresh', 14), ' 强制刷新配额'
      )
    ) : null
  );
}

// --- Route Chain (Virtual Model visualization) ---
export function RouteChain({ name, strategy, targets }) {
  return h('div', { className: 'route-chain-card' },
    h('div', { className: 'route-chain-header' },
      h('span', { className: 'route-chain-name font-headline' }, name),
      h('span', { className: 'badge badge-outline badge-sm' }, getStrategyLabel(strategy))
    ),
    h('div', { className: 'route-chain-flow' },
      ...targets.map((target, i) => {
        const parts = target.model.split('/');
        return h('div', { className: 'route-chain-step-wrap' },
          i > 0 ? h('span', { className: 'route-chain-arrow' }, '→') : null,
          h('div', { className: `route-chain-node ${target.enabled ? '' : 'route-chain-node-disabled'}` },
            h('span', { className: 'route-chain-num' }, `${i + 1}`),
            h('div', { className: 'route-chain-info' },
              h('span', { className: 'route-chain-provider' }, parts[0]),
              h('span', { className: 'route-chain-model text-muted' }, parts.slice(1).join('/'))
            ),
            h('span', { className: `status-dot ${target.enabled ? 'status-active' : 'status-disabled'}` })
          )
        );
      })
    )
  );
}

// --- Bar Chart (horizontal) ---
export function BarChart({ items, maxValue, colorVar = 'var(--primary)' }) {
  if (!items || items.length === 0) return h('div', { className: 'text-muted' }, '暂无数据');
  const max = maxValue || Math.max(...items.map(i => i.value));

  return h('div', { className: 'bar-chart' },
    ...items.map(item => {
      const pct = max > 0 ? (item.value / max) * 100 : 0;
      return h('div', { className: 'bar-chart-row' },
        h('div', { className: 'bar-chart-label' },
          h('span', {}, item.label),
          h('span', { className: 'text-muted text-label-sm' }, `${formatNumber(item.value)} (${Math.round(item.percent || pct)}%)`)
        ),
        h('div', { className: 'bar-chart-track' },
          h('div', {
            className: 'bar-chart-fill',
            style: {
              width: `${pct}%`,
              background: item.color || colorVar,
            }
          })
        )
      );
    })
  );
}
