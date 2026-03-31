// ============================================================
// API Client — Wraps proxy API with auth
// ============================================================

class ProxyAPI {
  constructor() {
    this.apiKey = localStorage.getItem('proxy_api_key') || '';
    this.baseUrl = window.location.origin;
  }

  setApiKey(key) {
    this.apiKey = key;
    localStorage.setItem('proxy_api_key', key);
  }

  getApiKey() {
    return this.apiKey;
  }

  hasApiKey() {
    return !!this.apiKey;
  }

  async request(path, options = {}) {
    const url = `${this.baseUrl}${path}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };
    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`;
    }

    const resp = await fetch(url, { ...options, headers });
    if (!resp.ok) {
      const text = await resp.text().catch(() => resp.statusText);
      throw new APIError(resp.status, text);
    }
    return resp.json();
  }

  // --- Endpoints ---

  async getStatus() {
    return this.request('/');
  }

  async getQuotaStats(provider = null) {
    const qs = provider ? `?provider=${encodeURIComponent(provider)}` : '';
    return this.request(`/v1/quota-stats${qs}`);
  }

  async refreshQuota(action = 'reload', scope = 'all', provider = null, credential = null) {
    const body = { action, scope };
    if (provider) body.provider = provider;
    if (credential) body.credential = credential;
    return this.request('/v1/quota-stats', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  async getModels(enriched = true) {
    return this.request(`/v1/models?enriched=${enriched}`);
  }

  async getProviders() {
    return this.request('/v1/providers');
  }

  async getModelInfo(modelId) {
    return this.request(`/v1/models/${encodeURIComponent(modelId)}`);
  }

  async getModelInfoStats() {
    return this.request('/v1/model-info/stats');
  }

  /**
   * Test connectivity with current API key
   * Uses an authenticated endpoint to verify the key is valid
   * @returns {Promise<{ok: boolean, status?: number, detail?: string}>}
   */
  async testConnection() {
    try {
      await this.getModels(false);
      return { ok: true };
    } catch (e) {
      if (e instanceof APIError && e.status === 401) {
        // Call debug endpoint to get key comparison info
        try {
          const debugResp = await fetch(`${this.baseUrl}/webui/auth-test`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(this.apiKey ? { 'Authorization': `Bearer ${this.apiKey}` } : {}),
            },
            body: JSON.stringify({ key: this.apiKey }),
          });
          if (debugResp.ok) {
            const info = await debugResp.json();
            const detail = `服务端密钥: ${info.server_key_hint} (长度${info.server_key_len})\n` +
              `你输入的: ${info.client_key_hint} (长度${info.client_key_len})\n` +
              `匹配: ${info.match ? '✓' : '✗'}`;
            return { ok: false, status: 401, detail };
          }
        } catch (_) { /* debug endpoint not available, fall through */ }
        return { ok: false, status: 401, detail: '密钥无效或不匹配' };
      }
      if (e instanceof APIError) {
        return { ok: false, status: e.status, detail: e.message };
      }
      // Network error
      return { ok: false, status: 0, detail: `连接失败: ${e.message}` };
    }
  }

  /**
   * Clear stored API key and reload page to show auth modal
   */
  logout() {
    this.apiKey = '';
    localStorage.removeItem('proxy_api_key');
    window.location.reload();
  }
}

class APIError extends Error {
  constructor(status, message) {
    super(`API Error ${status}: ${message}`);
    this.status = status;
  }
}

// Singleton
export const api = new ProxyAPI();
export { APIError };

