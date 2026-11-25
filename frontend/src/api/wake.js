/**
 * Starting a sleeping API server.
 *
 * On a hosting plan that switches an idle server off, the server is started by
 * a request to its own address.  The console's requests reach it through the
 * static host, and those did not start it when this was measured: the hosting
 * platform answered each of them with its error page for as long as nobody
 * asked the server directly (docs/verification-report.md, section 11).
 *
 * So when a request shows that the API is not up, the browser also sends one
 * request straight to the server.  On the static host the address /wake is
 * redirected there (frontend/vercel.json); with a separate API address
 * (VITE_API_URL) that address is asked directly.  The answer cannot be read
 * across origins and is not needed.  On a deployment without a sleeping server
 * the request is answered by the reverse proxy and changes nothing.
 */
const API_ADDRESS = import.meta.env.VITE_API_URL || '';
export const WAKE_URL = API_ADDRESS ? `${API_ADDRESS.replace(/\/+$/, '')}/health/live` : '/wake';
export const WAKE_EVERY_MS = 20000;

let lastWakeAt = 0;

/** Did this failed request get no answer from the API itself? */
export function apiIsNotUp(error) {
  if (!error || error.code === 'ERR_CANCELED') return false;
  if (!error.response) return true; // no answer at all, or a timeout
  const { status, data } = error.response;
  // The API's own errors are JSON objects; a hosting platform or a proxy answers with a page or nothing.
  return [502, 503, 504].includes(status) && !(data && typeof data === 'object');
}

/** Asks the server's own address, at most once in WAKE_EVERY_MS. */
export function wakeServer() {
  const now = Date.now();
  if (now - lastWakeAt < WAKE_EVERY_MS) return false;
  if (typeof fetch !== 'function') return false;
  lastWakeAt = now;
  try {
    Promise.resolve(fetch(WAKE_URL, { mode: 'no-cors', cache: 'no-store' })).catch(() => {});
  } catch {
    /* the pages keep asking without it */
  }
  return true;
}

/** For tests: forget when the last request was sent. */
export function resetWake() {
  lastWakeAt = 0;
}
