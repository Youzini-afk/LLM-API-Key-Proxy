// ============================================================
// Sidebar Navigation Component
// ============================================================
import { h, icon } from '../utils/dom.js';

const NAV_ITEMS = [
  { id: 'dashboard', icon: 'dashboard', label: '仪表盘', hash: '#/' },
  { id: 'channels', icon: 'channels', label: '渠道管理', hash: '#/channels' },
  { id: 'models', icon: 'models', label: '模型列表', hash: '#/models' },
  { id: 'stats', icon: 'stats', label: '统计分析', hash: '#/stats' },
];

export function renderSidebar(container) {
  const sidebar = h('nav', { className: 'sidebar' },
    // Logo
    h('div', { className: 'sidebar-logo' },
      h('span', { className: 'sidebar-logo-icon' }, icon('bolt', 22)),
      h('div', { className: 'sidebar-logo-text' },
        h('span', { className: 'sidebar-logo-title' }, 'LLM Proxy'),
        h('span', { className: 'sidebar-logo-subtitle' }, '控制面板')
      )
    ),

    // Navigation
    h('ul', { className: 'sidebar-nav', id: 'sidebar-nav' },
      ...NAV_ITEMS.map(item =>
        h('li', {},
          h('a', {
            href: item.hash,
            className: 'sidebar-nav-item',
            dataset: { page: item.id },
          },
            h('span', { className: 'sidebar-nav-icon' }, icon(item.icon, 20)),
            h('span', { className: 'sidebar-nav-label' }, item.label)
          )
        )
      )
    ),

    // Bottom section
    h('div', { className: 'sidebar-bottom' },
      h('a', {
        href: '#/settings',
        className: 'sidebar-nav-item sidebar-nav-settings',
        dataset: { page: 'settings' },
      },
        h('span', { className: 'sidebar-nav-icon' }, icon('settings', 20)),
        h('span', { className: 'sidebar-nav-label' }, '设置')
      )
    )
  );

  container.appendChild(sidebar);
  updateActiveNav();
}

/**
 * Update active nav item based on current hash
 */
export function updateActiveNav() {
  const hash = window.location.hash || '#/';
  const navItems = document.querySelectorAll('.sidebar-nav-item');
  navItems.forEach(item => {
    const itemHash = item.getAttribute('href');
    const isActive = hash === itemHash || (hash === '' && itemHash === '#/');
    item.classList.toggle('active', isActive);
  });
}
