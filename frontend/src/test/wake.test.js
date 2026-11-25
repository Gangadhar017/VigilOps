import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import { WAKE_EVERY_MS, WAKE_URL, apiIsNotUp, resetWake, wakeServer } from '../api/wake';

// What the request to the API ended with, in the form the HTTP client reports it.
const failed = (response) => Object.assign(new Error('request failed'), { response });
const answerWith = (status, data) => ({ adapter: (config) => Promise.reject(failed({ status, data, headers: {}, config })) });
const noAnswer = { adapter: () => Promise.reject(Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK' })) };
const PLATFORM_PAGE = '<!DOCTYPE html><html><head><title>502</title></head><body><h1>Bad Gateway</h1></body></html>';

describe('starting a sleeping API server', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-11-25T12:00:00Z'));
    resetWake();
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ type: 'opaque' })));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('tells an answer of the API from the answer of something in front of it', () => {
    expect(apiIsNotUp(failed(undefined))).toBe(true); // no answer, or a timeout
    expect(apiIsNotUp(failed({ status: 502, data: PLATFORM_PAGE }))).toBe(true);
    expect(apiIsNotUp(failed({ status: 503, data: PLATFORM_PAGE }))).toBe(true);
    expect(apiIsNotUp(failed({ status: 502, data: '' }))).toBe(true);
    expect(apiIsNotUp(failed({ status: 504, data: null }))).toBe(true);

    // The API itself answered: there is nothing to start.
    expect(apiIsNotUp(failed({ status: 503, data: { status: 'unhealthy' } }))).toBe(false);
    expect(apiIsNotUp(failed({ status: 502, data: { detail: 'The demonstration application is not reachable.' } }))).toBe(false);
    expect(apiIsNotUp(failed({ status: 500, data: 'Internal Server Error' }))).toBe(false);
    expect(apiIsNotUp(failed({ status: 401, data: { detail: 'Not authenticated' } }))).toBe(false);
    expect(apiIsNotUp(Object.assign(new Error('canceled'), { code: 'ERR_CANCELED' }))).toBe(false);
  });

  it('asks the server on its own address, at most once in twenty seconds', () => {
    expect(WAKE_URL).toBe('/wake');
    expect(wakeServer()).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith('/wake', { mode: 'no-cors', cache: 'no-store' });

    vi.advanceTimersByTime(WAKE_EVERY_MS - 1000);
    expect(wakeServer()).toBe(false);
    expect(fetch).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(1000);
    expect(wakeServer()).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('is not disturbed when that request fails', async () => {
    fetch.mockImplementation(() => Promise.reject(new TypeError('Failed to fetch')));
    expect(wakeServer()).toBe(true);
    await vi.advanceTimersByTimeAsync(0);

    resetWake();
    fetch.mockImplementation(() => { throw new TypeError('blocked'); });
    expect(() => wakeServer()).not.toThrow();
  });

  it('is sent when a request of the console gets the hosting platform instead of the API', async () => {
    await expect(api.get('/api/health', answerWith(502, PLATFORM_PAGE))).rejects.toThrow();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith('/wake', { mode: 'no-cors', cache: 'no-store' });
  });

  it('is sent when a request of the console gets no answer', async () => {
    await expect(api.get('/api/incidents', noAnswer)).rejects.toThrow();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('is not sent when the API itself reports an error', async () => {
    await expect(api.get('/api/health', answerWith(503, { status: 'unhealthy' }))).rejects.toThrow();
    await expect(api.get('/api/incidents/999', answerWith(404, { detail: 'Not found' }))).rejects.toThrow();
    await expect(api.post('/api/auth/login', {}, answerWith(401, { detail: 'Incorrect e-mail or password.' }))).rejects.toThrow();
    expect(fetch).not.toHaveBeenCalled();
  });
});
