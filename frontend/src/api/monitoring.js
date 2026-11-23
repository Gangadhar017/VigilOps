import { get } from './client';

export const monitoringApi = {
  dashboard: () => get('/api/dashboard/summary'),
  overview: () => get('/api/monitoring/overview'),
  catalog: () => get('/api/monitoring/metrics'),
  timeseries: (job, metric, range = '15m') => get('/api/monitoring/timeseries', { job, metric, range }),
};
