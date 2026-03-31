import { h, icon } from '../utils/dom.js';

let toastContainer = null;

function ensureContainer() {
  if (!toastContainer) {
    toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
      toastContainer = h('div', { id: 'toast-container', className: 'toast-container' });
      document.body.appendChild(toastContainer);
    }
  }
  return toastContainer;
}

/**
 * Show a toast notification
 * @param {string} message
 * @param {'info'|'success'|'warning'|'error'} type
 * @param {number} duration - ms
 */
export function showToast(message, type = 'info', duration = 3000) {
  const container = ensureContainer();
  const typeIconMap = {
    info: 'info',
    success: 'checkCircle',
    warning: 'warning',
    error: 'error',
  };

  const toast = h('div', { className: `toast toast-${type}` },
    h('span', { className: 'toast-icon' }, icon(typeIconMap[type] || 'info', 18)),
    h('span', { className: 'toast-message' }, message),
    h('button', {
      className: 'toast-close',
      onClick: () => removeToast(toast),
    }, '×')
  );

  container.appendChild(toast);

  // Trigger animation
  requestAnimationFrame(() => toast.classList.add('toast-show'));

  if (duration > 0) {
    setTimeout(() => removeToast(toast), duration);
  }

  return toast;
}

function removeToast(toast) {
  toast.classList.remove('toast-show');
  toast.classList.add('toast-hide');
  setTimeout(() => toast.remove(), 300);
}
