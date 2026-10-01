(() => {
    'use strict';
    const preferenceKey = 'coursemc:live-room-devices:v1';
    let currentRoot = null;
    let dispose = () => {};

    function initialize() {
        const root = document.getElementById('ll-room');
        if (root === currentRoot) return;
        dispose();
        currentRoot = root;
        if (!root) return;
        const byId = (id) => document.getElementById(id);
        const panel = byId('ll-device-check');
        if (!panel) return;
        const ui = {
            open: byId('ll-device-open'), close: byId('ll-device-close'), done: byId('ll-device-done'),
            camera: byId('ll-device-camera-test'), mic: byId('ll-device-mic-test'),
            speaker: byId('ll-device-speaker-test'), video: byId('ll-device-video'),
            placeholder: byId('ll-device-placeholder'), meter: byId('ll-device-meter'),
            level: byId('ll-device-level'), micHint: byId('ll-device-mic-hint'),
            status: byId('ll-device-status'), audio: byId('ll-device-test-audio'),
        };
        const media = window.navigator?.mediaDevices;
        const supportsOutput = typeof ui.audio.setSinkId === 'function';
        const choices = [
            ['audioinput', byId('ll-device-mic-select'), byId('ll-room-audio-input'), 'Микрофон'],
            ['videoinput', byId('ll-device-camera-select'), byId('ll-room-video-input'), 'Камера'],
            ['audiooutput', byId('ll-device-speaker-select'), byId('ll-room-audio-output'), 'Динамики'],
        ];
        const preferences = {};
        try {
            const stored = JSON.parse(window.localStorage.getItem(preferenceKey) || '{}');
            for (const [kind] of choices) {
                if (typeof stored[kind] === 'string' && stored[kind].length <= 512) preferences[kind] = stored[kind];
            }
        } catch (_) { /* Выбор устройств необязателен. */ }
        const listeners = [];
        const streams = { camera: null, mic: null };
        const generations = { camera: 0, mic: 0 };
        let disposed = false;
        let context = null;
        let analyser = null;
        let source = null;
        let silentGain = null;
        let frame = null;
        let audioUrl = null;
        let listGeneration = 0;
        let speakerGeneration = 0;
        function listen(target, type, callback) {
            if (!target) return;
            target.addEventListener(type, callback);
            listeners.push([target, type, callback]);
        }
        function usable() { return !disposed && !panel.hidden && root.isConnected !== false; }
        function status(text, error = false) {
            ui.status.textContent = text;
            ui.status.dataset.error = String(error);
        }
        function errorText(error) {
            if (['NotAllowedError', 'SecurityError', 'PermissionDeniedError'].includes(error?.name))
                return 'Доступ не разрешён. Разрешите устройство в настройках браузера или продолжите без проверки.';
            if (['NotFoundError', 'OverconstrainedError'].includes(error?.name))
                return 'Устройство недоступно. Выберите «По умолчанию» или подключите другое устройство.';
            if (error?.name === 'NotReadableError') return 'Устройство занято другим приложением. Освободите его и попробуйте снова.';
            return 'Не удалось проверить устройство. Можно продолжить без проверки.';
        }
        function save() {
            try { window.localStorage.setItem(preferenceKey, JSON.stringify(preferences)); }
            catch (_) { /* Звонок работает и без localStorage. */ }
        }
        function selectValue(select, id, label) {
            if (id && ![...select.options].some((option) => option.value === id)) select.add(new Option(label, id));
            select.value = id || '';
        }
        function syncChoices() {
            for (const [kind, select, liveSelect, label] of choices) {
                const value = kind === 'audiooutput' && !supportsOutput ? '' : preferences[kind] || '';
                selectValue(select, value, `${label} (сохранённый выбор)`);
                if (liveSelect) selectValue(liveSelect, value, `${label} (сохранённый выбор)`);
            }
        }
        async function refreshDevices() {
            if (!media?.enumerateDevices) return;
            const request = ++listGeneration;
            try {
                // enumerateDevices не открывает устройства и не запрашивает разрешения.
                const devices = await media.enumerateDevices();
                if (disposed || request !== listGeneration) return;
                for (const [kind, select, liveSelect, label] of choices) {
                    const matching = devices.filter((device) => device.kind === kind && device.deviceId);
                    for (const target of [select, ...(root.dataset.connected === 'true' ? [] : [liveSelect])].filter(Boolean)) {
                        target.replaceChildren(new Option('По умолчанию', ''));
                        matching.forEach((device, index) => target.add(new Option(device.label || `${label} ${index + 1}`, device.deviceId)));
                    }
                }
                syncChoices();
            } catch (_) { if (usable()) status('Список устройств недоступен. Проверка использует устройство по умолчанию.'); }
        }
        function stop(kind) {
            generations[kind]++;
            streams[kind]?.getTracks().forEach((track) => track.stop());
            streams[kind] = null;
            ui[kind].disabled = false;
            ui[kind].setAttribute('aria-pressed', 'false');
            ui[kind].textContent = kind === 'camera' ? 'Проверить камеру' : 'Проверить микрофон';
            if (kind === 'camera') {
                ui.video.srcObject = null;
                ui.video.hidden = true;
                ui.placeholder.hidden = false;
            } else {
                if (frame !== null) window.cancelAnimationFrame(frame);
                frame = null;
                source?.disconnect(); analyser?.disconnect(); silentGain?.disconnect();
                if (context) void context.close().catch(() => {});
                context = analyser = source = silentGain = null;
                ui.level.style.width = '0%';
                ui.meter.setAttribute('aria-valuenow', '0');
                ui.micHint.textContent = 'Нажмите «Проверить микрофон» и скажите несколько слов.';
            }
        }
        function stopSpeaker() {
            speakerGeneration++;
            ui.audio.pause();
            ui.audio.removeAttribute('src');
            ui.audio.load();
            if (audioUrl) URL.revokeObjectURL(audioUrl);
            audioUrl = null;
            ui.speaker.disabled = false;
        }
        function close(restoreFocus = true) {
            stop('camera'); stop('mic'); stopSpeaker();
            panel.hidden = true;
            ui.open.setAttribute('aria-expanded', 'false');
            if (restoreFocus && !ui.open.disabled && root.isConnected !== false) ui.open.focus();
        }
        function measure(generation) {
            if (!usable() || generations.mic !== generation || !analyser) return;
            const samples = new Float32Array(analyser.fftSize);
            analyser.getFloatTimeDomainData(samples);
            const rms = Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / samples.length);
            const level = Math.min(100, Math.round(rms * 350));
            ui.level.style.width = `${level}%`;
            ui.meter.setAttribute('aria-valuenow', String(level));
            frame = window.requestAnimationFrame(() => measure(generation));
        }
        async function testCapture(kind) {
            if (!usable()) return;
            if (streams[kind]) { stop(kind); status('Проверка остановлена.'); return; }
            if (!media?.getUserMedia) return status('Проверка устройств доступна в защищённом браузере (HTTPS или localhost).', true);
            stop(kind);
            const generation = generations[kind];
            ui[kind].disabled = true;
            status('Разрешите доступ в окне браузера.');
            const id = preferences[kind === 'camera' ? 'videoinput' : 'audioinput'];
            const deviceId = id ? { exact: id } : undefined;
            const options = kind === 'camera' ? { video: { deviceId, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false } :
                { video: false, audio: { deviceId, echoCancellation: true, noiseSuppression: true } };
            try {
                const stream = await media.getUserMedia(options);
                if (!usable() || generations[kind] !== generation) {
                    stream.getTracks().forEach((track) => track.stop()); return;
                }
                streams[kind] = stream;
                for (const track of stream.getTracks()) track.addEventListener('ended', () => {
                    if (streams[kind] === stream) { stop(kind); if (usable()) status('Устройство отключилось. Выберите другое.', true); }
                });
                if (kind === 'camera') {
                    ui.video.srcObject = stream;
                    ui.video.hidden = false;
                    ui.placeholder.hidden = true;
                    await ui.video.play();
                } else {
                    const AudioContext = window.AudioContext || window.webkitAudioContext;
                    if (!AudioContext) throw new Error('AudioContext unavailable');
                    context = new AudioContext();
                    source = context.createMediaStreamSource(stream);
                    analyser = context.createAnalyser(); analyser.fftSize = 512;
                    silentGain = context.createGain(); silentGain.gain.value = 0;
                    source.connect(analyser); analyser.connect(silentGain); silentGain.connect(context.destination);
                    await context.resume();
                    if (usable() && generations[kind] === generation) {
                        ui.micHint.textContent = 'Говорите: полоска показывает уровень вашего голоса. Звук не воспроизводится.';
                        measure(generation);
                    }
                }
                if (!usable() || generations[kind] !== generation) return;
                ui[kind].setAttribute('aria-pressed', 'true');
                ui[kind].textContent = kind === 'camera' ? 'Выключить превью' : 'Остановить проверку';
                status(kind === 'camera' ? 'Превью видно только вам.' : 'Микрофон работает только для проверки уровня.');
                void refreshDevices();
            } catch (error) {
                if (generations[kind] === generation) { stop(kind); if (usable()) status(errorText(error), true); }
            } finally {
                if (generations[kind] === generation) ui[kind].disabled = false;
            }
        }
        function testTone() {
            const rate = 16000, count = Math.round(rate * 1.1);
            const buffer = new ArrayBuffer(44 + count * 2), view = new DataView(buffer);
            const write = (offset, text) => [...text].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0)));
            write(0, 'RIFF'); view.setUint32(4, 36 + count * 2, true); write(8, 'WAVE'); write(12, 'fmt ');
            view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
            view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true);
            view.setUint16(34, 16, true); write(36, 'data'); view.setUint32(40, count * 2, true);
            for (let i = 0; i < count; i++) {
                const time = i / rate, phase = time % .4;
                const envelope = Math.max(0, Math.min(1, phase / .025, (.25 - phase) / .025));
                view.setInt16(44 + i * 2, Math.round(Math.sin(time * Math.PI * 2 * 660) * envelope * 7000), true);
            }
            return new Blob([buffer], { type: 'audio/wav' });
        }
        listen(ui.open, 'click', () => {
            if (root.dataset.connected === 'true' || ui.open.disabled) return;
            panel.hidden = false;
            ui.open.setAttribute('aria-expanded', 'true');
            status('Выберите устройства и включите нужные проверки.');
            ui.close.focus();
            void refreshDevices();
        });
        listen(ui.close, 'click', () => close());
        listen(ui.done, 'click', () => close());
        listen(ui.camera, 'click', () => { void testCapture('camera'); });
        listen(ui.mic, 'click', () => { void testCapture('mic'); });
        listen(ui.speaker, 'click', async () => {
            if (!usable()) return;
            stopSpeaker();
            const generation = speakerGeneration;
            ui.speaker.disabled = true;
            try {
                audioUrl = URL.createObjectURL(testTone()); ui.audio.src = audioUrl;
                ui.audio.volume = Number(byId('ll-room-speaker-volume')?.value || 100) / 100;
                if (supportsOutput) await ui.audio.setSinkId(preferences.audiooutput || '');
                if (!usable() || generation !== speakerGeneration) return;
                await ui.audio.play();
                if (usable() && generation === speakerGeneration) status('Слышите три сигнала? Динамики готовы. Если нет — проверьте устройство и системную громкость.');
            } catch (error) { if (usable() && generation === speakerGeneration) status(errorText(error), true); }
            finally { if (generation === speakerGeneration) ui.speaker.disabled = false; }
        });
        for (const [kind, select, liveSelect] of choices) {
            listen(select, 'change', () => {
                preferences[kind] = select.value; save(); syncChoices();
                if (kind === 'audiooutput') stopSpeaker();
                else {
                    const capture = kind === 'audioinput' ? 'mic' : 'camera';
                    const testing = !!streams[capture]; stop(capture);
                    if (testing) void testCapture(capture);
                }
            });
            listen(liveSelect, 'change', () => {
                // Room сохраняет только успешно применённый выбор.
                window.setTimeout(() => { if (!disposed) selectValue(select, liveSelect.value, 'Выбранное устройство'); }, 0);
            });
        }
        listen(window, 'll-devices-changed', ({ detail }) => {
            if (detail && choices.some(([kind]) => kind === detail.kind)) {
                preferences[detail.kind] = detail.id; syncChoices();
            }
        });
        listen(window, 'll-prejoin-close', () => close(false));
        listen(window, 'pagehide', () => close(false));
        listen(window, 'beforeunload', () => close(false));
        listen(panel, 'click', (event) => { if (event.target === panel) close(); });
        listen(document, 'keydown', (event) => {
            if (panel.hidden) return;
            if (event.key === 'Escape') { event.preventDefault(); close(); }
            if (event.key === 'Tab') {
                const buttons = [...panel.querySelectorAll('button:not(:disabled), select:not(:disabled)')];
                const first = buttons[0], last = buttons[buttons.length - 1];
                if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
                if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
            }
        });
        listen(media, 'devicechange', () => { void refreshDevices(); });
        const outputHelp = supportsOutput ? 'Выбор действует для звука участников и теста динамиков.' :
            'Этот браузер использует системные динамики. Выберите устройство вывода в настройках системы.';
        byId('ll-device-output-help').textContent = outputHelp;
        byId('ll-room-output-help').textContent = outputHelp;
        choices[2][1].disabled = !supportsOutput;
        syncChoices();
        dispose = () => {
            disposed = true; listGeneration++; close(false);
            for (const [target, type, callback] of listeners) target.removeEventListener(type, callback);
        };
    }
    window.addEventListener('ll-page-updated', initialize);
    initialize();
})();
