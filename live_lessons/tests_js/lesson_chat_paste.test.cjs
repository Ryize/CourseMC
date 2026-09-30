const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../static/live_lessons/lesson_chat.js'), 'utf8');

function chatFixture({ live = false } = {}) {
    const elements = new Map();
    const windowListeners = new Map();
    const makeElement = () => ({
        dataset: {}, files: [], hidden: false, value: '', textContent: '',
        scrollHeight: 0, scrollTop: 0, clientHeight: 0,
        listeners: {}, classList: { add() {} },
        addEventListener(type, callback) { this.listeners[type] = callback; },
        append() {}, appendChild() {}, prepend() {}, setAttribute() {},
        querySelector() { return this.label || (this.label = { textContent: 'Отправить' }); },
    });
    for (const id of [
        'll-chat', 'll-chat-messages', 'll-chat-older', 'll-chat-empty', 'll-chat-error',
        'll-chat-form', 'll-chat-body', 'll-chat-file', 'll-chat-selected-file',
        'll-chat-selected-row', 'll-chat-clear-file', 'll-chat-send', 'll-chat-count',
    ]) elements.set(id, makeElement());
    const root = elements.get('ll-chat');
    root.dataset = { live: String(live), userId: '1', messagesUrl: '/messages/', sendUrl: '/send/' };
    elements.get('ll-chat-form').querySelectorAll = () => [
        elements.get('ll-chat-body'), elements.get('ll-chat-file'), elements.get('ll-chat-send'),
    ];
    const fileInput = elements.get('ll-chat-file');
    fileInput.accept = '.png,.jpg,.pdf,.txt,.py';
    const selectedRow = elements.get('ll-chat-selected-row');
    selectedRow.hidden = true;
    const requests = [];
    class MockFormData {
        constructor() { this.values = new Map(); }
        set(key, file, name) { this.values.set(key, { file, name }); }
    }
    const context = {
        document: {
            hidden: false,
            getElementById: (id) => elements.get(id),
            createElement: makeElement,
            createDocumentFragment: makeElement,
            addEventListener() {},
        },
        window: { addEventListener(type, callback) { windowListeners.set(type, callback); },
            setInterval() {}, LivekitClient: { ConnectionState: { Connected: 'connected' } } },
        location: { href: 'http://localhost/' },
        URL, FormData: MockFormData, TextEncoder,
        fetch: async (url, options = {}) => {
            requests.push({ url, options });
            return {
                ok: true, headers: { get: () => 'application/json' },
                json: async () => options.method === 'POST' ? {
                    message: { id: 1, author: 'Ученик', author_id: 1,
                        created_at: '2026-09-29T12:00:00Z', body: '', attachment: null },
                } : { messages: [], has_more: false },
            };
        },
    };
    vm.runInNewContext(source, context);
    return { elements, requests, windowListeners };
}

test('live chat stays inactive until the media room is joined', async () => {
    const { elements, requests, windowListeners } = chatFixture({ live: true });
    assert.equal(elements.get('ll-chat-send').disabled, true);
    assert.equal(requests.length, 0);
    elements.get('ll-chat-form').listeners.submit({ preventDefault() {} });
    await new Promise(setImmediate);
    assert.equal(requests.length, 0);
    windowListeners.get('ll-livekit-room')({ detail: { room: { state: 'connected' } } });
    await new Promise(setImmediate);
    assert.equal(elements.get('ll-chat-send').disabled, false);
    assert.equal(requests.length, 1); // История загружается только после входа.
    windowListeners.get('ll-livekit-room')({ detail: { room: null } });
    assert.equal(elements.get('ll-chat-send').disabled, true);
});

function pasteEvent(clipboardData) {
    return {
        clipboardData, prevented: false,
        preventDefault() { this.prevented = true; },
    };
}

test('text paste remains native and does not attach a file', () => {
    const { elements } = chatFixture();
    const event = pasteEvent({ files: [], items: [{ kind: 'string' }] });
    elements.get('ll-chat-form').listeners.paste(event);
    assert.equal(event.prevented, false);
    assert.equal(elements.get('ll-chat-selected-row').hidden, true);
});

test('pasted image from clipboard items is sent as an attachment', async () => {
    const { elements, requests } = chatFixture();
    const file = { name: '', type: 'image/png', size: 1024 };
    const event = pasteEvent({ files: [], items: [{ kind: 'file', getAsFile: () => file }] });
    elements.get('ll-chat-form').listeners.paste(event);
    assert.equal(event.prevented, true);
    assert.equal(elements.get('ll-chat-selected-row').hidden, false);
    assert.match(elements.get('ll-chat-selected-file').textContent, /Вставленный файл\.png/);

    elements.get('ll-chat-form').listeners.submit({ preventDefault() {} });
    await new Promise(setImmediate);
    const payload = requests.find(({ options }) => options.method === 'POST').options.body;
    assert.deepEqual(payload.values.get('attachment'), { file, name: 'Вставленный файл.png' });
    assert.equal(elements.get('ll-chat-selected-row').hidden, true);
});

test('multiple, oversized and unsupported files are rejected before upload', () => {
    const { elements } = chatFixture();
    const form = elements.get('ll-chat-form');
    const image = { name: 'picture.png', type: 'image/png', size: 10 };
    const multiple = pasteEvent({ files: [image, image] });
    form.listeners.paste(multiple);
    assert.equal(multiple.prevented, true);
    assert.match(elements.get('ll-chat-error').textContent, /только один файл/);

    form.listeners.paste(pasteEvent({ files: [{ name: 'program.exe', type: '', size: 10 }] }));
    assert.match(elements.get('ll-chat-error').textContent, /не поддерживается/);
    form.listeners.paste(pasteEvent({ files: [{ ...image, size: 26 * 1024 * 1024 }] }));
    assert.match(elements.get('ll-chat-error').textContent, /25 МБ/);
    assert.equal(elements.get('ll-chat-selected-row').hidden, true);
});
