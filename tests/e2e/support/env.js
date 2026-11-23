// Reads the repository's .env file (the same file Docker Compose uses) so the
// tests sign in with whatever bootstrap accounts this installation has.
// Credentials are never written into the test sources or the reports.
const fs = require('fs');
const path = require('path');

function loadEnv() {
  const file = path.resolve(__dirname, '..', '..', '..', '.env');
  const values = {};
  if (!fs.existsSync(file)) {
    throw new Error(`Missing ${file}. Copy .env.example to .env and start the stack first.`);
  }
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue;
    const index = trimmed.indexOf('=');
    values[trimmed.slice(0, index).trim()] = trimmed.slice(index + 1).trim();
  }
  return values;
}

const env = loadEnv();

const accounts = {
  admin: { email: env.BOOTSTRAP_ADMIN_EMAIL, password: env.BOOTSTRAP_ADMIN_PASSWORD },
  operator: { email: env.BOOTSTRAP_OPERATOR_EMAIL, password: env.BOOTSTRAP_OPERATOR_PASSWORD },
};

/** Sign in through the real login form. */
async function signIn(page, account) {
  await page.goto('/login');
  await page.getByLabel('E-mail').fill(account.email);
  await page.getByLabel('Password', { exact: true }).fill(account.password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('heading', { name: 'Overview', level: 1 }).waitFor();
}

module.exports = { env, accounts, signIn };
