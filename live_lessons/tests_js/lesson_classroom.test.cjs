const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../static/live_lessons/lesson_classroom.js'), 'utf8');
const tick = () => new Promise(setImmediate);

function fixture({ teacher = true, waiting = [], admission = 'admitted' } = {}) {
    const elements = new Map();
    const timers = new Map();
    let timerId = 0;
    const requests = [];
    const events = [];
    let soundCount = 0;
    let audioContext = null;
    class Target {
        constructor() { this.listeners = new Map(); this.dataset = {}; this.children = []; this.hidden = false; this.disabled = false; this.textContent = ''; }
        addEventListener(type, callback) { if (!this.listeners.has(type)) this.listeners.set(type, new Set()); this.listeners.get(type).add(callback); }
        removeEventListener(type, callback) { this.listeners.get(type)?.delete(callback); }
        dispatchEvent(event) { for (const callback of this.listeners.get(event.type) || []) callback(event); }
        append(...children) { this.children.push(...children); }
        replaceChildren(...children) { this.children = children; }
        setAttribute(name, value) { this[name] = value; }
        click() { this.dispatchEvent({ type: 'click' }); }
    }
    const doc = new Target();
    doc.createElement = () => new Target();
    doc.getElementById = (id) => elements.get(id);
    for (const id of ['ll-room', 'll-live-page', 'll-waiting-banner', 'll-waiting-list', 'll-waiting-count',
        'll-waiting-sound', 'll-admission-status', 'll-waiting-cancel', 'll-classroom-notice', 'll-hands', 'll-hands-list',
        'll-connection-indicator', 'll-connection-label', 'll-connection-warning', 'll-connection-details',
        'll-room-settings', 'll-room-settings-toggle']) elements.set(id, new Target());
    const settings = ['microphone', 'screen', 'waiting_room', 'entry_locked'].map((setting) => {
        const node = new Target(); node.dataset.classroomSetting = setting; return node;
    });
    const muteAll = new Target(); muteAll.dataset.classroomAction = 'mute_all';
    const root = elements.get('ll-room');
    root.dataset = { teacher: String(teacher), classroomUrl: '/classroom/', classroomActionUrl: '/action/', classroomManageUrl: '/manage/' };
    root.querySelectorAll = (selector) => selector === '[data-classroom-setting]' ? settings : [muteAll];
    root.querySelector = () => ({ value: 'csrf' });
    elements.get('ll-live-page').dataset.teacher = String(teacher);
    let state = { teacher, active: true, settings: { microphone: true, screen: true, waiting_room: true, entry_locked: false },
        own: { identity: 'self', admission, hand_raised: false, entry_allowed: true }, waiting, hands: [] };
    const win = new Target();
    win.location = { href: 'http://localhost/lesson/' };
    win.navigator = { onLine: true };
    win.LivekitClient = { ConnectionState: { Connected: 'connected' } };
    win.setTimeout = (callback, delay) => { const id = ++timerId; timers.set(id, { callback, delay }); return id; };
    win.clearTimeout = (id) => timers.delete(id);
    class AudioContext {
        constructor() { this.state = 'suspended'; this.currentTime = 1; audioContext = this; }
        async resume() { this.state = 'running'; }
        createOscillator() { return { frequency: {}, connect() {}, disconnect() {}, start() { soundCount++; }, stop() {} }; }
        createGain() { return { gain: { setValueAtTime() {}, linearRampToValueAtTime() {}, exponentialRampToValueAtTime() {} }, connect() {}, disconnect() {} }; }
    }
    win.AudioContext = AudioContext;
    win.addEventListener('ll-classroom-state', ({ detail }) => events.push(detail.state));
    win.addEventListener('ll-wait-cancelled', () => events.push('cancelled'));
    let hold = null;
    const context = { window: win, document: doc, URL, AbortController, TextEncoder,
        Event: class { constructor(type) { this.type = type; } },
        CustomEvent: class { constructor(type, { detail }) { this.type = type; this.detail = detail; } },
        FormData: class { constructor() { this.values = new Map(); } set(key, value) { this.values.set(key, value); } },
        fetch: async (url, options) => {
            requests.push({ url: String(url), options });
            if (hold && !options.method) { const pending = hold; hold = null; await pending; }
            if (options.method === 'POST') {
                const action = options.body.values.get('action');
                if (['admit', 'deny'].includes(action)) state.waiting = state.waiting.filter((p) => p.identity !== options.body.values.get('identity'));
                if (action === 'cancel_wait') state.own.admission = 'left';
                if (action === 'raise_hand') state.own.hand_raised = true;
                if (action === 'lower_hand') state.own.hand_raised = false;
                if (Object.hasOwn(state.settings, action)) state.settings[action] = options.body.values.get('enabled') === 'true';
            }
            const data = options.method ? { ok: true } : JSON.parse(JSON.stringify(state));
            return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => data };
        },
    };
    vm.runInNewContext(source, context);
    return { elements, win, doc, settings, muteAll, requests, events, timers,
        soundCount: () => soundCount, audioContext: () => audioContext, state: () => state, setState: (value) => { state = value; },
        hold: (promise) => { hold = promise; } };
}

test('teacher sees top admission buttons; chime waits for gesture and sounds once per new request', async () => {
    const f = fixture({ waiting: [{ identity: 'p1', name: 'Ученик <script>', request: 'first' }] });
    await tick();
    assert.equal(f.elements.get('ll-waiting-banner').hidden, false);
    assert.equal(f.elements.get('ll-waiting-count').textContent, '1');
    const row = f.elements.get('ll-waiting-list').children[0];
    assert.equal(row.children[0].textContent, 'У');
    assert.equal(row.children[0]['aria-hidden'], 'true');
    assert.equal(row.children[1].textContent, 'Ученик <script> в комнате ожидания');
    assert.equal(row.children[2].textContent, 'Впустить');
    assert.match(row.children[2].className, /ll-waiting-admit/);
    assert.equal(row.children[3].textContent, '×');
    assert.equal(row.children[3]['aria-label'], 'Отклонить запрос: Ученик <script>');
    assert.equal(f.soundCount(), 0);
    assert.equal(f.elements.get('ll-waiting-sound').hidden, false);
    f.doc.dispatchEvent({ type: 'pointerdown' });
    await tick();
    assert.equal(f.soundCount(), 2);
    f.win.dispatchEvent({ type: 'll-classroom-refresh' });
    await tick();
    assert.equal(f.soundCount(), 2);
    f.state().waiting.push({ identity: 'p2', name: 'Другой', request: 'second' });
    f.win.dispatchEvent({ type: 'll-classroom-refresh' });
    await tick();
    assert.equal(f.soundCount(), 4);
    row.children[2].click();
    await tick();
    const post = f.requests.find((r) => r.options.method === 'POST');
    assert.equal(post.url, '/manage/');
    assert.equal(post.options.body.values.get('action'), 'admit');
    assert.equal(post.options.body.values.get('identity'), 'p1');
    assert.equal(post.options.headers['X-CSRFToken'], 'csrf');
    assert.equal(f.elements.get('ll-waiting-count').textContent, '1');
});

test('notification cross denies only the selected waiting participant', async () => {
    const f = fixture({ waiting: [
        { identity: 'p1', name: 'Первый', request: 'one' },
        { identity: 'p2', name: 'Второй', request: 'two' },
    ] });
    await tick();
    f.elements.get('ll-waiting-list').children[0].children[3].click();
    await tick();
    const post = f.requests.find((r) => r.options.method === 'POST');
    assert.equal(post.options.body.values.get('action'), 'deny');
    assert.equal(post.options.body.values.get('identity'), 'p1');
    assert.equal(f.elements.get('ll-waiting-count').textContent, '1');
    assert.equal(f.elements.get('ll-waiting-list').children[0].children[1].textContent, 'Второй в комнате ожидания');
});

test('waiting student can cancel and keeps a heartbeat in a background tab', async () => {
    const f = fixture({ teacher: false, admission: 'waiting' });
    await tick();
    assert.equal(f.elements.get('ll-waiting-cancel').hidden, false);
    assert.match(f.elements.get('ll-admission-status').textContent, /зале ожидания/);
    f.doc.hidden = true;
    f.doc.dispatchEvent({ type: 'visibilitychange' });
    assert.ok([...f.timers.values()].some((t) => t.delay === 10000));
    f.elements.get('ll-waiting-cancel').click();
    await tick();
    assert.equal(f.elements.get('ll-waiting-cancel').hidden, true);
    assert.ok(f.events.includes('cancelled'));
});

test('server refresh plays sound in hidden unfocused tab without running polling timers', async () => {
    const f = fixture();
    await tick();
    f.doc.dispatchEvent({ type: 'pointerdown' });
    await tick();
    f.doc.hidden = true;
    f.doc.hasFocus = () => false;
    f.audioContext().state = 'suspended';
    f.state().waiting.push({ identity: 'new', name: 'Ученик', request: 'background' });
    f.win.dispatchEvent({ type: 'll-classroom-refresh' });
    await tick();
    assert.equal(f.soundCount(), 2);
    assert.equal(f.elements.get('ll-waiting-banner').hidden, false);
    f.win.dispatchEvent({ type: 'll-classroom-refresh' });
    await tick();
    assert.equal(f.soundCount(), 2);
});

test('healthy connection does not show a connected notification', async () => {
    const f = fixture();
    await tick();
    f.win.dispatchEvent({ type: 'll-connection', detail: { state: 'connected', quality: 'excellent' } });
    assert.equal(f.elements.get('ll-connection-indicator').hidden, true);
    assert.equal(f.elements.get('ll-connection-warning').hidden, true);
    assert.match(f.elements.get('ll-connection-details').textContent, /Отличная связь/);
});

test('connected heartbeat and ordered hands expose teacher lower controls', async () => {
    const f = fixture();
    await tick();
    f.state().hands = [{ identity: 'p1', name: 'Первый' }, { identity: 'self', name: 'Вы' }];
    const room = { state: 'connected', localParticipant: { publishData: async () => {} } };
    f.win.dispatchEvent({ type: 'll-livekit-room', detail: { room } });
    await tick();
    assert.ok(f.requests.at(-1).url.includes('presence=connected'));
    const rows = f.elements.get('ll-hands-list').children;
    assert.equal(rows[0].children[0].textContent, '1. Первый');
    assert.equal(rows[1].children[0].textContent, '2. Вы');
    rows[0].children[1].click();
    await tick();
    const post = f.requests.find((r) => r.options.method === 'POST');
    assert.equal(post.options.body.values.get('action'), 'lower_hand');
    assert.equal(post.options.body.values.get('identity'), 'p1');
});

test('group setting posts an explicit value, refreshes and re-enables the control', async () => {
    const f = fixture();
    await tick();
    const input = f.settings[0];
    input.checked = false;
    input.dispatchEvent({ type: 'change' });
    assert.equal(input.disabled, true);
    await tick();
    const post = f.requests.find((r) => r.options.method === 'POST');
    assert.equal(post.options.body.values.get('action'), 'microphone');
    assert.equal(post.options.body.values.get('enabled'), 'false');
    assert.equal(input.disabled, false);
    assert.equal(input.checked, false);
});

test('poor network warning explains recovery and indicator opens settings', async () => {
    const f = fixture();
    await tick();
    f.win.dispatchEvent({ type: 'll-connection', detail: { state: 'connected', quality: 'poor' } });
    assert.equal(f.elements.get('ll-connection-label').textContent, 'Слабая связь');
    assert.equal(f.elements.get('ll-connection-warning').hidden, false);
    assert.match(f.elements.get('ll-connection-warning').textContent, /720p/);
    f.elements.get('ll-connection-indicator').click();
    assert.equal(f.elements.get('ll-room-settings').hidden, false);
    f.win.dispatchEvent({ type: 'll-connection', detail: { state: 'connected', quality: 'excellent' } });
    assert.equal(f.elements.get('ll-connection-warning').hidden, true);
    f.win.navigator.onLine = false;
    f.win.dispatchEvent({ type: 'offline' });
    assert.equal(f.elements.get('ll-connection-label').textContent, 'Нет сети');
});

test('page updates preserve controller for same root and dispose it on lesson end', async () => {
    const f = fixture();
    await tick();
    const count = f.requests.length;
    f.win.dispatchEvent({ type: 'll-page-updated' });
    await tick();
    assert.equal(f.requests.length, count);
    f.elements.delete('ll-room');
    f.win.dispatchEvent({ type: 'll-page-updated' });
    assert.equal(f.win.listeners.get('ll-classroom-refresh').size, 0);
    assert.equal(f.timers.size, 0);
});
