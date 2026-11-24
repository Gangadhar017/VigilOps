// Record the demonstration as a video: the fallback for a live demo.
//
//   docker compose up --build -d          (from the repository root; demo controls on)
//   cd tests/e2e
//   node record-demo.js                    writes ../../recordings/vigilops-demo.webm
//   node record-demo.js --out=D:/somewhere --pace=1.5
//
// One browser tab walks through the whole story against the RUNNING stack and
// Playwright records it: the product page, the OrbitCrate store, a controlled
// outage, the incident, the remediation request, the approval, the verified
// recovery, a security finding, VigilAI and the audit trail.  Captions at the
// bottom of the screen say what is happening.  Nothing is staged: every screen
// is the real application answering real requests, so the waits are real too
// (the alert needs about half a minute to become an incident).
//
// It signs in with the bootstrap accounts from the repository's .env file and
// changes the same things the live demonstration changes (one outage, one
// incident, one remediation request).  The video is not committed: the
// recordings/ folder is ignored by git.
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
const OUT = path.resolve(__dirname, typeof args.out === 'string' ? args.out : '../../recordings');
const PACE = Number(args.pace) > 0 ? Number(args.pace) : 1; // 1.5 = half as slow again
const SIZE = { width: 1280, height: 720 };

let current = '';

/** Draw (or update) the caption bar.  Styles are set through the DOM, which the page's CSP allows. */
async function draw(page) {
  await page
    .evaluate((text) => {
      let bar = document.getElementById('demo-caption');
      if (!bar) {
        bar = document.createElement('div');
        bar.id = 'demo-caption';
        Object.assign(bar.style, {
          position: 'fixed', left: '50%', bottom: '16px', transform: 'translateX(-50%)', zIndex: '2147483647',
          width: 'max-content', maxWidth: '84%', padding: '10px 18px', borderRadius: '8px',
          background: 'rgba(8, 10, 9, 0.94)', color: '#ffffff', border: '1px solid #c8f135',
          boxShadow: '0 12px 32px rgba(0, 0, 0, 0.5)', textAlign: 'center', pointerEvents: 'none',
          font: '500 17px/1.4 "IBM Plex Sans", "Manrope", system-ui, sans-serif',
        });
        document.body.appendChild(bar);
      }
      bar.textContent = text;
      bar.style.display = text ? 'block' : 'none';
    }, current)
    .catch(() => {}); // the page is navigating; the load handler draws it again
}

async function say(page, text, seconds = 3.5) {
  current = text;
  console.log(`  ${text}`);
  await draw(page);
  await page.waitForTimeout(seconds * 1000 * PACE);
}

const pause = (page, seconds) => page.waitForTimeout(seconds * 1000 * PACE);

async function scrollTo(page, selector) {
  await page.evaluate((target) => document.querySelector(target)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), selector);
  await pause(page, 1.2);
}

async function signIn(page, account, who) {
  await page.goto('/login');
  await say(page, `${who} signs in`, 1.5);
  await page.getByLabel('E-mail').pressSequentially(account.email, { delay: 35 });
  await page.getByLabel('Password', { exact: true }).fill(account.password);
  await pause(page, 0.6);
  await page.getByRole('button', { name: 'Sign in' }).click();
  // After a sign-out the application returns the next user to the page the
  // previous one was on, so wait for the console itself and then open the Overview.
  await page.getByRole('button', { name: 'Logout' }).waitFor();
  await page.getByRole('navigation').getByRole('link', { name: 'Overview', exact: true }).click();
  await page.getByRole('heading', { name: 'Overview', level: 1 }).waitFor();
}

async function signOut(page) {
  await page.getByRole('button', { name: 'Logout' }).click();
  await page.getByRole('heading', { name: 'Sign in' }).waitFor();
}

async function adminApi() {
  const login = await fetch(`${BASE}/api/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: accounts.admin.email, password: accounts.admin.password }),
  });
  if (!login.ok) throw new Error(`Administrator sign-in failed: HTTP ${login.status}`);
  const { access_token: token } = await login.json();
  return (method, url, body) => fetch(`${BASE}${url}`, {
    method, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: body ? JSON.stringify(body) : undefined,
  });
}

async function clearFault() {
  // Never leave the store broken, whatever happened during the recording.
  const call = await adminApi();
  await call('POST', '/api/demo/faults', { mode: 'none' });
}

/**
 * A clean starting state, as in the preparation checklist of the demonstration
 * script: no fault active, and no resolved incident of the outage alert left
 * over (a resolved one would be reopened instead of a new incident appearing).
 */
async function prepare() {
  const call = await adminApi();
  await call('POST', '/api/demo/faults', { mode: 'none' });
  const listing = await (await call('GET', '/api/incidents?status=RESOLVED&q=ApplicationUnavailable&page_size=100')).json();
  for (const incident of listing.items || []) {
    await call('POST', `/api/incidents/${incident.id}/transition`, { status: 'CLOSED', note: 'Closed before recording the demonstration.' });
  }
  const active = await (await call('GET', '/api/incidents?active_only=true&q=ApplicationUnavailable')).json();
  if (active.total) throw new Error('An outage incident is still active. Resolve it before recording.');
}

async function walkthrough(page) {
  // --- 1. product page ------------------------------------------------------
  await page.goto('/');
  await page.getByRole('heading', { level: 1 }).waitFor();
  await say(page, 'VigilOps: the public product page. No account is needed to read it.', 4.5);
  await scrollTo(page, '#capabilities');
  await say(page, 'Six capabilities: monitoring, incidents, security findings, remediation, audit trail, VigilAI.', 4.5);
  await scrollTo(page, '#workflow');
  await say(page, 'One closed loop: detect, open an incident, request, approve, execute, verify, record.', 4.5);
  await scrollTo(page, '#architecture');
  await say(page, 'Seven containers. Only the reverse proxy is published.', 4);
  await scrollTo(page, '#roles');
  await say(page, 'Two roles: an Operator requests, an Administrator approves.', 4);

  // --- 2. the monitored application -----------------------------------------
  await page.goto('/orbitcrate/');
  await page.getByRole('heading', { name: 'Crate XL' }).waitFor();
  await say(page, 'OrbitCrate: the demonstration store that VigilOps monitors.', 4);
  await page.getByRole('button', { name: 'Choose Crate M' }).click();
  await pause(page, 1.2);
  await page.getByRole('checkbox', { name: /Daily backups/ }).check();
  await page.getByRole('button', { name: 'One server more' }).click();
  await say(page, 'The price is calculated by the store on every change: real requests.', 3.5);
  await page.getByLabel('Project name').pressSequentially('campus-portal', { delay: 45 });
  await page.getByRole('button', { name: 'Place order' }).click();
  await page.locator('.order').first().waitFor();
  await say(page, 'A demonstration order: received, provisioning, then active. Nothing is charged.', 5);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
  await say(page, 'Store pulse: the response time of each request, measured in the browser.', 4);

  // --- 3. healthy state in the console --------------------------------------
  await signIn(page, accounts.admin, 'The Administrator');
  await say(page, 'Overview: live Prometheus telemetry of the store. Everything is healthy.', 5);

  // --- 4. controlled outage -------------------------------------------------
  await page.goto('/settings');
  await page.getByRole('tab', { name: 'Demo controls' }).click();
  await say(page, 'Demonstration controls: only an Administrator can inject a fault.', 3.5);
  await page.locator('li').filter({ has: page.getByText('outage', { exact: true }) }).getByRole('button', { name: 'Inject' }).click();
  await pause(page, 1.5);
  await page.getByRole('dialog').getByRole('button', { name: 'Inject fault' }).click();
  await say(page, 'A controlled outage is injected into the store.', 3);

  await page.goto('/orbitcrate/');
  await say(page, 'The store has really stopped answering: HTTP 503.', 4.5);

  await page.goto('/monitoring');
  await page.getByRole('tab', { name: /demo-app/ }).filter({ hasText: 'Down' }).waitFor({ timeout: 60_000 });
  await say(page, 'Monitoring: Prometheus reports the scrape target down.', 4.5);
  await signOut(page);

  // --- 5. the Operator works the incident -----------------------------------
  await signIn(page, accounts.operator, 'The Operator');
  await page.goto('/incidents');
  await say(page, 'Waiting for the alert: the rule must hold for 15 seconds before it fires.', 2);
  const row = page.getByRole('row', { name: /Demo application is unavailable/ }).filter({ hasText: /Open/ }).first();
  await row.waitFor({ timeout: 150_000 });
  await say(page, 'Alertmanager called the webhook: an incident is open.', 4);
  await row.click();
  await page.getByRole('button', { name: 'Acknowledge' }).waitFor();
  await say(page, 'The incident is labelled as a simulated fault, with severity and a recommended action.', 5);
  await page.getByRole('button', { name: 'Acknowledge' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Acknowledge' }).click();
  await say(page, 'The Operator acknowledges the incident.', 3);

  await page.getByRole('button', { name: 'Request remediation' }).scrollIntoViewIfNeeded();
  await say(page, 'ACTION-001: what the worker will do and how success is verified.', 4.5);
  await page.getByRole('button', { name: 'Request remediation' }).click();
  await page.getByLabel(/Justification/).pressSequentially('The store is down. Recover the application.', { delay: 30 });
  await pause(page, 1);
  await page.getByRole('button', { name: 'Submit request' }).click();
  await page.waitForURL(/\/remediation\/\d+$/);
  const requestPath = new URL(page.url()).pathname;
  await say(page, 'The request waits for approval. The Operator has no Approve or Execute button.', 5.5);
  await signOut(page);

  // --- 6. the Administrator approves and dispatches -------------------------
  await signIn(page, accounts.admin, 'The Administrator');
  await page.goto(requestPath);
  await page.getByRole('button', { name: 'Approve', exact: true }).waitFor();
  await say(page, 'The Administrator reviews the request.', 3.5);
  await page.getByRole('button', { name: 'Approve', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Approve', exact: true }).click();
  await page.getByRole('button', { name: 'Execute', exact: true }).waitFor();
  await say(page, 'Approved. Nothing has run yet: execution is a separate decision.', 3.5);
  await page.getByRole('button', { name: 'Execute', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Execute', exact: true }).click();
  await say(page, 'The restricted worker runs the action, then the result is verified independently.', 2);
  await page.getByText('The action was executed and independently verified.').waitFor({ timeout: 240_000 });
  await say(page, 'Succeeded: health check, Prometheus target and cleared alert were all confirmed.', 5.5);
  await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }));
  await say(page, 'Execution details, verification checks and the audit trail of this request.', 5);

  await page.goto('/incidents');
  await say(page, 'The incident is resolved, with the evidence attached.', 4.5);

  await page.goto('/orbitcrate/');
  await page.getByRole('heading', { name: 'Crate XL' }).waitFor();
  await say(page, 'The store is answering again.', 4.5);

  // --- 7. security findings -------------------------------------------------
  await page.goto('/findings');
  await page.getByRole('heading', { name: 'Security Findings', level: 1 }).waitFor();
  await say(page, 'Security findings: a cloud configuration scanned against rules SEC-001 to SEC-005.', 5);
  const finding = page.getByRole('row', { name: /SEC-00\d/ }).first();
  if (await finding.count()) {
    await finding.click();
    await page.getByRole('heading', { name: /SEC-00\d/ }).waitFor();
    await say(page, 'Each finding has its evidence and a recommended fix.', 5);
  }

  // --- 8. VigilAI -----------------------------------------------------------
  await page.goto('/');
  await page.getByRole('button', { name: 'Open VigilAI assistant' }).click();
  const chat = page.getByRole('dialog', { name: 'VigilAI assistant' });
  await chat.getByLabel('Ask VigilAI about VigilOps').pressSequentially('What does SEC-001 mean?', { delay: 40 });
  await say(page, 'VigilAI: a read-only assistant grounded in the documentation and the current state.', 1.5);
  await chat.getByLabel('Ask VigilAI about VigilOps').press('Enter');
  await chat.getByText(/public access/i).first().waitFor({ timeout: 60_000 });
  await say(page, 'It explains. It cannot approve or execute anything.', 6);
  await page.keyboard.press('Escape');

  // --- 9. audit trail -------------------------------------------------------
  await page.goto('/audit');
  await page.getByLabel('Category').selectOption('REMEDIATION');
  await say(page, 'Audit trail: who requested, who approved, what was executed and how it ended.', 6);
  await say(page, 'End of the demonstration.', 3);
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  await prepare();
  const browser = await chromium.launch();
  const context = await browser.newContext({
    baseURL: BASE, viewport: SIZE, colorScheme: 'dark', recordVideo: { dir: OUT, size: SIZE },
  });
  await context.addInitScript(() => window.localStorage.setItem('vigilops.theme', 'dark'));
  const page = await context.newPage();
  page.on('load', () => draw(page));
  const started = Date.now();
  let failure = null;
  try {
    console.log(`Recording against ${BASE}`);
    await walkthrough(page);
  } catch (error) {
    failure = error;
    await page.screenshot({ path: path.join(OUT, 'where-it-stopped.png') }).catch(() => {});
  }
  const video = page.video();
  await context.close(); // finishes the video file
  await browser.close();
  await clearFault().catch(() => {});

  const target = path.join(OUT, failure ? 'vigilops-demo-incomplete.webm' : 'vigilops-demo.webm');
  if (video) {
    fs.rmSync(target, { force: true });
    fs.renameSync(await video.path(), target);
    console.log(`\n${failure ? 'Incomplete recording' : 'Recording'}: ${target}  (${Math.round((Date.now() - started) / 1000)} s, ${(fs.statSync(target).size / 1048576).toFixed(1)} MB)`);
  }
  if (failure) {
    console.error(`The walkthrough stopped: ${failure.message.split('\n')[0]}`);
    process.exit(1);
  }
})().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
