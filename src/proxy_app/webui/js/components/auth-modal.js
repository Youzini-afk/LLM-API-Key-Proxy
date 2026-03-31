// ============================================================
// Auth Modal Component
// ============================================================
import { h, $, icon } from '../utils/dom.js';
import { api } from '../api.js';
import { showToast } from './toast.js';

/**
 * Show authentication modal if no API key is stored
 * @returns {Promise<boolean>} true if authenticated
 */
export async function checkAuth() {
  // If key exists, test it
  if (api.hasApiKey()) {
    const result = await api.testConnection();
    if (result.ok) return true;
    // Key is invalid, show modal
  }

  return showAuthModal();
}

/**
 * Display the auth modal and wait for user to authenticate
 * @returns {Promise<boolean>}
 */
export function showAuthModal() {
  return new Promise((resolve) => {
    const existing = $('#auth-modal');
    if (existing) existing.remove();

    const overlay = h('div', { id: 'auth-modal', className: 'modal-overlay' },
      h('div', { className: 'modal-card' },
        h('div', { className: 'modal-header' },
          h('span', { className: 'modal-icon' }, icon('lock', 28)),
          h('h2', { className: 'modal-title' }, '连接到代理服务')
        ),
        h('p', { className: 'modal-desc' }, '请输入您的 PROXY_API_KEY 进行身份验证。此密钥与 API 访问密钥相同。'),
        h('div', { className: 'modal-body' },
          h('label', { className: 'input-label' }, '认证密钥'),
          h('input', {
            id: 'auth-key-input',
            type: 'password',
            className: 'input-field',
            placeholder: '输入 PROXY_API_KEY...',
            autocomplete: 'off',
          }),
          h('div', { id: 'auth-error-msg', className: 'auth-error-msg', style: 'display:none' }),
          h('label', { className: 'input-checkbox-label mt-md' },
            h('input', { type: 'checkbox', id: 'auth-show-key' }),
            h('span', {}, ' 显示密钥')
          )
        ),
        h('div', { className: 'modal-footer' },
          h('button', {
            className: 'btn btn-ghost',
            onClick: () => {
              // Try without key (for unsecured proxies)
              api.setApiKey('');
              overlay.remove();
              resolve(true);
            }
          }, '跳过（无密钥）'),
          h('button', {
            id: 'auth-submit-btn',
            className: 'btn btn-primary',
            onClick: async () => {
              const input = $('#auth-key-input');
              const btn = $('#auth-submit-btn');
              const errEl = $('#auth-error-msg');
              const key = input.value.trim();
              if (!key) {
                input.classList.add('input-error');
                return;
              }

              btn.textContent = '验证中...';
              btn.disabled = true;
              errEl.style.display = 'none';

              api.setApiKey(key);
              const result = await api.testConnection();

              if (result.ok) {
                showToast('认证成功', 'success');
                overlay.remove();
                resolve(true);
              } else {
                const errText = result.status
                  ? `错误 ${result.status}: ${result.detail}`
                  : result.detail;
                errEl.textContent = errText;
                errEl.style.display = 'block';
                showToast('认证失败', 'error');
                btn.textContent = '连接';
                btn.disabled = false;
                input.classList.add('input-error');
              }
            }
          }, '连接')
        )
      )
    );

    document.body.appendChild(overlay);

    // Focus input
    setTimeout(() => {
      const input = $('#auth-key-input');
      input.focus();
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') $('#auth-submit-btn').click();
        input.classList.remove('input-error');
      });
    }, 100);

    // Show/hide password toggle
    const showKeyCheckbox = $('#auth-show-key');
    if (showKeyCheckbox) {
      showKeyCheckbox.addEventListener('change', () => {
        const input = $('#auth-key-input');
        input.type = showKeyCheckbox.checked ? 'text' : 'password';
      });
    }
  });
}
