import { get } from './client';

export const auditApi = {
  list: (params) => get('/api/audit/events', params),
  meta: () => get('/api/audit/meta'),
};
