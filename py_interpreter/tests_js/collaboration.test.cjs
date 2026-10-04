const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const {SharedClient, Binding, replacement, toBase64, fromBase64} = require('../static/py_interpreter/collaboration.js');
const runtime = {TextEncoder, TextDecoder, crypto: require('node:crypto').webcrypto,
    setTimeout, clearTimeout, setInterval, clearInterval, console, Uint8Array, ArrayBuffer,
    Map, Set}; vm.createContext(runtime);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/py_interpreter/vendor/yjs.js'), 'utf8'), runtime);
const Y = runtime.CourseCodeY;

function apiFixture() {
    const events = {};
    const input = {value: '', selectionStart: 0, selectionEnd: 0,
        addEventListener(name, callback) { events[name] = callback; }, removeEventListener() {},
        setSelectionRange(start, end) { this.selectionStart = start; this.selectionEnd = end; }};
    return {editor: null, codeInput: input, editable: false,
        getCode() { return input.value; }, setCode(value) { input.value = value; }, updatePosition() {},
        setEditable(value) { this.editable = value; }, type(value) { input.value = value; events.input(); }};
}
function clientFixture() {
    const nodes = {};
    global.document = {getElementById(id) { return nodes[id] ||= {textContent: '', hidden: true}; }};
    const api = apiFixture(), client = new SharedClient(Y, {dataset: {syncUrl: '/sync'}}, api);
    client.render = () => {};
    const server = new Y.Doc(); server.getText('code').insert(0, 'print(1)\n');
    client.post = async (_url, data) => {
        if (data.update) Y.applyUpdate(server, fromBase64(data.update));
        return {update: toBase64(Y.encodeStateAsUpdate(server, fromBase64(data.vector))),
            vector: toBase64(Y.encodeStateVector(server)), identity: 'teacher', can_edit: true,
            active: true, people: [], members: [], snapshots: []};
    };
    return {client, api, server};
}

test('text replacement handles non-BMP characters without corrupting UTF-16', () => {
    const patch = replacement('a🐱b', 'a🐶b');
    assert.equal(patch.start, 1); assert.equal(patch.remove, 2); assert.equal(patch.insert, '🐶');
});
test('two real Yjs documents merge simultaneous edits, replay is harmless', () => {
    const initial = new Y.Doc(); initial.getText('code').insert(0, 'print(1)\n');
    const a = new Y.Doc(), b = new Y.Doc(), state = Y.encodeStateAsUpdate(initial);
    Y.applyUpdate(a, state); Y.applyUpdate(b, state);
    a.getText('code').insert(0, '# учитель\n'); b.getText('code').insert(0, '# ученик🐱\n');
    const updateA = Y.encodeStateAsUpdate(a), updateB = Y.encodeStateAsUpdate(b);
    Y.applyUpdate(a, updateB); Y.applyUpdate(b, updateA); Y.applyUpdate(b, updateA);
    assert.equal(a.getText('code').toString(), b.getText('code').toString());
    assert.match(a.getText('code').toString(), /учитель/); assert.match(a.getText('code').toString(), /ученик🐱/);
});
test('own undo keeps a remote participant change', () => {
    const doc = new Y.Doc(), api = apiFixture(); doc.getText('code').insert(0, 'abc');
    const binding = new Binding(Y, doc, api, () => true, () => {});
    api.type('abcD'); doc.transact(() => doc.getText('code').insert(0, 'R'), 'server');
    binding.undo.undo();
    assert.equal(doc.getText('code').toString(), 'Rabc'); assert.equal(api.getCode(), 'Rabc');
    binding.destroy(); doc.destroy();
});
test('read-only editor rejects local changes, server update still displayed', () => {
    const doc = new Y.Doc(), api = apiFixture(); doc.getText('code').insert(0, 'abc');
    const binding = new Binding(Y, doc, api, () => false, () => {});
    api.type('forbidden'); assert.equal(api.getCode(), 'abc');
    doc.transact(() => doc.getText('code').insert(0, 'R'), 'server');
    assert.equal(api.getCode(), 'Rabc'); binding.destroy(); doc.destroy();
});
test('relative cursor follows insertion before the cursor', () => {
    const doc = new Y.Doc(), api = apiFixture(); doc.getText('code').insert(0, 'abc');
    const binding = new Binding(Y, doc, api, () => true, () => {});
    api.codeInput.setSelectionRange(2, 2);
    const selection = binding.selection(); doc.getText('code').insert(0, '🐱'); binding.restore(selection);
    assert.equal(api.codeInput.selectionStart, 4); binding.destroy(); doc.destroy();
});
test('new edit while a request is in flight is not removed from the outbox', async () => {
    const {client, api, server} = clientFixture(); await client.sync();
    api.type('print(12)\n');
    const normalPost = client.post; let resolve;
    client.post = (...args) => new Promise((done) => { resolve = () => normalPost(...args).then(done); });
    const sync = client.sync(); api.type('print(123)\n'); resolve(); await sync;
    assert.equal(client.pending.length, 1); client.post = normalPost; await client.sync();
    assert.equal(server.getText('code').toString(), 'print(123)\n'); client.close(); server.destroy();
});
test('failed response keeps update, retry after server accepted it does not duplicate text', async () => {
    const {client, api, server} = clientFixture(); await client.sync(); api.type('# hi\nprint(1)\n');
    const normalPost = client.post;
    client.post = async (...args) => { await normalPost(...args); throw new Error('offline'); };
    await client.sync(); assert.equal(client.pending.length, 1); assert.equal(api.editable, false);
    client.post = normalPost; await client.sync();
    assert.equal(client.pending.length, 0); assert.equal(server.getText('code').toString(), '# hi\nprint(1)\n');
    client.close(); server.destroy();
});
test('revoked access retains a downloadable recovery and rejoins canonical state', async () => {
    const {client, api, server} = clientFixture(); await client.sync(); api.type('unsaved');
    const normalPost = client.post;
    client.post = async () => { const error = new Error('read only'); error.status = 403; throw error; };
    await client.sync(); assert.equal(client.recovery, 'unsaved'); assert.equal(client.pending.length, 0);
    client.post = normalPost; await client.sync(); assert.equal(api.getCode(), 'print(1)\n');
    client.close(); server.destroy();
});

test('publishing flushes pending code before posting the target lesson', async () => {
    const {client, api, server} = clientFixture(); await client.sync();
    client.root.dataset.publishUrl = '/publish';
    api.type('# latest\nprint(1)\n');
    const normalPost = client.post, calls = [];
    client.post = async (url, data) => {
        calls.push(url);
        if (url === '/publish') {
            assert.equal(server.getText('code').toString(), api.getCode());
            assert.deepEqual(data, {title: 'Функции', code_target: '410:1'});
            return {ok: true};
        }
        return normalPost(url, data);
    };
    assert.deepEqual(await client.publish('Функции', '410:1'), {ok: true});
    assert.deepEqual(calls, ['/sync', '/publish']);
    client.close(); server.destroy();
});

test('publishing is not attempted if synchronization failed', async () => {
    const {client, api, server} = clientFixture(); await client.sync();
    client.root.dataset.publishUrl = '/publish'; api.type('unsaved code');
    const calls = [];
    client.post = async (url) => { calls.push(url); throw new Error('offline'); };
    await assert.rejects(client.publish('Пример', '410:1'), /дождитесь сохранения/);
    assert.deepEqual(calls, ['/sync']);
    assert.equal(client.pending.length, 1);
    client.close(); server.destroy();
});

test('saving a call version continues to use the version API, not publication', async () => {
    const {client, server} = clientFixture(); await client.sync();
    client.root.dataset.manageUrl = '/manage';
    const normalPost = client.post;
    client.post = async (url, data) => {
        if (url === '/manage') { assert.deepEqual(data, {action: 'save', title: 'Версия'}); return {ok: true}; }
        return normalPost(url, data);
    };
    assert.deepEqual(await client.save('Версия'), {ok: true});
    client.close(); server.destroy();
});
