import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';
import { setImmediate as nextTurn } from 'node:timers/promises';

// Execute the recovered release expressions themselves. Account state is a
// fixture for pure visibility checks; no account service or inventory is used.
const paths = [
  new URL('../recovered/wuwa-tappo-cn-1.0.5/frontend/assets/index-BGIVWra7.js', import.meta.url),
  new URL('../dist/Wuwa Tappo.app/Contents/Resources/original/assets/index-BGIVWra7.js', import.meta.url),
];

function section(source, start, end) {
  const first = source.indexOf(start), last = source.indexOf(end, first);
  assert(first >= 0 && last > first, `Original chest source changed: ${start}`);
  return source.slice(first, last);
}

function gate() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function chestRequests() {
  const source = readFileSync(paths[1], 'utf8'), ref = value => ({ value });
  const animation = gate(), claim = gate(), bagReads = [], claims = [];
  let balance = 3000, session = 'fixture';
  const context = vm.createContext({
    A: { isLoggedIn: true, get totalClickCount() { return balance; }, cumulativeClickCount: 3500,
      applyChestClickConsume(count) { balance -= count; } },
    Oe: ref(false), Xn: ref(false), Ke: ref(false), Vi: ref(false), Wi: ref(false),
    Gi: ref(false), Yi: ref(false), ro: ref(true), io: ref(true), L: ref('fixture'),
    x: ref(false), B: ref(false), C: ref([]), E: ref([]), $s: 1000,
    Te: () => false, tn: () => session, lh: () => animation.promise, Ru() {},
    Sv() { const read = gate(); bagReads.push(read); return read.promise; },
    rv(args) { claims.push(args.place); return claim.promise; },
    Cv: x => x, ct: x => x, ps: () => true, Wp() {}, Nn() {}, Iu() {}, Pu() {}, Mu() {}, iv() {},
    mg() {}, vi() {}, Eu: () => false, Xu: () => false, Rt: s => s, yi: t => t, T: s => s,
    pn() {}, we: 0, ie: ref([]), _e: new Map(), window: { setTimeout() {} }, Fu: 0, Pv: 0,
    ye() {}, Oo() {}, Oi() {}, qt() {}, console: { warn() {} },
  });
  vm.runInContext(section(source, 'let ne = null, bagSession = null;', 'let de=null;async function') +
    section(source, 'function Ae(){const e=new Map;for(const t of C.value)', 'async function Vt(e){ne&&') +
    section(source, 'async function Jp(', 'function eh(e){') +
    section(source, 'async function Pc(e){', 'function ao('), context);
  return { animation, claim, bagReads, claims, context, balance: () => balance,
    hints: () => context.ie.value.map(item => context.Qp(item)), replaceSession() { session = 'different'; } };
}

test('a slow bag read cannot delay a claim beyond its animation or hold the next chest locked', async () => {
  const s = chestRequests();
  const first = s.context.Pc('left');
  await s.context.Pc('left');
  assert.deepEqual(s.claims, []);
  s.animation.resolve(); await nextTurn();
  assert.deepEqual(s.claims, ['left']);
  await s.context.Pc('right');
  s.claim.resolve({ click_consume: 1000, asset_name: 'item', asset_type: 'emote', asset_id: 42 });
  await first;
  assert.equal(s.context.Xn.value, false);
  assert.equal(s.balance(), 2000);
  assert.deepEqual(s.hints(), ['']);
  assert.equal(s.bagReads.length, 1);
  s.bagReads[0].resolve([]); await nextTurn();
  assert.equal(s.bagReads.length, 2);
  s.bagReads[1].resolve([{ asset_id: 42, quantity: 1 }]); await nextTurn();
  assert.equal(s.context.C.value[0].quantity, 1);
  assert.deepEqual(s.claims, ['left']);
});

test('a fast pre-claim read preserves the original reward labels', async () => {
  for (const owned of [false, true]) {
    const s = chestRequests(), opening = s.context.Pc('right');
    s.bagReads[0].resolve(owned ? [{ asset_id: 42, quantity: 1 }] : []);
    await nextTurn();
    assert.deepEqual(s.claims, ['right']);
    s.context.C.value = []; // Later inventory updates must not change this hint.
    s.claim.resolve({ click_consume: 1000, asset_name: 'item', asset_type: 'emote', asset_id: 42 });
    s.animation.resolve(); await opening;
    assert.deepEqual(s.hints(), [owned ? 'reward_item_duplicate' : 'reward_item_new_emote']);
    s.bagReads[1].resolve([]); await nextTurn();
  }
});

test('a replaced session or a failed claim cannot spend clicks or cause a second claim', async () => {
  for (const replaced of [true, false]) {
    const s = chestRequests(), opening = s.context.Pc('left');
    if (replaced) s.replaceSession();
    s.bagReads[0].reject(Error('fixture timeout')); await nextTurn();
    if (!replaced) s.claim.reject(Error('fixture unavailable'));
    s.animation.resolve(); await opening;
    assert.deepEqual(s.claims, replaced ? [] : ['left']);
    assert.equal(s.balance(), 3000);
    assert.equal(s.context.Xn.value, false);
  }
});

test('late inventory and claim responses cannot overwrite a replacement account', async () => {
  const s = chestRequests(), opening = s.context.Pc('left');
  s.animation.resolve(); await nextTurn();
  s.replaceSession();
  const newRead = s.context.ee();
  s.bagReads[1].resolve([{ asset_id: 7, quantity: 2 }]); await newRead;
  s.bagReads[0].resolve([{ asset_id: 42, quantity: 1 }]);
  s.claim.resolve({ click_consume: 1000, asset_name: 'item', asset_type: 'emote', asset_id: 42 });
  await opening;
  assert.equal(s.context.C.value[0].asset_id, 7);
  assert.equal(s.balance(), 3000);
  assert.deepEqual(s.hints(), []);
  assert.equal(s.bagReads.length, 2);
});

function originalRules(source, values = {}) {
  const constants = source.match(/Sr=30\*6e4,\$s=1e3,Pw=2e3,/);
  assert(constants, 'Missing original chest constants');
  const ref = value => ({ value });
  let loginEntries = 0;
  const context = {
    pe: getter => ({ get value() { return getter(); } }),
    A: { isLoggedIn: values.loggedIn ?? true, totalClickCount: values.clicks ?? 0 },
    Ke: ref(values.loading ?? false), Xn: ref(false), Oe: ref(values.disablePointer ?? false),
    Yt: ref(values.leftMs ?? 0), Kt: ref(values.rightMs ?? 0), Xo: ref(0), zo: ref(0),
    Yn: ref(values.clicks ?? 0), Tr: ref(values.always ?? false), bt: ref(values.hover ?? false),
    Vi: ref(false), Wi: ref(false), Gi: ref(false), Yi: ref(false), ys: () => 1_000_000,
    Te: () => false, Ru: () => {}, F: () => { loginEntries++; },
    rv: () => { throw Error('Guest chest attempted a reward request'); },
  };
  const code = 'const Sr=30*6e4,$s=1e3,Pw=2e3;'
    + section(source, 'function bc(e){', 'function oo(){')
    + section(source, 'const ro=pe(', 'function oh(){')
    + section(source, 'async function Pc(e){', 'function ao(')
    + `;({snapshot:()=>({left:si.value,right:li.value,leftReady:ro.value,rightReady:io.value,
      actionable:nh(),duration:Sr,minimum:$s,twoSlots:Pw}),
      remaining:Co,seconds:_c,format:bc,cooldown:ri,open:Pc})`;
  const api = vm.runInNewContext(code, context);
  return { api, context, loginEntries: () => loginEntries };
}

for (const path of paths) {
  const source = readFileSync(path, 'utf8');
  const label = path.pathname.includes('/recovered/') ? 'official recovery' : 'shipped macOS bundle';
  test(`${label}: guest always has two login entries regardless of clicks`, async () => {
    for (const clicks of [0, 999, 1000, 1999, 2000]) {
      const { api, context, loginEntries } = originalRules(source, { loggedIn: false, clicks });
      assert.equal(api.snapshot().left, true);
      assert.equal(api.snapshot().right, true);
      await api.open('left');
      await api.open('right');
      assert.equal(loginEntries(), 2);
      assert.equal(context.A.totalClickCount, clicks);
      assert.equal(context.Xo.value, 0);
      assert.equal(context.zo.value, 0);
    }
  });
  test(`${label}: logged-in visibility follows character balance and cooldowns`, () => {
    const cases = [
      [{ clicks: 999, always: true, hover: true }, [false, false]],
      [{ clicks: 1000 }, [true, false]],
      [{ clicks: 1999 }, [true, false]],
      [{ clicks: 1000, leftMs: 1000 }, [false, true]],
      [{ clicks: 1000, leftMs: 1000, rightMs: 1000 }, [false, false]],
      [{ clicks: 1000, leftMs: 1000, rightMs: 1000, hover: true }, [false, true]],
      [{ clicks: 2000 }, [true, true]],
      [{ clicks: 2000, leftMs: 1000 }, [false, true]],
      [{ clicks: 2000, leftMs: 1000, rightMs: 1000 }, [false, false]],
      [{ clicks: 2000, leftMs: 1000, rightMs: 1000, hover: true }, [true, true]],
      [{ clicks: 2000, leftMs: 1000, rightMs: 1000, always: true }, [true, true]],
    ];
    for (const [values, expected] of cases) {
      const state = originalRules(source, values).api.snapshot();
      assert.deepEqual([state.left, state.right], expected, JSON.stringify(values));
      assert.equal(state.actionable, (state.left && state.leftReady) || (state.right && state.rightReady));
    }
  });
  test(`${label}: thirty-minute per-slot cooldown and deadline boundaries`, () => {
    const { api, context } = originalRules(source);
    assert.equal(api.snapshot().duration, 1_800_000);
    assert.equal(api.snapshot().minimum, 1000);
    assert.equal(api.snapshot().twoSlots, 2000);
    api.cooldown('left', 1_800_000);
    assert.equal(context.Xo.value, 1_800_000);
    assert.equal(context.Yt.value, 0);
    assert.equal(context.Kt.value, 0);
    assert.equal(context.zo.value, 0);
    assert.equal(api.remaining(1_000_001), 1);
    assert.equal(api.remaining(1_000_000), 0);
    assert.equal(api.remaining(999_999), 0);
    for (const invalid of [undefined, null, -1, NaN, Infinity]) assert.equal(api.remaining(invalid), 0);
    assert.equal(api.format(api.seconds(1_800_000)), '30:00');
    assert.equal(api.format(api.seconds(1)), '00:01');
  });
}
