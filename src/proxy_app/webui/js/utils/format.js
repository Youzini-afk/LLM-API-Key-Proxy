// ============================================================
// Formatting Utilities
// ============================================================

/**
 * Format large numbers with K/M/B suffix
 * @param {number} num
 * @param {number} decimals
 * @returns {string}
 */
export function formatNumber(num, decimals = 1) {
  if (num == null || isNaN(num)) return '-';
  if (num === 0) return '0';
  const abs = Math.abs(num);
  if (abs >= 1e9) return (num / 1e9).toFixed(decimals) + 'B';
  if (abs >= 1e6) return (num / 1e6).toFixed(decimals) + 'M';
  if (abs >= 1e4) return (num / 1e3).toFixed(decimals) + 'K';
  return num.toLocaleString('zh-CN');
}

/**
 * Format token count (always use K/M)
 */
export function formatTokens(num) {
  if (num == null || isNaN(num)) return '-';
  if (num === 0) return '0';
  if (num >= 1e6) return (num / 1e6).toFixed(1) + 'M';
  if (num >= 1e3) return (num / 1e3).toFixed(1) + 'K';
  return String(num);
}

/**
 * Format cost in USD
 */
export function formatCost(cost) {
  if (cost == null || isNaN(cost)) return '-';
  if (cost === 0) return '$0.00';
  if (cost < 0.01) return '<$0.01';
  return '$' + cost.toFixed(2);
}

/**
 * Format percentage
 */
export function formatPercent(value, decimals = 0) {
  if (value == null || isNaN(value)) return '-';
  return value.toFixed(decimals) + '%';
}

/**
 * Format seconds into human-readable duration (中文)
 */
export function formatDuration(seconds) {
  if (seconds == null || seconds <= 0) return '-';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}时 ${m}分`;
  if (m > 0) return `${m}分 ${s}秒`;
  return `${s}秒`;
}

/**
 * Format cooldown remaining from a timestamp
 * @param {number|null} cooldownUntil - Unix timestamp
 * @returns {{ text: string, seconds: number, isActive: boolean }}
 */
export function formatCooldown(cooldownUntil) {
  if (!cooldownUntil) return { text: '-', seconds: 0, isActive: false };
  const remaining = cooldownUntil - (Date.now() / 1000);
  if (remaining <= 0) return { text: '-', seconds: 0, isActive: false };
  return {
    text: formatDuration(remaining),
    seconds: remaining,
    isActive: true,
  };
}

/**
 * Format uptime from a start timestamp
 */
export function formatUptime(startTime) {
  if (!startTime) return '-';
  const seconds = (Date.now() / 1000) - startTime;
  return formatDuration(seconds);
}

/**
 * Mask an API key for display
 * @param {string} key
 * @returns {string}
 */
export function maskKey(key) {
  if (!key) return '-';
  if (key.length <= 8) return key.slice(0, 2) + '...' + key.slice(-2);
  // For credential names like "antigravity_oauth_1.json"
  if (key.includes('.json') || key.includes('oauth')) return key;
  // For API keys like "sk-xxxxx..."
  return key.slice(0, 6) + '...' + key.slice(-4);
}

/**
 * Get status info (color, label, icon) for a credential status
 */
export function getStatusInfo(status) {
  const statusMap = {
    active: { label: '活跃', color: 'var(--status-active)', dot: '🟢' },
    cooldown: { label: '冷却中', color: 'var(--status-cooldown)', dot: '🟡' },
    exhausted: { label: '已耗尽', color: 'var(--status-exhausted)', dot: '🔴' },
    error: { label: '错误', color: 'var(--error)', dot: '🔴' },
    disabled: { label: '已禁用', color: 'var(--status-disabled)', dot: '⚫' },
  };
  return statusMap[status] || statusMap.active;
}

/**
 * Get strategy label in Chinese
 */
export function getStrategyLabel(strategy) {
  const map = {
    sequential: '顺序路由',
    primary_backup: '主备模式',
    weighted_random: '加权随机',
  };
  return map[strategy] || strategy;
}

/**
 * Calculate cache hit percentage
 */
export function calcCachePercent(cached, total) {
  if (!total || total === 0) return 0;
  return Math.round((cached / total) * 100);
}

/**
 * Format timestamp to locale string
 */
export function formatTime(ts) {
  if (!ts) return '-';
  return new Date(ts * 1000).toLocaleString('zh-CN');
}
