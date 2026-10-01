(() => {
    'use strict';

    // Сохраняем исходные элементы/ID: контроллеры комнаты продолжают ими управлять.
    // Уведомления больше не меняют высоту звонка и остаются видимыми в fullscreen.
    const stack = document.createElement('div');
    stack.className = 'll-notification-stack';
    stack.setAttribute('aria-label', 'Уведомления');
    const records = new Map();
    function placeStack() {
        (document.fullscreenElement || document.webkitFullscreenElement || document.body).append(stack);
    }
    function register(source) {
        if (records.has(source)) return;
        const toast = document.createElement('div');
        toast.className = 'll-toast';
        toast.dataset.kind = source.dataset.noticeKind || 'info';
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'll-toast-close';
        close.textContent = '×';
        close.setAttribute('aria-label', 'Закрыть уведомление');
        const record = { toast, owner: source.closest('#ll-room, #ll-live-page'), text: '', dismissed: '', timer: null };
        records.set(source, record);
        toast.hidden = true;
        toast.append(source, close);
        stack.append(toast);
        function dismiss() {
            record.dismissed = record.text;
            toast.hidden = true;
            window.clearTimeout(record.timer);
        }
        close.addEventListener('click', dismiss);
        function sync() {
            const text = source.hidden ? '' : source.textContent.trim();
            if (!text) record.dismissed = '';
            toast.hidden = !text || text === record.dismissed;
            if (text === record.text) return;
            record.text = text;
            window.clearTimeout(record.timer);
            if (text && source.dataset.noticePersistent !== 'true') {
                record.timer = window.setTimeout(dismiss, source.dataset.noticeKind === 'error' ? 10000 : 7000);
            }
        }
        record.observer = new MutationObserver(sync);
        record.observer.observe(source, { attributes: true, attributeFilter: ['hidden'], childList: true, characterData: true, subtree: true });
        sync();
    }
    function scan() {
        for (const source of document.querySelectorAll('[data-ll-notice]')) register(source);
        for (const [source, record] of records) {
            if (record.owner && !record.owner.isConnected) {
                window.clearTimeout(record.timer);
                record.observer.disconnect();
                record.toast.remove();
                records.delete(source);
            }
        }
    }
    placeStack();
    scan();
    document.addEventListener('fullscreenchange', placeStack);
    document.addEventListener('webkitfullscreenchange', placeStack);
    window.addEventListener('ll-page-updated', scan);
})();
