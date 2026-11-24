/* OrbitCrate storefront.  Plain JavaScript, no build step.
 *
 * Every address is relative, so the store works at the root of its own port
 * and behind a path prefix of a reverse proxy.  Text from the server is always
 * written with textContent, never as HTML.
 */
(() => {
  'use strict';

  const SLOW_MS = 800;          // a response slower than this is shown as slow
  const HEARTBEAT_MS = 5000;    // how often an open page refreshes its orders
  const BUSY_POLL_MS = 2000;    // ... while an order is being set up or the store is failing
  const MAX_SAMPLES = 28;       // bars in the store pulse
  const PROJECT_PATTERN = /^[A-Za-z0-9][A-Za-z0-9 ._-]{1,39}$/;
  const STEPS = ['received', 'provisioning', 'active'];
  const STATUS_TEXT = { received: 'Received', provisioning: 'Provisioning', active: 'Active', cancelled: 'Cancelled' };

  const $ = (id) => document.getElementById(id);

  function el(tag, props, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props || {})) {
      if (value === false || value == null) continue;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else if (key === 'height') node.style.height = value;
      else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
      else if (key in node && typeof value !== 'string') node[key] = value;
      else node.setAttribute(key, value === true ? '' : value);
    }
    for (const child of children.flat()) {
      if (child == null || child === false) continue;
      node.append(child.nodeType ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  // ---------------------------------------------------------------- session
  function newId() {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
  }

  const session = (() => {
    const key = 'orbitcrate.session';
    try {
      const stored = localStorage.getItem(key);
      if (stored && /^[A-Za-z0-9_-]{8,64}$/.test(stored)) return stored;
      const created = newId();
      localStorage.setItem(key, created);
      return created;
    } catch (error) {
      return newId();  // storage blocked: the orders last as long as this page
    }
  })();

  // ------------------------------------------------------------------ money
  const whole = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });
  const exact = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const money = (value) => (Number.isInteger(value) ? whole : exact).format(value);

  // -------------------------------------------------------------- store pulse
  const samples = [];
  let health = 'checking';
  let lastFailure = 0;

  function record(ms, status) {
    const failed = status === 0 || status >= 500;
    samples.push({ ms, status, kind: failed ? 'fail' : ms >= SLOW_MS ? 'slow' : 'ok' });
    if (samples.length > MAX_SAMPLES) samples.shift();
    if (failed) lastFailure = status;

    const recent = samples.slice(-3);
    const failures = recent.filter((sample) => sample.kind === 'fail').length;
    const latest = samples[samples.length - 1];
    if (failures >= 2 || (recent.length < 3 && latest.kind === 'fail')) health = 'down';
    else if (latest.kind === 'slow') health = 'slow';
    else if (latest.kind === 'ok') health = 'ok';
    renderPulse();
  }

  function renderPulse() {
    const latest = samples[samples.length - 1];
    const label = { checking: 'Checking', ok: 'Operational', slow: 'Slow responses', down: 'Not answering' }[health];
    const pillText = { checking: 'Checking the store', ok: 'Store operational', slow: 'Store is slow', down: 'Store is failing' }[health];

    $('status-pill').dataset.state = health;
    $('status-text').textContent = pillText;
    $('pulse-state').dataset.state = health;
    $('pulse-state').textContent = label;
    $('pulse-ms').textContent = latest ? String(Math.round(latest.ms)) : '--';

    const bars = [];
    for (let index = 0; index < MAX_SAMPLES - samples.length; index += 1) {
      bars.push(el('i', { 'data-kind': 'empty', height: '6%' }));
    }
    for (const sample of samples) {
      const height = Math.max(12, Math.min(100, Math.sqrt(sample.ms / 2000) * 100));
      bars.push(el('i', { 'data-kind': sample.kind, height: `${height.toFixed(0)}%` }));
    }
    $('pulse-bars').replaceChildren(...bars);

    const count = (kind) => samples.filter((sample) => sample.kind === kind).length;
    $('pulse-summary').textContent = samples.length
      ? `Last ${samples.length}: ${count('ok')} normal, ${count('slow')} slow, ${count('fail')} failed.`
      : '';

    const alert = $('alert');
    if (health === 'down') {
      alert.textContent = lastFailure
        ? `The store is not answering correctly (HTTP ${lastFailure}). Retrying automatically.`
        : 'The store cannot be reached. Retrying automatically.';
      alert.hidden = false;
    } else {
      alert.hidden = true;
    }
  }

  // -------------------------------------------------------------------- API
  class StoreError extends Error {
    constructor(message, status) {
      super(message);
      this.status = status;
    }
  }

  function detailOf(data, status) {
    if (data && typeof data.detail === 'string') return data.detail;
    if (data && Array.isArray(data.detail) && data.detail.length) return 'Some of the values are not valid.';
    return `The store answered HTTP ${status}.`;
  }

  async function api(path, options = {}) {
    const headers = { Accept: 'application/json', 'X-Session-Id': session };
    if (options.body) headers['Content-Type'] = 'application/json';
    const started = performance.now();
    let response;
    try {
      response = await fetch(path, {
        method: options.method || 'GET',
        headers,
        body: options.body ? JSON.stringify(options.body) : undefined,
        cache: 'no-store',
      });
    } catch (error) {
      record(performance.now() - started, 0);
      throw new StoreError('The store cannot be reached.', 0);
    }
    record(performance.now() - started, response.status);
    let data = null;
    try {
      data = await response.json();
    } catch (error) {
      data = null;
    }
    if (!response.ok) throw new StoreError(detailOf(data, response.status), response.status);
    return data;
  }

  // ------------------------------------------------------------------ toast
  let toastTimer = 0;
  function toast(message, kind) {
    const node = $('toast');
    node.textContent = message;
    node.dataset.kind = kind || 'info';
    node.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { node.hidden = true; }, 4200);
  }

  // ---------------------------------------------------------------- catalogue
  let catalog = null;

  function specs(plan) {
    return [
      ['vCPU', String(plan.vcpu)],
      ['Memory', `${plan.ram_gb} GB`],
      ['SSD storage', `${plan.disk_gb} GB`],
      ['Transfer', `${plan.transfer_tb} TB`],
    ];
  }

  function renderPlans() {
    $('plan-grid').replaceChildren(...catalog.plans.map((plan) => el(
      'article', { class: `plan${plan.featured ? ' plan--featured' : ''}` },
      plan.featured && el('span', { class: 'plan__tag', text: 'Balanced choice' }),
      el('h3', { text: plan.name }),
      el('p', { class: 'plan__summary', text: plan.summary }),
      el('p', { class: 'plan__price' }, money(plan.price), el('small', { text: '/ month' })),
      el('ul', { class: 'specs' }, specs(plan).map(([name, value]) => el('li', null, el('span', { text: name }), el('b', { text: value })))),
      el('button', {
        class: `btn ${plan.featured ? 'btn--primary' : 'btn--quiet'}`,
        type: 'button',
        text: `Choose ${plan.name}`,
        onclick: () => choosePlan(plan.id),
      }),
    )));
  }

  function choosePlan(planId) {
    const input = document.querySelector(`input[name="plan"][value="${planId}"]`);
    if (input) input.checked = true;
    requestEstimate();
    $('configure').scrollIntoView();
  }

  function renderBuilder() {
    const preferred = (catalog.plans.find((plan) => plan.featured) || catalog.plans[0]).id;
    $('plan-options').replaceChildren(...catalog.plans.map((plan) => el(
      'label', { class: 'tile' },
      el('input', { type: 'radio', name: 'plan', value: plan.id, checked: plan.id === preferred }),
      el('span', { class: 'tile__box' },
        el('span', { class: 'tile__name' }, plan.name, el('em', { text: money(plan.price) })),
        el('span', { class: 'tile__meta', text: `${plan.vcpu} vCPU, ${plan.ram_gb} GB memory, ${plan.disk_gb} GB SSD` })),
    )));

    $('region-options').replaceChildren(...catalog.regions.map((region, index) => {
      const extra = Math.round((region.multiplier - 1) * 100);
      return el('label', { class: 'tile' },
        el('input', { type: 'radio', name: 'region', value: region.id, checked: index === 0 }),
        el('span', { class: 'tile__box' },
          el('span', { class: 'tile__name', text: region.name }),
          el('span', { class: 'tile__meta', text: extra ? `${extra}% above base price` : 'Base price' })));
    }));

    $('addon-options').replaceChildren(...catalog.addons.map((addon) => el(
      'label', { class: 'extra' },
      el('input', { type: 'checkbox', name: 'addons', value: addon.id }),
      el('span', { class: 'extra__name', text: addon.name }),
      el('span', { class: 'extra__price', text: addon.kind === 'percent' ? `+${addon.value}%` : `+${money(addon.value)} / server` }),
      el('span', { class: 'extra__text', text: addon.description }),
    )));

    $('term-options').replaceChildren(...catalog.terms.map((term, index) => el(
      'label', null,
      el('input', { type: 'radio', name: 'term', value: term.id, checked: index === 0 }),
      el('span', { text: term.discount_percent ? `${term.name} (${term.discount_percent}% off)` : term.name }),
    )));
  }

  async function loadCatalog() {
    try {
      catalog = await api('api/catalog');
    } catch (error) {
      $('plan-grid').replaceChildren(el('p', { class: 'placeholder', text: `Plans could not be loaded. ${error.message} Trying again.` }));
      setTimeout(loadCatalog, 3000);
      return;
    }
    renderPlans();
    renderBuilder();
    renderOrders(true);
    requestEstimate();
  }

  // ---------------------------------------------------------------- estimate
  let estimateTimer = 0;
  let estimateRun = 0;
  let priced = false;

  function quantity() {
    const input = $('quantity');
    const value = Math.min(10, Math.max(1, Math.round(Number(input.value) || 1)));
    if (String(value) !== input.value) input.value = String(value);
    return value;
  }

  function selection() {
    const data = new FormData($('builder'));
    return { plan: data.get('plan'), region: data.get('region'), quantity: quantity(), addons: data.getAll('addons'), term: data.get('term') };
  }

  function requestEstimate() {
    if (!catalog) return;
    clearTimeout(estimateTimer);
    document.querySelector('.summary').classList.add('is-busy');
    estimateTimer = setTimeout(estimate, 180);
  }

  async function estimate() {
    const run = ++estimateRun;
    const summary = document.querySelector('.summary');
    try {
      const price = await api('api/estimate', { method: 'POST', body: selection() });
      if (run !== estimateRun) return;
      $('summary-body').replaceChildren(
        el('ul', { class: 'lines' },
          price.lines.map((line) => el('li', null, el('span', { text: line.label }), el('b', { text: money(line.amount) }))),
          el('li', { class: 'is-sub' }, el('span', { text: 'Net' }), el('b', { text: money(price.net) })),
          el('li', { class: 'is-sub' }, el('span', { text: price.tax_label }), el('b', { text: money(price.tax) }))),
        el('p', { class: 'total' }, el('span', { text: 'Monthly total' }), el('strong', { text: money(price.monthly_total) })),
      );
      priced = true;
    } catch (error) {
      if (run !== estimateRun) return;
      $('summary-body').replaceChildren(el('p', { class: 'summary__wait', 'data-kind': 'error', text: `The price could not be calculated. ${error.message}` }));
      priced = false;
      setTimeout(() => { if (run === estimateRun) requestEstimate(); }, 3000);
    }
    summary.classList.remove('is-busy');
    $('place-order').disabled = !priced;
  }

  // ------------------------------------------------------------------ orders
  let orders = [];
  let ordersLoaded = false;
  let shown = '';
  let pollTimer = 0;

  function describe(order) {
    const chosen = order.selection;
    const parts = [`${chosen.quantity} x ${chosen.plan_name}`, chosen.region_name];
    if (catalog) {
      for (const id of chosen.addons) {
        const addon = catalog.addons.find((item) => item.id === id);
        if (addon) parts.push(addon.name);
      }
      const term = catalog.terms.find((item) => item.id === chosen.term);
      if (term) parts.push(term.name);
    }
    return parts.join(' · ');
  }

  function etaText(order) {
    if (order.status === 'cancelled') return 'Cancelled. Nothing is running for this order.';
    if (order.status === 'active') return 'Set up and running.';
    return order.ready_in_seconds > 0 ? `Ready in about ${order.ready_in_seconds} s.` : 'Almost ready.';
  }

  function orderCard(order) {
    const position = STEPS.indexOf(order.status);
    const track = el('ol', { class: 'track', 'data-cancelled': order.status === 'cancelled' },
      STEPS.map((step, index) => el('li', {
        class: order.status === 'active' || index < position ? 'is-done' : index === position ? 'is-now' : '',
        text: STATUS_TEXT[step],
      })));
    return el('article', { class: 'order', 'data-order': order.id },
      el('div', null,
        el('p', { class: 'order__id', text: order.id }),
        el('p', { class: 'order__project', text: order.project }),
        el('p', { class: 'order__what', text: describe(order) })),
      el('div', { class: 'order__progress' },
        el('span', { class: 'chip', 'data-status': order.status, text: STATUS_TEXT[order.status] || order.status }),
        track,
        el('p', { class: 'order__eta', text: etaText(order) })),
      el('div', { class: 'order__side' },
        el('p', { class: 'order__price' }, money(order.monthly_total), el('small', { text: ' / month' })),
        order.status !== 'cancelled' && el('button', {
          class: 'btn btn--quiet', type: 'button', text: 'Cancel order', onclick: () => cancelOrder(order.id),
        })));
  }

  function renderOrders(force) {
    if (!ordersLoaded) return;
    const signature = JSON.stringify(orders);
    if (!force && signature === shown) return;
    shown = signature;

    const open = orders.filter((order) => order.status !== 'cancelled').length;
    $('order-count').textContent = String(open);
    $('order-count').hidden = open === 0;

    if (!orders.length) {
      $('order-list').replaceChildren(el('div', { class: 'empty' },
        el('strong', { text: 'No orders yet' }),
        'Configure a server above and place the order. It appears here and moves from received to provisioning to active.'));
      return;
    }
    $('order-list').replaceChildren(...orders.map(orderCard));
  }

  function inProgress() {
    return orders.some((order) => order.status === 'received' || order.status === 'provisioning');
  }

  async function refreshOrders() {
    clearTimeout(pollTimer);
    if (document.hidden) return;  // resumes on visibilitychange
    try {
      const data = await api('api/orders');
      orders = data.orders;
      ordersLoaded = true;
      renderOrders(false);
    } catch (error) {
      if (!ordersLoaded) {
        $('order-list').replaceChildren(el('p', { class: 'placeholder', text: `Your orders could not be loaded. ${error.message}` }));
      }
    }
    pollTimer = setTimeout(refreshOrders, inProgress() || health === 'down' ? BUSY_POLL_MS : HEARTBEAT_MS);
  }

  async function placeOrder(event) {
    event.preventDefault();
    const input = $('project');
    const problem = $('project-error');
    const project = input.value.trim();
    if (!PROJECT_PATTERN.test(project)) {
      problem.textContent = 'Use 2 to 40 letters, digits, spaces, dots, dashes or underscores, starting with a letter or digit.';
      problem.hidden = false;
      input.focus();
      return;
    }
    problem.hidden = true;
    const button = $('place-order');
    button.disabled = true;
    button.textContent = 'Placing order…';
    try {
      const order = await api('api/orders', { method: 'POST', body: { ...selection(), project } });
      input.value = '';
      toast(`Order ${order.id} received.`);
      await refreshOrders();
      $('orders').scrollIntoView();
    } catch (error) {
      toast(`The order was not placed. ${error.message}`, 'error');
    }
    button.textContent = 'Place order';
    button.disabled = !priced;
  }

  async function cancelOrder(orderId) {
    try {
      await api(`api/orders/${encodeURIComponent(orderId)}/cancel`, { method: 'POST' });
      toast(`Order ${orderId} cancelled.`);
    } catch (error) {
      toast(`The order was not cancelled. ${error.message}`, 'error');
    }
    refreshOrders();
  }

  // ------------------------------------------------------------------- start
  const builder = $('builder');
  builder.addEventListener('change', requestEstimate);
  builder.addEventListener('submit', placeOrder);
  $('quantity').addEventListener('input', requestEstimate);
  $('quantity-less').addEventListener('click', () => { $('quantity').value = String(quantity() - 1); requestEstimate(); });
  $('quantity-more').addEventListener('click', () => { $('quantity').value = String(quantity() + 1); requestEstimate(); });
  $('project').addEventListener('input', () => { $('project-error').hidden = true; });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshOrders(); });

  // Behind a path prefix the platform that monitors this store is at the site root.
  if (location.pathname.replace(/\/+$/, '') !== '') $('console-link').hidden = false;
  // Opened without the trailing slash (possible behind some proxies, which then
  // supply a base element so that everything still loads): tidy the address.
  if (!location.pathname.endsWith('/')) {
    history.replaceState(null, '', `${location.pathname}/${location.search}${location.hash}`);
  }

  renderPulse();
  loadCatalog();
  refreshOrders();
})();
