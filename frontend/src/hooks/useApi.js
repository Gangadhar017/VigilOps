import { useCallback, useEffect, useRef, useState } from 'react';
import { errorMessage } from '../api/client';

/**
 * Load data from the backend with loading / error / retry state.
 *
 * @param {() => Promise<any>} fetcher  function returning a promise
 * @param {any[]} deps                  re-fetch when these change
 * @param {{interval?: number, enabled?: boolean}} options
 *        interval: poll every N ms (paused while the tab is hidden, so an
 *        unattended tab does not generate requests)
 */
export function useApi(fetcher, deps = [], { interval = 0, enabled = true } = {}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(enabled);
  const [refreshing, setRefreshing] = useState(false);
  const fetcherRef = useRef(fetcher);
  const requestId = useRef(0);
  fetcherRef.current = fetcher;

  const load = useCallback(async (background = false) => {
    const id = ++requestId.current;
    if (background) setRefreshing(true);
    else setLoading(true);
    try {
      const result = await fetcherRef.current();
      if (id === requestId.current) {
        setData(result);
        setError(null);
      }
    } catch (err) {
      // Keep showing the last good data; surface the problem next to it.
      if (id === requestId.current) setError(errorMessage(err));
    } finally {
      if (id === requestId.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return undefined;
    }
    load(false);
    return () => {
      requestId.current += 1; // ignore responses that arrive after unmount / dependency change
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, load, ...deps]);

  useEffect(() => {
    if (!enabled || !interval) return undefined;
    const timer = window.setInterval(() => {
      if (!document.hidden) load(true);
    }, interval);
    return () => window.clearInterval(timer);
  }, [enabled, interval, load]);

  return { data, error, loading, refreshing, reload: () => load(Boolean(data)), setData };
}

/** Debounce a fast-changing value (search boxes). */
export function useDebounced(value, delay = 350) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
