import fs from 'node:fs';
import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// The store's start page is plain HTML and one script in public/, served by the
// static host at the store's address (vercel.json).  It is not part of the React
// application, so the test loads the two files as a browser would.
const ROOT = process.cwd();
const PAGE = fs.readFileSync(path.join(ROOT, 'public', 'orbitcrate-start.html'), 'utf8');
const SCRIPT = fs.readFileSync(path.join(ROOT, 'public', 'orbitcrate-start.js'), 'utf8');
const HOSTING = JSON.parse(fs.readFileSync(path.join(ROOT, 'vercel.json'), 'utf8'));

const answer = (body) => ({ json: async () => body });
const errorPage = () => ({ json: async () => { throw new SyntaxError('Unexpected token <'); } });

function openPage() {
  const body = PAGE.slice(PAGE.indexOf('<body>') + '<body>'.length, PAGE.indexOf('</body>'));
  document.documentElement.setAttribute('data-state', 'opening');
  document.body.innerHTML = body.replace(/<script[^>]*><\/script>/, '');
  new Function(SCRIPT)(); // eslint-disable-line no-new-func
}

const headline = () => document.getElementById('headline').textContent;

describe('start page of the store', () => {
  let location;

  beforeEach(() => {
    vi.useFakeTimers();
    location = { replace: vi.fn(), search: '', hash: '' };
    vi.stubGlobal('location', location);
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    document.body.innerHTML = '';
  });

  it('opens the store at once when it answers, keeping the query and the anchor', async () => {
    location.search = '?ref=console';
    location.hash = '#plans';
    fetch.mockResolvedValue(answer({ status: 'operational', product: 'OrbitCrate' }));
    openPage();
    await vi.advanceTimersByTimeAsync(0);

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toBe('/orbitcrate/api/status');
    expect(location.replace).toHaveBeenCalledWith('/orbitcrate/open?ref=console#plans');
    expect(headline()).toBe('Opening the store');
    expect(document.getElementById('detail').hidden).toBe(true);
  });

  it('says that the server is starting while the platform answers with its error page, then opens', async () => {
    fetch
      .mockResolvedValueOnce(errorPage()) // the hosting platform's "Bad Gateway" page
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValue(answer({ status: 'operational' }));
    openPage();
    await vi.advanceTimersByTimeAsync(1000);

    expect(location.replace).not.toHaveBeenCalled();
    expect(headline()).toBe('Starting the demonstration server');
    expect(document.getElementById('detail').textContent).toMatch(/opens here by itself/);
    expect(document.getElementById('elapsed').hidden).toBe(false);
    expect(document.getElementById('actions').hidden).toBe(true);

    await vi.advanceTimersByTimeAsync(6500);
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(location.replace).toHaveBeenCalledTimes(1);
    expect(location.replace).toHaveBeenCalledWith('/orbitcrate/open');
  });

  it('says so when a single answer takes long, without waiting for it to fail', async () => {
    fetch.mockReturnValue(new Promise(() => {})); // a waking server holds the request
    openPage();
    await vi.advanceTimersByTimeAsync(1000);
    expect(headline()).toBe('Opening the store');
    await vi.advanceTimersByTimeAsync(1000);
    expect(headline()).toBe('Starting the demonstration server');
    expect(document.getElementById('elapsed').textContent).toBe('Waiting for 0:02');
  });

  it('opens the store when the store itself reports an outage: that is the store answering', async () => {
    fetch.mockResolvedValue(answer({ status: 'unavailable', detail: 'Service component is not running.' }));
    openPage();
    await vi.advanceTimersByTimeAsync(0);
    expect(location.replace).toHaveBeenCalledWith('/orbitcrate/open');
  });

  it('keeps waiting while only the API answers that the store is not reachable', async () => {
    fetch.mockResolvedValue(answer({ detail: 'The demonstration application is not reachable.' }));
    openPage();
    await vi.advanceTimersByTimeAsync(20000);
    expect(location.replace).not.toHaveBeenCalled();
    expect(fetch.mock.calls.length).toBeGreaterThan(3);
    expect(headline()).toBe('Starting the demonstration server');
  });

  it('gives up after four minutes and starts again on request', async () => {
    fetch.mockResolvedValue(errorPage());
    openPage();
    await vi.advanceTimersByTimeAsync(239000);
    expect(headline()).toBe('Starting the demonstration server');
    await vi.advanceTimersByTimeAsync(6000);

    expect(headline()).toBe('The store is not answering');
    expect(document.documentElement.getAttribute('data-state')).toBe('unreachable');
    expect(document.getElementById('actions').hidden).toBe(false);
    expect(document.getElementById('elapsed').hidden).toBe(true);
    const asked = fetch.mock.calls.length;
    await vi.advanceTimersByTimeAsync(30000);
    expect(fetch.mock.calls.length).toBe(asked); // it has stopped asking

    fetch.mockResolvedValue(answer({ status: 'operational' }));
    document.getElementById('retry').click();
    await vi.advanceTimersByTimeAsync(0);
    expect(location.replace).toHaveBeenCalledWith('/orbitcrate/open');
  });
});

describe('hosting rules for the store', () => {
  const rules = HOSTING.rewrites;
  const position = (source) => rules.findIndex((rule) => rule.source === source);
  const forwarded = position('/orbitcrate/:path(.*)');

  it('serve the start page at the store address, in both spellings, ahead of the forwarding rule', () => {
    expect(forwarded).toBeGreaterThan(-1);
    for (const address of ['/orbitcrate', '/orbitcrate/']) {
      expect(position(address)).toBeGreaterThan(-1);
      expect(position(address)).toBeLessThan(forwarded);
      expect(rules[position(address)].destination).toBe('/orbitcrate-start.html');
    }
  });

  it('forward the address the start page opens to the store page on the server', () => {
    const open = rules[position('/orbitcrate/open')];
    expect(open.destination).toMatch(/^https:\/\/[^/]+\/orbitcrate\/$/);
    expect(position('/orbitcrate/open')).toBeLessThan(forwarded);
    expect(SCRIPT).toContain("STORE_URL = '/orbitcrate/open'");
  });

  it('are met by a start page without inline script, as the content policy requires', () => {
    const policy = HOSTING.headers[0].headers.find((header) => header.key === 'Content-Security-Policy').value;
    expect(policy).toContain("script-src 'self'");
    expect(PAGE).toContain('<script src="/orbitcrate-start.js"></script>');
    expect(PAGE.match(/<script/g)).toHaveLength(1);
    expect(PAGE).not.toMatch(/\son[a-z]+=/); // no inline event handlers either
    // Nothing is loaded from the server the page is waiting for.
    expect(PAGE).not.toMatch(/(?:href|src)="(?:\/orbitcrate\/(?!open")|static\/)/);
  });
});
