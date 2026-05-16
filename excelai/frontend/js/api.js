(function () {
  const STORAGE_KEY = 'excelai_token';

  function getToken() {
    return localStorage.getItem(STORAGE_KEY);
  }

  function setToken(token) {
    localStorage.setItem(STORAGE_KEY, token);
  }

  function clearToken() {
    localStorage.removeItem(STORAGE_KEY);
  }

  function decodeBase64Url(segment) {
    const normalized = segment.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized + '='.repeat((4 - normalized.length % 4) % 4);
    return JSON.parse(atob(padded));
  }

  function decodeJwt(token) {
    try {
      const parts = token.split('.');
      if (parts.length !== 3) return null;
      const header = decodeBase64Url(parts[0]);
      const payload = decodeBase64Url(parts[1]);
      return { header, payload };
    } catch (error) {
      return null;
    }
  }

  function isTokenValid(token) {
    const decoded = decodeJwt(token);
    if (!decoded || !decoded.payload || !decoded.payload.exp) return false;
    return decoded.payload.exp * 1000 > Date.now();
  }

  function getApiBase() {
    return '';
  }

  async function request(path, options = {}) {
    const token = getToken();
    const headers = new Headers(options.headers || {});
    if (!(options.body instanceof FormData) && !headers.has('Content-Type') && options.body) {
      headers.set('Content-Type', 'application/json');
    }
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const response = await fetch(`${getApiBase()}${path}`, {
      ...options,
      headers,
    });
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok) {
      const message = typeof payload === 'string' ? payload : payload.detail || payload.error || 'Request failed';
      throw new Error(message);
    }
    return payload;
  }

  async function download(path, body, filename) {
    const token = getToken();
    const response = await fetch(`${getApiBase()}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      throw new Error(errorPayload.detail || errorPayload.error || 'Download failed');
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  function showToast(message, type = 'info') {
    const host = document.getElementById('toastHost');
    if (!host) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    host.appendChild(toast);
    window.setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(12px)';
      window.setTimeout(() => toast.remove(), 220);
    }, 3600);
  }

  async function safeRequest(path, options) {
    try {
      return await request(path, options);
    } catch (error) {
      throw error;
    }
  }

  window.ExcelAI = {
    STORAGE_KEY,
    getToken,
    setToken,
    clearToken,
    decodeJwt,
    isTokenValid,
    request: safeRequest,
    download,
    showToast,
  };
})();
