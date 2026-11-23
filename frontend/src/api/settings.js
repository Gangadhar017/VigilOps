import { get, patch, post, put } from './client';

export const settingsApi = {
  get: () => get('/api/settings'),
  update: (key, value) => put(`/api/settings/${key}`, { value }),
};

export const usersApi = {
  list: (params) => get('/api/users', params),
  create: (payload) => post('/api/users', payload),
  update: (id, payload) => patch(`/api/users/${id}`, payload),
  resetPassword: (id, new_password) => post(`/api/users/${id}/reset-password`, { new_password }),
};

export const demoApi = {
  status: () => get('/api/demo/status'),
  injectFault: (mode) => post('/api/demo/faults', { mode }),
  resetConfig: () => post('/api/demo/reset-config'),
};
