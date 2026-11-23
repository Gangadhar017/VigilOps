import axios from 'axios';

// The access token lives in sessionStorage: it disappears when the tab closes,
// and it is never written to a cookie (so there is no CSRF surface).
const TOKEN_KEY = 'vigilops.token';

export const tokenStore = {
  get: () => {
    try {
      return window.sessionStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (token) => {
    try {
      window.sessionStorage.setItem(TOKEN_KEY, token);
    } catch {
      /* storage unavailable: the session then lasts until reload */
    }
  },
  clear: () => {
    try {
      window.sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

export const UNAUTHORIZED_EVENT = 'vigilops:unauthorized';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 25000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = tokenStore.get();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const isLogin = error.config?.url?.includes('/api/auth/login');
    if (status === 401 && !isLogin && tokenStore.get()) {
      // The session expired or was revoked: let the app return to the login page.
      tokenStore.clear();
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
    }
    return Promise.reject(error);
  },
);

/** Human-readable message for any failed request. */
export function errorMessage(error, fallback = 'Something went wrong. Please try again.') {
  if (!error) return fallback;
  if (error.code === 'ECONNABORTED') return 'The request timed out. Check that the VigilOps backend is running.';
  if (!error.response) return 'Cannot reach the VigilOps API. Check that the backend is running.';
  const detail = error.response.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (error.response.status === 403) return 'Your role is not permitted to perform this action.';
  if (error.response.status === 404) return 'The requested item was not found.';
  if (error.response.status >= 500) return 'The server reported an error. Please try again.';
  return fallback;
}

/** Drop empty values so they are not sent as query parameters. */
export function cleanParams(params = {}) {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '' && value !== false),
  );
}

export const get = (url, params) => api.get(url, { params: cleanParams(params) }).then((r) => r.data);
export const post = (url, body) => api.post(url, body ?? {}).then((r) => r.data);
export const put = (url, body) => api.put(url, body ?? {}).then((r) => r.data);
export const patch = (url, body) => api.patch(url, body ?? {}).then((r) => r.data);
