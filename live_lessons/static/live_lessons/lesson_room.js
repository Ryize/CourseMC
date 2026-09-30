(() => {
    'use strict';

    const root = document.getElementById('ll-room');
    if (!root) return;

    const sdk = window.LivekitClient;
    const byId = (id) => document.getElementById(id);
    const ui = {
        state: byId('ll-room-state'), error: byId('ll-room-error'),
        join: byId('ll-room-join'), leave: byId('ll-room-leave'), unlock: byId('ll-room-unlock'),
        lobby: byId('ll-room-lobby'), mic: byId('ll-room-mic'), camera: byId('ll-room-camera'),
        screen: byId('ll-room-screen'), quality: byId('ll-room-quality'), fps: byId('ll-room-fps'),
        micVolume: byId('ll-room-mic-volume'), micVolumeValue: byId('ll-room-mic-volume-value'),
        noiseSuppression: byId('ll-room-noise-suppression'),
        voiceEnhancement: byId('ll-room-voice-enhancement'),
        speakerVolume: byId('ll-room-speaker-volume'), speakerVolumeValue: byId('ll-room-speaker-volume-value'),
        audioInput: byId('ll-room-audio-input'), videoInput: byId('ll-room-video-input'),
        count: byId('ll-room-count'), members: byId('ll-room-members'),
        tracks: byId('ll-room-tracks'), empty: byId('ll-room-empty'), audio: byId('ll-room-audio'),
        settings: byId('ll-room-settings'), settingsToggle: byId('ll-room-settings-toggle'),
        settingsClose: byId('ll-room-settings-close'), actual: byId('ll-room-actual'),
        workspace: byId('ll-room-workspace'), sidebar: byId('ll-room-sidebar'),
        sidebarTitle: byId('ll-room-sidebar-title'), sidebarClose: byId('ll-room-sidebar-close'),
        membersToggle: byId('ll-room-members-toggle'), chatToggle: byId('ll-room-chat-toggle'),
        reactionsToggle: byId('ll-room-reactions-toggle'), reactionsMenu: byId('ll-room-reactions-menu'),
        membersPanel: byId('ll-room-members-panel'), chatPanel: byId('ll-room-chat-panel'),
        fullscreen: byId('ll-room-fullscreen'),
    };
    let room = null;
    let busy = false;
    let closed = false;
    let stateTimer = null;
    const videoElements = new Map();
    const audioElements = new Map();
    const avatarTiles = new Map();
    const reactionTargets = new Map();
    const reactions = new Map();
    const reactionOptions = Object.freeze({
        hand: ['✋', 'Поднял руку'], like: ['👍', 'Лайк'], check: ['✅', 'Галочка'],
        cross: ['❌', 'Крестик'], fire: ['🔥', 'Огонь'],
    });
    const reactionTopic = 'lesson-reaction';
    const reactionDurationMs = 5000;
    let microphoneProcessor = null;
    let microphoneProcessorTrack = null;
    const audioConstraintsSupported = window.navigator?.mediaDevices?.getSupportedConstraints?.() || {};
    const noiseSuppressionSupported = !!audioConstraintsSupported.noiseSuppression;
    const voiceEnhancementSupported = !!(audioConstraintsSupported.autoGainControl || audioConstraintsSupported.echoCancellation);
    let noiseSuppressionPreference = true;
    let voiceEnhancementPreference = true;
    let applyingAudioSettings = false;
    const qualitySizes = Object.freeze({
        '2k': [2560, 1440], '1080': [1920, 1080], '720': [1280, 720],
        '480': [854, 480], '360': [640, 360],
    });
    const allowedFps = new Set([15, 30, 60]);
    const preferencesKey = 'coursemc:live-room-screen:v1';

    function showError(value) {
        ui.error.textContent = value || '';
        ui.error.hidden = !value;
    }

    function setState(label, kind) {
        ui.state.textContent = label;
        ui.state.dataset.state = kind;
    }

    function errorText(error) {
        if (['NotAllowedError', 'PermissionDeniedError', 'SecurityError'].includes(error?.name)) {
            return 'Браузер не разрешил доступ к устройству или экрану. Проверьте разрешения сайта.';
        }
        if (error?.name === 'NotFoundError') return 'Устройство не найдено. Проверьте его подключение.';
        return error?.message || 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.';
    }

    function isScreenShareCancellation(error) {
        let reason = error;
        for (let depth = 0; reason && depth < 3; depth += 1) {
            if (['NotAllowedError', 'PermissionDeniedError', 'AbortError'].includes(reason.name)) return true;
            reason = reason.cause;
        }
        return false;
    }

    function isConnected() {
        return !!sdk && room?.state === sdk.ConnectionState.Connected;
    }

    function updateButtons() {
        const active = isConnected();
        root.dataset.connected = String(active);
        ui.lobby.hidden = active;
        ui.join.disabled = !!room || busy || closed;
        ui.join.textContent = busy && !active ? 'Подключаем…' : 'Войти в комнату';
        ui.leave.disabled = !active || busy;
        ui.chatToggle.disabled = !active || busy;
        ui.chatToggle.title = active ? 'Открыть чат занятия' : 'Чат доступен после входа в комнату';
        if (!active && !ui.sidebar.hidden && ui.sidebar.dataset.tab === 'chat') toggleSidebar('chat');
        for (const button of [ui.mic, ui.camera, ui.screen]) button.disabled = !active || busy;
        ui.reactionsToggle.disabled = !active || busy;
        if (!active || busy) closeReactions();
        ui.audioInput.disabled = !active || busy;
        ui.videoInput.disabled = !active || busy;
        const participant = room?.localParticipant;
        const micOn = !!participant?.isMicrophoneEnabled;
        const cameraOn = !!participant?.isCameraEnabled;
        const screenOn = !!participant?.isScreenShareEnabled;
        ui.mic.setAttribute('aria-pressed', String(micOn));
        ui.camera.setAttribute('aria-pressed', String(cameraOn));
        ui.screen.setAttribute('aria-pressed', String(screenOn));
        ui.mic.setAttribute('aria-label', micOn ? 'Выключить микрофон' : 'Включить микрофон');
        ui.camera.setAttribute('aria-label', cameraOn ? 'Выключить камеру' : 'Включить камеру');
        ui.screen.setAttribute('aria-label', screenOn ? 'Остановить демонстрацию' : 'Показать экран');
        ui.screen.querySelector('.ll-room-control-label').textContent = screenOn ? 'Остановить экран' : 'Демонстрация';
        ui.quality.disabled = busy;
        ui.fps.disabled = busy;
        updateEmpty();
    }

    function trackKey(participant, publication) {
        return `${participant.identity}:${publication.trackSid}`;
    }

    function updateEmpty() {
        ui.empty.hidden = !isConnected() || videoElements.size > 0 || avatarTiles.size > 0;
        ui.tracks.classList.toggle('ll-room-tracks-with-screen',
            [...videoElements.values()].some(({ figure }) => figure.classList.contains('ll-room-tile-screen')));
    }

    function participantName(participant) {
        return participant.isLocal ? 'Вы' : (participant.name || participant.identity || 'Участник');
    }

    function createAvatar(participant) {
        const wrap = document.createElement('div');
        wrap.className = 'll-room-tile-avatar-wrap';
        const mark = document.createElement('span');
        mark.className = 'll-room-tile-avatar-mark';
        mark.textContent = (participant.name || participant.identity || 'У').trim().charAt(0).toLocaleUpperCase() || 'У';
        const badge = document.createElement('span');
        badge.className = 'll-room-reaction-badge';
        badge.dataset.name = participantName(participant);
        badge.setAttribute('role', 'status');
        badge.setAttribute('aria-live', 'polite');
        wrap.append(mark, badge);
        renderReaction(participant.identity, badge);
        return { wrap, badge };
    }

    function renderReaction(identity, badge = reactionTargets.get(identity)) {
        if (!badge) return;
        const option = reactionOptions[reactions.get(identity)?.key];
        badge.hidden = !option;
        badge.textContent = option?.[0] || '';
        if (option) badge.setAttribute('aria-label', `${badge.dataset.name}: ${option[1]}`);
    }

    function showReaction(identity, key) {
        if (!Object.prototype.hasOwnProperty.call(reactionOptions, key)) return;
        const previous = reactions.get(identity);
        if (previous) window.clearTimeout(previous.timer);
        const timer = window.setTimeout(() => {
            reactions.delete(identity);
            renderReaction(identity);
        }, reactionDurationMs);
        reactions.set(identity, { key, timer });
        renderReaction(identity);
    }

    function closeReactions() {
        ui.reactionsMenu.hidden = true;
        ui.reactionsToggle.setAttribute('aria-expanded', 'false');
    }

    async function sendReaction(key) {
        if (!isConnected() || !Object.prototype.hasOwnProperty.call(reactionOptions, key)) return;
        closeReactions();
        const activeRoom = room;
        try {
            await activeRoom.localParticipant.publishData(new TextEncoder().encode(key), {
                reliable: false, topic: reactionTopic,
            });
            if (room === activeRoom) showReaction(activeRoom.localParticipant.identity, key);
        } catch (error) {
            showError(`Не удалось отправить реакцию: ${errorText(error)}`);
        }
    }

    function removeAvatarTile(identity) {
        const tile = avatarTiles.get(identity);
        if (!tile) return;
        tile.figure.remove();
        avatarTiles.delete(identity);
        if (reactionTargets.get(identity) === tile.badge) reactionTargets.delete(identity);
    }

    function ensureAvatarTile(participant) {
        if (avatarTiles.has(participant.identity)) return;
        const figure = document.createElement('figure');
        figure.className = 'll-room-tile ll-room-tile-avatar';
        figure.dataset.identity = participant.identity;
        const { wrap, badge } = createAvatar(participant);
        const caption = document.createElement('figcaption');
        caption.textContent = participantName(participant);
        figure.append(wrap, caption);
        ui.tracks.appendChild(figure);
        avatarTiles.set(participant.identity, { figure, badge });
        reactionTargets.set(participant.identity, badge);
        updateEmpty();
    }

    function syncAvatarTiles() {
        if (!room) return;
        const people = [room.localParticipant, ...room.remoteParticipants.values()];
        const identities = new Set(people.map((participant) => participant.identity));
        for (const identity of avatarTiles.keys()) {
            if (!identities.has(identity)) removeAvatarTile(identity);
        }
        for (const participant of people) {
            const hasCamera = [...videoElements.values()].some((video) =>
                !video.isScreen && video.participantIdentity === participant.identity);
            if (hasCamera) removeAvatarTile(participant.identity);
            else ensureAvatarTile(participant);
        }
        updateEmpty();
    }

    function attachTrack(track, publication, participant) {
        const key = trackKey(participant, publication);
        if (track.kind === sdk.Track.Kind.Audio) {
            if (participant.isLocal || audioElements.has(key)) return;
            const element = track.attach();
            element.autoplay = true;
            if (typeof track.setVolume === 'function') track.setVolume(Number(ui.speakerVolume.value) / 100);
            else element.volume = Number(ui.speakerVolume.value) / 100;
            ui.audio.appendChild(element);
            audioElements.set(key, { track, element });
            return;
        }
        if (track.kind !== sdk.Track.Kind.Video || videoElements.has(key)) return;
        const figure = document.createElement('figure');
        const isScreen = publication.source === sdk.Track.Source.ScreenShare;
        figure.className = isScreen ? 'll-room-tile ll-room-tile-screen' :
            `ll-room-tile ll-room-tile-avatar${publication.isMuted ? '' : ' ll-room-tile-has-video'}`;
        figure.dataset.identity = participant.identity;
        const element = track.attach();
        element.autoplay = true;
        element.playsInline = true;
        element.muted = !!participant.isLocal;
        const caption = document.createElement('figcaption');
        const name = participantName(participant);
        caption.textContent = `${name}${isScreen ? ' · экран' : ' · камера'}`;
        const expand = document.createElement('button');
        expand.className = 'll-room-expand';
        expand.type = 'button';
        expand.textContent = 'На весь экран';
        expand.title = 'На весь экран';
        expand.setAttribute('aria-pressed', 'false');
        expand.setAttribute('aria-label', `Показать на весь экран: ${caption.textContent}`);
        expand.addEventListener('click', async () => {
            try {
                if (document.fullscreenElement === figure) await document.exitFullscreen();
                else if (figure.requestFullscreen) await figure.requestFullscreen();
            } catch (error) { showError(errorText(error)); }
        });
        if (isScreen) figure.append(element, caption, expand);
        else {
            const { wrap, badge } = createAvatar(participant);
            figure.append(element, wrap, caption, expand);
            removeAvatarTile(participant.identity);
            reactionTargets.set(participant.identity, badge);
        }
        ui.tracks.appendChild(figure);
        videoElements.set(key, { track, element, figure, expand, caption,
            participantIdentity: participant.identity, isScreen });
        updateEmpty();
    }

    function detachTrack(publication, participant) {
        const key = trackKey(participant, publication);
        const video = videoElements.get(key);
        if (video) {
            video.track.detach(video.element);
            video.figure.remove();
            videoElements.delete(key);
            if (!video.isScreen) reactionTargets.delete(video.participantIdentity);
        }
        const audio = audioElements.get(key);
        if (audio) {
            audio.track.detach(audio.element);
            audio.element.remove();
            audioElements.delete(key);
        }
        syncAvatarTiles();
        updateEmpty();
    }

    function detachParticipant(participant) {
        const prefix = `${participant.identity}:`;
        for (const [key, video] of videoElements) {
            if (!key.startsWith(prefix)) continue;
            video.track.detach(video.element);
            video.figure.remove();
            videoElements.delete(key);
            if (!video.isScreen) reactionTargets.delete(video.participantIdentity);
        }
        for (const [key, audio] of audioElements) {
            if (!key.startsWith(prefix)) continue;
            audio.track.detach(audio.element);
            audio.element.remove();
            audioElements.delete(key);
        }
        removeAvatarTile(participant.identity);
        const reaction = reactions.get(participant.identity);
        if (reaction) window.clearTimeout(reaction.timer);
        reactions.delete(participant.identity);
        updateEmpty();
    }

    function clearTracks() {
        for (const { track, element, figure } of videoElements.values()) {
            track.detach(element);
            figure.remove();
        }
        for (const { track, element } of audioElements.values()) {
            track.detach(element);
            element.remove();
        }
        videoElements.clear();
        audioElements.clear();
        for (const tile of avatarTiles.values()) tile.figure.remove();
        avatarTiles.clear();
        reactionTargets.clear();
        for (const reaction of reactions.values()) window.clearTimeout(reaction.timer);
        reactions.clear();
        microphoneProcessor = null;
        microphoneProcessorTrack = null;
        updateEmpty();
    }

    function createMicrophoneProcessor(gain) {
        return {
            name: 'coursemc-microphone-gain', processedTrack: undefined,
            source: null, gainNode: null, destination: null,
            async init({ track, audioContext }) {
                this.source = audioContext.createMediaStreamSource(new MediaStream([track]));
                this.gainNode = audioContext.createGain();
                this.gainNode.gain.value = gain;
                this.destination = audioContext.createMediaStreamDestination();
                this.source.connect(this.gainNode);
                this.gainNode.connect(this.destination);
                this.processedTrack = this.destination.stream.getAudioTracks()[0];
            },
            async restart(options) { await this.destroy(); await this.init(options); },
            async destroy() {
                this.source?.disconnect();
                this.gainNode?.disconnect();
                this.destination?.disconnect();
                this.processedTrack = undefined;
            },
            setGain(value) {
                if (this.gainNode) this.gainNode.gain.value = value;
            },
        };
    }

    function microphoneTrack() {
        const publication = [...(room?.localParticipant.trackPublications.values() || [])].find(
            (item) => item.source === sdk.Track.Source.Microphone && item.track,
        );
        return publication?.track;
    }

    function audioCaptureOptions() {
        return {
            ...(audioConstraintsSupported.echoCancellation ? { echoCancellation: ui.voiceEnhancement.checked } : {}),
            ...(noiseSuppressionSupported ? { noiseSuppression: ui.noiseSuppression.checked } : {}),
            ...(audioConstraintsSupported.autoGainControl ? { autoGainControl: ui.voiceEnhancement.checked } : {}),
        };
    }

    async function applyAudioSettings(track) {
        if (!track || track.isMuted) return;
        const options = audioCaptureOptions();
        if (!Object.keys(options).length) return;
        if (typeof track.applyConstraints !== 'function') {
            throw new Error('Ваш браузер не позволяет менять настройки звука во время звонка.');
        }
        const currentConstraints = track.mediaStreamTrack?.getConstraints?.() || {};
        await track.applyConstraints({ ...currentConstraints, ...options });
        const actual = track.mediaStreamTrack?.getSettings?.();
        for (const [name, enabled] of Object.entries(options)) {
            if (typeof actual?.[name] === 'boolean' && actual[name] !== enabled) {
                throw new Error('Микрофон не применил выбранную настройку звука.');
            }
        }
    }

    async function changeAudioSetting(kind) {
        if (applyingAudioSettings) return;
        const noise = kind === 'noise';
        const input = noise ? ui.noiseSuppression : ui.voiceEnhancement;
        const previous = noise ? noiseSuppressionPreference : voiceEnhancementPreference;
        if (input.checked === previous) return;
        applyingAudioSettings = true;
        ui.noiseSuppression.disabled = true;
        ui.voiceEnhancement.disabled = true;
        showError('');
        try {
            await applyAudioSettings(microphoneTrack());
            if (noise) noiseSuppressionPreference = input.checked;
            else voiceEnhancementPreference = input.checked;
            savePreferences();
        } catch (error) {
            input.checked = previous;
            await applyAudioSettings(microphoneTrack()).catch(() => {});
            showError(`Не удалось изменить ${noise ? 'шумоподавление' : 'улучшение голоса'}: ${errorText(error)}`);
        } finally {
            applyingAudioSettings = false;
            ui.noiseSuppression.disabled = !noiseSuppressionSupported;
            ui.voiceEnhancement.disabled = !voiceEnhancementSupported;
        }
    }

    async function applyMicrophoneGain() {
        const track = microphoneTrack();
        if (!track || typeof track.setProcessor !== 'function') return;
        if (microphoneProcessorTrack === track) {
            microphoneProcessor?.setGain(Number(ui.micVolume.value) / 100);
            return;
        }
        const processor = createMicrophoneProcessor(Number(ui.micVolume.value) / 100);
        microphoneProcessorTrack = track;
        try {
            await track.setProcessor(processor);
            microphoneProcessor = processor;
        } catch (error) {
            microphoneProcessorTrack = null;
            showError(`Не удалось настроить громкость микрофона: ${errorText(error)}`);
        }
    }

    function updateVolume() {
        ui.micVolumeValue.value = `${ui.micVolume.value}%`;
        ui.speakerVolumeValue.value = `${ui.speakerVolume.value}%`;
        microphoneProcessor?.setGain(Number(ui.micVolume.value) / 100);
        for (const { track, element } of audioElements.values()) {
            if (typeof track.setVolume === 'function') track.setVolume(Number(ui.speakerVolume.value) / 100);
            else element.volume = Number(ui.speakerVolume.value) / 100;
        }
        savePreferences();
    }

    async function moderateParticipant(identity, action, button) {
        if (!isConnected() || !root.dataset.moderateUrl || !room.remoteParticipants.has(identity)) return;
        if (action === 'remove' && !window.confirm('Удалить участника с занятия? Повторный вход для этого аккаунта или гостевой сессии будет закрыт.')) return;
        button.disabled = true;
        showError('');
        try {
            const body = new FormData();
            body.set('identity', identity);
            body.set('action', action);
            body.set('csrfmiddlewaretoken', root.querySelector('[name=csrfmiddlewaretoken]').value);
            const response = await fetch(root.dataset.moderateUrl, {
                method: 'POST', credentials: 'same-origin', cache: 'no-store',
                body, headers: { Accept: 'application/json' },
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Не удалось выполнить действие.');
            if (action === 'mute') updateMembers();
        } catch (error) { showError(errorText(error)); }
        finally { button.disabled = false; }
    }

    function updateMembers() {
        ui.members.replaceChildren();
        if (!room) {
            ui.count.textContent = 'Участники';
            return;
        }
        const people = [room.localParticipant, ...room.remoteParticipants.values()];
        const lastTwo = people.length % 100;
        const last = people.length % 10;
        const word = lastTwo >= 11 && lastTwo <= 14 ? 'участников' :
            (last === 1 ? 'участник' : (last >= 2 && last <= 4 ? 'участника' : 'участников'));
        ui.count.textContent = `${people.length} ${word}`;
        for (const participant of people) {
            const item = document.createElement('li');
            const name = document.createElement('span');
            name.className = 'll-room-member-name';
            name.textContent = participant.isLocal ? 'Вы' : (participant.name || participant.identity || 'Участник');
            item.appendChild(name);
            item.dataset.identity = participant.identity;
            if (participant.isSpeaking) item.classList.add('ll-room-member-speaking');
            if (root.dataset.moderateUrl && !participant.isLocal) {
                const actions = document.createElement('span');
                actions.className = 'll-room-member-actions';
                const microphone = [...participant.trackPublications.values()].find(
                    (publication) => publication.source === sdk.Track.Source.Microphone && !publication.isMuted,
                );
                const mute = document.createElement('button');
                mute.type = 'button';
                mute.className = 'll-room-member-action';
                mute.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5m-4 0h8M3 3l18 18"/></svg>';
                mute.title = 'Выключить микрофон участника';
                mute.setAttribute('aria-label', `Выключить микрофон: ${name.textContent}`);
                mute.disabled = !microphone;
                mute.addEventListener('click', () => { void moderateParticipant(participant.identity, 'mute', mute); });
                const remove = document.createElement('button');
                remove.type = 'button';
                remove.className = 'll-room-member-action ll-room-member-remove';
                remove.textContent = '×';
                remove.title = 'Удалить со встречи';
                remove.setAttribute('aria-label', `Удалить со встречи: ${name.textContent}`);
                remove.addEventListener('click', () => { void moderateParticipant(participant.identity, 'remove', remove); });
                actions.append(mute, remove);
                item.appendChild(actions);
            }
            ui.members.appendChild(item);
        }
        syncAvatarTiles();
    }

    function updateSpeakers(people) {
        const speaking = new Set(people.map((participant) => participant.identity));
        for (const item of ui.members.children) {
            item.classList.toggle('ll-room-member-speaking', speaking.has(item.dataset.identity));
        }
        for (const [key, { figure }] of videoElements) {
            figure.classList.toggle('ll-room-tile-speaking', speaking.has(key.split(':')[0]));
        }
        for (const [identity, { figure }] of avatarTiles) {
            figure.classList.toggle('ll-room-tile-speaking', speaking.has(identity));
        }
    }

    function updateActualScreen(publication) {
        if (publication?.source !== sdk.Track.Source.ScreenShare || !publication.track) return;
        const settings = publication.track.mediaStreamTrack?.getSettings?.();
        const size = settings?.width && settings?.height ? `${settings.width} × ${settings.height}` : 'не определено';
        const fps = settings?.frameRate ? ` · ${Math.round(settings.frameRate)} кадр/с` : '';
        ui.actual.textContent = `Источник экрана: ${size}${fps}. У зрителей качество может отличаться.`;
    }

    function showExistingTracks(activeRoom) {
        for (const publication of activeRoom.localParticipant.trackPublications.values()) {
            if (publication.track) attachTrack(publication.track, publication, activeRoom.localParticipant);
        }
        for (const participant of activeRoom.remoteParticipants.values()) {
            for (const publication of participant.trackPublications.values()) {
                if (publication.track) attachTrack(publication.track, publication, participant);
            }
        }
    }

    async function refreshDevices() {
        if (!room || !sdk) return;
        const activeRoom = room;
        for (const [kind, select, fallback] of [
            ['audioinput', ui.audioInput, 'Микрофон'], ['videoinput', ui.videoInput, 'Камера'],
        ]) {
            try {
                const selected = activeRoom.getActiveDevice(kind) || select.value;
                const devices = await sdk.Room.getLocalDevices(kind, false);
                if (room !== activeRoom) return;
                select.replaceChildren(new Option('По умолчанию', ''));
                devices.forEach((device, index) => {
                    select.add(new Option(device.label || `${fallback} ${index + 1}`, device.deviceId));
                });
                select.value = devices.some((device) => device.deviceId === selected) ? selected : '';
            } catch (_) { /* Отсутствие списка устройств не прерывает урок. */ }
        }
    }

    function resetConnection() {
        if (stateTimer) window.clearInterval(stateTimer);
        stateTimer = null;
        clearTracks();
        room = null;
        window.dispatchEvent(new CustomEvent('ll-livekit-room', { detail: { room: null } }));
        busy = false;
        ui.unlock.hidden = true;
        ui.members.replaceChildren();
        ui.count.textContent = 'Участники';
        ui.actual.textContent = '';
        setState('Не подключено', 'idle');
        updateButtons();
    }

    async function checkRemovalAfterDisconnect() {
        try {
            const response = await fetch(root.dataset.stateUrl, {
                credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' },
            });
            if (response.ok && (await response.json()).removed) {
                closed = true;
                setState('Вы удалены', 'error');
                showError('Преподаватель удалил вас из этого занятия.');
                updateButtons();
            }
        } catch (_) { /* При потере сети оставляем возможность подключиться повторно. */ }
    }

    function registerEvents(activeRoom) {
        const event = sdk.RoomEvent;
        activeRoom.on(event.TrackSubscribed, (track, publication, participant) => attachTrack(track, publication, participant));
        activeRoom.on(event.TrackUnsubscribed, (_track, publication, participant) => detachTrack(publication, participant));
        activeRoom.on(event.LocalTrackPublished, (publication) => {
            if (publication.track) attachTrack(publication.track, publication, activeRoom.localParticipant);
            if (publication.source === sdk.Track.Source.Microphone) void applyMicrophoneGain();
            updateActualScreen(publication);
            updateButtons();
        });
        activeRoom.on(event.LocalTrackUnpublished, (publication) => {
            detachTrack(publication, activeRoom.localParticipant);
            if (publication.source === sdk.Track.Source.Microphone) {
                microphoneProcessor = null;
                microphoneProcessorTrack = null;
            }
            if (publication.source === sdk.Track.Source.ScreenShare) ui.actual.textContent = '';
            updateButtons();
        });
        activeRoom.on(event.ParticipantConnected, updateMembers);
        activeRoom.on(event.TrackPublished, updateMembers);
        activeRoom.on(event.TrackUnpublished, updateMembers);
        const onTrackMuteChanged = (publication, participant) => {
            if (publication?.source === sdk.Track.Source.Camera && participant) {
                const video = videoElements.get(trackKey(participant, publication));
                video?.figure.classList.toggle('ll-room-tile-has-video', !publication.isMuted);
            }
            updateMembers();
            updateButtons();
        };
        activeRoom.on(event.TrackMuted, onTrackMuteChanged);
        activeRoom.on(event.TrackUnmuted, onTrackMuteChanged);
        activeRoom.on(event.ParticipantDisconnected, (participant) => {
            detachParticipant(participant);
            updateMembers();
        });
        activeRoom.on(event.ActiveSpeakersChanged, updateSpeakers);
        activeRoom.on(event.MediaDevicesChanged, () => { void refreshDevices(); });
        activeRoom.on(event.AudioPlaybackStatusChanged, () => {
            ui.unlock.hidden = activeRoom.canPlaybackAudio;
        });
        activeRoom.on(event.DataReceived, (payload, participant, _kind, topic) => {
            if (topic === 'lesson-chat-updated') window.dispatchEvent(new Event('ll-chat-update'));
            if (topic === reactionTopic && participant?.identity &&
                activeRoom.remoteParticipants.has(participant.identity) && payload?.length <= 16) {
                showReaction(participant.identity, new TextDecoder().decode(payload));
            }
        });
        activeRoom.on(event.Reconnecting, () => setState('Переподключение', 'connecting'));
        activeRoom.on(event.Reconnected, () => {
            setState('Подключено', 'connected');
            updateButtons();
        });
        activeRoom.on(event.Disconnected, () => {
            if (room === activeRoom) {
                const unexpectedlyDisconnected = !busy;
                resetConnection();
                if (unexpectedlyDisconnected) void checkRemovalAfterDisconnect();
            }
        });
    }

    function screenOptions() {
        const [width, height] = qualitySizes[ui.quality.value] || qualitySizes['1080'];
        const chosenFps = Number(ui.fps.value);
        const frameRate = allowedFps.has(chosenFps) ? chosenFps : 30;
        const bitsPerSecondAt30 = {
            '2k': 8000000, '1080': 5000000, '720': 2800000,
            '480': 1300000, '360': 800000,
        };
        const base = bitsPerSecondAt30[ui.quality.value] || bitsPerSecondAt30['1080'];
        const maxBitrate = Math.round(base * (frameRate === 15 ? 0.7 : frameRate === 60 ? 1.6 : 1));
        return {
            capture: { contentHint: frameRate === 60 ? 'motion' : 'detail',
                resolution: { width, height, frameRate } },
            publish: { screenShareEncoding: { maxBitrate, maxFramerate: frameRate },
                degradationPreference: frameRate === 60 ? 'balanced' : 'maintain-resolution' },
        };
    }

    function restorePreferences() {
        try {
            const stored = JSON.parse(window.localStorage.getItem(preferencesKey) || '{}');
            if (Object.prototype.hasOwnProperty.call(qualitySizes, stored.quality)) ui.quality.value = stored.quality;
            if (allowedFps.has(Number(stored.fps))) ui.fps.value = String(stored.fps);
            if (Number.isInteger(stored.micVolume) && stored.micVolume >= 0 && stored.micVolume <= 200)
                ui.micVolume.value = String(stored.micVolume);
            if (Number.isInteger(stored.speakerVolume) && stored.speakerVolume >= 0 && stored.speakerVolume <= 100)
                ui.speakerVolume.value = String(stored.speakerVolume);
            if (typeof stored.noiseSuppression === 'boolean') ui.noiseSuppression.checked = stored.noiseSuppression;
            if (typeof stored.voiceEnhancement === 'boolean') ui.voiceEnhancement.checked = stored.voiceEnhancement;
        } catch (_) { /* Настройки необязательны. */ }
        if (!noiseSuppressionSupported) {
            ui.noiseSuppression.checked = false;
            ui.noiseSuppression.disabled = true;
            ui.noiseSuppression.title = 'Этот браузер не поддерживает управление шумоподавлением.';
        }
        if (!voiceEnhancementSupported) {
            ui.voiceEnhancement.checked = false;
            ui.voiceEnhancement.disabled = true;
            ui.voiceEnhancement.title = 'Этот браузер не поддерживает улучшение голоса.';
        }
        noiseSuppressionPreference = ui.noiseSuppression.checked;
        voiceEnhancementPreference = ui.voiceEnhancement.checked;
        ui.micVolumeValue.value = `${ui.micVolume.value}%`;
        ui.speakerVolumeValue.value = `${ui.speakerVolume.value}%`;
    }

    function savePreferences() {
        try {
            window.localStorage.setItem(preferencesKey, JSON.stringify({
                quality: ui.quality.value, fps: Number(ui.fps.value),
                micVolume: Number(ui.micVolume.value), speakerVolume: Number(ui.speakerVolume.value),
                noiseSuppression: ui.noiseSuppression.checked,
                voiceEnhancement: ui.voiceEnhancement.checked,
            }));
        } catch (_) { /* Недоступный localStorage не мешает звонку. */ }
    }

    function closeSettings() {
        ui.settings.hidden = true;
        ui.settingsToggle.setAttribute('aria-expanded', 'false');
    }

    function toggleSidebar(tab) {
        if (tab === 'chat' && !isConnected() && ui.sidebar.hidden) return;
        const wasOpen = !ui.sidebar.hidden;
        const previous = ui.sidebar.dataset.tab;
        const shouldOpen = !wasOpen || previous !== tab;
        ui.sidebar.hidden = !shouldOpen;
        ui.workspace.classList.toggle('ll-room-workspace-with-sidebar', shouldOpen);
        ui.sidebar.dataset.tab = shouldOpen ? tab : '';
        ui.membersPanel.hidden = !shouldOpen || tab !== 'members';
        ui.chatPanel.hidden = !shouldOpen || tab !== 'chat';
        ui.sidebarTitle.textContent = tab === 'chat' ? 'Чат занятия' : 'Участники';
        ui.membersToggle.setAttribute('aria-expanded', String(shouldOpen && tab === 'members'));
        ui.chatToggle.setAttribute('aria-expanded', String(shouldOpen && tab === 'chat'));
        if (shouldOpen && tab === 'chat') window.dispatchEvent(new Event('ll-chat-update'));
    }

    async function checkLessonState() {
        if (!room) return;
        try {
            const response = await fetch(root.dataset.stateUrl, {
                credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' },
            });
            if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
                if (response.status === 404 || response.redirected) {
                    closed = true;
                    await leave();
                    setState('Доступ закрыт', 'error');
                    showError('Доступ к занятию больше недоступен. Обновите страницу.');
                }
                return;
            }
            const state = await response.json();
            if (!state.can_join) {
                closed = true;
                await leave();
                setState(state.removed ? 'Вы удалены' : 'Занятие завершено', 'idle');
                showError(state.removed ? 'Преподаватель удалил вас из этого занятия.' : 'Преподаватель завершил занятие.');
            }
        } catch (_) { /* Переподключение к серверу проверим при следующем запросе. */ }
    }

    async function join() {
        if (!sdk) return showError('Клиент видеосвязи не загрузился. Проверьте интернет и обновите страницу.');
        if (room || busy || closed) return;
        busy = true;
        showError('');
        setState('Подключение', 'connecting');
        updateButtons();
        try {
            const response = await fetch(root.dataset.tokenUrl, {
                method: 'POST', credentials: 'same-origin', cache: 'no-store',
                headers: {
                    'X-CSRFToken': root.querySelector('[name=csrfmiddlewaretoken]').value,
                    Accept: 'application/json',
                },
            });
            if (!response.headers.get('content-type')?.includes('application/json')) {
                throw new Error('Сессия истекла. Обновите страницу и войдите снова.');
            }
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Не удалось войти в комнату.');
            const url = new URL(data.server_url);
            if (!['ws:', 'wss:'].includes(url.protocol) || (location.protocol === 'https:' && url.protocol !== 'wss:')) {
                throw new Error('Адрес медиасервера настроен неверно.');
            }
            const activeRoom = new sdk.Room({
                adaptiveStream: true, dynacast: true,
                audioCaptureDefaults: audioCaptureOptions(),
            });
            room = activeRoom;
            registerEvents(activeRoom);
            await activeRoom.connect(url.href, data.participant_token);
            window.dispatchEvent(new CustomEvent('ll-livekit-room', { detail: { room: activeRoom } }));
            busy = false;
            setState('Подключено', 'connected');
            ui.unlock.hidden = activeRoom.canPlaybackAudio;
            showExistingTracks(activeRoom);
            void applyMicrophoneGain();
            for (const publication of activeRoom.localParticipant.trackPublications.values()) updateActualScreen(publication);
            updateMembers();
            updateButtons();
            void refreshDevices();
            stateTimer = window.setInterval(() => { void checkLessonState(); }, 15000);
            void checkLessonState();
        } catch (error) {
            if (room) await room.disconnect().catch(() => {});
            resetConnection();
            setState('Не удалось подключиться', 'error');
            showError(errorText(error));
        } finally {
            busy = false;
            updateButtons();
        }
    }

    async function leave() {
        if (!room) return;
        const activeRoom = room;
        busy = true;
        updateButtons();
        try { await activeRoom.disconnect(); }
        catch (_) { /* Интерфейс всё равно освобождает локальные треки. */ }
        finally { if (room === activeRoom) resetConnection(); }
    }

    async function toggle(kind) {
        if (!isConnected() || busy) return;
        const startingScreenShare = kind === 'screen' && !room.localParticipant.isScreenShareEnabled;
        busy = true;
        showError('');
        updateButtons();
        try {
            const participant = room.localParticipant;
            if (kind === 'mic') {
                const enabled = !participant.isMicrophoneEnabled;
                await participant.setMicrophoneEnabled(enabled, enabled ? audioCaptureOptions() : undefined);
                if (participant.isMicrophoneEnabled) {
                    await applyAudioSettings(microphoneTrack());
                    await applyMicrophoneGain();
                }
            }
            if (kind === 'camera') await participant.setCameraEnabled(!participant.isCameraEnabled);
            if (kind === 'screen') {
                const enabled = !participant.isScreenShareEnabled;
                const options = enabled ? screenOptions() : null;
                await participant.setScreenShareEnabled(enabled, options?.capture, options?.publish);
            }
            void refreshDevices();
        } catch (error) {
            if (!(startingScreenShare && isScreenShareCancellation(error))) showError(errorText(error));
        } finally {
            busy = false;
            updateButtons();
        }
    }

    async function switchDevice(kind, select) {
        if (!isConnected() || !select.value || busy) return;
        busy = true;
        updateButtons();
        try {
            await room.switchActiveDevice(kind, select.value);
            if (kind === 'audioinput') await applyAudioSettings(microphoneTrack());
        }
        catch (error) { showError(errorText(error)); }
        finally { busy = false; updateButtons(); }
    }

    ui.join.addEventListener('click', () => { void join(); });
    ui.leave.addEventListener('click', () => { void leave(); });
    ui.mic.addEventListener('click', () => { void toggle('mic'); });
    ui.camera.addEventListener('click', () => { void toggle('camera'); });
    ui.screen.addEventListener('click', () => { void toggle('screen'); });
    ui.reactionsToggle.addEventListener('click', () => {
        if (!isConnected() || busy) return;
        const open = ui.reactionsMenu.hidden;
        closeSettings();
        ui.reactionsMenu.hidden = !open;
        ui.reactionsToggle.setAttribute('aria-expanded', String(open));
    });
    for (const button of ui.reactionsMenu.children) {
        button.addEventListener('click', () => { void sendReaction(button.dataset.reaction); });
    }
    ui.audioInput.addEventListener('change', () => { void switchDevice('audioinput', ui.audioInput); });
    ui.videoInput.addEventListener('change', () => { void switchDevice('videoinput', ui.videoInput); });
    ui.quality.addEventListener('change', savePreferences);
    ui.fps.addEventListener('change', savePreferences);
    ui.micVolume.addEventListener('input', updateVolume);
    ui.noiseSuppression.addEventListener('change', () => { void changeAudioSetting('noise'); });
    ui.voiceEnhancement.addEventListener('change', () => { void changeAudioSetting('voice'); });
    ui.speakerVolume.addEventListener('input', updateVolume);
    ui.settingsToggle.addEventListener('click', () => {
        const open = ui.settings.hidden;
        if (open) closeReactions();
        ui.settings.hidden = !open;
        ui.settingsToggle.setAttribute('aria-expanded', String(open));
    });
    ui.settingsClose.addEventListener('click', closeSettings);
    ui.membersToggle.addEventListener('click', () => { closeSettings(); closeReactions(); toggleSidebar('members'); });
    ui.chatToggle.addEventListener('click', () => { closeSettings(); closeReactions(); toggleSidebar('chat'); });
    ui.sidebarClose.addEventListener('click', () => { toggleSidebar(ui.sidebar.dataset.tab || 'members'); });
    ui.fullscreen.addEventListener('click', async () => {
        try {
            if (document.fullscreenElement === root) await document.exitFullscreen();
            else await root.requestFullscreen();
        } catch (error) { showError(errorText(error)); }
    });
    document.addEventListener('fullscreenchange', () => {
        const expanded = document.fullscreenElement === root;
        ui.fullscreen.querySelector('span').textContent = expanded ? 'Свернуть' : 'Развернуть';
        ui.fullscreen.setAttribute('aria-label', expanded ? 'Выйти из полноэкранного режима' : 'Развернуть комнату на весь экран');
        for (const { figure, expand, caption } of videoElements.values()) {
            const tileExpanded = document.fullscreenElement === figure;
            expand.textContent = tileExpanded ? 'Свернуть' : 'На весь экран';
            expand.title = tileExpanded ? 'Вернуться к обычному виду' : 'На весь экран';
            expand.setAttribute('aria-pressed', String(tileExpanded));
            expand.setAttribute('aria-label', tileExpanded ?
                `Вернуться к обычному виду: ${caption.textContent}` :
                `Показать на весь экран: ${caption.textContent}`);
        }
    });
    document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape') return;
        closeSettings();
        closeReactions();
        if (!ui.sidebar.hidden) toggleSidebar(ui.sidebar.dataset.tab || 'members');
    });
    document.addEventListener('pointerdown', (event) => {
        if (!ui.reactionsMenu.hidden && !ui.reactionsMenu.contains(event.target) &&
            !ui.reactionsToggle.contains(event.target)) closeReactions();
    });
    ui.unlock.addEventListener('click', async () => {
        try { await room?.startAudio(); ui.unlock.hidden = true; }
        catch (error) { showError(errorText(error)); }
    });
    window.addEventListener('beforeunload', () => { if (room) void room.disconnect(); });
    if (!sdk) showError('Клиент видеосвязи не загрузился. Проверьте интернет и обновите страницу.');
    restorePreferences();
    updateButtons();
})();
