import { get, post } from './client';

export const remediationApi = {
  actions: () => get('/api/remediation/actions'),
  list: (params) => get('/api/remediation/requests', params),
  get: (id) => get(`/api/remediation/requests/${id}`),
  create: (source_type, source_id, action_code, justification) =>
    post('/api/remediation/requests', { source_type, source_id, action_code, justification }),
  approve: (id, comment) => post(`/api/remediation/requests/${id}/approve`, { comment: comment || null }),
  reject: (id, comment) => post(`/api/remediation/requests/${id}/reject`, { comment }),
  execute: (id) => post(`/api/remediation/requests/${id}/execute`),
  retry: (id) => post(`/api/remediation/requests/${id}/retry`),
  cancel: (id, comment) => post(`/api/remediation/requests/${id}/cancel`, { comment: comment || null }),
};
