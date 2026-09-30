(() => {
    'use strict';

    const root = document.getElementById('ll-chat');
    if (!root) return;
    const byId = (id) => document.getElementById(id);
    const ui = {
        messages: byId('ll-chat-messages'), older: byId('ll-chat-older'),
        empty: byId('ll-chat-empty'), error: byId('ll-chat-error'),
        form: byId('ll-chat-form'), body: byId('ll-chat-body'),
        file: byId('ll-chat-file'), selected: byId('ll-chat-selected-file'),
        selectedRow: byId('ll-chat-selected-row'), clearFile: byId('ll-chat-clear-file'),
        send: byId('ll-chat-send'), count: byId('ll-chat-count'),
    };
    const live = root.dataset.live === 'true';
    let mediaRoom = null;
    function connected() {
        return !!mediaRoom && !!window.LivekitClient &&
            mediaRoom.state === window.LivekitClient.ConnectionState.Connected;
    }

    function updateAvailability() {
        if (!live || !ui.form) return;
        const active = connected();
        ui.form.querySelectorAll('textarea, input, button').forEach((field) => { field.disabled = !active; });
        ui.body.placeholder = active ? 'Сообщение участникам…' : 'Войдите в комнату, чтобы написать сообщение';
    }
    let oldestId = null;
    let newestId = null;
    let fetching = false;
    let refreshPending = false;
    let lastSignalRefresh = 0;
    let lastFetchAt = 0;
    let fetchErrorShown = false;
    let pastedFile = null;
    let pastedFileName = '';
    const displayed = new Set();
    const maxAttachmentBytes = 25 * 1024 * 1024;
    const allowedExtensions = new Set((ui.file?.accept || '').split(',')
        .map((type) => type.trim().replace(/^\./, '').toLowerCase()).filter(Boolean));
    const clipboardExtensions = {
        'image/png': 'png', 'image/jpeg': 'jpg', 'image/jpg': 'jpg', 'image/gif': 'gif',
        'image/webp': 'webp', 'video/mp4': 'mp4', 'video/webm': 'webm',
        'application/pdf': 'pdf', 'text/plain': 'txt', 'text/markdown': 'md',
        'text/x-python': 'py',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
    };

    function showError(text, fromFetch = false) {
        ui.error.textContent = text || '';
        ui.error.hidden = !text;
        fetchErrorShown = !!text && fromFetch;
    }

    function humanSize(bytes) {
        return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} МБ` :
            `${Math.max(1, Math.ceil(bytes / 1024))} КБ`;
    }

    function renderMessage(message) {
        const item = document.createElement('li');
        item.className = 'll-chat-message';
        if (String(message.author_id) === root.dataset.userId) item.classList.add('ll-chat-own');
        item.dataset.id = String(message.id);
        const avatar = document.createElement('span');
        avatar.className = 'll-chat-avatar';
        avatar.textContent = Array.from(message.author.trim())[0]?.toUpperCase() || '•';
        avatar.setAttribute('aria-hidden', 'true');
        const bubble = document.createElement('div');
        bubble.className = 'll-chat-bubble';
        const header = document.createElement('div');
        header.className = 'll-chat-message-header';
        const author = document.createElement('strong');
        author.textContent = message.author;
        const when = document.createElement('time');
        when.dateTime = message.created_at;
        when.textContent = new Date(message.created_at).toLocaleString('ru-RU', {
            day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
        });
        header.append(author, when);
        bubble.appendChild(header);
        if (message.body) {
            const body = document.createElement('p');
            body.className = 'll-chat-message-body';
            body.textContent = message.body;
            bubble.appendChild(body);
        }
        if (message.attachment) {
            const link = document.createElement('a');
            link.className = 'll-chat-attachment';
            link.href = message.attachment.url;
            link.textContent = `${message.attachment.name} · ${humanSize(message.attachment.size)}`;
            link.setAttribute('download', message.attachment.name);
            bubble.appendChild(link);
        }
        item.append(avatar, bubble);
        return item;
    }

    function updateSelectedFile() {
        const file = pastedFile || ui.file.files[0];
        ui.selected.textContent = file ? `${pastedFileName || file.name} · ${humanSize(file.size)}` : '';
        ui.selectedRow.hidden = !file;
    }

    function clipboardFiles(clipboard) {
        const files = Array.from(clipboard?.files || []);
        if (files.length) return files;
        for (const item of clipboard?.items || []) {
            if (item.kind === 'file') {
                const file = item.getAsFile();
                if (file) files.push(file);
            }
        }
        return files;
    }

    function pasteAttachment(event) {
        if (live && !connected()) return;
        const files = clipboardFiles(event.clipboardData);
        if (!files.length) return; // Обычный текст вставляется браузером как прежде.
        event.preventDefault();
        if (files.length !== 1) {
            showError('За один раз можно прикрепить только один файл.');
            return;
        }
        const file = files[0];
        const extension = clipboardExtensions[file.type];
        const name = file.name && /\.[^./\\]+$/.test(file.name) ? file.name :
            extension ? `Вставленный файл.${extension}` : file.name;
        const suffix = name?.split('.').pop().toLowerCase();
        if (!allowedExtensions.has(suffix)) {
            showError('Этот тип файла не поддерживается.');
            return;
        }
        if (!file.size || file.size > maxAttachmentBytes) {
            showError('Размер файла должен быть от 1 байта до 25 МБ.');
            return;
        }
        pastedFile = file;
        pastedFileName = name;
        ui.file.value = '';
        updateSelectedFile();
        showError('');
    }

    function addMessages(messages, prepend = false) {
        if (!messages.length) return;
        const nearBottom = ui.messages.scrollHeight - ui.messages.scrollTop - ui.messages.clientHeight < 100;
        const oldHeight = ui.messages.scrollHeight;
        const fragment = document.createDocumentFragment();
        for (const message of messages) {
            if (displayed.has(message.id)) continue;
            displayed.add(message.id);
            oldestId = oldestId === null ? message.id : Math.min(oldestId, message.id);
            newestId = newestId === null ? message.id : Math.max(newestId, message.id);
            fragment.appendChild(renderMessage(message));
        }
        if (prepend) {
            ui.messages.prepend(fragment);
            ui.messages.scrollTop += ui.messages.scrollHeight - oldHeight;
        } else {
            ui.messages.append(fragment);
            if (nearBottom || displayed.size <= messages.length) ui.messages.scrollTop = ui.messages.scrollHeight;
        }
        ui.empty.hidden = displayed.size > 0;
        ui.count.textContent = displayed.size ? `${displayed.size} в истории` : '';
    }

    async function loadPage(mode = 'initial') {
        if (live && !connected()) return;
        if (document.hidden && mode === 'new') return;
        if (fetching) {
            if (mode === 'new') refreshPending = true;
            return;
        }
        fetching = true;
        const url = new URL(root.dataset.messagesUrl, location.href);
        if (mode === 'new' && newestId !== null) url.searchParams.set('after', newestId);
        if (mode === 'older' && oldestId !== null) url.searchParams.set('before', oldestId);
        try {
            const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store',
                headers: { Accept: 'application/json' } });
            if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
                throw new Error('Не удалось загрузить чат. Обновите страницу.');
            }
            const data = await response.json();
            addMessages(data.messages, mode === 'older');
            if (mode !== 'older') lastFetchAt = Date.now();
            if (mode !== 'new') ui.older.hidden = !data.has_more;
            if (fetchErrorShown) showError('');
            if (mode === 'new' && data.has_more) window.setTimeout(() => { void loadPage('new'); }, 0);
        } catch (error) {
            showError(error.message || 'Не удалось загрузить чат.', true);
        } finally {
            fetching = false;
            if (refreshPending) {
                refreshPending = false;
                void loadPage('new');
            }
        }
    }

    async function send(event) {
        event.preventDefault();
        if (!ui.form || ui.send.disabled || (live && !connected())) return;
        showError('');
        ui.send.disabled = true;
        ui.send.querySelector('span').textContent = 'Отправка…';
        try {
            const payload = new FormData(ui.form);
            if (pastedFile) payload.set('attachment', pastedFile, pastedFileName);
            const response = await fetch(root.dataset.sendUrl, {
                method: 'POST', credentials: 'same-origin', cache: 'no-store',
                body: payload, headers: { Accept: 'application/json' },
            });
            if (!response.headers.get('content-type')?.includes('application/json')) {
                throw new Error('Сессия истекла. Обновите страницу и войдите снова.');
            }
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Не удалось отправить сообщение.');
            addMessages([data.message]);
            ui.body.value = '';
            ui.file.value = '';
            pastedFile = null;
            pastedFileName = '';
            updateSelectedFile();
            if (mediaRoom && window.LivekitClient &&
                mediaRoom.state === window.LivekitClient.ConnectionState.Connected) {
                const bytes = new TextEncoder().encode(String(data.message.id));
                try { await mediaRoom.localParticipant.publishData(bytes, {
                    reliable: true, topic: 'lesson-chat-updated',
                }); } catch (_) { /* История уже сохранена в Django; остальные увидят её при опросе. */ }
            }
        } catch (error) {
            showError(error.message || 'Не удалось отправить сообщение.');
        } finally {
            ui.send.disabled = live && !connected();
            ui.send.querySelector('span').textContent = 'Отправить';
        }
    }

    ui.older.addEventListener('click', () => { void loadPage('older'); });
    if (ui.form) {
        ui.form.addEventListener('submit', (event) => { void send(event); });
        ui.form.addEventListener('paste', pasteAttachment);
        ui.file.addEventListener('change', () => {
            if (ui.file.files.length) {
                pastedFile = null;
                pastedFileName = '';
            }
            updateSelectedFile();
            showError('');
        });
        ui.clearFile.addEventListener('click', () => {
            pastedFile = null;
            pastedFileName = '';
            ui.file.value = '';
            updateSelectedFile();
            showError('');
        });
        ui.body.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && !event.shiftKey && !event.isComposing &&
                window.matchMedia('(pointer: fine)').matches) {
                event.preventDefault();
                ui.form.requestSubmit();
            }
        });
    }
    window.addEventListener('ll-livekit-room', (event) => {
        mediaRoom = event.detail.room;
        updateAvailability();
        if (connected()) void loadPage();
    });
    window.addEventListener('ll-chat-update', () => {
        const now = Date.now();
        if (now - lastSignalRefresh < 800) return;
        lastSignalRefresh = now;
        void loadPage('new');
    });
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && live) void loadPage('new');
    });
    if (live) window.setInterval(() => {
        if (connected() && Date.now() - lastFetchAt >= 30000) void loadPage('new');
    }, 4000);
    updateAvailability();
    if (!live) void loadPage();
})();
