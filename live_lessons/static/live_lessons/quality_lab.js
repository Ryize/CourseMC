(() => {
    'use strict';

    const sdk = window.LivekitClient;
    const byId = (id) => document.getElementById(id);
    const ui = {
        url: byId('lab-url'), token: byId('lab-token'), state: byId('lab-state'),
        message: byId('lab-message'), connect: byId('lab-connect'),
        disconnect: byId('lab-disconnect'), unlock: byId('lab-audio-unlock'),
        mic: byId('lab-mic'), camera: byId('lab-camera'), screen: byId('lab-screen'),
        preset: byId('lab-preset'), report: byId('lab-report'),
        participants: byId('lab-participants'), quality: byId('lab-quality'),
        capture: byId('lab-capture'), bitrate: byId('lab-bitrate'),
        packetLoss: byId('lab-packet-loss'), tracks: byId('lab-tracks'),
        empty: byId('lab-empty'), audio: byId('lab-audio'),
    };

    let room = null;
    let timer = null;
    let previousBytes = null;
    let busy = false;
    const videoTiles = new Map();
    const audioElements = new Map();
    const measurements = [];

    function message(value) {
        ui.message.textContent = value || '';
        ui.message.hidden = !value;
    }

    function state(label, kind) {
        ui.state.textContent = label;
        ui.state.dataset.state = kind;
    }

    function errorText(error) {
        if (error?.name === 'NotAllowedError' || error?.name === 'PermissionDeniedError') {
            return 'Доступ к устройству или экрану не предоставлен. Проверьте разрешения браузера.';
        }
        if (error?.name === 'NotFoundError') {
            return 'Нужное устройство не найдено. Проверьте подключение микрофона или камеры.';
        }
        return error?.message || 'Не удалось выполнить действие. Проверьте сервер и подключение.';
    }

    function publication(source) {
        return room?.localParticipant.getTrackPublication(source);
    }

    function updateButtons() {
        const connected = room?.state === sdk?.ConnectionState?.Connected;
        const active = connected && !busy;
        ui.connect.disabled = !!room || busy;
        ui.disconnect.disabled = !room || busy;
        for (const button of [ui.mic, ui.camera, ui.screen]) button.disabled = !active;
        const micOn = !!(sdk && room && publication(sdk.Track.Source.Microphone)?.track);
        const cameraOn = !!(sdk && room && publication(sdk.Track.Source.Camera)?.track);
        const screenOn = !!(sdk && room && publication(sdk.Track.Source.ScreenShare)?.track);
        ui.mic.textContent = micOn ? 'Выключить микрофон' : 'Включить микрофон';
        ui.camera.textContent = cameraOn ? 'Выключить камеру' : 'Включить камеру';
        ui.screen.textContent = screenOn ? 'Остановить демонстрацию' : 'Показать экран';
        ui.preset.disabled = screenOn;
    }

    function keyFor(participant, publicationInfo) {
        return `${participant.identity}:${publicationInfo.trackSid}`;
    }

    function updateEmpty() {
        ui.empty.hidden = videoTiles.size > 0;
    }

    function attachTrack(track, publicationInfo, participant) {
        const key = keyFor(participant, publicationInfo);
        if (track.kind === sdk.Track.Kind.Audio) {
            if (participant.isLocal || audioElements.has(key)) return;
            const element = track.attach();
            element.autoplay = true;
            ui.audio.appendChild(element);
            audioElements.set(key, { track, element });
            return;
        }
        if (track.kind !== sdk.Track.Kind.Video || videoTiles.has(key)) return;
        const figure = document.createElement('figure');
        figure.className = 'lab-tile';
        const isScreen = publicationInfo.source === sdk.Track.Source.ScreenShare;
        if (isScreen) figure.dataset.screen = 'true';
        const element = track.attach();
        element.playsInline = true;
        element.autoplay = true;
        element.muted = !!participant.isLocal;
        const caption = document.createElement('figcaption');
        const label = participant.name || participant.identity || 'Участник';
        caption.textContent = `${label}${participant.isLocal ? ' · вы' : ''}${isScreen ? ' · экран' : ''}`;
        const expand = document.createElement('button');
        expand.className = 'lab-expand';
        expand.type = 'button';
        expand.textContent = 'На весь экран';
        expand.setAttribute('aria-label', `Показать на весь экран: ${caption.textContent}`);
        expand.addEventListener('click', () => {
            if (figure.requestFullscreen) void figure.requestFullscreen().catch((error) => message(errorText(error)));
        });
        figure.append(element, caption, expand);
        ui.tracks.appendChild(figure);
        videoTiles.set(key, { track, element, figure });
        updateEmpty();
    }

    function detachTrack(publicationInfo, participant) {
        const key = keyFor(participant, publicationInfo);
        const video = videoTiles.get(key);
        if (video) {
            video.track.detach(video.element);
            video.figure.remove();
            videoTiles.delete(key);
        }
        const audio = audioElements.get(key);
        if (audio) {
            audio.track.detach(audio.element);
            audio.element.remove();
            audioElements.delete(key);
        }
        updateEmpty();
    }

    function clearTracks() {
        for (const { track, element, figure } of videoTiles.values()) {
            track.detach(element);
            figure.remove();
        }
        for (const { track, element } of audioElements.values()) {
            track.detach(element);
            element.remove();
        }
        videoTiles.clear();
        audioElements.clear();
        updateEmpty();
    }

    function qualityName(value) {
        const names = {
            excellent: 'Отличное', good: 'Хорошее', poor: 'Нестабильное',
            lost: 'Связь потеряна', unknown: 'Ожидание данных',
        };
        return names[value] || 'Ожидание данных';
    }

    function updateParticipants() {
        ui.participants.textContent = room ? String(room.remoteParticipants.size + 1) : '—';
    }

    function screenOptions() {
        const presets = {
            text: { contentHint: 'text', resolution: { width: 1920, height: 1080, frameRate: 15 } },
            motion: { contentHint: 'motion', resolution: { width: 1280, height: 720, frameRate: 30 } },
            economy: { contentHint: 'text', resolution: { width: 854, height: 480, frameRate: 15 } },
        };
        return presets[ui.preset.value] || { contentHint: 'text' };
    }

    function statsOf(report, type, mediaType) {
        if (!report) return [];
        const values = typeof report.values === 'function' ? [...report.values()] : Object.values(report);
        return values.filter((entry) => entry.type === type &&
            (entry.kind || entry.mediaType) === mediaType && !entry.isRemote);
    }

    async function collectMetrics() {
        if (!room || room.state !== sdk.ConnectionState.Connected) return;
        const sampledRoom = room;
        const sample = { at: new Date().toISOString(), participants: sampledRoom.remoteParticipants.size + 1 };
        sample.connectionQuality = sampledRoom.localParticipant.connectionQuality || 'unknown';
        const screen = sampledRoom.localParticipant.getTrackPublication(sdk.Track.Source.ScreenShare)?.track;
        const settings = screen?.mediaStreamTrack?.getSettings?.();
        sample.capture = settings?.width && settings?.height
            ? { width: settings.width, height: settings.height, frameRate: settings.frameRate || null }
            : null;
        let bytesSent = 0;
        let outgoingFound = false;
        const localVideo = [sdk.Track.Source.Camera, sdk.Track.Source.ScreenShare];
        for (const source of localVideo) {
            const track = sampledRoom.localParticipant.getTrackPublication(source)?.track;
            if (!track?.getRTCStatsReport) continue;
            try {
                for (const item of statsOf(await track.getRTCStatsReport(), 'outbound-rtp', 'video')) {
                    bytesSent += item.bytesSent || 0;
                    outgoingFound = true;
                }
            } catch (_) { /* Статистика отдельного трека может быть недоступна в браузере. */ }
        }
        const now = performance.now();
        sample.videoMbps = outgoingFound && previousBytes && now > previousBytes.at
            ? Math.max(0, (bytesSent - previousBytes.value) * 8 / ((now - previousBytes.at) * 1000))
            : null;
        previousBytes = outgoingFound ? { value: bytesSent, at: now } : null;
        let received = 0;
        let lost = 0;
        for (const participant of sampledRoom.remoteParticipants.values()) {
            for (const pub of participant.videoTrackPublications.values()) {
                if (!pub.track?.getRTCStatsReport) continue;
                try {
                    for (const item of statsOf(await pub.track.getRTCStatsReport(), 'inbound-rtp', 'video')) {
                        received += item.packetsReceived || 0;
                        lost += item.packetsLost || 0;
                    }
                } catch (_) { /* Отображаем доступные показатели, не прерывая звонок. */ }
            }
        }
        sample.inboundPacketLossPercent = received + lost > 0
            ? Math.max(0, lost) / (received + Math.max(0, lost)) * 100 : null;
        if (room !== sampledRoom) return;
        ui.participants.textContent = String(sample.participants);
        ui.quality.textContent = qualityName(sample.connectionQuality);
        ui.capture.textContent = sample.capture
            ? `${sample.capture.width} × ${sample.capture.height}, ${Math.round(sample.capture.frameRate || 0)} кадр/с`
            : 'Нет демонстрации';
        ui.bitrate.textContent = sample.videoMbps == null ? 'Нет данных' : `${sample.videoMbps.toFixed(2)} Мбит/с`;
        ui.packetLoss.textContent = sample.inboundPacketLossPercent == null
            ? 'Нет данных' : `${sample.inboundPacketLossPercent.toFixed(1)}%`;
        measurements.push(sample);
        if (measurements.length > 1800) measurements.shift();
        ui.report.disabled = false;
    }

    function registerEvents(activeRoom) {
        const event = sdk.RoomEvent;
        activeRoom.on(event.TrackSubscribed, (track, pub, participant) => attachTrack(track, pub, participant));
        activeRoom.on(event.TrackUnsubscribed, (_track, pub, participant) => detachTrack(pub, participant));
        activeRoom.on(event.LocalTrackPublished, (pub) => {
            if (pub.track) attachTrack(pub.track, pub, activeRoom.localParticipant);
            updateButtons();
        });
        activeRoom.on(event.LocalTrackUnpublished, (pub) => {
            detachTrack(pub, activeRoom.localParticipant);
            updateButtons();
        });
        activeRoom.on(event.ParticipantConnected, updateParticipants);
        activeRoom.on(event.ParticipantDisconnected, (participant) => {
            for (const pub of participant.trackPublications.values()) detachTrack(pub, participant);
            updateParticipants();
        });
        activeRoom.on(event.ConnectionQualityChanged, (quality, participant) => {
            if (participant.isLocal) ui.quality.textContent = qualityName(quality);
        });
        activeRoom.on(event.Reconnecting, () => state('Переподключение', 'connecting'));
        activeRoom.on(event.Reconnected, () => state('Подключено', 'connected'));
        activeRoom.on(event.AudioPlaybackStatusChanged, () => {
            ui.unlock.hidden = activeRoom.canPlaybackAudio;
        });
        activeRoom.on(event.Disconnected, () => {
            if (room === activeRoom) resetConnection();
        });
    }

    function resetConnection() {
        if (timer) window.clearInterval(timer);
        timer = null;
        previousBytes = null;
        clearTracks();
        room = null;
        busy = false;
        ui.unlock.hidden = true;
        ui.quality.textContent = '—';
        ui.participants.textContent = '—';
        ui.capture.textContent = '—';
        ui.bitrate.textContent = '—';
        ui.packetLoss.textContent = '—';
        state('Не подключено', 'idle');
        updateButtons();
    }

    async function connect() {
        if (!sdk) return message('Не удалось загрузить клиент видеосвязи. Проверьте интернет и обновите страницу.');
        const address = ui.url.value.trim();
        const token = ui.token.value.trim();
        let url;
        try { url = new URL(address); } catch (_) { return message('Укажите корректный адрес LiveKit.'); }
        if (!['ws:', 'wss:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
            return message('Укажите адрес LiveKit в формате ws:// или wss:// без логина и параметров.');
        }
        if (!token) return message('Вставьте токен участника.');
        if (location.protocol === 'https:' && url.protocol !== 'wss:') {
            return message('На защищённой странице используйте адрес wss://.');
        }
        message('');
        state('Подключение', 'connecting');
        busy = true;
        updateButtons();
        const activeRoom = new sdk.Room({
            adaptiveStream: true,
            dynacast: true,
            audioCaptureDefaults: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        room = activeRoom;
        registerEvents(activeRoom);
        try {
            await activeRoom.connect(url.href, token);
            ui.token.value = '';
            measurements.length = 0;
            ui.report.disabled = true;
            busy = false;
            state('Подключено', 'connected');
            updateParticipants();
            updateButtons();
            ui.unlock.hidden = activeRoom.canPlaybackAudio;
            timer = window.setInterval(() => { void collectMetrics(); }, 2000);
            void collectMetrics();
        } catch (error) {
            activeRoom.disconnect();
            resetConnection();
            state('Ошибка подключения', 'error');
            message(errorText(error));
        }
    }

    async function disconnect() {
        if (!room) return;
        busy = true;
        updateButtons();
        await room.disconnect();
        resetConnection();
    }

    async function toggle(kind) {
        if (!room || busy) return;
        busy = true;
        updateButtons();
        message('');
        try {
            const participant = room.localParticipant;
            if (kind === 'mic') await participant.setMicrophoneEnabled(!publication(sdk.Track.Source.Microphone)?.track);
            if (kind === 'camera') await participant.setCameraEnabled(!publication(sdk.Track.Source.Camera)?.track);
            if (kind === 'screen') {
                const enabled = !publication(sdk.Track.Source.ScreenShare)?.track;
                await participant.setScreenShareEnabled(enabled, enabled ? screenOptions() : undefined);
            }
        } catch (error) {
            message(errorText(error));
        } finally {
            busy = false;
            updateButtons();
        }
    }

    function downloadReport() {
        const report = {
            label: 'CourseMC local connection quality lab',
            screenPreset: ui.preset.value,
            note: 'Показатели браузера; потери пакетов накопительные. Содержимое медиа и токен не включены.',
            samples: measurements,
        };
        const href = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
        const link = document.createElement('a');
        link.href = href;
        link.download = 'coursemc-quality-lab.json';
        link.click();
        window.setTimeout(() => URL.revokeObjectURL(href), 1000);
    }

    ui.connect.addEventListener('click', () => { void connect(); });
    ui.disconnect.addEventListener('click', () => { void disconnect(); });
    ui.mic.addEventListener('click', () => { void toggle('mic'); });
    ui.camera.addEventListener('click', () => { void toggle('camera'); });
    ui.screen.addEventListener('click', () => { void toggle('screen'); });
    ui.unlock.addEventListener('click', async () => {
        try { await room?.startAudio(); ui.unlock.hidden = true; }
        catch (error) { message(errorText(error)); }
    });
    ui.report.addEventListener('click', downloadReport);
    window.addEventListener('beforeunload', () => { if (room) void room.disconnect(); });
    if (!sdk) message('Клиент видеосвязи не загрузился. Проверьте интернет и обновите страницу.');
})();
