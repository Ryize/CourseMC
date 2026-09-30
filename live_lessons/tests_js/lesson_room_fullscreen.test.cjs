const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../static/live_lessons/lesson_room.js'), 'utf8');

function roomFixture({ teacher = false, supportsNoiseSuppression = true,
    supportsVoiceEnhancement = true, savedPreferences = null } = {}) {
    const elements = new Map();
    const documentListeners = new Map();
    const requests = [];
    const timers = new Map();
    let nextTimerId = 0;
    const storage = new Map();
    if (savedPreferences) storage.set('coursemc:live-room-screen:v1', JSON.stringify(savedPreferences));
    let latestRoom = null;
    const doc = {
        fullscreenElement: null,
        getElementById: (id) => elements.get(id),
        addEventListener(type, callback) { documentListeners.set(type, callback); },
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
                doc.fullscreenElement = this;
                documentListeners.get('fullscreenchange')();
                return Promise.resolve();
            },
        };
        element.classList = {
            contains(name) { return element.className.split(/\s+/).includes(name); },
            toggle(name, force) {
                const names = new Set(element.className.split(/\s+/).filter(Boolean));
                if (force) names.add(name); else names.delete(name);
                element.className = [...names].join(' ');
            },
            add(name) { element.className += ` ${name}`; },
        };
        return element;
    }
    doc.createElement = makeElement;
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
    ]) elements.set(id, makeElement());
    elements.get('ll-room-reactions-menu').hidden = true;
    for (const reaction of ['hand', 'like', 'check', 'cross', 'fire']) {
        const button = makeElement('button');
        button.dataset.reaction = reaction;
        elements.get('ll-room-reactions-menu').appendChild(button);
    }
    elements.get('ll-room').dataset = { tokenUrl: '/token/', stateUrl: '/state/',
        ...(teacher ? { moderateUrl: '/moderate/' } : {}) };
    elements.get('ll-room-quality').value = '1080';
    elements.get('ll-room-fps').value = '30';
    elements.get('ll-room-mic-volume').value = '100';
    elements.get('ll-room-speaker-volume').value = '100';
    elements.get('ll-room-noise-suppression').checked = true;
    elements.get('ll-room-voice-enhancement').checked = true;
    const track = { kind: 'video', attach: () => makeElement('video') };
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
        async connect() {}
        getActiveDevice() { return ''; }
    }
    MockRoom.getLocalDevices = async () => [];
    const sdk = {
        Room: MockRoom, RoomEvent: Object.fromEntries([
            'TrackSubscribed', 'TrackUnsubscribed', 'LocalTrackPublished', 'LocalTrackUnpublished',
            'ParticipantConnected', 'ParticipantDisconnected', 'TrackPublished', 'TrackUnpublished',
            'TrackMuted', 'TrackUnmuted', 'ActiveSpeakersChanged', 'MediaDevicesChanged',
            'AudioPlaybackStatusChanged', 'DataReceived', 'Reconnecting', 'Reconnected', 'Disconnected',
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
            LivekitClient: sdk, addEventListener() {}, dispatchEvent() {}, confirm: () => true,
            navigator: { mediaDevices: { getSupportedConstraints: () =>
                ({ ...(supportsNoiseSuppression ? { noiseSuppression: true } : {}),
                    ...(supportsVoiceEnhancement ? { autoGainControl: true, echoCancellation: true } : {}) }) } },
            localStorage: { getItem: (key) => storage.get(key) || null,
                setItem(key, value) { storage.set(key, value); } },
            setInterval: () => 1,
            setTimeout(callback) { const id = ++nextTimerId; timers.set(id, callback); return id; },
            clearTimeout(id) { timers.delete(id); },
        },
        Event: class {}, CustomEvent: class {},
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
    for (const id of ['ll-room-audio-input', 'll-room-video-input']) {
        elements.get(id).add = () => {};
    }
    vm.runInNewContext(source, context);
    return { elements, doc, requests, storage, timers, getRoom: () => latestRoom };
}

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

test('all five local reactions are broadcast and briefly appear beside the avatar', async () => {
    const { elements, getRoom, timers } = roomFixture();
    const toggle = elements.get('ll-room-reactions-toggle');
    const menu = elements.get('ll-room-reactions-menu');
    assert.equal(toggle.disabled, true);
    elements.get('ll-room-join').listeners.get('click')();
    await new Promise(setImmediate);
    const room = getRoom();
    assert.equal(toggle.disabled, false);
    const expected = [['hand', '✋'], ['like', '👍'], ['check', '✅'], ['cross', '❌'], ['fire', '🔥']];
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
    assert.equal(room.sentData.length, 5);
    assert.equal(timers.size, 1);
    for (const callback of timers.values()) callback();
    assert.equal(avatarFor(elements, room.localParticipant.identity).badge.hidden, true);
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

    const camera = { kind: 'video', attach: () => ({}), detach() {} };
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
