const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../static/live_lessons/lesson_room.js'), 'utf8');

function roomFixture({ teacher = false, supportsNoiseSuppression = true,
    supportsVoiceEnhancement = true, savedPreferences = null, initialRoom = true,
    savedDevices = null, supportsOutput = false, fullscreen = 'native', connectError = null } = {}) {
    const elements = new Map();
    const documentListeners = new Map();
    const windowListeners = new Map();
    const requests = [];
    const timers = new Map();
    let nextTimerId = 0;
    const storage = new Map();
    if (savedPreferences) storage.set('coursemc:live-room-screen:v1', JSON.stringify(savedPreferences));
    if (savedDevices) storage.set('coursemc:live-room-devices:v1', JSON.stringify(savedDevices));
    let latestRoom = null;
    const doc = {
        fullscreenElement: null,
        getElementById: (id) => elements.get(id),
        addEventListener(type, callback) { documentListeners.set(type, callback); },
        removeEventListener(type) { documentListeners.delete(type); },
        exitFullscreen() {
            this.fullscreenElement = null;
            documentListeners.get('fullscreenchange')();
            return Promise.resolve();
        },
    };
    function makeElement(tagName = 'div') {
        const element = {
            tagName, children: [], dataset: {}, listeners: new Map(), attributes: new Map(),
            hidden: false, disabled: false, textContent: '', className: '', value: '',
            addEventListener(type, callback) { this.listeners.set(type, callback); },
            setAttribute(name, value) { this.attributes.set(name, value); },
            getAttribute(name) { return this.attributes.get(name); },
            append(...children) {
                for (const child of children) { child.parentElement = this; this.children.push(child); }
            },
            appendChild(child) { this.append(child); },
            replaceChildren(...children) {
                for (const child of this.children) child.parentElement = null;
                this.children = [];
                this.append(...children);
            },
            remove() {
                if (!this.parentElement) return;
                const siblings = this.parentElement.children;
                siblings.splice(siblings.indexOf(this), 1);
                this.parentElement = null;
            },
            contains(target) { return this === target || this.children.some((child) => child.contains(target)); },
            querySelector(selector) {
                if (selector === '[name=csrfmiddlewaretoken]') return { value: 'csrf' };
                if (!this.label) this.label = makeElement('span');
                return this.label;
            },
            requestFullscreen() {
                if (fullscreen === 'reject') return Promise.reject(new TypeError('Fullscreen unavailable'));
                doc.fullscreenElement = this;
                documentListeners.get('fullscreenchange')();
                return Promise.resolve();
            },
        };
        let ownText = '';
        Object.defineProperty(element, 'textContent', {
            get() { return ownText + this.children.map((child) => child.textContent).join(''); },
            set(value) { ownText = String(value); this.children = []; },
        });
        element.classList = {
            contains(name) { return element.className.split(/\s+/).includes(name); },
            toggle(name, force) {
                const names = new Set(element.className.split(/\s+/).filter(Boolean));
                if (force) names.add(name); else names.delete(name);
                element.className = [...names].join(' ');
            },
            add(name) { element.className += ` ${name}`; },
        };
        element.style = { setProperty(name, value) { this[name] = value; } };
        element.focus = () => { doc.activeElement = element; };
        if (fullscreen === 'missing' || fullscreen === 'webkit') delete element.requestFullscreen;
        if (fullscreen === 'webkit') element.webkitRequestFullscreen = function () {
            doc.webkitFullscreenElement = this;
            documentListeners.get('webkitfullscreenchange')();
        };
        if (tagName === 'audio' && supportsOutput) element.setSinkId = async () => {};
        return element;
    }
    doc.createElement = makeElement;
    doc.body = makeElement('body');
    if (fullscreen === 'disabled') doc.fullscreenEnabled = false;
    if (fullscreen === 'webkit') {
        delete doc.exitFullscreen;
        doc.webkitExitFullscreen = function () {
            this.webkitFullscreenElement = null;
            documentListeners.get('webkitfullscreenchange')();
        };
    }
    for (const id of [
        'll-room', 'll-room-state', 'll-room-error', 'll-room-join', 'll-room-leave',
        'll-room-unlock', 'll-room-lobby', 'll-room-mic', 'll-room-camera',
        'll-room-screen', 'll-room-quality', 'll-room-fps', 'll-room-audio-input',
        'll-room-mic-volume', 'll-room-mic-volume-value', 'll-room-speaker-volume',
        'll-room-speaker-volume-value', 'll-room-noise-suppression', 'll-room-voice-enhancement',
        'll-room-video-input', 'll-room-count', 'll-room-members', 'll-room-tracks',
        'll-room-empty', 'll-room-audio', 'll-room-settings', 'll-room-settings-toggle',
        'll-room-settings-close', 'll-room-actual', 'll-room-workspace',
        'll-room-sidebar', 'll-room-sidebar-title', 'll-room-sidebar-close',
        'll-room-members-toggle', 'll-room-chat-toggle', 'll-room-members-panel',
        'll-room-chat-panel', 'll-room-fullscreen', 'll-room-reactions-toggle', 'll-room-reactions-menu',
        'll-room-audio-output', 'll-device-open',
    ]) elements.set(id, makeElement());
    doc.body.appendChild(elements.get('ll-room'));
    elements.get('ll-room').appendChild(elements.get('ll-room-tracks'));
    elements.get('ll-room-reactions-menu').hidden = true;
    elements.get('ll-room-error').hidden = true;
    elements.get('ll-room-settings').hidden = true;
    elements.get('ll-room-sidebar').hidden = true;
    for (const reaction of ['hand', 'like', 'check', 'cross', 'fire']) {
        const button = makeElement('button');
        button.dataset.reaction = reaction;
        elements.get('ll-room-reactions-menu').appendChild(button);
    }
    elements.get('ll-room').dataset = { tokenUrl: '/token/', stateUrl: '/state/', teacher: String(teacher),
        ...(teacher ? { moderateUrl: '/moderate/' } : {}) };
    elements.get('ll-room-quality').value = '1080';
    elements.get('ll-room-fps').value = '30';
    elements.get('ll-room-mic-volume').value = '100';
    elements.get('ll-room-speaker-volume').value = '100';
    elements.get('ll-room-noise-suppression').checked = true;
    elements.get('ll-room-voice-enhancement').checked = true;
    const track = { kind: 'video', attach: () => makeElement('video'), detach: () => [] };
    const publication = { track, trackSid: 'v1', source: 'camera' };
    class MockRoom {
        constructor(options) {
            latestRoom = this;
            this.options = options;
            this.state = 'connected';
            this.localParticipant = {
                identity: 'teacher', name: 'Преподаватель', isLocal: true,
                trackPublications: new Map([['video', publication]]),
                isScreenShareEnabled: false,
                publishData: async (data, options) => { this.sentData.push({ data, options }); },
            };
            this.sentData = [];
            this.remoteParticipants = new Map();
            this.canPlaybackAudio = true;
            this.events = new Map();
        }
        on(type, callback) { this.events.set(type, callback); }
        emit(type, ...args) { this.events.get(type)?.(...args); }
        async connect(url, token, options) {
            this.connectOptions = options;
            if (connectError) throw connectError;
        }
        async disconnect() { this.state = 'disconnected'; this.emit('Disconnected'); }
        getActiveDevice() { return ''; }
    }
    MockRoom.getLocalDevices = async () => [];
    const sdk = {
        Room: MockRoom, RoomEvent: Object.fromEntries([
            'TrackSubscribed', 'TrackUnsubscribed', 'LocalTrackPublished', 'LocalTrackUnpublished',
            'ParticipantConnected', 'ParticipantDisconnected', 'TrackPublished', 'TrackUnpublished',
            'TrackMuted', 'TrackUnmuted', 'ActiveSpeakersChanged', 'MediaDevicesChanged',
            'AudioPlaybackStatusChanged', 'DataReceived', 'Reconnecting', 'Reconnected', 'Disconnected',
            'ConnectionQualityChanged', 'ParticipantPermissionsChanged',
        ].map((name) => [name, name])), ConnectionState: { Connected: 'connected' },
        Track: { Kind: { Audio: 'audio', Video: 'video' },
            Source: { Camera: 'camera', ScreenShare: 'screen', Microphone: 'microphone' } },
    };
    const context = {
        document: doc, URL, TextEncoder, TextDecoder, location: { protocol: 'http:' },
        MediaStream: class { constructor(tracks) { this.tracks = tracks; } },
        FormData: class {
            constructor() { this.values = new Map(); }
            set(key, value) { this.values.set(key, value); }
        },
        window: {
            LivekitClient: sdk,
            addEventListener(type, callback) { windowListeners.set(type, callback); },
            removeEventListener(type) { windowListeners.delete(type); },
            dispatchEvent(event) { windowListeners.get(event.type)?.(event); }, confirm: () => true,
            navigator: { mediaDevices: { getSupportedConstraints: () =>
                ({ ...(supportsNoiseSuppression ? { noiseSuppression: true } : {}),
                    ...(supportsVoiceEnhancement ? { autoGainControl: true, echoCancellation: true } : {}) }) } },
            localStorage: { getItem: (key) => storage.get(key) || null,
                setItem(key, value) { storage.set(key, value); } },
            setInterval: () => 1,
            clearInterval() {},
            setTimeout(callback) { const id = ++nextTimerId; timers.set(id, callback); return id; },
            clearTimeout(id) { timers.delete(id); },
        },
        Event: class { constructor(type) { this.type = type; } },
        CustomEvent: class { constructor(type, { detail }) { this.type = type; this.detail = detail; } },
        Option: class { constructor(label, value) { this.label = label; this.value = value; } },
        fetch: async (url, options) => {
            requests.push({ url, options });
            return {
                ok: true, headers: { get: () => 'application/json' },
                json: async () => String(url) === '/state/' ? { can_join: true } :
                    String(url) === '/moderate/' ? { ok: true } :
                        { server_url: 'ws://127.0.0.1:7880', participant_token: 'test' },
            };
        },
    };
    for (const id of ['ll-room-audio-input', 'll-room-video-input', 'll-room-audio-output']) {
        elements.get(id).add = () => {};
    }
    const roomRoot = elements.get('ll-room');
    if (!initialRoom) elements.delete('ll-room');
    vm.runInNewContext(source, context);
    return { elements, doc, makeElement, documentListeners, requests, storage, timers, windowListeners, roomRoot, context, getRoom: () => latestRoom };
}

test('room inserted after lesson start initializes once and remains inactive until explicit join', async () => {
    const f = roomFixture({ initialRoom: false });
    assert.equal(f.elements.get('ll-room-join').listeners.has('click'), false);
    f.elements.set('ll-room', f.roomRoot);
    f.windowListeners.get('ll-page-updated')();
    assert.equal(f.elements.get('ll-room-join').listeners.has('click'), true);
    assert.equal(f.getRoom(), null);
    const join = f.elements.get('ll-room-join').listeners.get('click');
    f.windowListeners.get('ll-page-updated')();
    assert.equal(f.elements.get('ll-room-join').listeners.get('click'), join);
    join();
    await new Promise(setImmediate);
    assert.equal(f.elements.get('ll-room-chat-toggle').disabled, false);
});

test('waiting queue push is accepted only from server and only by teacher', async () => {
    for (const teacher of [true, false]) {
        const f = roomFixture({ teacher });
        let refreshes = 0;
        f.context.window.addEventListener('ll-classroom-refresh', () => { refreshes++; });
        f.elements.get('ll-room-join').listeners.get('click')();
        await new Promise(setImmediate);
        const room = f.getRoom();
        room.emit('DataReceived', new TextEncoder().encode('refresh'), { identity: 'student' }, undefined, 'lesson-waiting-updated');
        assert.equal(refreshes, 0);
        room.emit('DataReceived', new TextEncoder().encode('refresh'), undefined, undefined, 'lesson-waiting-updated');
        assert.equal(refreshes, teacher ? 1 : 0);
    }
});

test('lesson state event disconnects active room and cleans up listeners before history is shown', async () => {
    const f = roomFixture();
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const pending = [];
    f.windowListeners.get('ll-lesson-state')({ detail: {
        state: { status: 'ended', can_join: false }, waitUntil: (promise) => pending.push(promise),
    } });
    await Promise.all(pending);
    assert.equal(f.getRoom().state, 'disconnected');
    assert.equal(f.elements.get('ll-room-join').disabled, true);
    f.elements.delete('ll-room');
    f.windowListeners.get('ll-page-updated')();
    assert.equal(f.windowListeners.has('ll-lesson-state'), false);
    assert.equal(f.windowListeners.has('beforeunload'), false);
});

function avatarFor(elements, identity) {
    const figure = elements.get('ll-room-tracks').children.find((child) =>
        child.dataset.identity === identity && !child.classList.contains('ll-room-tile-screen'));
    assert.ok(figure, `no tile for ${identity}`);
    const wrap = figure.children.find((child) => child.className === 'll-room-tile-avatar-wrap');
    assert.ok(wrap);
    return { figure, badge: wrap.children.find((child) => child.className === 'll-room-reaction-badge') };
}

test('chat unlocks only after joining the room', async () => {
    const { elements } = roomFixture();
    assert.equal(elements.get('ll-room-chat-toggle').disabled, true);
    elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    assert.equal(elements.get('ll-room-chat-toggle').disabled, false);
});

function pressSpace(f, overrides = {}) {
    const event = { key: ' ', code: 'Space', target: {},
        preventDefault() { this.defaultPrevented = true; }, ...overrides };
    f.documentListeners.get('keydown')(event);
    return event;
}

test('personal pin keeps the same participant tile and order through camera mute and republish', async () => {
    const f = roomFixture();
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = f.getRoom();
    const student = { identity: 'student', name: 'Ученик', trackPublications: new Map() };
    room.remoteParticipants.set(student.identity, student);
    room.emit('ParticipantConnected', student);
    const tracks = f.elements.get('ll-room-tracks');
    const tile = tracks.children.find((figure) => figure.dataset.identity === 'student');
    const order = tile.style.order;
    const requestsBefore = f.requests.length;
    tile.pinButton.listeners.get('click')();
    assert.equal(tile.pinButton.getAttribute('aria-pressed'), 'true');
    assert.equal(tracks.classList.contains('ll-room-tracks-pinned'), true);
    assert.equal(room.sentData.length, 0);
    assert.equal(f.requests.length, requestsBefore);
    const camera = { kind: 'video', attach: () => f.makeElement('video'), detach() {} };
    let publication = { track: camera, trackSid: 'camera-1', source: 'camera' };
    room.emit('TrackSubscribed', camera, publication, student);
    assert.equal(tracks.children.find((figure) => figure.dataset.identity === 'student'), tile);
    publication.isMuted = true;
    room.emit('TrackMuted', publication, student);
    assert.equal(tile.classList.contains('ll-room-tile-has-video'), false);
    assert.equal(tile.classList.contains('ll-room-tile-pinned'), true);
    room.emit('TrackUnsubscribed', camera, publication, student);
    publication = { ...publication, trackSid: 'camera-2', isMuted: false };
    room.emit('TrackSubscribed', camera, publication, student);
    assert.equal(tile.classList.contains('ll-room-tile-has-video'), true);
    assert.equal(tile.style.order, order);
    assert.equal(tracks.children.filter((figure) => figure.dataset.identity === 'student').length, 1);
    tile.pinButton.listeners.get('click')();
    assert.equal(tracks.classList.contains('ll-room-tracks-pinned'), false);
});

test('screen pin is separate from participant pin and disappears safely when sharing stops', async () => {
    const f = roomFixture();
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = f.getRoom(), tracks = f.elements.get('ll-room-tracks');
    const cameraTile = tracks.children[0];
    cameraTile.pinButton.listeners.get('click')();
    const screen = { kind: 'video', attach: () => f.makeElement('video'), detach() {} };
    const publication = { track: screen, trackSid: 'screen-1', source: 'screen' };
    room.emit('LocalTrackPublished', publication);
    assert.equal(cameraTile.classList.contains('ll-room-tile-pinned'), true);
    const screenTile = tracks.children.find((figure) => figure.dataset.source === 'screen');
    screenTile.pinButton.listeners.get('click')();
    assert.equal(cameraTile.classList.contains('ll-room-tile-pinned'), false);
    assert.equal(screenTile.classList.contains('ll-room-tile-pinned'), true);
    room.emit('LocalTrackUnpublished', publication);
    assert.equal(tracks.classList.contains('ll-room-tracks-pinned'), false);
    assert.equal(cameraTile.parentElement, tracks);
});

test('participant departure clears its personal pin without disturbing others', async () => {
    const f = roomFixture();
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = f.getRoom(), tracks = f.elements.get('ll-room-tracks');
    const student = { identity: 'student', name: 'Ученик', trackPublications: new Map() };
    room.remoteParticipants.set(student.identity, student);
    room.emit('ParticipantConnected', student);
    tracks.children.find((figure) => figure.dataset.identity === 'student').pinButton.listeners.get('click')();
    const ownTile = tracks.children.find((figure) => figure.dataset.identity === 'teacher');
    room.remoteParticipants.delete(student.identity);
    room.emit('ParticipantDisconnected', student);
    assert.equal(tracks.classList.contains('ll-room-tracks-pinned'), false);
    assert.equal(tracks.children.length, 1);
    assert.equal(tracks.children[0], ownTile);
});

test('joining closes preflight and uses chosen devices without turning microphone or camera on', async () => {
    const f = roomFixture({ savedDevices: { audioinput: 'mic-2', videoinput: 'cam-2', audiooutput: 'speaker-2' }, supportsOutput: true });
    let closes = 0;
    f.context.window.addEventListener('ll-prejoin-close', () => { closes++; });
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = f.getRoom();
    assert.equal(closes, 1);
    assert.equal(room.options.audioCaptureDefaults.deviceId, 'mic-2');
    assert.equal(room.options.videoCaptureDefaults.deviceId, 'cam-2');
    assert.equal(room.options.audioOutput.deviceId, 'speaker-2');
    assert.equal(f.elements.get('ll-room-mic').getAttribute('aria-pressed'), 'false');
    assert.equal(f.elements.get('ll-room-camera').getAttribute('aria-pressed'), 'false');
});

test('system default device can be restored and failed device switch does not persist', async () => {
    const f = roomFixture({ savedDevices: { audioinput: 'mic-2' } });
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = f.getRoom(), input = f.elements.get('ll-room-audio-input');
    const switches = [];
    room.switchActiveDevice = async (kind, id) => { switches.push([kind, id]); return true; };
    input.value = '';
    input.listeners.get('change')();
    await new Promise(setImmediate);
    assert.deepEqual(switches, [['audioinput', 'default']]);
    assert.equal(JSON.parse(f.storage.get('coursemc:live-room-devices:v1')).audioinput, '');
    room.switchActiveDevice = async () => false;
    input.value = 'missing'; input.listeners.get('change')();
    await new Promise(setImmediate);
    assert.equal(JSON.parse(f.storage.get('coursemc:live-room-devices:v1')).audioinput, '');
    assert.equal(input.value, '');
    assert.equal(f.elements.get('ll-room-error').hidden, false);
});

test('Space toggles microphone once, ignores held key and never joins automatically', async () => {
    const f = roomFixture();
    assert.equal(pressSpace(f).defaultPrevented, undefined);
    assert.equal(f.getRoom(), null);
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = f.getRoom();
    const changes = [];
    room.localParticipant.setMicrophoneEnabled = async (enabled) => {
        room.localParticipant.isMicrophoneEnabled = enabled;
        changes.push(enabled);
    };
    assert.equal(pressSpace(f).defaultPrevented, true);
    pressSpace(f, { repeat: true });
    pressSpace(f); // ignored while the first async toggle is in flight
    await new Promise(setImmediate);
    assert.deepEqual(changes, [true]);
    assert.equal(f.elements.get('ll-room-mic').getAttribute('aria-pressed'), 'true');
    pressSpace(f);
    await new Promise(setImmediate);
    assert.deepEqual(changes, [true, false]);
    assert.equal(f.elements.get('ll-room-mic').getAttribute('aria-pressed'), 'false');
});

test('Space preserves chat, form controls, settings, composition and modified shortcuts', async () => {
    const f = roomFixture();
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    let toggles = 0;
    f.getRoom().localParticipant.setMicrophoneEnabled = async () => { toggles += 1; };
    f.elements.get('ll-room-chat-toggle').listeners.get('click')();
    assert.equal(pressSpace(f).defaultPrevented, undefined);
    f.elements.get('ll-room-sidebar-close').listeners.get('click')();
    for (const overrides of [
        { target: { isContentEditable: true } },
        { target: { closest: () => ({ tagName: 'TEXTAREA' }) } },
        { ctrlKey: true }, { metaKey: true }, { altKey: true }, { shiftKey: true },
        { isComposing: true }, { defaultPrevented: true },
    ]) pressSpace(f, overrides);
    f.elements.get('ll-room-settings-toggle').listeners.get('click')();
    assert.equal(pressSpace(f).defaultPrevented, undefined);
    await new Promise(setImmediate);
    assert.equal(toggles, 0);
});

function micBadge(figure) {
    const caption = figure.children.find((child) => child.tagName === 'figcaption');
    return caption.children.find((child) => child.className === 'll-room-mic-muted');
}

test('muted badges follow microphone state on avatars, cameras, screens and participant list', async () => {
    const f = roomFixture();
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = f.getRoom();
    const student = { identity: 'student', name: 'Ученик', isMicrophoneEnabled: false,
        trackPublications: new Map() };
    room.remoteParticipants.set(student.identity, student);
    room.emit('ParticipantConnected');
    assert.equal(micBadge(avatarFor(f.elements, 'student').figure).getAttribute('aria-label'), 'Микрофон выключен');
    const listBadge = () => f.elements.get('ll-room-members').children[1].children[0].children
        .find((child) => child.className === 'll-room-mic-muted');
    assert.ok(listBadge());
    student.isMicrophoneEnabled = true;
    room.emit('TrackUnmuted', { source: 'microphone' }, student);
    assert.equal(micBadge(avatarFor(f.elements, 'student').figure), undefined);
    assert.equal(listBadge(), undefined);
    for (const source of ['camera', 'screen']) {
        const track = { kind: 'video', attach: () => f.doc.createElement('video'), detach: () => [] };
        room.emit('TrackSubscribed', track, { source, trackSid: source, track }, student);
    }
    student.isMicrophoneEnabled = false;
    room.emit('TrackMuted', { source: 'microphone' }, student);
    const tiles = f.elements.get('ll-room-tracks').children.filter((tile) => tile.dataset.identity === 'student');
    assert.equal(tiles.length, 2);
    assert.ok(tiles.every(micBadge));
    student.isMicrophoneEnabled = true;
    room.emit('TrackUnmuted', { source: 'microphone' }, student);
    assert.ok(tiles.every((tile) => !micBadge(tile)));
});

test('four local reactions are broadcast and briefly appear beside the avatar', async () => {
    const { elements, getRoom, timers } = roomFixture();
    const toggle = elements.get('ll-room-reactions-toggle');
    const menu = elements.get('ll-room-reactions-menu');
    assert.equal(toggle.disabled, true);
    elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = getRoom();
    assert.equal(toggle.disabled, false);
    const expected = [['like', '👍'], ['check', '✅'], ['cross', '❌'], ['fire', '🔥']];
    for (const [key, symbol] of expected) {
        toggle.listeners.get('click')();
        assert.equal(menu.hidden, false);
        assert.equal(toggle.getAttribute('aria-expanded'), 'true');
        menu.children.find((button) => button.dataset.reaction === key).listeners.get('click')();
        await new Promise(setImmediate);
        assert.equal(menu.hidden, true);
        assert.equal(room.sentData.at(-1).options.topic, 'lesson-reaction');
        assert.equal(room.sentData.at(-1).options.reliable, false);
        assert.equal(new TextDecoder().decode(room.sentData.at(-1).data), key);
        const { badge } = avatarFor(elements, room.localParticipant.identity);
        assert.equal(badge.hidden, false);
        assert.equal(badge.textContent, symbol);
    }
    assert.equal(room.sentData.length, 4);
    assert.equal(timers.size, 1);
    for (const callback of timers.values()) callback();
    assert.equal(avatarFor(elements, room.localParticipant.identity).badge.hidden, true);
});

test('raised hand is persistent, returns after a temporary reaction and lowers only on classroom state', async () => {
    const f = roomFixture();
    let handClicks = 0;
    f.windowListeners.set('ll-hand-toggle', () => { handClicks += 1; });
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = f.getRoom();
    const hand = f.elements.get('ll-room-reactions-menu').children[0];
    hand.listeners.get('click')();
    assert.equal(handClicks, 1);
    assert.equal(room.sentData.length, 0);
    const state = { teacher: false, settings: { microphone: true, screen: true },
        own: { identity: room.localParticipant.identity, admission: 'admitted', entry_allowed: true, hand_raised: true },
        hands: [{ identity: room.localParticipant.identity }] };
    f.windowListeners.get('ll-classroom-state')({ detail: { state } });
    assert.equal(avatarFor(f.elements, room.localParticipant.identity).badge.textContent, '✋');
    assert.equal(hand.getAttribute('aria-pressed'), 'true');
    f.elements.get('ll-room-reactions-menu').children[4].listeners.get('click')();
    await new Promise(setImmediate);
    assert.equal(avatarFor(f.elements, room.localParticipant.identity).badge.textContent, '🔥');
    for (const callback of f.timers.values()) callback();
    assert.equal(avatarFor(f.elements, room.localParticipant.identity).badge.textContent, '✋');
    state.hands = [];
    state.own.hand_raised = false;
    f.windowListeners.get('ll-classroom-state')({ detail: { state } });
    assert.equal(avatarFor(f.elements, room.localParticipant.identity).badge.hidden, true);
    assert.equal(hand.getAttribute('aria-label'), 'Поднять руку');
});

test('teacher restrictions disable microphone and screen, including Space, without affecting camera', async () => {
    const f = roomFixture();
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = f.getRoom();
    const changes = [];
    room.localParticipant.isMicrophoneEnabled = true;
    room.localParticipant.isScreenShareEnabled = true;
    room.localParticipant.setMicrophoneEnabled = async (value) => { changes.push(['mic', value]); room.localParticipant.isMicrophoneEnabled = value; };
    room.localParticipant.setScreenShareEnabled = async (value) => { changes.push(['screen', value]); room.localParticipant.isScreenShareEnabled = value; };
    f.windowListeners.get('ll-classroom-state')({ detail: { state: {
        teacher: false, settings: { microphone: false, screen: false },
        own: { admission: 'admitted', entry_allowed: true }, hands: [],
    } } });
    await new Promise(setImmediate);
    assert.equal(f.elements.get('ll-room-mic').disabled, true);
    assert.equal(f.elements.get('ll-room-screen').disabled, true);
    assert.equal(f.elements.get('ll-room-camera').disabled, false);
    f.documentListeners.get('keydown')({ key: ' ', code: 'Space', target: null, preventDefault() {} });
    assert.deepEqual(changes, [['mic', false], ['screen', false]]);
});

test('only local connection quality and reconnect events feed diagnosis', async () => {
    const f = roomFixture();
    const updates = [];
    f.windowListeners.set('ll-connection', ({ detail }) => updates.push(detail));
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = f.getRoom();
    room.emit('ConnectionQualityChanged', 'poor', room.localParticipant);
    assert.equal(updates.at(-1).quality, 'poor');
    const count = updates.length;
    room.emit('ConnectionQualityChanged', 'lost', { isLocal: false });
    assert.equal(updates.length, count);
    room.emit('Reconnecting');
    assert.equal(updates.at(-1).state, 'reconnecting');
    room.emit('Reconnected');
    assert.equal(updates.at(-1).state, 'connected');
});

test('waiting response never connects media; admission enters automatically with devices still off', async () => {
    const f = roomFixture();
    const normalFetch = f.context.fetch;
    f.context.fetch = async () => ({ ok: true, status: 202, headers: { get: () => 'application/json' },
        json: async () => ({ waiting: true, admission: 'waiting' }) });
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    assert.equal(f.getRoom(), null);
    assert.equal(f.elements.get('ll-room-join').disabled, true);
    assert.match(f.elements.get('ll-room-join').textContent, /Ждём/);
    assert.equal(f.elements.get('ll-room-chat-toggle').disabled, true);
    f.context.fetch = normalFetch;
    f.windowListeners.get('ll-classroom-state')({ detail: { state: {
        teacher: false, settings: { microphone: true, screen: true },
        own: { admission: 'admitted', entry_allowed: true }, hands: [],
    } } });
    await new Promise(setImmediate);
    assert.ok(f.getRoom());
    assert.equal(f.elements.get('ll-room-chat-toggle').disabled, false);
    assert.equal(!!f.getRoom().localParticipant.isMicrophoneEnabled, false);
    assert.equal(!!f.getRoom().localParticipant.isCameraEnabled, false);
});

test('denial or locked entry never auto-connects and cancellation leaves the join button available', async () => {
    const f = roomFixture();
    const render = (admission, entry_allowed = true) => f.windowListeners.get('ll-classroom-state')({ detail: { state: {
        teacher: false, settings: { microphone: true, screen: true }, own: { admission, entry_allowed }, hands: [],
    } } });
    render('waiting');
    f.windowListeners.get('ll-wait-cancelled')();
    assert.equal(f.elements.get('ll-room-join').disabled, false);
    render('left');
    render('denied');
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    assert.equal(f.getRoom(), null);
    render(null, false);
    assert.equal(f.elements.get('ll-room-join').disabled, true);
    assert.equal(f.getRoom(), null);
});

test('remote reaction follows the participant from avatar tile to camera and then disappears', async () => {
    const { elements, getRoom, timers } = roomFixture();
    elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = getRoom();
    const student = { identity: 'course-user-7', name: 'Ученик', isLocal: false,
        trackPublications: new Map() };
    room.remoteParticipants.set(student.identity, student);
    room.emit('ParticipantConnected', student);
    assert.equal(avatarFor(elements, student.identity).figure.classList.contains('ll-room-tile-avatar'), true);
    room.emit('DataReceived', new TextEncoder().encode('fire'), student, undefined, 'lesson-reaction');
    assert.equal(avatarFor(elements, student.identity).badge.textContent, '🔥');
    assert.equal(avatarFor(elements, room.localParticipant.identity).badge.hidden, true);

    const camera = { kind: 'video', attach: () => ({ remove() {} }), detach() {} };
    const publication = { track: camera, trackSid: 'remote-v1', source: 'camera', isMuted: false };
    student.trackPublications.set('camera', publication);
    room.emit('TrackSubscribed', camera, publication, student);
    assert.equal(avatarFor(elements, student.identity).figure.classList.contains('ll-room-tile-has-video'), true);
    assert.equal(avatarFor(elements, student.identity).badge.textContent, '🔥');

    publication.isMuted = true;
    room.emit('TrackMuted', publication, student);
    assert.equal(avatarFor(elements, student.identity).figure.classList.contains('ll-room-tile-has-video'), false);
    room.emit('TrackUnsubscribed', camera, publication, student);
    assert.equal(avatarFor(elements, student.identity).badge.textContent, '🔥');

    room.emit('DataReceived', new TextEncoder().encode('unknown'), student, undefined, 'lesson-reaction');
    room.emit('DataReceived', new TextEncoder().encode('like'), { identity: 'stranger' }, undefined, 'lesson-reaction');
    assert.equal(avatarFor(elements, student.identity).badge.textContent, '🔥');
    for (const callback of timers.values()) callback();
    assert.equal(avatarFor(elements, student.identity).badge.hidden, true);
});

test('teacher controls target only remote participants', async () => {
    const { elements, getRoom, requests } = roomFixture({ teacher: true });
    elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = getRoom();
    const student = { identity: 'course-user-7', name: 'Ученик', isLocal: false,
        trackPublications: new Map([['mic', { source: 'microphone', isMuted: false }]]) };
    room.remoteParticipants.set(student.identity, student);
    room.emit('ParticipantConnected');
    const [self, remote] = elements.get('ll-room-members').children;
    assert.equal(self.children.length, 1);
    assert.equal(remote.children[0].textContent, 'Ученик');
    const [mute, remove] = remote.children[1].children;
    assert.equal(mute.disabled, false);
    mute.listeners.get('click')();
    await new Promise(setImmediate);
    remove.listeners.get('click')();
    await new Promise(setImmediate);
    const actions = requests.filter(({ url }) => url === '/moderate/')
        .map(({ options }) => [options.body.values.get('action'), options.body.values.get('identity')]);
    assert.deepEqual(actions, [['mute', 'course-user-7'], ['remove', 'course-user-7']]);
});

test('remote teacher mute updates the local microphone button', async () => {
    const { elements, getRoom } = roomFixture();
    elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = getRoom();
    const microphone = { source: 'microphone', isMuted: false };
    room.localParticipant.trackPublications.set('mic', microphone);
    Object.defineProperty(room.localParticipant, 'isMicrophoneEnabled', {
        get: () => !microphone.isMuted,
    });
    const button = elements.get('ll-room-mic');

    room.emit('TrackUnmuted', microphone, room.localParticipant);
    assert.equal(button.getAttribute('aria-pressed'), 'true');
    assert.equal(button.getAttribute('aria-label'), 'Выключить микрофон');

    microphone.isMuted = true;
    room.emit('TrackMuted', microphone, room.localParticipant);
    assert.equal(button.getAttribute('aria-pressed'), 'false');
    assert.equal(button.getAttribute('aria-label'), 'Включить микрофон');
});

test('noise suppression preference is restored and used for microphone capture', async () => {
    const { elements, getRoom, storage } = roomFixture({ savedPreferences: { noiseSuppression: false } });
    const noise = elements.get('ll-room-noise-suppression');
    assert.equal(noise.checked, false);
    elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = getRoom();
    assert.equal(room.options.audioCaptureDefaults.noiseSuppression, false);
    const applied = [];
    const track = { applyConstraints: async (options) => { applied.push(options.noiseSuppression); } };
    let captureOptions;
    room.localParticipant.setMicrophoneEnabled = async (_enabled, options) => {
        captureOptions = options;
        room.localParticipant.isMicrophoneEnabled = true;
        room.localParticipant.trackPublications.set('mic', { source: 'microphone', track });
    };
    elements.get('ll-room-mic').listeners.get('click')();
    await new Promise(setImmediate);
    assert.equal(captureOptions.noiseSuppression, false);
    assert.deepEqual(applied, [false]);

    noise.checked = true;
    noise.listeners.get('change')();
    await new Promise(setImmediate);
    assert.deepEqual(applied, [false, true]);
    assert.equal(JSON.parse(storage.get('coursemc:live-room-screen:v1')).noiseSuppression, true);
});

test('noise suppression changes on an active mic and reapplies after device switch', async () => {
    const { elements, getRoom } = roomFixture();
    elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = getRoom();
    const applied = [];
    const track = { applyConstraints: async (options) => { applied.push(options.noiseSuppression); } };
    room.localParticipant.trackPublications.set('mic', { source: 'microphone', track });
    const noise = elements.get('ll-room-noise-suppression');
    noise.checked = false;
    noise.listeners.get('change')();
    await new Promise(setImmediate);
    assert.deepEqual(applied, [false]);
    assert.equal(noise.disabled, false);

    room.switchActiveDevice = async () => {};
    const input = elements.get('ll-room-audio-input');
    input.value = 'new-microphone';
    input.listeners.get('change')();
    await new Promise(setImmediate);
    assert.deepEqual(applied, [false, false]);
});

test('voice enhancement independently controls echo cancellation and automatic gain', async () => {
    const { elements, getRoom, storage } = roomFixture({ savedPreferences: { voiceEnhancement: false } });
    const voice = elements.get('ll-room-voice-enhancement');
    assert.equal(voice.checked, false);
    elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = getRoom();
    assert.equal(room.options.audioCaptureDefaults.echoCancellation, false);
    assert.equal(room.options.audioCaptureDefaults.autoGainControl, false);
    assert.equal(room.options.audioCaptureDefaults.noiseSuppression, true);

    const applied = [];
    room.localParticipant.trackPublications.set('mic', { source: 'microphone', track: {
        applyConstraints: async (options) => { applied.push(options); },
    } });
    voice.checked = true;
    voice.listeners.get('change')();
    await new Promise(setImmediate);
    assert.deepEqual({ ...applied[0] }, { echoCancellation: true, noiseSuppression: true, autoGainControl: true });
    assert.equal(JSON.parse(storage.get('coursemc:live-room-screen:v1')).voiceEnhancement, true);

    const noise = elements.get('ll-room-noise-suppression');
    noise.checked = false;
    noise.listeners.get('change')();
    await new Promise(setImmediate);
    assert.deepEqual({ ...applied[1] }, { echoCancellation: true, noiseSuppression: false, autoGainControl: true });
});

test('failed noise suppression change restores the switch and unsupported browsers disable it', async () => {
    const { elements, getRoom, storage } = roomFixture();
    elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    getRoom().localParticipant.trackPublications.set('mic', { source: 'microphone',
        track: { applyConstraints: async () => { throw new Error('Настройка недоступна'); } } });
    const noise = elements.get('ll-room-noise-suppression');
    noise.checked = false;
    noise.listeners.get('change')();
    await new Promise(setImmediate);
    assert.equal(noise.checked, true);
    assert.equal(noise.disabled, false);
    assert.match(elements.get('ll-room-error').textContent, /Настройка недоступна/);
    assert.equal(storage.size, 0);

    const unsupported = roomFixture({ supportsNoiseSuppression: false });
    assert.equal(unsupported.elements.get('ll-room-noise-suppression').disabled, true);
    assert.equal(unsupported.elements.get('ll-room-noise-suppression').checked, false);
    assert.match(unsupported.elements.get('ll-room-noise-suppression').title, /не поддерживает/);
    const unsupportedVoice = roomFixture({ supportsVoiceEnhancement: false });
    assert.equal(unsupportedVoice.elements.get('ll-room-voice-enhancement').disabled, true);
    assert.equal(unsupportedVoice.elements.get('ll-room-voice-enhancement').checked, false);
});

test('speaker slider changes existing audio and microphone gain processor updates live', async () => {
    const { elements, getRoom } = roomFixture();
    elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = getRoom();
    const student = { identity: 'course-user-7', name: 'Ученик', isLocal: false,
        trackPublications: new Map() };
    const volumes = [];
    const audioTrack = { kind: 'audio', attach: () => ({ autoplay: false }),
        setVolume(value) { volumes.push(value); } };
    room.emit('TrackSubscribed', audioTrack, { trackSid: 'a1', source: 'microphone' }, student);
    elements.get('ll-room-speaker-volume').value = '35';
    elements.get('ll-room-speaker-volume').listeners.get('input')();
    assert.equal(volumes.at(-1), .35);
    assert.equal(elements.get('ll-room-speaker-volume-value').value, '35%');

    let processor;
    const graphNode = () => ({ connect() {}, disconnect() {} });
    const audioContext = {
        createMediaStreamSource: graphNode,
        createGain: () => ({ ...graphNode(), gain: { value: 1 } }),
        createMediaStreamDestination: () => ({ ...graphNode(), stream: {
            getAudioTracks: () => [{ kind: 'audio' }],
        } }),
    };
    const micTrack = { async setProcessor(value) {
        processor = value;
        await value.init({ track: this, audioContext });
    } };
    room.localParticipant.trackPublications.set('mic', { source: 'microphone', track: micTrack });
    room.emit('LocalTrackPublished', { source: 'microphone', track: micTrack, trackSid: 'local-a1' });
    await new Promise(setImmediate);
    assert.ok(processor);
    elements.get('ll-room-mic-volume').value = '150';
    elements.get('ll-room-mic-volume').listeners.get('input')();
    assert.equal(processor.gainNode.gain.value, 1.5);
    assert.equal(elements.get('ll-room-mic-volume-value').value, '150%');
});

test('video tile button enters and exits fullscreen, including browser Escape', async () => {
    const { elements, doc } = roomFixture();
    elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const figure = elements.get('ll-room-tracks').children[0];
    assert.ok(figure);
    const button = figure.children.find((child) => child.className === 'll-room-expand');
    assert.equal(button.textContent, 'На весь экран');

    await button.listeners.get('click')();
    assert.equal(doc.fullscreenElement, figure);
    assert.equal(button.textContent, 'Свернуть');
    assert.equal(button.getAttribute('aria-pressed'), 'true');

    await button.listeners.get('click')();
    assert.equal(doc.fullscreenElement, null);
    assert.equal(button.textContent, 'На весь экран');
    assert.equal(button.getAttribute('aria-pressed'), 'false');

    await button.listeners.get('click')();
    await doc.exitFullscreen(); // Эквивалент выхода через Esc в браузере.
    assert.equal(button.textContent, 'На весь экран');
});

for (const fullscreen of ['missing', 'disabled', 'reject']) {
    test(`mobile room expands within the viewport when native fullscreen is ${fullscreen}`, async () => {
        const f = roomFixture({ fullscreen });
        const root = f.elements.get('ll-room');
        const button = f.elements.get('ll-room-fullscreen');
        await button.listeners.get('click')();
        assert.equal(root.classList.contains('ll-room-window-expanded'), true);
        assert.equal(f.doc.body.classList.contains('ll-room-scroll-locked'), true);
        assert.equal(button.querySelector('span').textContent, 'Свернуть');
        assert.equal(button.getAttribute('aria-pressed'), 'true');
        assert.equal(f.elements.get('ll-room-error').hidden, true);

        await button.listeners.get('click')();
        assert.equal(root.classList.contains('ll-room-window-expanded'), false);
        assert.equal(f.doc.body.classList.contains('ll-room-scroll-locked'), false);
        assert.equal(button.querySelector('span').textContent, 'Развернуть');
        assert.equal(f.doc.activeElement, button);
    });

    test(`mobile screen viewing opens and closes when native fullscreen is ${fullscreen}`, async () => {
        const f = roomFixture({ fullscreen });
        f.elements.get('ll-room-join').listeners.get('click')();
        await new Promise(setImmediate);
        const participant = { identity: 'student', name: 'Ученик', trackPublications: new Map() };
        f.getRoom().remoteParticipants.set(participant.identity, participant);
        const track = { kind: 'video', attach: () => f.makeElement('video'), detach: () => [] };
        f.getRoom().emit('TrackSubscribed', track, { trackSid: 'screen-1', source: 'screen' }, participant);
        const figure = f.elements.get('ll-room-tracks').children.find((tile) => tile.dataset.source === 'screen');
        const button = figure.expandButton;
        await button.listeners.get('click')();
        assert.equal(figure.classList.contains('ll-room-tile-window-expanded'), true);
        assert.equal(button.textContent, 'Свернуть');
        assert.equal(f.elements.get('ll-room-error').hidden, true);
        await button.listeners.get('click')();
        assert.equal(figure.classList.contains('ll-room-tile-window-expanded'), false);
        assert.equal(button.getAttribute('aria-pressed'), 'false');
        assert.equal(f.doc.body.classList.contains('ll-room-scroll-locked'), false);
    });
}

test('prefixed WebKit fullscreen enters and exits without the standard API', async () => {
    const f = roomFixture({ fullscreen: 'webkit' });
    const root = f.elements.get('ll-room');
    const button = f.elements.get('ll-room-fullscreen');
    await button.listeners.get('click')();
    assert.equal(f.doc.webkitFullscreenElement, root);
    assert.equal(root.classList.contains('ll-room-expanded'), true);
    assert.equal(root.classList.contains('ll-room-window-expanded'), false);
    await button.listeners.get('click')();
    assert.equal(f.doc.webkitFullscreenElement, null);
    assert.equal(root.classList.contains('ll-room-expanded'), false);
});

test('leaving an expanded mobile call restores the page without turning devices on', async () => {
    const f = roomFixture({ fullscreen: 'missing' });
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    await f.elements.get('ll-room-fullscreen').listeners.get('click')();
    f.elements.get('ll-room-leave').listeners.get('click')();
    await new Promise(setImmediate);
    assert.equal(f.doc.body.classList.contains('ll-room-scroll-locked'), false);
    assert.equal(f.roomRoot.classList.contains('ll-room-window-expanded'), false);
    assert.equal(f.elements.get('ll-room-join').disabled, false);
    assert.equal(f.elements.get('ll-room-mic').getAttribute('aria-pressed'), 'false');
});

test('Escape restores the normal mobile layout and scrolling', async () => {
    const f = roomFixture({ fullscreen: 'missing' });
    const button = f.elements.get('ll-room-fullscreen');
    await button.listeners.get('click')();
    f.documentListeners.get('keydown')({ key: 'Escape' });
    assert.equal(f.elements.get('ll-room').classList.contains('ll-room-window-expanded'), false);
    assert.equal(f.doc.body.classList.contains('ll-room-scroll-locked'), false);
    assert.equal(button.querySelector('span').textContent, 'Развернуть');
});

test('stopping an expanded screen removes the mobile overlay and restores scrolling', async () => {
    const f = roomFixture({ fullscreen: 'missing' });
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const participant = { identity: 'student', name: 'Ученик', trackPublications: new Map() };
    const track = { kind: 'video', attach: () => f.makeElement('video'), detach: () => [] };
    const publication = { trackSid: 'screen-1', source: 'screen' };
    f.getRoom().remoteParticipants.set(participant.identity, participant);
    f.getRoom().emit('TrackSubscribed', track, publication, participant);
    const figure = f.elements.get('ll-room-tracks').children.find((tile) => tile.dataset.source === 'screen');
    await figure.expandButton.listeners.get('click')();
    f.getRoom().emit('TrackUnsubscribed', track, publication, participant);
    assert.equal(figure.parentElement, null);
    assert.equal(f.elements.get('ll-room').classList.contains('ll-room-window-expanded'), false);
    assert.equal(f.doc.body.classList.contains('ll-room-scroll-locked'), false);
});

test('lesson end and page replacement both clean up mobile expansion', async () => {
    for (const removePage of [false, true]) {
        const f = roomFixture({ fullscreen: 'missing' });
        await f.elements.get('ll-room-fullscreen').listeners.get('click')();
        if (removePage) {
            f.elements.delete('ll-room');
            f.windowListeners.get('ll-page-updated')();
        } else {
            const pending = [];
            f.windowListeners.get('ll-lesson-state')({ detail: {
                state: { status: 'ended', can_join: false }, waitUntil: (promise) => pending.push(promise),
            } });
            await Promise.all(pending);
        }
        assert.equal(f.doc.body.classList.contains('ll-room-scroll-locked'), false);
        assert.equal(f.roomRoot.classList.contains('ll-room-window-expanded'), false);
    }
});

test('late native fullscreen completion cannot reopen a removed screen', async () => {
    const f = roomFixture();
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const figure = f.elements.get('ll-room-tracks').children[0];
    let complete;
    figure.requestFullscreen = () => new Promise((resolve) => { complete = resolve; });
    const opening = figure.expandButton.listeners.get('click')();
    f.getRoom().emit('ParticipantDisconnected', f.getRoom().localParticipant);
    f.doc.fullscreenElement = figure;
    complete();
    await opening;
    assert.equal(f.doc.fullscreenElement, null);
    assert.equal(f.doc.body.classList.contains('ll-room-scroll-locked'), false);
});

test('slow-network connect keeps server ICE candidates and gives ICE more time', async () => {
    const f = roomFixture();
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    assert.equal(f.getRoom().connectOptions.peerConnectionTimeout, 30000);
    assert.equal(f.getRoom().connectOptions.websocketTimeout, 20000);
    assert.equal(f.getRoom().connectOptions.maxRetries, 2);
    assert.equal(f.getRoom().connectOptions.rtcConfig, undefined);
});

test('VPN transport failure is explained in Russian and allows another join', async () => {
    const f = roomFixture({ connectError: new Error('could not establish pc connection') });
    f.elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    assert.match(f.elements.get('ll-room-error').textContent, /VPN/);
    assert.doesNotMatch(f.elements.get('ll-room-error').textContent, /could not establish/);
    assert.equal(f.elements.get('ll-room-join').disabled, false);
    assert.equal(f.getRoom().state, 'disconnected');
});

test('canceling the screen picker is silent and leaves screen sharing available', async () => {
    const { elements, getRoom } = roomFixture();
    elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    getRoom().localParticipant.setScreenShareEnabled = async () => {
        const error = new Error('Permission denied');
        error.name = 'NotAllowedError';
        throw error;
    };

    elements.get('ll-room-screen').listeners.get('click')();
    await new Promise(setImmediate);

    assert.equal(elements.get('ll-room-error').hidden, true);
    assert.equal(elements.get('ll-room-error').textContent, '');
    assert.equal(elements.get('ll-room-screen').disabled, false);
    assert.equal(elements.get('ll-room-screen').getAttribute('aria-pressed'), 'false');
});

test('other screen errors and microphone permission errors remain visible', async () => {
    const { elements, getRoom } = roomFixture();
    elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    getRoom().localParticipant.setScreenShareEnabled = async () => {
        throw new Error('Медиасервер недоступен');
    };

    elements.get('ll-room-screen').listeners.get('click')();
    await new Promise(setImmediate);
    assert.equal(elements.get('ll-room-error').hidden, false);
    assert.equal(elements.get('ll-room-error').textContent, 'Медиасервер недоступен');

    getRoom().localParticipant.setMicrophoneEnabled = async () => {
        const error = new Error('Permission denied');
        error.name = 'NotAllowedError';
        throw error;
    };
    elements.get('ll-room-mic').listeners.get('click')();
    await new Promise(setImmediate);
    assert.match(elements.get('ll-room-error').textContent, /Браузер не разрешил доступ/);
});
