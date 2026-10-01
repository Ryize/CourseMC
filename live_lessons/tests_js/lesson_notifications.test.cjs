const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../static/live_lessons/lesson_notifications.js'), 'utf8');

function fixture() {
    const observers = [], timers = new Map(), events = new Map();
    const owner = { isConnected: true };
    let nextTimer = 0;
    class Node {
        constructor() { this.children = []; this.dataset = {}; this.textContent = ''; this.hidden = false; this.events = new Map(); }
        append(...nodes) {
            for (const node of nodes) { node.remove(); node.parent = this; this.children.push(node); }
        }
        remove() { if (this.parent) this.parent.children = this.parent.children.filter((n) => n !== this); this.parent = null; }
        setAttribute(key, value) { this[key] = value; }
        addEventListener(type, callback) { this.events.set(type, callback); }
        closest() { return owner; }
    }
    const body = new Node();
    const error = new Node(); error.dataset = { llNotice: '', noticeKind: 'error' }; error.hidden = true;
    body.append(error);
    const doc = { body, createElement: () => new Node(),
        addEventListener: (type, callback) => events.set(type, callback),
        querySelectorAll() {
            const result = [];
            function visit(node) { if (Object.hasOwn(node.dataset, 'llNotice')) result.push(node); node.children.forEach(visit); }
            visit(body);
            if (doc.fullscreenElement) visit(doc.fullscreenElement);
            return result;
        },
    };
    const win = { setTimeout: (callback, ms) => { const id = ++nextTimer; timers.set(id, { callback, ms }); return id; },
        clearTimeout: (id) => timers.delete(id), addEventListener: (type, callback) => events.set(type, callback) };
    class Observer {
        constructor(callback) { this.callback = callback; observers.push(this); }
        observe() { this.connected = true; }
        disconnect() { this.connected = false; }
    }
    vm.runInNewContext(source, { document: doc, window: win, MutationObserver: Observer });
    const stack = body.children.find((n) => n.className === 'll-notification-stack');
    return { doc, body, error, owner, stack, events, timers, Node,
        sync: () => observers.filter((o) => o.connected).forEach((o) => o.callback()) };
}

test('notices leave page flow, preserve the original node and can be dismissed', () => {
    const f = fixture(), toast = f.stack.children[0];
    assert.equal(toast.hidden, true);
    assert.equal(toast.children[0], f.error);
    f.error.textContent = 'Ошибка'; f.error.hidden = false; f.sync();
    assert.equal(toast.hidden, false);
    assert.equal(toast.dataset.kind, 'error');
    assert.ok([...f.timers.values()].some((t) => t.ms === 10000));
    toast.children[1].events.get('click')();
    f.sync();
    assert.equal(toast.hidden, true);
    f.error.hidden = true; f.sync();
    f.error.hidden = false; f.sync();
    assert.equal(toast.hidden, false);
});

test('fullscreen keeps notices in the fullscreen subtree and restores them on exit', () => {
    const f = fixture();
    const fullscreen = new f.Node();
    f.doc.fullscreenElement = fullscreen;
    f.events.get('fullscreenchange')();
    assert.equal(f.stack.parent, fullscreen);
    f.doc.fullscreenElement = null;
    f.events.get('fullscreenchange')();
    assert.equal(f.stack.parent, f.body);
});

test('ending a lesson removes detached room notices and their timers', () => {
    const f = fixture();
    f.error.textContent = 'Ошибка'; f.error.hidden = false; f.sync();
    f.owner.isConnected = false;
    f.events.get('ll-page-updated')();
    assert.equal(f.stack.children.length, 0);
    assert.equal(f.timers.size, 0);
});

test('persistent network warning stays visible without a dismissal timer', () => {
    const f = fixture();
    f.error.dataset.noticePersistent = 'true';
    f.error.textContent = 'Нет сети'; f.error.hidden = false; f.sync();
    assert.equal(f.stack.children[0].hidden, false);
    assert.equal(f.timers.size, 0);
});
