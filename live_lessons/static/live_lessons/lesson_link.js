(() => {
    'use strict';

    const button = document.querySelector('[data-lesson-copy]');
    if (!button) return;

    const label = button.querySelector('span');
    const originalLabel = label.textContent;
    let resetTimer;
    let copied = false;

    function setLabel(value) {
        window.clearTimeout(resetTimer);
        label.textContent = value;
        button.title = value === 'Скопировано' ? 'Ссылка скопирована' : 'Скопировать ссылку на занятие';
        if (value !== originalLabel) {
            resetTimer = window.setTimeout(() => { label.textContent = originalLabel; button.title = 'Скопировать ссылку на занятие'; }, 2500);
        }
    }

    function legacyCopy(value) {
        const field = document.createElement('textarea');
        field.value = value;
        field.setAttribute('readonly', '');
        field.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0';
        document.body.appendChild(field);
        field.select();
        try {
            if (!document.execCommand('copy')) throw new Error('Clipboard copy failed');
        } finally {
            field.remove();
        }
    }

    async function copyLink(allowLegacy) {
        const url = button.dataset.lessonUrl;
        if (!url) return false;
        try {
            if (!navigator.clipboard?.writeText) throw new Error('Clipboard API unavailable');
            await navigator.clipboard.writeText(url);
        } catch (_) {
            if (!allowLegacy) return false;
            try { legacyCopy(url); }
            catch (_) { return false; }
        }
        copied = true;
        setLabel('Скопировано');
        return true;
    }

    button.addEventListener('click', async () => {
        if (!await copyLink(true)) setLabel('Не удалось скопировать');
    });

    // Browsers may deny clipboard writes without a user gesture. The button remains a fallback.
    if (button.dataset.autoCopy === 'true') {
        void copyLink(false);
        document.getElementById('ll-room-join')?.addEventListener('click', () => {
            if (!copied) void copyLink(false);
        });
    }
})();
