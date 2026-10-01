const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../static/live_lessons/lesson_devices.js'), 'utf8');
const flush = () => new Promise(setImmediate);

function fixture({ supportsOutput = true, saved = {} } = {}) {
    const elements = new Map(), windowEvents = new Map(), documentEvents = new Map(), mediaEvents = new Map();
    const storage = new Map([['coursemc:live-room-devices:v1', JSON.stringify(saved)]]);
    const captures = [], streams = [], contexts = [], frames = new Map(), urls = new Set();
    let frameId = 0;
    const doc = { activeElement: null, getElementById: (id) => elements.get(id),
        addEventListener(type, callback) { documentEvents.set(type, callback); },
        removeEventListener(type) { documentEvents.delete(type); } };
    function element() {
        return { hidden: false, disabled: false, dataset: {}, textContent: '', value: '', options: [],
            style: {}, attributes: new Map(), listeners: new Map(), paused: true,
            addEventListener(type, callback) { this.listeners.set(type, callback); },
            removeEventListener(type) { this.listeners.delete(type); },
            setAttribute(name, value) { this.attributes.set(name, value); },
            removeAttribute(name) { this.attributes.delete(name); if (name === 'src') this.src = ''; },
            getAttribute(name) { return this.attributes.get(name); },
            replaceChildren(...items) { this.options = items; },
            add(option) { this.options.push(option); },
            focus() { doc.activeElement = this; },
            async play() { this.paused = false; }, pause() { this.paused = true; }, load() {},
        };
    }
    for (const id of ['ll-room', 'll-device-check', 'll-device-open', 'll-device-close', 'll-device-done',
        'll-device-camera-test', 'll-device-mic-test', 'll-device-speaker-test', 'll-device-video',
        'll-device-placeholder', 'll-device-meter', 'll-device-level', 'll-device-mic-hint',
        'll-device-status', 'll-device-test-audio', 'll-device-mic-select', 'll-room-audio-input',
        'll-device-camera-select', 'll-room-video-input', 'll-device-speaker-select', 'll-room-audio-output',
        'll-device-output-help', 'll-room-output-help', 'll-room-speaker-volume']) elements.set(id, element());
    elements.get('ll-device-check').hidden = true;
    elements.get('ll-room').isConnected = true;
    elements.get('ll-room-speaker-volume').value = '75';
    if (supportsOutput) elements.get('ll-device-test-audio').setSinkId = async function (id) { this.sinkId = id; };
    const devices = [
        { kind: 'audioinput', deviceId: 'mic-1', label: 'Микрофон 1' },
        { kind: 'audioinput', deviceId: 'mic-2', label: 'Микрофон 2' },
        { kind: 'videoinput', deviceId: 'cam-1', label: 'Камера 1' },
        { kind: 'audiooutput', deviceId: 'speaker-1', label: 'Динамики 1' },
    ];
    function makeStream() {
        const track = { stopped: false, listeners: new Map(), stop() { this.stopped = true; },
            addEventListener(type, fn) { this.listeners.set(type, fn); } };
        const stream = { getTracks: () => [track], track }; streams.push(stream); return stream;
    }
    const media = { enumerateDevices: async () => devices,
        getUserMedia: async (options) => { captures.push(options); return makeStream(); },
        addEventListener(type, fn) { mediaEvents.set(type, fn); },
        removeEventListener(type) { mediaEvents.delete(type); } };
    function audioNode() { return { connections: [], connect(to) { this.connections.push(to); }, disconnect() { this.disconnected = true; } }; }
    class AudioContext {
        constructor() { contexts.push(this); this.destination = {}; }
        createMediaStreamSource() { return this.source = audioNode(); }
        createAnalyser() { const node = audioNode(); node.getFloatTimeDomainData = (array) => array.fill(.1); return this.analyser = node; }
        createGain() { const node = audioNode(); node.gain = { value: 1 }; return this.gain = node; }
        async resume() {} async close() { this.closed = true; }
    }
    const win = { navigator: { mediaDevices: media }, AudioContext,
        localStorage: { getItem: (key) => storage.get(key), setItem: (key, value) => storage.set(key, value) },
        addEventListener(type, fn) { windowEvents.set(type, fn); }, removeEventListener(type) { windowEvents.delete(type); },
        requestAnimationFrame(fn) { const id = ++frameId; frames.set(id, fn); return id; },
        cancelAnimationFrame(id) { frames.delete(id); }, setTimeout: (fn) => fn(),
    };
    const context = { window: win, document: doc, Blob,
        URL: { createObjectURL() { const url = `blob:${urls.size}`; urls.add(url); return url; }, revokeObjectURL(url) { urls.delete(url); } },
        Option: class { constructor(label, value) { this.label = label; this.value = value; } },
    };
    vm.runInNewContext(source, context);
    return { elements, media, devices, captures, streams, contexts, frames, urls, storage, context, doc,
        documentEvents, windowEvents, makeStream, click: (id) => elements.get(id).listeners.get('click')(),
        open() { this.click('ll-device-open'); }, close() { this.click('ll-device-close'); } };
}

test('preflight only lists devices until a user explicitly starts an individual test', async () => {
    const f = fixture();
    assert.equal(f.captures.length, 0);
    f.open(); await flush();
    assert.equal(f.captures.length, 0);
    assert.equal(f.elements.get('ll-device-mic-select').options.length, 3);
    f.click('ll-device-camera-test'); await flush();
    assert.equal(f.captures.length, 1);
    assert.equal(f.captures[0].audio, false);
    assert.equal(f.elements.get('ll-device-video').srcObject, f.streams[0]);
    assert.equal(f.elements.get('ll-device-camera-test').getAttribute('aria-pressed'), 'true');
    f.close();
    assert.equal(f.streams[0].track.stopped, true);
    assert.equal(f.elements.get('ll-device-video').srcObject, null);
    assert.equal(f.doc.activeElement, f.elements.get('ll-device-open'));
});

test('microphone meter measures captured audio but never feeds audible sound to speakers', async () => {
    const f = fixture(); f.open();
    f.click('ll-device-mic-test'); await flush();
    assert.equal(f.captures[0].video, false);
    assert.equal(f.elements.get('ll-device-meter').getAttribute('aria-valuenow'), '35');
    assert.equal(f.contexts[0].gain.gain.value, 0);
    assert.equal(f.frames.size, 1);
    f.windowEvents.get('ll-prejoin-close')();
    assert.equal(f.streams[0].track.stopped, true);
    assert.equal(f.contexts[0].closed, true);
    assert.equal(f.contexts[0].source.disconnected, true);
    assert.equal(f.frames.size, 0);
    assert.equal(f.elements.get('ll-device-check').hidden, true);
});

test('closing during permission request stops a late stream and does not reopen preview', async () => {
    const f = fixture(); let resolve;
    f.media.getUserMedia = () => new Promise((done) => { resolve = done; });
    f.open(); f.click('ll-device-camera-test');
    f.close();
    const stream = f.makeStream(); resolve(stream); await flush();
    assert.equal(stream.track.stopped, true);
    assert.equal(f.elements.get('ll-device-check').hidden, true);
    assert.equal(f.elements.get('ll-device-video').srcObject, null);
});

test('permission denial is recoverable and does not disable the next test', async () => {
    const f = fixture();
    f.media.getUserMedia = async () => { throw Object.assign(new Error('denied'), { name: 'NotAllowedError' }); };
    f.open(); f.click('ll-device-mic-test'); await flush();
    assert.match(f.elements.get('ll-device-status').textContent, /Доступ не разрешён/);
    assert.equal(f.elements.get('ll-device-mic-test').disabled, false);
    f.media.getUserMedia = async () => f.makeStream();
    f.click('ll-device-mic-test'); await flush();
    assert.equal(f.elements.get('ll-device-mic-test').getAttribute('aria-pressed'), 'true');
    f.close();
});

test('device selection is remembered and switching during preview releases the old device', async () => {
    const f = fixture({ saved: { videoinput: 'cam-1' } }); f.open(); await flush();
    f.click('ll-device-mic-test'); await flush();
    const select = f.elements.get('ll-device-mic-select'); select.value = 'mic-2';
    select.listeners.get('change')(); await flush();
    assert.equal(f.streams[0].track.stopped, true);
    assert.equal(f.captures[1].audio.deviceId.exact, 'mic-2');
    assert.equal(f.elements.get('ll-room-audio-input').value, 'mic-2');
    assert.equal(JSON.parse(f.storage.get('coursemc:live-room-devices:v1')).audioinput, 'mic-2');
    assert.equal(f.elements.get('ll-device-camera-select').value, 'cam-1');
    f.close();
});

test('speaker check uses selected output and frees the test sound when closed', async () => {
    const f = fixture({ saved: { audiooutput: 'speaker-1' } }); f.open(); await flush();
    await f.click('ll-device-speaker-test');
    const audio = f.elements.get('ll-device-test-audio');
    assert.equal(audio.sinkId, 'speaker-1'); assert.equal(audio.volume, .75);
    assert.equal(audio.paused, false); assert.equal(f.urls.size, 1);
    assert.equal(f.captures.length, 0);
    f.close(); assert.equal(audio.paused, true); assert.equal(f.urls.size, 0);
});

test('browsers without output selection still offer speaker test and explain system fallback', async () => {
    const f = fixture({ supportsOutput: false, saved: { audiooutput: 'speaker-1' } }); f.open(); await flush();
    assert.equal(f.elements.get('ll-device-speaker-select').disabled, true);
    assert.equal(f.elements.get('ll-device-speaker-select').value, '');
    assert.match(f.elements.get('ll-device-output-help').textContent, /системные динамики/);
    await f.click('ll-device-speaker-test');
    assert.equal(f.elements.get('ll-device-test-audio').paused, false); f.close();
});

test('page removal, pagehide and same-root updates do not leak or recreate device tests', async () => {
    for (const event of ['pagehide', 'll-page-updated']) {
        const f = fixture(); f.open(); f.click('ll-device-camera-test'); await flush();
        const handler = f.elements.get('ll-device-camera-test').listeners.get('click');
        f.windowEvents.get('ll-page-updated')();
        assert.equal(f.elements.get('ll-device-camera-test').listeners.get('click'), handler);
        assert.equal(f.streams[0].track.stopped, false);
        if (event === 'll-page-updated') f.elements.delete('ll-room');
        f.windowEvents.get(event)();
        assert.equal(f.streams[0].track.stopped, true);
    }
});
