import { get, post } from './client';

export const securityApi = {
  rules: () => get('/api/security/rules'),
  targets: () => get('/api/security/targets'),
  target: (name) => get(`/api/security/targets/${encodeURIComponent(name)}`),
  runScan: (target) => post('/api/security/scans', target ? { target } : {}),
  scans: (params) => get('/api/security/scans', params),
  findings: (params) => get('/api/security/findings', params),
  finding: (id) => get(`/api/security/findings/${id}`),
  acceptRisk: (id, reason) => post(`/api/security/findings/${id}/accept-risk`, { reason }),
  revokeRiskAcceptance: (id) => post(`/api/security/findings/${id}/revoke-risk-acceptance`),
};
