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

    const ct = resp.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
      return resp.json();
    }
    return resp.text();
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

  // ---------------------
  // Admin APIs
  // ---------------------
  async getAdminConfig() {
    return this.request('/admin/config');
  }

  async validateAdminConfig() {
    return this.request('/admin/config/validate', { method: 'POST' });
  }

  async applyAdminConfig() {
    return this.request('/admin/config/apply', { method: 'POST' });
  }

  async getChannels() {
    return this.request('/admin/channels');
  }

  async createChannel(payload) {
    return this.request('/admin/channels', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async updateChannel(channelId, payload) {
    return this.request(`/admin/channels/${encodeURIComponent(channelId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  async deleteChannel(channelId) {
    return this.request(`/admin/channels/${encodeURIComponent(channelId)}`, {
      method: 'DELETE',
    });
  }

  async addChannelKey(channelId, payload) {
    return this.request(`/admin/channels/${encodeURIComponent(channelId)}/keys`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async updateChannelKey(channelId, keyId, payload) {
    return this.request(`/admin/channels/${encodeURIComponent(channelId)}/keys/${encodeURIComponent(keyId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  async deleteChannelKey(channelId, keyId) {
    return this.request(`/admin/channels/${encodeURIComponent(channelId)}/keys/${encodeURIComponent(keyId)}`, {
      method: 'DELETE',
    });
  }

  async testChannel(channelId) {
    return this.request(`/admin/channels/${encodeURIComponent(channelId)}/test`, {
      method: 'POST',
    });
  }

  async getVirtualModels() {
    return this.request('/admin/virtual-models');
  }

  async createVirtualModel(payload) {
    return this.request('/admin/virtual-models', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async updateVirtualModel(name, payload) {
    return this.request(`/admin/virtual-models/${encodeURIComponent(name)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  async deleteVirtualModel(name) {
    return this.request(`/admin/virtual-models/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    });
  }

  async reloadRuntime() {
    return this.request('/admin/runtime/reload', { method: 'POST' });
  }

  async getRuntimeStatus() {
    return this.request('/admin/runtime/status');
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
