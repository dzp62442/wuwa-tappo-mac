import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const assets = new URL('../dist/Wuwa Tappo.app/Contents/Resources/original/assets/', import.meta.url);
const core = readFileSync(new URL('index-BelNnexT.js', assets), 'utf8');
const login = readFileSync(new URL('login-D7Mrat3T.js', assets), 'utf8');

function section(source, start, end) {
  const first = source.indexOf(start), last = source.indexOf(end, first);
  assert(first >= 0 && last > first);
  return source.slice(first, last);
}

function monitor(onlineMode = true) {
  const timers = new Map();
  let now = 10000, next = 0, requests = 0, healthy = false;
  const context = vm.createContext({
    Date: { now: () => now }, performance: { now: () => now },
    Math: Object.assign(Object.create(Math), { random: () => 0 }),
    window: {
      __MACOS_ONLINE__: onlineMode, addEventListener() {}, removeEventListener() {},
      setTimeout(fn, delay) { timers.set(++next, { fn, at: now + delay }); return next; },
      clearTimeout(id) { timers.delete(id); },
    },
    ref: value => ({ value }), readonly: value => value, listen: async () => () => {},
    console: { warn() {} }, logDiagnostic() {}, reportAlert() {}, requestNetworkDiagnostics() {},
    navigator: { onLine: true }, ApiHost: 'https://fixture.invalid', PRE_RELEASE_ENABLED: false,
    MAINTENANCE_HTTP_STATUS: 503, diagnosticRequestId() {}, diagnosticErrorCode: () => 'network_error',
    AbortController,
    async fetch() {
      requests++;
      if (!healthy) throw Error('fixture offline');
      return { ok: true, status: 200, headers: new Headers() };
    },
  });
  const source = 'const ' + section(core, 'HEALTHCHECK_TIMEOUT_MS=', 'const emptyAssetNameDictionaries=');
  const gate = section(login, 'async function $(){const n=Date.now()+Ln;', 'async function D(){');
  vm.runInContext(source + ';const Z=networkSnapshot,Ln=5000;' + gate + ';startNetworkMonitoring()', context);
  return {
    context, status: () => vm.runInContext('snapshot.value.status', context),
    requests: () => requests, restore() { healthy = true; },
    async advance(duration) {
      const end = now + duration;
      for (;;) {
        await new Promise(resolve => setImmediate(resolve));
        const item = [...timers].sort((a, b) => a[1].at - b[1].at)[0];
        if (!item || item[1].at > end) break;
        timers.delete(item[0]); now = item[1].at; item[1].fn();
      }
      now = end;
    },
  };
}

test('path recovery just after a failed retry unblocks the passport gate without a restart', async () => {
  for (const gap of [30, 900, 1001]) {
    const m = monitor();
    m.context.handleNativeNetworkStatusChanged({ internetAccess: false });
    await m.advance(2000 + gap);
    assert.equal(m.status(), 'offline');
    assert.equal(m.requests(), 2);
    m.restore();
    m.context.handleNativeNetworkStatusChanged({ internetAccess: true });
    const passportReady = m.context.$();
    await m.advance(5100);
    assert.equal(await passportReady, true);
    assert.equal(m.status(), 'online');
    await m.advance(6 * 3600000);
    assert.equal(m.requests(), 3);
  }
});

test('a burst of API and socket failures leaves one probe, and stop cancels it', async () => {
  const m = monitor();
  m.restore(); await m.advance(0);
  for (const source of ['api', 'socket', 'api']) m.context.reportNetworkTransportFailure(source);
  await m.advance(999);
  assert.equal(m.requests(), 1);
  await m.advance(1);
  assert.equal(m.status(), 'online');
  assert.equal(m.requests(), 2);
  m.context.handleBrowserOffline();
  m.context.stopNetworkMonitoring();
  await m.advance(60000);
  assert.equal(m.requests(), 2);
});

test('offline audit starts without reaching the network', async () => {
  const m = monitor(false);
  await m.advance(60000);
  assert.equal(m.status(), 'offline');
  assert.equal(m.requests(), 0);
});
