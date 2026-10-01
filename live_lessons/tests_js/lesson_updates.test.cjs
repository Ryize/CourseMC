const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../static/live_lessons/lesson_updates.js'), 'utf8');
const flush = async () => { await new Promise(setImmediate); await new Promise(setImmediate); };

function fixture({ kind = 'detail', status = 'scheduled', room = false } = {}) {
    const elements = new Map();
    const timers = new Map();
    const listeners = new Map();
    const events = [];
    const requests = [];
    let nextId = 0;
    let state = { revision: 'v1', status, can_join: status === 'live', removed: false };
    let errorStatus = 0;
    let hold = null;
    const element = () => ({
        dataset: {}, hidden: false, textContent: '', listeners: new Map(), fields: [],
        html: '', replacements: 0, querySelectorAll() { return this.fields; },
        addEventListener(type, callback) { this.listeners.set(type, callback); },
        closest() { return this; }, contains() { return true; },
        replaceChildren() { this.innerHTML = ''; },
        get innerHTML() { return this.html; },
        set innerHTML(value) {
            this.html = value;
            this.replacements += 1;
            if (this === elements.get('ll-lesson-room')) {
                if (value) elements.set('ll-room', element()); else elements.delete('ll-room');
            }
        },
    });
    for (const id of ['ll-live-page', 'll-updates-notice', 'll-lesson-before', 'll-lesson-after',
        'll-lesson-room', 'll-lesson-list-content']) elements.set(id, element());
    if (room) elements.set('ll-room', element());
    const root = elements.get('ll-live-page');
    root.dataset = { updatesKind: kind, revision: state.revision, status, stateUrl: '/state/' };
    const main = { classes: new Set(), classList: { toggle(name, active) {
        if (active) main.classes.add(name); else main.classes.delete(name);
    } } };
    root.closest = () => main;
    const document = {
        hidden: false, activeElement: null, getElementById: (id) => elements.get(id),
        addEventListener(type, callback) { listeners.set(`document:${type}`, callback); },
    };
    const navigator = { onLine: true };
    const addListener = (type, callback) => {
        if (!listeners.has(type)) listeners.set(type, []);
        listeners.get(type).push(callback);
    };
    const dispatch = (event) => {
        events.push(event);
        for (const callback of listeners.get(event.type) || []) callback(event);
    };
    const window = {
        addEventListener: addListener, dispatchEvent: dispatch,
        setTimeout(callback, delay) { const id = ++nextId; timers.set(id, { callback, delay }); return id; },
        clearTimeout(id) { timers.delete(id); },
    };
    const context = {
        window, document, navigator, URL, AbortController, location: { href: 'https://example.test/live-lessons/lesson/' },
        FormData: class { constructor(form) { this.form = form; } },
        Event: class { constructor(type) { this.type = type; } },
        CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
        fetch: async (target, options = {}) => {
            const url = new URL(target, 'https://example.test');
            requests.push({ url, options });
            if (hold && url.pathname === '/state/') await hold;
            const currentError = errorStatus;
            let data;
            if (options.method === 'POST' && !currentError) {
                state = { ...state, revision: 'v2', status: 'live', can_join: true };
                data = { ok: true };
            } else if (url.pathname === '/state/') data = { ...state };
            else if (kind === 'list') data = {
                revision: state.revision, changed: url.searchParams.get('revision') !== state.revision,
                html: `list:${state.revision}`,
            };
            else data = {
                state: { ...state }, before_html: `before:${state.status}`, after_html: `after:${state.status}`,
                room_html: state.can_join && url.searchParams.get('room') === '1' ? '<section id="ll-room"></section>' : null,
            };
            return { ok: !currentError, status: currentError || 200, redirected: false,
                headers: { get: () => 'application/json' }, json: async () => data };
        },
    };
    vm.runInNewContext(source, context);
    const poll = async () => {
        const entry = [...timers].find(([, timer]) => timer.delay !== 10000);
        assert.ok(entry, 'poll timer is scheduled');
        timers.delete(entry[0]);
        entry[1].callback();
        await flush();
    };
    return {
        elements, root, main, document, navigator, requests, events, timers, listeners, poll, window,
        setState: (next) => { state = { ...state, ...next }; },
        setError: (code) => { errorStatus = code; }, setHold: (promise) => { hold = promise; },
    };
}

test('waiting page checks state and reveals the room after start, without navigation or autojoin', async () => {
    const f = fixture();
    await flush();
    assert.equal(f.requests.length, 1);
    assert.equal(f.requests[0].url.pathname, '/state/');
    assert.equal(f.elements.has('ll-room'), false);
    assert.equal([...f.timers.values()][0].delay, 3000);
    f.setState({ revision: 'v2', status: 'live', can_join: true });
    await f.poll();
    assert.equal(f.elements.has('ll-room'), true);
    assert.ok(f.main.classes.has('ll-shell-live'));
    assert.equal(f.root.dataset.status, 'live');
    assert.ok(f.events.some((event) => event.type === 'll-page-updated'));
    assert.ok(f.requests.every(({ options }) => !options.method));
    assert.equal(f.requests.at(-1).url.searchParams.get('room'), '1');
});

test('unchanged state does not fetch HTML or replace the room', async () => {
    const f = fixture({ status: 'live', room: true });
    const originalRoom = f.elements.get('ll-room');
    await flush();
    await f.poll();
    assert.equal(f.requests.length, 2);
    assert.ok(f.requests.every(({ url }) => url.pathname === '/state/'));
    assert.equal(f.elements.get('ll-room'), originalRoom);
    assert.equal(f.elements.get('ll-lesson-room').replacements, 0);
});

test('changing controls during a call preserves the exact media DOM and selected lesson', async () => {
    const f = fixture({ status: 'live', room: true });
    const originalRoom = f.elements.get('ll-room');
    const select = { name: 'target', tagName: 'SELECT', value: 'group:lesson', checked: false,
        options: [{ value: 'group:lesson' }], focus() { this.focused = true; } };
    f.elements.get('ll-lesson-after').fields = [select];
    f.document.activeElement = select;
    await flush();
    f.setState({ revision: 'v2' });
    await f.poll();
    assert.equal(f.elements.get('ll-room'), originalRoom);
    assert.equal(f.elements.get('ll-lesson-room').replacements, 0);
    assert.equal(f.requests.at(-1).url.searchParams.has('room'), false);
    assert.equal(select.value, 'group:lesson');
    assert.equal(select.focused, true);
});

test('closing lesson waits for media disconnect and then switches to ended history', async () => {
    const f = fixture({ status: 'live', room: true });
    await flush();
    let disconnect;
    const finished = new Promise((resolve) => { disconnect = resolve; });
    f.window.addEventListener('ll-lesson-state', (event) => {
        if (!event.detail.state.can_join) event.detail.waitUntil(finished);
    });
    f.setState({ revision: 'v2', status: 'ended', can_join: false });
    await f.poll();
    assert.equal(f.elements.has('ll-room'), true);
    disconnect();
    await flush();
    assert.equal(f.elements.has('ll-room'), false);
    assert.equal(f.elements.get('ll-lesson-after').html, 'after:ended');
    assert.equal(f.main.classes.has('ll-shell-live'), false);
});

test('teacher action is posted once and immediately refreshes controls, without page reload', async () => {
    const f = fixture();
    await flush();
    const button = { disabled: false };
    f.root.fields = [button];
    const form = { action: 'https://example.test/start/', closest() { return this; } };
    let prevented = false;
    const submit = f.root.listeners.get('submit');
    const action = submit({ target: form, preventDefault() { prevented = true; } });
    assert.equal(button.disabled, true);
    await submit({ target: form, preventDefault() {} });
    await action;
    assert.equal(prevented, true);
    assert.equal(button.disabled, false);
    assert.equal(f.requests.filter(({ options }) => options.method === 'POST').length, 1);
    assert.equal(f.root.dataset.status, 'live');
    assert.equal(f.elements.has('ll-room'), true);
});

test('list refresh returns only changes and reflects new lessons and status', async () => {
    const f = fixture({ kind: 'list' });
    await flush();
    const slot = f.elements.get('ll-lesson-list-content');
    assert.equal(slot.replacements, 0);
    f.setState({ revision: 'v2' });
    await f.poll();
    assert.equal(slot.html, 'list:v2');
    await f.poll();
    assert.equal(slot.replacements, 1);
});

test('hidden and offline tabs stop polling; returning to the tab checks immediately', async () => {
    const f = fixture();
    await flush();
    f.document.hidden = true;
    f.listeners.get('document:visibilitychange')();
    assert.equal(f.timers.size, 0);
    f.document.hidden = false;
    f.listeners.get('document:visibilitychange')();
    await flush();
    assert.equal(f.requests.length, 2);
    f.navigator.onLine = false;
    f.listeners.get('offline')[0]();
    assert.equal(f.timers.size, 0);
    f.navigator.onLine = true;
    f.listeners.get('online')[0]();
    await flush();
    assert.equal(f.requests.length, 3);
});

test('network failures back off and recover without duplicate requests or manual refresh', async () => {
    const f = fixture();
    await flush();
    f.setError(503);
    await f.poll();
    assert.equal([...f.timers.values()][0].delay, 6000);
    await f.poll();
    await f.poll();
    assert.equal(f.elements.get('ll-updates-notice').hidden, false);
    f.setError(0);
    let release;
    f.setHold(new Promise((resolve) => { release = resolve; }));
    await f.poll();
    const before = f.requests.length;
    f.listeners.get('online')[0]();
    f.listeners.get('document:visibilitychange')();
    assert.equal(f.requests.length, before);
    release();
    await flush();
    assert.equal(f.elements.get('ll-updates-notice').hidden, true);
    assert.equal([...f.timers.values()][0].delay, 3000);
});

test('revoked access closes the call, stops polling and never inserts login HTML', async () => {
    const f = fixture({ status: 'live', room: true });
    await flush();
    f.setError(404);
    await f.poll();
    assert.ok(f.events.some((event) => event.detail?.state.status === 'unavailable'));
    assert.equal(f.elements.get('ll-lesson-after').replacements, 0);
    assert.equal(f.timers.size, 0);
    assert.match(f.elements.get('ll-updates-notice').textContent, /Доступ/);
});

test('cached page suspends polling on pagehide and resumes on pageshow', async () => {
    const f = fixture();
    await flush();
    f.listeners.get('pagehide')[0]();
    assert.equal(f.timers.size, 0);
    f.listeners.get('online')[0]();
    await flush();
    assert.equal(f.requests.length, 1);
    f.listeners.get('pageshow')[0]();
    await flush();
    assert.equal(f.requests.length, 2);
    assert.equal([...f.timers.values()][0].delay, 3000);
});

test('an active background call keeps checking closure; leaving it suspends hidden polling', async () => {
    const f = fixture({ status: 'live', room: true });
    await flush();
    f.listeners.get('ll-livekit-room')[0]({ detail: { room: {} } });
    f.document.hidden = true;
    f.listeners.get('document:visibilitychange')();
    assert.equal([...f.timers.values()][0].delay, 15000);
    await f.poll();
    assert.equal(f.requests.length, 2);
    f.listeners.get('ll-livekit-room')[0]({ detail: { room: null } });
    assert.equal(f.timers.size, 0);
});
