/*
 * Start page of the OrbitCrate store on the static host (frontend/vercel.json).
 *
 * The store runs on the API server.  On a hosting plan that switches an idle
 * server off, the first visit would get the hosting platform's error page
 * until the server has started.  The static host never sleeps, so it serves
 * this page at the store's address instead: it asks the store whether it
 * answers, says so while the server is starting, and opens the store by
 * itself.  When the server is awake the visitor sees the store after one
 * short extra request.
 */
(function () {
  'use strict';

  var STATUS_URL = '/orbitcrate/api/status';
  var STORE_URL = '/orbitcrate/open';
  var SLOW_AFTER_MS = 1500; // say "starting" only if the first answer takes longer
  var RETRY_EVERY_MS = 3000;
  var REQUEST_TIMEOUT_MS = 40000; // a waking server may hold the request for a while
  var GIVE_UP_AFTER_MS = 240000;

  var TEXT = {
    opening: {
      headline: 'Opening the store',
      detail: '',
    },
    starting: {
      headline: 'Starting the demonstration server',
      detail:
        'The server behind this store is switched off when nobody has used it for 15 minutes, ' +
        'and needs about a minute to start. The store opens here by itself; there is no need to reload.',
    },
    unreachable: {
      headline: 'The store is not answering',
      detail:
        'The server did not start within four minutes. It may be restarting or temporarily unavailable.',
    },
  };

  var page = document.documentElement;
  var headline = document.getElementById('headline');
  var detail = document.getElementById('detail');
  var elapsed = document.getElementById('elapsed');
  var actions = document.getElementById('actions');
  var retryButton = document.getElementById('retry');

  var run = 0;
  var startedAt = 0;
  var clock = null;

  function show(state) {
    page.setAttribute('data-state', state);
    headline.textContent = TEXT[state].headline;
    detail.textContent = TEXT[state].detail;
    detail.hidden = TEXT[state].detail === '';
    actions.hidden = state !== 'unreachable';
    elapsed.hidden = state !== 'starting';
  }

  function tick() {
    var seconds = Math.floor((Date.now() - startedAt) / 1000);
    var rest = seconds % 60;
    elapsed.textContent = 'Waiting for ' + Math.floor(seconds / 60) + ':' + (rest < 10 ? '0' : '') + rest;
  }

  function wait(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  /*
   * The store itself answers with a JSON object that has a "status" field, also
   * while it simulates an outage (it then shows that on its own page).  A
   * hosting platform's placeholder page, a gateway error, or no answer at all
   * means that the server is not up yet.
   */
  function storeAnswers() {
    var controller = typeof AbortController === 'function' ? new AbortController() : null;
    var timer = controller ? setTimeout(function () { controller.abort(); }, REQUEST_TIMEOUT_MS) : null;
    return fetch(STATUS_URL, {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
      signal: controller ? controller.signal : undefined,
    })
      .then(function (response) { return response.json(); })
      .then(function (body) { return Boolean(body) && typeof body.status === 'string'; })
      .catch(function () { return false; })
      .then(function (answers) {
        if (timer) clearTimeout(timer);
        return answers;
      });
  }

  function stopClock() {
    if (clock) clearInterval(clock);
    clock = null;
  }

  async function open() {
    var mine = ++run; // a later run (Try again, return from history) replaces this one
    startedAt = Date.now();
    stopClock();
    show('opening');
    tick();
    clock = setInterval(tick, 1000);
    var slow = setTimeout(function () {
      if (mine === run && page.getAttribute('data-state') === 'opening') show('starting');
    }, SLOW_AFTER_MS);

    for (;;) {
      var answers = await storeAnswers();
      if (mine !== run) return;
      if (answers) {
        clearTimeout(slow);
        stopClock();
        // replace(): "Back" in the store returns to where the visitor came from, not to this page.
        location.replace(STORE_URL + location.search + location.hash);
        return;
      }
      if (Date.now() - startedAt > GIVE_UP_AFTER_MS) {
        clearTimeout(slow);
        stopClock();
        show('unreachable');
        return;
      }
      show('starting');
      await wait(RETRY_EVERY_MS);
      if (mine !== run) return;
    }
  }

  retryButton.addEventListener('click', open);
  // Shown again from the browser's page cache (after "Back"): ask afresh.
  window.addEventListener('pageshow', function (event) { if (event.persisted) open(); });
  open();
})();
