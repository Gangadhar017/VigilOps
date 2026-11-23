import { api } from './client';

/**
 * Is the VigilOps API answering?
 *
 * Resolves to true as soon as the API itself replies - with "healthy", or with
 * its own "unhealthy" answer (HTTP 503 with a status field), because in both
 * cases the server is up and sign-in can report what is wrong.  Anything else
 * (a timeout, a network error, a hosting platform's placeholder page while the
 * server is waking up) resolves to false.
 */
export const healthApi = {
  ping: () =>
    api
      .get('/api/health', { timeout: 20000 })
      .then((response) => typeof response.data?.status === 'string')
      .catch((error) => typeof error.response?.data?.status === 'string'),
};
