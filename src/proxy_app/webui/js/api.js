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
   * @returns {Promise<boolean>}
   */
  async testConnection() {
    try {
      await this.getStatus();
      return true;
    } catch (e) {
      if (e instanceof APIError && e.status === 401) return false;
      // Connection error or other non-auth error — might still be valid
      return true;
    }
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
