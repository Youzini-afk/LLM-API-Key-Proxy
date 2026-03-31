// ============================================================
// Channels Page — 渠道管理
// ============================================================
import { h, clearChildren, icon, delegate } from '../utils/dom.js';
import { api } from '../api.js';
import { formatNumber, formatTokens } from '../utils/format.js';
import { KeyTable, StatusBadge } from '../components/ui.js';
import { showToast } from '../components/toast.js';

export async function renderChannels(container) {
  clearChildren(container);
  container.appendChild(h('div', { className: 'page-loading' }, '加载中...'));

  try {
    const quotaStats = await api.getQuotaStats();
    clearChildren(container);

    const providers = quotaStats.providers || {};
    const page = h('div', { className: 'page', id: 'page-channels' });

    // Page header
    page.appendChild(h('div', { className: 'page-title' },
      h('span', { className: 'page-title-icon' }, icon('link', 24)),
      '渠道管理',
      h('div', { className: 'page-actions' },
        h('button', { className: 'btn btn-ghost btn-sm', id: 'btn-expand-all' }, '全部展开'),
        h('button', { className: 'btn btn-ghost btn-sm', id: 'btn-collapse-all' }, '全部折叠'),
        h('button', {
          className: 'btn btn-primary btn-sm',
          onClick: async () => {
            showToast('正在刷新配额...', 'info');
            try {
              await api.refreshQuota('reload');
              showToast('配额已刷新', 'success');
              renderChannels(container);
            } catch (e) {
              showToast('刷新失败: ' + e.message, 'error');
            }
          }
        }, icon('refresh', 14), ' 刷新配额')
      )
    ));

    // Channel list
    const channelList = h('div', { className: 'channel-list' });

    const providerEntries = Object.entries(providers);
    providerEntries.forEach(([provName, provData], index) => {
      const creds = provData.credentials || [];
      const active = creds.filter(c => !c.cooldown_until || c.cooldown_until <= Date.now() / 1000).length;
      const cooldown = provData.on_cooldown_count || 0;
      const exhausted = provData.exhausted_count || 0;
      const tokens = provData.tokens || {};
      const totalTokens = (tokens.total_input || 0) + (tokens.total_output || 0);
      const isFirst = index === 0;

      const accordion = h('div', { className: `channel-accordion ${isFirst ? 'channel-accordion-open' : ''}`, dataset: { channel: provName } },
        // Header (clickable)
        h('div', { className: 'channel-accordion-header', onClick: (e) => {
          const acc = e.currentTarget.parentElement;
          acc.classList.toggle('channel-accordion-open');
        }},
          h('div', { className: 'channel-accordion-left' },
            h('span', { className: 'channel-accordion-arrow' }, '▶'),
            h('span', { className: 'channel-accordion-name font-headline' }, provName),
            h('div', { className: 'channel-accordion-badges' },
              h('span', { className: 'badge badge-sm badge-outline' }, `${creds.length} Keys`),
              active > 0 ? h('span', { className: 'badge badge-sm badge-success' }, `${active} 活跃`) : null,
              cooldown > 0 ? h('span', { className: 'badge badge-sm badge-warning' }, `${cooldown} 冷却`) : null,
              exhausted > 0 ? h('span', { className: 'badge badge-sm badge-error' }, `${exhausted} 耗尽`) : null,
            )
          ),
          h('div', { className: 'channel-accordion-right text-muted' },
            h('span', {}, `请求: ${formatNumber(provData.total_requests || 0)}`),
            h('span', {}, `Token: ${formatTokens(totalTokens)}`)
          )
        ),
        // Body (expandable)
        h('div', { className: 'channel-accordion-body' },
          KeyTable({
            credentials: creds.map(c => ({
              credential: c.credential || c.name || '未知',
              status: c.cooldown_until && c.cooldown_until > Date.now() / 1000 ? 'cooldown' :
                (c.exhausted ? 'exhausted' : 'active'),
              requests: c.requests || 0,
              tokens: c.tokens || {},
              approx_cost: c.approx_cost || 0,
              cooldown_until: c.cooldown_until || null,
            })),
            onForceRefresh: async () => {
              showToast(`正在强制刷新 ${provName}...`, 'info');
              try {
                await api.refreshQuota('force_refresh', 'provider', provName);
                showToast(`${provName} 配额已刷新`, 'success');
                renderChannels(container);
              } catch (e) {
                showToast('刷新失败: ' + e.message, 'error');
              }
            }
          })
        )
      );

      channelList.appendChild(accordion);
    });

    if (providerEntries.length === 0) {
      channelList.appendChild(h('div', { className: 'page-empty' }, '未发现已配置的渠道'));
    }

    page.appendChild(channelList);
    container.appendChild(page);

    // Expand/Collapse All
    delegate(page, 'click', '#btn-expand-all', () => {
      page.querySelectorAll('.channel-accordion').forEach(a => a.classList.add('channel-accordion-open'));
    });
    delegate(page, 'click', '#btn-collapse-all', () => {
      page.querySelectorAll('.channel-accordion').forEach(a => a.classList.remove('channel-accordion-open'));
    });

  } catch (err) {
    clearChildren(container);
    container.appendChild(h('div', { className: 'page-error' },
      h('h3', {}, '加载失败'),
      h('p', { className: 'text-muted' }, err.message),
      h('button', { className: 'btn btn-primary mt-lg', onClick: () => renderChannels(container) }, '重试')
    ));
  }
}
