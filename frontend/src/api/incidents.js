import { get, post } from './client';

export const incidentsApi = {
  list: (params) => get('/api/incidents', params),
  get: (id) => get(`/api/incidents/${id}`),
  transition: (id, status, note, overrideMonitoring = false) =>
    post(`/api/incidents/${id}/transition`, { status, note: note || null, override_monitoring: overrideMonitoring }),
  comment: (id, note) => post(`/api/incidents/${id}/comments`, { note }),
};
