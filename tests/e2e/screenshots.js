// Capture the pages of a running VigilOps instance as PNG files.
//
//   cd tests/e2e
//   node screenshots.js                         every page, dark and light, into ../../.runtime/shots
//   node screenshots.js --out=../../docs/screenshots --theme=dark
//   node screenshots.js --only=login,overview --mobile
//
// Used to review the interface after a visual change and to produce the
// screenshots in the documentation.  It signs in with the bootstrap
// Administrator from the repository's .env file and only reads data; the one
// thing it changes is the browser's own theme preference.
const fs = require('fs');
const path = require('path');
const { chromium } = require('@playwright/test');
const { env, accounts } = require('./support/env');

const args = Object.fromEntries(
  process.argv.slice(2).map((arg) => {
    const [key, value] = arg.replace(/^--/, '').split('=');
    return [key, value === undefined ? true : value];
  }),
);
const BASE = process.env.BASE_URL || `http://localhost:${env.VIGILOPS_HTTP_PORT || '8080'}`;
const OUT = path.resolve(__dirname, args.out || '../../.runtime/shots');
const THEMES = args.theme && args.theme !== 'both' ? [args.theme] : ['dark', 'light'];
const ONLY = typeof args.only === 'string' ? new Set(args.only.split(',')) : null;
const MOBILE = Boolean(args.mobile);
const VIEWPORT = MOBILE ? { width: 390, height: 844 } : { width: 1360, height: 850 };

const wanted = (name) => !ONLY || ONLY.has(name);

async function settle(page, ms = 900) {
  // Pages poll the API, so "network idle" never comes; wait for the first data instead.
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(ms);
}

async function shot(page, theme, name, options = {}) {
  if (!wanted(name)) return;
  const file = path.join(OUT, `${theme}${MOBILE ? '-mobile' : ''}-${name}.png`);
  await page.screenshot({ path: file, fullPage: Boolean(options.fullPage), animations: 'disabled' });
  console.log('  wrote', path.relative(process.cwd(), file));
}

async function firstId(page, apiPath) {
  return page.evaluate(async (url) => {
    const token = window.sessionStorage.getItem('vigilops.token');
    const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) return null;
    const body = await response.json();
    return body.items && body.items.length ? body.items[0].id : null;
  }, apiPath);
}

async function run(browser, theme) {
  console.log(`${theme}${MOBILE ? ' (phone size)' : ''}`);
  const context = await browser.newContext({ viewport: VIEWPORT, colorScheme: theme, baseURL: BASE });
  await context.addInitScript((value) => window.localStorage.setItem('vigilops.theme', value), theme);
  const page = await context.newPage();

  await page.goto('/login');
  await settle(page);
  await shot(page, theme, 'login');

  await page.getByLabel('E-mail').fill(accounts.admin.email);
  await page.getByLabel('Password', { exact: true }).fill(accounts.admin.password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('heading', { name: 'Overview', level: 1 }).waitFor();
  await settle(page, 2500);
  await shot(page, theme, 'overview', { fullPage: true });

  const pages = [
    ['monitoring', '/monitoring', true],
    ['incidents', '/incidents', false],
    ['findings', '/findings', false],
    ['remediation', '/remediation', false],
    ['audit', '/audit', false],
    ['help', '/help', true],
    ['settings', '/settings', false],
  ];
  for (const [name, url, fullPage] of pages) {
    if (!wanted(name)) continue;
    await page.goto(url);
    await settle(page, 1800);
    await shot(page, theme, name, { fullPage });
  }

  const details = [
    ['incident-detail', '/api/incidents?page_size=1', '/incidents/'],
    ['finding-detail', '/api/security/findings?page_size=1', '/findings/'],
    ['remediation-detail', '/api/remediation/requests?page_size=1', '/remediation/'],
  ];
  for (const [name, api, prefix] of details) {
    if (!wanted(name)) continue;
    const id = await firstId(page, api);
    if (id === null) {
      console.log(`  skipped ${name}: no record yet`);
      continue;
    }
    await page.goto(prefix + id);
    await settle(page, 1800);
    await shot(page, theme, name, { fullPage: true });
  }

  for (const tab of ['Users', 'Platform', 'Permissions', 'Demo controls']) {
    const name = `settings-${tab.toLowerCase().replace(/\s+/g, '-')}`;
    if (!wanted(name)) continue;
    await page.goto('/settings');
    await settle(page, 800);
    await page.getByRole('tab', { name: tab }).or(page.getByRole('button', { name: tab, exact: true })).first().click();
    await settle(page, 1200);
    await shot(page, theme, name, { fullPage: true });
  }

  if (wanted('assistant')) {
    await page.goto('/');
    await settle(page, 1500);
    await page.getByRole('button', { name: 'Open VigilAI assistant' }).click();
    await settle(page, 800);
    await shot(page, theme, 'assistant');
  }

  if (MOBILE && wanted('menu')) {
    await page.goto('/');
    await settle(page, 1200);
    await page.getByRole('button', { name: 'Open navigation' }).click();
    await settle(page, 500);
    await shot(page, theme, 'menu');
  }
  await context.close();
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  try {
    for (const theme of THEMES) await run(browser, theme);
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
