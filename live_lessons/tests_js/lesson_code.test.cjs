const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
function fixture() {
    class Element {
        constructor() { this.events = {}; this.dataset = {}; this.hidden = true; this.attrs = {}; }
        addEventListener(name, fn) { this.events[name] = fn; }
        removeEventListener(name) { delete this.events[name]; }
        setAttribute(name, value) { this.attrs[name] = value; }
        getAttribute(name) { return name === 'src' ? this.src || null : this.attrs[name] || null; }
        click() { this.events.click?.(); }
    }
    const elements = {}, messages = [], observers = [], events = {};
    for (const id of ['ll-room','ll-room-code-toggle','ll-room-code-close','ll-room-code','ll-room-code-frame']) elements[id] = new Element();
    elements['ll-room'].dataset.connected = 'false';
    elements['ll-room-code-frame'].dataset.src = '/interpreter/shared?embedded=1';
    elements['ll-room-code-frame'].contentWindow = {postMessage(message, origin) { messages.push({message, origin}); }};
    const document = {getElementById(id) { return elements[id] || null; },
        body: {classList: {contains() { return false; }}}, addEventListener(name, fn) { events[name] = fn; }};
    class Observer {
        constructor(fn) { this.fn = fn; observers.push(this); }
        observe() {} disconnect() { this.stopped = true; }
    }
    const window = {addEventListener(name, fn) { events[name] = fn; }};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/live_lessons/lesson_code.js'), 'utf8'),
        {document, window, MutationObserver: Observer, location: {origin: 'http://localhost'}});
    events.DOMContentLoaded();
    return {elements, messages, observers, events, connect(value) {
        elements['ll-room'].dataset.connected = String(value); observers[0].fn();
    }};
}
test('code button stays disabled until joining the media room', () => {
    const f = fixture(); assert.equal(f.elements['ll-room-code-toggle'].disabled, true);
    f.elements['ll-room-code-toggle'].click(); assert.equal(f.elements['ll-room-code'].hidden, true);
    f.connect(true); assert.equal(f.elements['ll-room-code-toggle'].disabled, false);
});
test('closing and reopening preserve the iframe and do not reconnect media', () => {
    const f = fixture(); f.connect(true); f.elements['ll-room-code-toggle'].click();
    assert.equal(f.elements['ll-room-code'].hidden, false);
    assert.equal(f.elements['ll-room-code-frame'].src, '/interpreter/shared?embedded=1');
    f.elements['ll-room-code-close'].click(); assert.equal(f.elements['ll-room-code'].hidden, true);
    f.elements['ll-room-code-toggle'].click(); assert.equal(f.elements['ll-room-code'].hidden, false);
    assert.equal(f.elements['ll-room-code-frame'].src, '/interpreter/shared?embedded=1');
});
test('leaving closes editor and immediately sends read-only connection state', () => {
    const f = fixture(); f.connect(true); f.elements['ll-room-code-toggle'].click(); f.connect(false);
    assert.equal(f.elements['ll-room-code'].hidden, true);
    assert.equal(f.elements['ll-room-code-toggle'].disabled, true);
    assert.equal(f.messages.at(-1).message.type, 'shared-code-connection');
    assert.equal(f.messages.at(-1).message.connected, false);
});
test('lesson state changes keep handlers; removing room disconnects observers', () => {
    const f = fixture(); f.events['ll-page-updated'](); assert.equal(f.observers.length, 2);
    delete f.elements['ll-room']; f.events['ll-page-updated'](); assert.equal(f.observers[0].stopped, true);
    assert.equal(f.elements['ll-room-code-toggle'].events.click, undefined);
});
