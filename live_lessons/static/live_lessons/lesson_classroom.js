(() => {
    'use strict';

    // Звук требует действия пользователя. Контекст общий: старт урока не теряет разрешение.
    let soundContext = null;
    let pendingChime = false;
    let soundUnlocked = false;
    let resumingSound = false;
    function chime() {
        if (soundContext?.state !== 'running') {
            pendingChime = true;
            // Разрешённый ранее контекст может приостановиться после смены окна.
            if (soundUnlocked && soundContext && !resumingSound) {
                resumingSound = true;
                void soundContext.resume().then(() => {
                    if (pendingChime && soundContext.state === 'running') chime();
                }).catch(() => {}).finally(() => { resumingSound = false; });
            }
            return;
        }
        pendingChime = false;
        try {
            for (const [offset, frequency] of [[0, 660], [0.16, 880]]) {
                const oscillator = soundContext.createOscillator();
                const gain = soundContext.createGain();
                const start = soundContext.currentTime + offset;
                oscillator.frequency.value = frequency;
                gain.gain.setValueAtTime(0, start);
                gain.gain.linearRampToValueAtTime(0.08, start + 0.015);
                gain.gain.exponentialRampToValueAtTime(0.001, start + 0.14);
                oscillator.connect(gain);
                gain.connect(soundContext.destination);
                oscillator.onended = () => { oscillator.disconnect(); gain.disconnect(); };
                oscillator.start(start);
                oscillator.stop(start + 0.15);
            }
        } catch (_) { /* Звук не должен мешать допуску в комнату. */ }
    }
    async function unlockSound() {
        if (document.getElementById('ll-live-page')?.dataset.teacher !== 'true') return;
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        try {
            soundContext ||= new AudioContext();
            await soundContext.resume();
            soundUnlocked = soundContext.state === 'running';
            if (pendingChime) chime();
        } catch (_) { /* Покажем кнопку для повторного разрешения. */ }
    }
    document.addEventListener('pointerdown', () => { void unlockSound(); });
    document.addEventListener('keydown', () => { void unlockSound(); });

    let currentRoot = null;
    let dispose = () => {};
    function initialize() {
        const root = document.getElementById('ll-room');
        if (root === currentRoot) return;
        dispose();
        currentRoot = root;
        if (!root) return;
        const byId = (id) => document.getElementById(id);
        const ui = {
            banner: byId('ll-waiting-banner'), waiting: byId('ll-waiting-list'), count: byId('ll-waiting-count'),
            sound: byId('ll-waiting-sound'), admission: byId('ll-admission-status'),
            cancel: byId('ll-waiting-cancel'), notice: byId('ll-classroom-notice'),
            hands: byId('ll-hands'), handsList: byId('ll-hands-list'),
            indicator: byId('ll-connection-indicator'), label: byId('ll-connection-label'),
            warning: byId('ll-connection-warning'), connectionDetails: byId('ll-connection-details'),
        };
        const settings = [...root.querySelectorAll('[data-classroom-setting]')];
        const commands = [...root.querySelectorAll('[data-classroom-action]')];
        let activeRoom = null;
        let state = null;
        let timer = null;
        let controller = null;
        let stopped = false;
        let posting = false;
        let version = 0;
        let failures = 0;
        let refreshPending = false;
        let networkNotice = false;
        let queueRevision = '';
        let handsRevision = '';
        let connection = { state: 'disconnected', quality: 'unknown' };
        const seenRequests = new Set();
        const listeners = [];
        function listen(target, type, callback) {
            target.addEventListener(type, callback);
            listeners.push([target, type, callback]);
        }
        function notice(text) {
            ui.notice.textContent = text || '';
            ui.notice.hidden = !text;
        }
        function button(text, callback, primary = false) {
            const node = document.createElement('button');
            node.type = 'button';
            node.className = `ll-classroom-button${primary ? ' ll-classroom-button-primary' : ''}`;
            node.textContent = text;
            node.disabled = posting;
            node.addEventListener('click', () => { if (!posting) void callback(node); });
            return node;
        }
        function render(next) {
            state = next;
            const waiting = next.waiting || [];
            if (ui.banner) {
                ui.banner.hidden = !waiting.length;
                ui.count.textContent = String(waiting.length);
                ui.sound.hidden = soundContext?.state === 'running';
                let fresh = false;
                for (const person of waiting) {
                    const key = `${person.identity}:${person.request}`;
                    if (!seenRequests.has(key)) { seenRequests.add(key); fresh = true; }
                }
                if (fresh) chime();
                if (!waiting.length) pendingChime = false;
                const revision = JSON.stringify(waiting);
                if (revision !== queueRevision) {
                    queueRevision = revision;
                    ui.waiting.replaceChildren(...waiting.map((person) => {
                        const row = document.createElement('div');
                        row.className = 'll-waiting-row';
                        const avatar = document.createElement('span');
                        avatar.className = 'll-waiting-avatar';
                        avatar.textContent = Array.from(person.name.trim())[0]?.toUpperCase() || '•';
                        avatar.setAttribute('aria-hidden', 'true');
                        const name = document.createElement('span');
                        name.className = 'll-waiting-name';
                        name.textContent = `${person.name} в комнате ожидания`;
                        const admit = button('Впустить', (node) => post('admit', { identity: person.identity }, true, node), true);
                        admit.className += ' ll-waiting-admit';
                        admit.setAttribute('aria-label', `Впустить: ${person.name}`);
                        const dismiss = button('×', (node) => post('deny', { identity: person.identity }, true, node));
                        dismiss.className += ' ll-waiting-dismiss';
                        dismiss.setAttribute('aria-label', `Отклонить запрос: ${person.name}`);
                        dismiss.title = 'Отклонить запрос';
                        row.append(avatar, name, admit, dismiss);
                        return row;
                    }));
                }
            }
            const hands = next.hands || [];
            ui.hands.hidden = !hands.length;
            const revision = JSON.stringify([hands, next.own.identity, next.teacher]);
            if (revision !== handsRevision) {
                handsRevision = revision;
                ui.handsList.replaceChildren(...hands.map((person, index) => {
                    const row = document.createElement('li');
                    const name = document.createElement('span');
                    name.textContent = `${index + 1}. ${person.name}`;
                    row.append(name);
                    if (next.teacher || person.identity === next.own.identity) {
                        row.append(button('Опустить', (node) => post('lower_hand', { identity: person.identity }, false, node)));
                    }
                    return row;
                }));
            }
            for (const input of settings) {
                input.checked = !!next.settings[input.dataset.classroomSetting];
                input.disabled = posting || !next.active;
            }
            for (const command of commands) command.disabled = posting || !next.active;
            const admission = next.own.admission;
            const waitingOwn = admission === 'waiting';
            ui.cancel.hidden = !waitingOwn;
            ui.cancel.disabled = posting;
            ui.admission.textContent = !next.active ? 'Занятие завершено.' :
                admission === 'denied' ? 'Преподаватель не разрешил вход в эту комнату.' :
                waitingOwn ? 'Вы в зале ожидания. Преподаватель получил уведомление и скоро вас впустит.' :
                !next.own.entry_allowed ? 'Преподаватель закрыл вход новым участникам.' : '';
            ui.admission.hidden = !ui.admission.textContent;
            window.dispatchEvent(new CustomEvent('ll-classroom-state', { detail: { state: next } }));
        }
        function renderConnection() {
            const offline = window.navigator.onLine === false;
            const reconnecting = connection.state === 'reconnecting';
            const connected = connection.state === 'connected';
            const poor = ['poor', 'lost'].includes(connection.quality);
            const labels = { excellent: 'Отличная связь', good: 'Хорошая связь', poor: 'Слабая связь', lost: 'Связь потеряна' };
            const label = offline ? 'Нет сети' : reconnecting ? 'Переподключение' :
                connected ? (labels[connection.quality] || 'Проверяем связь') : 'Не подключено';
            const advice = offline ? 'Нет соединения с интернетом. После его восстановления попробуем подключиться снова.' :
                reconnecting ? 'Восстанавливаем соединение. Не закрывайте страницу; если это длится долго, проверьте сеть.' :
                connected && poor ? 'Слабое соединение: звук или видео могут прерываться. Выключите камеру или снизьте качество демонстрации до 720p / 480p и 15 кадров/с.' : '';
            // При обычном входе/хорошей связи не показываем уведомление о подключении.
            ui.indicator.hidden = !reconnecting && !offline && !(connected && poor);
            ui.indicator.dataset.quality = offline || reconnecting ? 'lost' : connection.quality;
            ui.label.textContent = label;
            ui.indicator.title = label;
            ui.warning.textContent = advice;
            ui.warning.hidden = !advice;
            ui.connectionDetails.textContent = connected || reconnecting || offline ?
                `${label}. ${advice || 'Если видео прерывается, снизьте качество демонстрации. Читаемость кода важнее частоты кадров.'}` :
                'Войдите в комнату, чтобы проверить соединение.';
        }
        function schedule() {
            window.clearTimeout(timer);
            if (stopped) return;
            if (window.navigator.onLine === false || (document.hidden && !activeRoom &&
                state?.own.admission !== 'waiting' && root.dataset.teacher !== 'true')) return;
            timer = window.setTimeout(() => { void poll(); }, failures ? Math.min(30000, 3000 * 2 ** failures) : document.hidden ? 10000 : 3000);
        }
        async function poll() {
            if (stopped || root.isConnected === false) return;
            if (controller || posting) { refreshPending = true; return; }
            refreshPending = false;
            controller = new AbortController();
            const pending = controller;
            const requestVersion = version;
            const timeout = window.setTimeout(() => pending.abort(), 10000);
            try {
                const url = new URL(root.dataset.classroomUrl, window.location.href);
                if (activeRoom?.state === window.LivekitClient?.ConnectionState.Connected) url.searchParams.set('presence', 'connected');
                const response = await fetch(url.href, {
                    credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' }, signal: pending.signal,
                });
                if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Сессия истекла. Войдите на сайт снова.');
                if ([401, 403, 404].includes(response.status)) { stopped = true; throw new Error('Доступ к занятию закрыт.'); }
                if (!response.ok) throw new Error('Не удалось обновить управление комнатой.');
                const next = await response.json();
                if (stopped || version !== requestVersion) return;
                failures = 0;
                if (networkNotice) { notice(''); networkNotice = false; }
                render(next);
            } catch (error) {
                if (error.name === 'AbortError' && (stopped || version !== requestVersion)) return;
                failures += 1;
                if (failures > 2 || stopped) {
                    networkNotice = true;
                    notice(error.message || 'Не удалось обновить комнату. Повторим после восстановления сети.');
                }
            } finally {
                window.clearTimeout(timeout);
                if (controller === pending) controller = null;
                if (refreshPending && !posting && !stopped) void poll();
                else schedule();
            }
        }
        async function post(action, values = {}, manage = false, trigger = null) {
            if (posting || stopped) return;
            posting = true;
            version += 1; // Старый GET не должен отменять результат нового действия.
            networkNotice = false;
            for (const input of [...settings, ...commands]) input.disabled = true;
            if (trigger) trigger.disabled = true;
            const pending = new AbortController();
            const timeout = window.setTimeout(() => pending.abort(), 30000);
            try {
                const body = new FormData();
                body.set('action', action);
                for (const [key, value] of Object.entries(values)) body.set(key, String(value));
                const response = await fetch(manage ? root.dataset.classroomManageUrl : root.dataset.classroomActionUrl, {
                    method: 'POST', credentials: 'same-origin', cache: 'no-store', body, signal: pending.signal,
                    headers: { 'X-CSRFToken': root.querySelector('[name=csrfmiddlewaretoken]').value, Accept: 'application/json' },
                });
                if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Сессия истекла. Обновите страницу.');
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || 'Не удалось выполнить действие.');
                if (stopped) return;
                notice(result.message || (action === 'mute_all' ? 'Микрофоны участников выключены. Они могут включить их сами, если это разрешено.' : ''));
                if (action === 'cancel_wait') window.dispatchEvent(new Event('ll-wait-cancelled'));
                if (activeRoom) {
                    void activeRoom.localParticipant.publishData(new TextEncoder().encode('refresh'), {
                        reliable: true, topic: 'lesson-classroom-updated',
                    }).catch(() => {});
                }
            } catch (error) {
                if (!stopped) notice(error.name === 'AbortError' ? 'Запрос занял слишком много времени. Проверяем состояние комнаты…' : error.message);
            } finally {
                window.clearTimeout(timeout);
                posting = false;
                if (trigger) trigger.disabled = false;
                if (!stopped) {
                    // Дождаться завершения старого GET, если он ещё выполняется.
                    if (controller) { refreshPending = true; controller.abort(); }
                    else void poll();
                }
            }
        }
        for (const input of settings) listen(input, 'change', () => {
            void post(input.dataset.classroomSetting, { enabled: input.checked }, true);
        });
        for (const command of commands) listen(command, 'click', () => {
            void post(command.dataset.classroomAction, {}, true, command);
        });
        if (ui.sound) listen(ui.sound, 'click', async () => {
            pendingChime = true;
            await unlockSound();
            ui.sound.hidden = soundContext?.state === 'running';
            if (!ui.sound.hidden) notice('Браузер пока не разрешил звук. Уведомления о входе всё равно появятся сверху.');
        });
        listen(ui.cancel, 'click', () => { void post('cancel_wait', {}, false, ui.cancel); });
        listen(ui.indicator, 'click', () => {
            const panel = byId('ll-room-settings');
            panel.hidden = false;
            byId('ll-room-settings-toggle').setAttribute('aria-expanded', 'true');
        });
        listen(window, 'll-hand-toggle', () => {
            if (activeRoom && state) void post(state.own.hand_raised ? 'lower_hand' : 'raise_hand');
        });
        listen(window, 'll-livekit-room', ({ detail: { room } }) => {
            const wasConnected = !!activeRoom;
            activeRoom = room;
            if (!room && wasConnected) void post('leave');
            else void poll();
        });
        listen(window, 'll-classroom-refresh', () => { void poll(); });
        listen(window, 'll-connection', ({ detail }) => { connection = { ...connection, ...detail }; renderConnection(); });
        listen(window, 'online', () => { renderConnection(); void poll(); });
        listen(window, 'offline', () => { renderConnection(); window.clearTimeout(timer); });
        listen(document, 'visibilitychange', () => { if (!document.hidden) void poll(); else schedule(); });
        dispose = () => {
            stopped = true;
            controller?.abort();
            window.clearTimeout(timer);
            for (const [target, type, callback] of listeners) target.removeEventListener(type, callback);
        };
        renderConnection();
        void poll();
    }
    window.addEventListener('ll-page-updated', initialize);
    initialize();
})();
