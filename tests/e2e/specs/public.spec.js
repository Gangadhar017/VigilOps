// Browser end-to-end tests of what a visitor can reach without an account:
// the product page at the site root and OrbitCrate, the monitored
// demonstration application, at /orbitcrate/.
const { test, expect } = require('@playwright/test');
const { accounts, signIn } = require('../support/env');

test.describe('Product page', () => {
  test('a visitor who is not signed in sees the product page and can go to sign-in', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Monitoring, incidents and controlled remediation in one console.');
    await expect(page.getByText('Demonstration environment is ready')).toBeVisible();
    for (const name of ['Six parts, one closed loop', 'From a signal to a verified fix', 'Small services with narrow jobs']) {
      await expect(page.getByRole('heading', { name })).toBeVisible();
    }
    // The captures of the console are real files of this build.
    for (const image of await page.getByRole('img', { name: /VigilOps overview page|remediation request in the console|OrbitCrate storefront/ }).all()) {
      await image.scrollIntoViewIfNeeded();
      await expect.poll(() => image.evaluate((node) => node.complete && node.naturalWidth)).toBeGreaterThan(1000);
    }

    await page.getByRole('link', { name: 'Sign in' }).first().click();
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
    // ... and back to the product page from there.
    await page.getByRole('link', { name: 'What is VigilOps?' }).click();
    await expect(page).toHaveURL(/\/welcome$/);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Monitoring, incidents');
  });

  test('the section tabs follow the reader', async ({ page }) => {
    await page.goto('/');
    const tabs = page.getByRole('navigation', { name: 'On this page' });
    await expect(tabs.locator('[aria-current="true"]')).toHaveCount(0);
    await tabs.getByRole('link', { name: 'Architecture' }).click();
    await expect(page).toHaveURL(/#architecture$/);
    await expect(tabs.locator('[aria-current="true"]')).toHaveText('Architecture');
  });

  test('a signed-in user still gets the console at the site root', async ({ page }) => {
    await signIn(page, accounts.operator);
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Overview', level: 1 })).toBeVisible();
    // The product page stays available to them under its own address.
    await page.goto('/welcome');
    await expect(page.getByRole('link', { name: 'Open the console' }).first()).toBeVisible();
  });
});

test.describe('OrbitCrate, the monitored demonstration application', () => {
  test('a visitor configures a server, sees the price and follows the order to active', async ({ page }) => {
    await page.goto('/orbitcrate/');
    await expect(page.getByText('Demonstration store.')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Crate XL' })).toBeVisible();
    await expect(page.locator('#status-text')).toHaveText('Store operational');

    await page.getByRole('button', { name: 'Choose Crate L' }).click();
    await page.getByRole('radio', { name: /Singapore/ }).check({ force: true });
    await page.getByRole('checkbox', { name: /Daily backups/ }).check();
    await page.getByRole('button', { name: 'One server more' }).click();
    const summary = page.locator('.summary');
    await expect(summary.getByText('2 x Crate L in Singapore')).toBeVisible();
    // 2 x 2399 x 1.08 = 5181.84; backups 20% = 1036.37; net 6218.21; GST 18% = 1119.28
    await expect(summary.locator('.total strong')).toHaveText('₹7,337.49');

    // The project name is validated before anything is sent.
    await page.getByRole('button', { name: 'Place order' }).click();
    await expect(page.locator('#project-error')).toBeVisible();
    await page.getByLabel('Project name').fill('e2e-campus-portal');
    await page.getByRole('button', { name: 'Place order' }).click();

    const order = page.locator('.order').first();
    await expect(order.locator('.order__project')).toHaveText('e2e-campus-portal');
    await expect(order.locator('.order__id')).toHaveText(/^OC-[A-Z2-9]{6}$/);
    await expect(order.locator('.chip')).toHaveText(/Received|Provisioning/);
    // The page follows the order by itself until it is active.
    await expect(order.locator('.chip')).toHaveText('Active', { timeout: 40_000 });
    await expect(order.getByText('Set up and running.')).toBeVisible();

    // The order belongs to this browser and survives a reload.
    await page.reload();
    await expect(page.locator('.order').first().locator('.order__project')).toHaveText('e2e-campus-portal');

    await page.locator('.order').first().getByRole('button', { name: 'Cancel order' }).click();
    await expect(page.locator('.order').first().locator('.chip')).toHaveText('Cancelled');
  });

  test('only the storefront is public: control, metrics and health paths are not routed', async ({ page, request }) => {
    const redirect = await request.get('/orbitcrate', { maxRedirects: 0 });
    expect(redirect.status()).toBe(308);
    expect(redirect.headers().location).toMatch(/\/orbitcrate\/$/);

    for (const path of ['internal/state', 'internal/fault', 'internal/recover', 'metrics', 'health', 'health/live', 'health/ready', 'docs']) {
      expect((await request.get(`/orbitcrate/${path}`)).status(), path).toBe(404);
      expect((await request.post(`/orbitcrate/${path}`, { data: { mode: 'outage' } })).status(), path).toBe(404);
    }
    const tooLarge = await request.post('/orbitcrate/api/estimate', { data: 'x'.repeat(6000), headers: { 'Content-Type': 'application/json' } });
    expect(tooLarge.status()).toBe(413);

    // A visitor without the store's session header cannot list anybody's orders.
    expect((await request.get('/orbitcrate/api/orders')).status()).toBe(400);
    await page.goto('/orbitcrate/');
    await expect(page.getByRole('link', { name: 'Open VigilOps' })).toHaveAttribute('href', '/');
  });

  test('the console links to the application whose traffic it measures', async ({ page, context }) => {
    await signIn(page, accounts.operator);
    const link = page.getByRole('link', { name: 'Open application' });
    await expect(link).toHaveAttribute('href', '/orbitcrate/');
    const [store] = await Promise.all([context.waitForEvent('page'), link.click()]);
    await expect(store.getByRole('heading', { name: 'Crate S', exact: true })).toBeVisible();
    await expect(store.locator('#pulse-state')).toHaveText('Operational');
    // The console is still open behind it.
    await expect(page.getByRole('heading', { name: 'Overview', level: 1 })).toBeVisible();
    await page.goto('/monitoring');
    await expect(page.getByRole('link', { name: 'Open the monitored application' })).toHaveAttribute('href', '/orbitcrate/');
  });
});

test.describe('Public pages on a phone-sized screen', () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test('no horizontal overflow on the product page or in the store', async ({ page }) => {
    for (const path of ['/', '/orbitcrate/']) {
      await page.goto(path);
      await page.getByRole('heading', { level: 1 }).waitFor();
      await page.waitForTimeout(800);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, `horizontal overflow on ${path}`).toBeLessThanOrEqual(1);
    }
  });
});
