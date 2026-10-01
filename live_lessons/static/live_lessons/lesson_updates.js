(() => {
    'use strict';

    const root = document.getElementById('ll-live-page');
    if (!root) return;
    window.coursemcLiveUpdates = true;
    const byId = (id) => document.getElementById(id);
    const notice = byId('ll-updates-notice');
    const isDetail = root.dataset.updatesKind === 'detail';
    let revision = root.dataset.revision;
    let timer = null;
    let running = null;
    let stopped = false;
    let suspended = false;
    let failures = 0;
    let submitting = false;
    let refreshPending = false;
    let mediaConnected = false;

    function showNotice(text) {
        notice.textContent = text || '';
        notice.hidden = !text;
    }

    async function notifyRoom(state) {
        // Обработчик комнаты завершает соединение до удаления её DOM при закрытии урока.
        const pending = [];
        window.dispatchEvent(new CustomEvent('ll-lesson-state', {
            detail: { state, waitUntil: (promise) => pending.push(promise) },
        }));
        await Promise.all(pending);
    }

    async function requestJSON(url, options = {}) {
        const controller = new AbortController();
        const timeout = window.setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch(url, {
                credentials: 'same-origin', cache: 'no-store', ...options,
                signal: controller.signal,
                headers: { Accept: 'application/json', ...options.headers },
            });
            if (response.redirected || response.status === 401 || response.status === 403 ||
                (response.status === 404 && !options.method)) {
                stopped = true;
                await notifyRoom({ status: 'unavailable', can_join: false, removed: false });
                throw new Error('Доступ к занятию закрыт или сессия истекла. Войдите на сайт снова.');
            }
            if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
                if (options.method && response.headers.get('content-type')?.includes('application/json')) {
                    const data = await response.json();
                    if (data.error) throw new Error(data.error);
                }
                throw new Error(options.method ? 'Не удалось выполнить действие. Попробуйте ещё раз.' :
                    'Не удалось обновить занятие. Повторим автоматически, когда восстановится связь.');
            }
            return await response.json();
        } catch (error) {
            if (error.name === 'AbortError') throw new Error('Сервер не ответил вовремя. Повторим обновление автоматически.');
            throw error;
        } finally {
            window.clearTimeout(timeout);
        }
    }

    function replaceContent(element, html) {
        // Не сбрасываем выбранный урок программы при фоновом появлении нового архива.
        const fields = [...element.querySelectorAll('select, textarea, input:not([type=hidden]):not([type=file])')]
            .map((field) => ({ name: field.name, value: field.value, checked: field.checked,
                focused: field === document.activeElement }));
        element.innerHTML = html;
        for (const field of element.querySelectorAll('select, textarea, input:not([type=hidden]):not([type=file])')) {
            const previous = fields.find((item) => item.name && item.name === field.name);
            if (!previous) continue;
            if (field.tagName !== 'SELECT' || [...field.options].some((option) => option.value === previous.value)) {
                field.value = previous.value;
                field.checked = previous.checked;
            }
            if (previous.focused) field.focus({ preventScroll: true });
        }
    }

    async function updateDetail(force) {
        const state = await requestJSON(root.dataset.stateUrl);
        await notifyRoom(state);
        if (!force && state.revision === revision) return;
        const url = new URL(location.href);
        url.searchParams.delete('room');
        // Комната создаётся лишь при открытии входа; уже подключённую не заменяем.
        if (!byId('ll-room')) url.searchParams.set('room', '1');
        const data = await requestJSON(url);
        await notifyRoom(data.state);
        replaceContent(byId('ll-lesson-before'), data.before_html);
        const roomSlot = byId('ll-lesson-room');
        const roomOpen = data.state.status === 'live' && (data.state.can_join || data.state.removed);
        if (!roomOpen) roomSlot.replaceChildren();
        else if (!byId('ll-room') && data.room_html) roomSlot.innerHTML = data.room_html;
        replaceContent(byId('ll-lesson-after'), data.after_html);
        root.dataset.status = data.state.status;
        root.dataset.roomOpen = String(roomOpen);
        root.closest('main').classList.toggle('ll-shell-live', roomOpen);
        revision = data.state.revision;
        window.dispatchEvent(new Event('ll-page-updated'));
        await notifyRoom(data.state);
    }

    async function updateList() {
        const url = new URL(location.href);
        url.searchParams.set('revision', revision);
        const data = await requestJSON(url);
        if (data.changed) replaceContent(byId('ll-lesson-list-content'), data.html);
        revision = data.revision;
    }

    function schedule() {
        window.clearTimeout(timer);
        if (stopped || suspended || submitting || (document.hidden && !mediaConnected) || navigator.onLine === false) return;
        const base = document.hidden ? 15000 :
            isDetail && root.dataset.status === 'scheduled' ? 3000 : 5000;
        timer = window.setTimeout(() => { void refresh(); }, Math.min(30000, base * 2 ** failures));
    }

    function refresh(force = false) {
        if (stopped || suspended || (document.hidden && !mediaConnected && !force) || navigator.onLine === false) return Promise.resolve();
        if (running || submitting) {
            if (force) refreshPending = true;
            return running || Promise.resolve();
        }
        window.clearTimeout(timer);
        running = (async () => {
            try {
                if (isDetail) await updateDetail(force); else await updateList();
                failures = 0;
                showNotice('');
            } catch (error) {
                failures = Math.min(4, failures + 1);
                if (stopped || failures >= 3 || force) showNotice(error.message || 'Не удалось обновить занятие.');
            } finally {
                running = null;
                if (refreshPending && !submitting) {
                    refreshPending = false;
                    void refresh(true);
                } else schedule();
            }
        })();
        return running;
    }

    root.addEventListener('submit', async (event) => {
        const form = event.target.closest('form[data-lesson-action]');
        if (!form || !root.contains(form)) return;
        event.preventDefault();
        if (submitting || stopped) return;
        submitting = true;
        window.clearTimeout(timer);
        const buttons = [...root.querySelectorAll('form[data-lesson-action] button')];
        buttons.forEach((button) => { button.disabled = true; });
        let actionError = '';
        let actionMessage = '';
        try {
            if (running) await running;
            const result = await requestJSON(form.action, { method: 'POST', body: new FormData(form) });
            actionMessage = result.message || '';
            showNotice('');
        } catch (error) {
            actionError = error.message || 'Не удалось выполнить действие.';
        } finally {
            submitting = false;
            buttons.forEach((button) => { button.disabled = false; });
            refreshPending = false;
            await refresh(true);
            if (actionError || actionMessage) showNotice(actionError || actionMessage);
        }
    });

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) schedule();
        else void refresh();
    });
    window.addEventListener('ll-livekit-room', (event) => {
        mediaConnected = !!event.detail.room;
        schedule();
    });
    window.addEventListener('online', () => { void refresh(); });
    window.addEventListener('offline', () => { window.clearTimeout(timer); });
    window.addEventListener('pageshow', () => { suspended = false; void refresh(); });
    window.addEventListener('pagehide', () => { suspended = true; window.clearTimeout(timer); });
    void refresh();
})();
