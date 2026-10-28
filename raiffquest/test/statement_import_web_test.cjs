// Exercise the actual JS bridge embedded in the Godot importer, without a browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { setImmediate: tick } = require('node:timers/promises');
const source = fs.readFileSync(path.join(__dirname, '../scripts/raiff/statement_import.gd'), 'utf8');
const bridge = source.match(/const JS_SETUP := """([\s\S]*?)"""/)[1];

function setup(fetchImpl) {
  const inputs = [], timers = new Map();
  let timerId = 0;
  const context = {
    window: { localStorage: { getItem() { throw new Error('blocked'); }, removeItem() {} } },
    document: {
      body: { appendChild() {} },
      createElement() {
        const input = { style: {}, files: [], listeners: {}, removed: false,
          addEventListener(name, callback) { this.listeners[name] = callback; },
          click() {}, remove() { this.removed = true; } };
        inputs.push(input); return input;
      },
    },
    AbortController,
    FormData: class { append() {} },
    setTimeout(callback) { timers.set(++timerId, callback); return timerId; },
    clearTimeout(id) { timers.delete(id); },
    fetch: fetchImpl,
  };
  vm.runInNewContext(bridge, context);
  return { app: context.window.raiffQuest, inputs, timers };
}

async function run() {
  let calls = 0;
  const good = setup(async () => { calls++; return { ok: true, json: async () => ({ game_profile: { cash: 500 } }) }; });
  assert.equal(good.app.takeStored('profile'), '', 'blocked browser storage must not crash boot');
  good.app.pick('.pdf', 1000);
  good.app.pick('.pdf', 1000);
  assert.equal(good.inputs.length, 1, 'one picker at a time');
  good.inputs[0].listeners.cancel();
  assert.equal(good.app.state, 'idle');
  assert.equal(good.inputs[0].removed, true);
  good.app.pick('.pdf', 1000);
  good.inputs[1].files = [{ size: 25 * 1024 * 1024 + 1 }];
  good.inputs[1].onchange();
  assert.equal(good.app.state, 'error');
  assert.equal(calls, 0, 'oversized file must not be uploaded');
  good.app.pick('.pdf', 1000);
  good.inputs[2].files = [{ size: 12 }];
  good.inputs[2].onchange();
  await tick();
  assert.equal(good.app.state, 'done');
  assert.equal(JSON.parse(good.app.result).game_profile.cash, 500);
  assert.equal(good.timers.size, 0);
  assert.equal(good.inputs[2].removed, true);

  const slow = setup((_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' })));
  }));
  slow.app.pick('.pdf', 1000);
  slow.inputs[0].files = [{ size: 12 }];
  slow.inputs[0].onchange();
  [...slow.timers.values()][0]();
  await tick();
  assert.equal(slow.app.state, 'error');
  assert.equal(slow.app.error, 'Serverul nu a răspuns la timp.');
  assert.equal(slow.timers.size, 0);
  assert.equal(slow.inputs[0].removed, true);
  console.log('[statement-import-web] PASS: storage, picker, size limit, upload, timeout, cleanup');
}
run().catch(error => { console.error(error); process.exitCode = 1; });
