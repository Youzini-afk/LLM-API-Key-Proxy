// ============================================================
// Header Component
// ============================================================
import { h, icon } from '../utils/dom.js';
import { api } from '../api.js';
import { maskKey } from '../utils/format.js';
import { showToast } from './toast.js';

/**
 * Render the global header bar
 */
export function renderHeader(container, { onRefresh, onIntervalChange }) {
  const header = h('header', { className: 'header' },
    // Left: status
    h('div', { className: 'header-left' },
      h('span', { className: 'header-status-dot pulse-active' }),
      h('span', { className: 'header-status-text', id: 'header-status' }, '已连接')
    ),

    // Right: controls
    h('div', { className: 'header-right' },
      // Auto-refresh selector
      h('div', { className: 'header-refresh flex items-center gap-sm' },
        h('label', { className: 'text-muted', style: { fontSize: 'var(--text-label-md)' } }, '自动刷新'),
        h('select', {
          id: 'refresh-interval',
          className: 'select-field select-sm',
          onChange: (e) => onIntervalChange?.(parseInt(e.target.value)),
        },
          h('option', { value: '0' }, '关闭'),
          h('option', { value: '10000' }, '10秒'),
          h('option', { value: '30000', selected: true }, '30秒'),
          h('option', { value: '60000' }, '1分钟'),
        ),
        h('button', {
          className: 'btn btn-icon',
          title: '立即刷新',
          onClick: () => onRefresh?.(),
        }, icon('refresh', 18))
      ),

      // API key indicator
      h('div', { className: 'header-key' },
        h('span', { className: 'badge badge-outline' },
          h('span', { className: 'header-status-dot', style: { width: '6px', height: '6px' } }),
          h('span', { className: 'text-mono', style: { fontSize: 'var(--text-label-sm)' } },
            maskKey(api.getApiKey()) || '无密钥'
          )
        )
      )
    )
  );

  container.appendChild(header);
}

/**
 * Update header status
 */
export function updateHeaderStatus(text, isOnline = true) {
  const statusEl = document.getElementById('header-status');
  const dotEl = statusEl?.previousElementSibling;
  if (statusEl) statusEl.textContent = text;
  if (dotEl) {
    dotEl.className = isOnline ? 'header-status-dot pulse-active' : 'header-status-dot pulse-error';
  }
}
