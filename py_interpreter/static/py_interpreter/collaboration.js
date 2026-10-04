/* Shared Python document: Yjs CRDT, authenticated Django transport, local execution. */
(() => {
    'use strict';
    const REMOTE = 'server';
    const toBase64 = (bytes) => {
        let value = '';
        for (const byte of bytes) value += String.fromCharCode(byte);
        return btoa(value);
    };
    const fromBase64 = (value) => Uint8Array.from(atob(value), (char) => char.charCodeAt(0));
    function replacement(before, after) {
        let start = 0, end = 0;
        while (start < before.length && start < after.length && before[start] === after[start]) start++;
        while (end < before.length - start && end < after.length - start &&
               before[before.length - end - 1] === after[after.length - end - 1]) end++;
        // Never split a UTF-16 surrogate pair.
        if (start && /[\uDC00-\uDFFF]/.test(before[start] || after[start] || '')) start--;
        if (end && /[\uDC00-\uDFFF]/.test(before[before.length - end] || after[after.length - end] || '')) end--;
        return {start, remove: before.length - start - end, insert: after.slice(start, after.length - end)};
    }

    class Binding {
        constructor(Y, doc, api, writable, changed) {
            this.Y = Y; this.doc = doc; this.api = api; this.writable = writable;
            this.text = doc.getText('code'); this.origin = {}; this.applying = false;
            this.markers = []; this.undo = new Y.UndoManager(this.text, {trackedOrigins: new Set([this.origin])});
            api.setCode(this.text.toString());
            this.onText = (event, transaction) => {
                if (transaction.origin === this.origin) return;
                this.applying = true;
                try {
                    if (api.editor) {
                        const aceDoc = api.editor.session.getDocument();
                        let index = 0;
                        for (const item of event.delta) {
                            if (item.retain) index += item.retain;
                            if (item.delete) {
                                aceDoc.remove({start: aceDoc.indexToPosition(index, 0),
                                    end: aceDoc.indexToPosition(index + item.delete, 0)});
                            }
                            if (typeof item.insert === 'string') {
                                aceDoc.insert(aceDoc.indexToPosition(index, 0), item.insert);
                                index += item.insert.length;
                            }
                        }
                    } else api.codeInput.value = this.text.toString();
                } finally { this.applying = false; api.updatePosition(); }
            };
            this.text.observe(this.onText);
            this.onChange = () => {
                if (this.applying) return;
                const after = api.getCode(), before = this.text.toString();
                if (!writable() || after.length > 20000) {
                    this.applying = true; api.setCode(before); this.applying = false;
                    if (after.length > 20000) changed('Максимум 20 000 символов кода.');
                    return;
                }
                const patch = replacement(before, after);
                doc.transact(() => {
                    if (patch.remove) this.text.delete(patch.start, patch.remove);
                    if (patch.insert) this.text.insert(patch.start, patch.insert);
                }, this.origin);
            };
            if (api.editor) {
                api.editor.session.on('change', this.onChange);
                for (const [name, win, mac] of [['undo', 'Ctrl-Z', 'Command-Z'], ['redo', 'Ctrl-Shift-Z|Ctrl-Y', 'Command-Shift-Z']]) {
                    api.editor.commands.addCommand({name, bindKey: {win, mac}, exec: () => {
                        if (writable() && !api.editor.getReadOnly()) this.undo[name]();
                    }});
                }
            } else {
                api.codeInput.addEventListener('input', this.onChange);
                api.root?.addEventListener('interpreter-code-change', this.onChange);
            }
        }
        selection() {
            const editor = this.api.editor, input = this.api.codeInput;
            let anchor, head;
            if (editor) {
                const aceDoc = editor.session.getDocument();
                anchor = aceDoc.positionToIndex(editor.selection.getSelectionAnchor(), 0);
                head = aceDoc.positionToIndex(editor.selection.getSelectionLead(), 0);
            } else {
                anchor = input.selectionStart; head = input.selectionEnd;
            }
            return {anchor: toBase64(this.Y.encodeRelativePosition(
                this.Y.createRelativePositionFromTypeIndex(this.text, anchor))),
            head: toBase64(this.Y.encodeRelativePosition(
                this.Y.createRelativePositionFromTypeIndex(this.text, head)))};
        }
        position(raw) {
            try {
                const absolute = this.Y.createAbsolutePositionFromRelativePosition(
                    this.Y.decodeRelativePosition(fromBase64(raw)), this.doc);
                return absolute?.type === this.text ? absolute.index : null;
            } catch (_) { return null; }
        }
        restore(selection) {
            const anchor = this.position(selection.anchor), head = this.position(selection.head);
            if (anchor === null || head === null) return;
            if (this.api.editor) {
                const aceDoc = this.api.editor.session.getDocument();
                const a = aceDoc.indexToPosition(anchor, 0), h = aceDoc.indexToPosition(head, 0);
                this.api.editor.selection.setSelectionAnchor(a.row, a.column);
                this.api.editor.selection.selectTo(h.row, h.column);
            } else this.api.codeInput.setSelectionRange(Math.min(anchor, head), Math.max(anchor, head));
        }
        cursors(people, identity) {
            const editor = this.api.editor;
            if (!editor) return;
            for (const marker of this.markers) editor.session.removeMarker(marker);
            this.markers = [];
            const Range = window.ace.require('ace/range').Range;
            for (const person of people) {
                if (person.identity === identity) continue;
                const anchor = this.position(person.cursor?.anchor), head = this.position(person.cursor?.head);
                if (anchor === null || head === null) continue;
                const doc = editor.session.getDocument(), a = doc.indexToPosition(Math.min(anchor, head), 0);
                const h = doc.indexToPosition(Math.max(anchor, head), 0);
                // A one-character marker also keeps a collapsed remote cursor visible.
                const range = new Range(a.row, a.column, h.row, h.column + (anchor === head ? 1 : 0));
                this.markers.push(editor.session.addMarker(range, `shared-code-cursor shared-code-color-${color(person.identity)}`, 'text', false));
            }
        }
        destroy() {
            this.cursors([], ''); this.text.unobserve(this.onText); this.undo.destroy();
            if (this.api.editor) this.api.editor.session.off('change', this.onChange);
            else {
                this.api.codeInput.removeEventListener('input', this.onChange);
                this.api.root?.removeEventListener('interpreter-code-change', this.onChange);
            }
        }
    }
    function color(identity) {
        let hash = 0;
        for (const char of identity) hash = (hash * 31 + char.charCodeAt(0)) | 0;
        return Math.abs(hash) % 6;
    }

    class SharedClient {
        constructor(Y, root, api) {
            this.Y = Y; this.root = root; this.api = api; this.pending = [];
            this.editable = false; this.busy = false; this.closed = false; this.binding = null;
            this.serverVector = null; this.identity = ''; this.recovery = '';
            this.reset();
        }
        reset() {
            this.binding?.destroy(); this.doc?.destroy();
            this.doc = new this.Y.Doc(); this.pending = []; this.binding = null; this.serverVector = null;
            this.doc.on('update', (update, origin) => {
                if (origin !== REMOTE) {
                    this.pending.push(update);
                    this.status('Сохранение…');
                    this.schedule(100);
                }
            });
        }
        status(text) {
            document.getElementById('shared-code-status').textContent = text;
            document.getElementById('draft-status').textContent = text;
        }
        showError(text = '') {
            const error = document.getElementById('shared-code-error');
            error.textContent = text; error.hidden = !text;
        }
        schedule(delay = 900) {
            if (this.closed) return;
            clearTimeout(this.timer);
            this.timer = setTimeout(() => this.sync(), delay);
        }
        async post(url, data) {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 8000);
            try {
                const response = await fetch(url, {method: 'POST', credentials: 'same-origin',
                    cache: 'no-store', signal: controller.signal,
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken':
                        this.root.querySelector('[name=csrfmiddlewaretoken]').value}, body: JSON.stringify(data)});
                const body = await response.json().catch(() => ({}));
                if (!response.ok) {
                    const error = new Error(body.error || (response.status === 403 ? 'Доступ к редактору закрыт.' : 'Не удалось синхронизировать код.'));
                    error.status = response.status; error.code = body.code; throw error;
                }
                return body;
            } finally { clearTimeout(timeout); }
        }
        async sync() {
            if (this.busy || this.closed) return;
            this.busy = true;
            const batch = this.pending.slice();
            try {
                const result = await this.post(this.root.dataset.syncUrl, {
                    vector: toBase64(this.Y.encodeStateVector(this.doc)),
                    update: batch.length ? toBase64(this.Y.mergeUpdates(batch)) : '',
                    cursor: this.binding?.selection() || {},
                });
                const selection = this.binding?.selection();
                this.Y.applyUpdate(this.doc, fromBase64(result.update), REMOTE);
                this.pending.splice(0, batch.length); // New edits made during this request stay queued.
                this.serverVector = fromBase64(result.vector); this.identity = result.identity;
                if (!this.binding) this.binding = new Binding(this.Y, this.doc, this.api,
                    () => this.editable, (message) => this.showError(message));
                else if (selection) this.binding.restore(selection);
                this.editable = result.can_edit && this.hostConnected !== false;
                this.api.setEditable(this.editable);
                this.showError();
                this.status(!result.active ? 'Занятие завершено · только просмотр' :
                    this.pending.length ? 'Сохранение…' : this.editable ? 'Общий код · все правки сохранены' : 'Просмотр · правки разрешает преподаватель');
                this.render(result);
                return true;
            } catch (error) {
                this.editable = false; this.api.setEditable(false);
                this.showError(error.message);
                this.status('Синхронизация приостановлена');
                if ([400, 403, 409].includes(error.status) && this.pending.length) {
                    this.recovery = this.api.getCode();
                    document.getElementById('shared-code-recovery').hidden = false;
                    this.reset(); // Rejoin canonical server state, never resubmit forbidden edits.
                }
            } finally {
                this.busy = false;
                this.schedule(this.pending.length ? 150 : 900);
            }
        }
        render(result) {
            const people = document.getElementById('shared-code-people'); people.replaceChildren();
            for (const person of result.people) {
                const label = document.createElement('span');
                label.className = `shared-code-person shared-code-color-${color(person.identity)}`;
                label.textContent = `${person.name}${person.identity === result.identity ? ' · вы' : ''}`;
                label.title = person.can_edit ? 'Редактирует' : 'Смотрит'; people.append(label);
            }
            this.binding.cursors(result.people, result.identity);
            const members = document.getElementById('shared-code-members');
            if (members && !members.contains(document.activeElement)) {
                members.replaceChildren();
                for (const member of result.members) {
                    const label = document.createElement('label'), text = document.createElement('span');
                    const input = document.createElement('input'); input.type = 'checkbox'; input.checked = member.can_edit;
                    input.disabled = !result.active; text.textContent = member.name;
                    input.addEventListener('change', async () => {
                        input.disabled = true;
                        try { await this.post(this.root.dataset.manageUrl, {action: 'grant', identity: member.identity, enabled: input.checked}); }
                        catch (error) { this.showError(error.message); }
                        finally { input.disabled = false; this.schedule(0); }
                    });
                    label.append(text, input); members.append(label);
                }
                if (!result.members.length) members.textContent = 'Другие участники пока не вошли в комнату.';
            }
            const versions = document.getElementById('shared-code-versions'); versions.replaceChildren();
            for (const version of result.snapshots) {
                const li = document.createElement('li'), a = document.createElement('a');
                a.href = version.url; a.textContent = `${version.title} · ${version.created_at} · .py`;
                li.append(a); versions.append(li);
            }
            if (!result.snapshots.length) versions.textContent = 'Сохранённых версий пока нет.';
        }
        async persist(url, data) {
            // Wait for any in-flight poll, then explicitly flush outstanding edits.
            while (this.busy) await new Promise((resolve) => setTimeout(resolve, 50));
            const synced = await this.sync();
            if (!synced || this.pending.length || !this.serverVector) throw new Error('Сначала дождитесь сохранения всех правок.');
            return this.post(url, data);
        }
        async save(title) {
            return this.persist(this.root.dataset.manageUrl, {action: 'save', title});
        }
        async publish(title, target) {
            return this.persist(this.root.dataset.publishUrl, {title, code_target: target});
        }
        close() {
            this.closed = true; clearTimeout(this.timer); this.api.setEditable(false);
            this.binding?.destroy(); this.doc.destroy();
        }
    }
    if (typeof module !== 'undefined') module.exports = {Binding, SharedClient, replacement, toBase64, fromBase64};
    if (typeof document === 'undefined') return;
    const root = document.querySelector('.interpreter[data-shared-id]');
    if (!root) return;
    root.addEventListener('interpreter-ready', (event) => {
        if (!window.CourseCodeY) {
            document.getElementById('shared-code-status').textContent = 'Не удалось загрузить совместный редактор. Обновите страницу.';
            return;
        }
        const client = new SharedClient(window.CourseCodeY, root, event.detail);
        client.sync();
        document.getElementById('shared-code-save')?.addEventListener('submit', async (event) => {
            event.preventDefault(); const button = event.currentTarget.querySelector('button'); button.disabled = true;
            try {
                await client.save(document.getElementById('shared-code-title').value);
                client.status('Версия созвона сохранена'); client.schedule(0);
            } catch (error) { client.showError(error.message); }
            finally { button.disabled = false; }
        });
        document.getElementById('shared-code-publish')?.addEventListener('submit', async (event) => {
            event.preventDefault(); const button = event.currentTarget.querySelector('button'); button.disabled = true;
            try {
                const result = await client.publish(document.getElementById('shared-code-title').value,
                    event.currentTarget.querySelector('[name=code_target]').value);
                const notice = document.getElementById('shared-code-published');
                notice.textContent = result.message; notice.hidden = false; client.schedule(0);
            } catch (error) { client.showError(error.message); }
            finally { button.disabled = false; }
        });
        document.getElementById('shared-code-recovery').addEventListener('click', () => {
            const url = URL.createObjectURL(new Blob([client.recovery], {type: 'text/x-python;charset=utf-8'}));
            const link = document.createElement('a'); link.href = url; link.download = 'unsaved-lesson.py'; link.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        });
        window.addEventListener('beforeunload', (event) => {
            if (client.pending.length || client.recovery) { event.preventDefault(); event.returnValue = ''; }
        });
        window.addEventListener('pagehide', () => client.close());
        window.addEventListener('message', (event) => {
            if (event.origin !== location.origin || event.source !== window.parent) return;
            if (event.data?.type === 'shared-code-theme') {
                document.body.classList.toggle('black', !!event.data.dark);
                client.api.editor?.resize();
            }
            if (event.data?.type === 'shared-code-connection' && !event.data.connected) {
                client.hostConnected = false; client.editable = false; client.api.setEditable(false);
            } else if (event.data?.type === 'shared-code-connection') {
                client.hostConnected = true; client.schedule(0);
            }
        });
    });
})();
