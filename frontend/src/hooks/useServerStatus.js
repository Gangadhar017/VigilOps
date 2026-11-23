import { useCallback, useEffect, useState } from 'react';
import { healthApi } from '../api/health';

// Timing of the availability probe.  An object so that tests can shorten it.
export const SERVER_PROBE = {
  slowAfterMs: 2500, // say "starting" only if the first answer takes longer than this
  retryEveryMs: 4000,
  giveUpAfterMs: 180000,
};

/**
 * Follows whether the API is answering, for pages that are useless without it
 * (the sign-in page).  A server on a hosting plan that sleeps when idle needs
 * about a minute to wake up; instead of a failed request the page can say so
 * and continue by itself.
 *
 * status: 'checking' (first probe in flight) | 'ready' | 'starting' | 'unreachable'
 */
export function useServerStatus() {
  const [status, setStatus] = useState('checking');
  const [round, setRound] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const startedAt = Date.now();
    setStatus('checking');
    const slowTimer = setTimeout(() => {
      if (!cancelled) setStatus((current) => (current === 'checking' ? 'starting' : current));
    }, SERVER_PROBE.slowAfterMs);

    (async () => {
      while (!cancelled) {
        let answering = false;
        try {
          answering = await healthApi.ping();
        } catch {
          answering = false;
        }
        if (cancelled) return;
        if (answering) {
          setStatus('ready');
          return;
        }
        if (Date.now() - startedAt > SERVER_PROBE.giveUpAfterMs) {
          setStatus('unreachable');
          return;
        }
        setStatus('starting');
        await new Promise((resolve) => setTimeout(resolve, SERVER_PROBE.retryEveryMs));
      }
    })();

    return () => {
      cancelled = true;
      clearTimeout(slowTimer);
    };
  }, [round]);

  const retry = useCallback(() => setRound((value) => value + 1), []);
  return { status, retry };
}
