(() => {
    'use strict';
    let currentRoot = null, dispose = () => {};
    function initialize() {
        const root = document.getElementById('ll-room');
        if (root === currentRoot) return;
        dispose(); currentRoot = root;
        if (!root) return;
        const button = document.getElementById('ll-room-code-toggle');
        const close = document.getElementById('ll-room-code-close');
        const panel = document.getElementById('ll-room-code');
        const frame = document.getElementById('ll-room-code-frame');
        const sendTheme = () => frame.contentWindow?.postMessage({type: 'shared-code-theme',
            dark: document.body.classList.contains('black')}, location.origin);
        const setOpen = (open) => {
            panel.hidden = !open; button.setAttribute('aria-expanded', String(open));
            if (open && !frame.getAttribute('src')) frame.src = frame.dataset.src;
            if (open) sendTheme();
        };
        const update = () => {
            const connected = root.dataset.connected === 'true';
            button.disabled = !connected;
            frame.contentWindow?.postMessage({type: 'shared-code-connection', connected}, location.origin);
            if (!connected) setOpen(false);
        };
        const toggle = () => { if (!button.disabled) setOpen(panel.hidden); };
        const hide = () => setOpen(false);
        button.addEventListener('click', toggle); close.addEventListener('click', hide);
        frame.addEventListener('load', sendTheme);
        const observer = new MutationObserver(update);
        observer.observe(root, {attributes: true, attributeFilter: ['data-connected']});
        const theme = new MutationObserver(sendTheme);
        theme.observe(document.body, {attributes: true, attributeFilter: ['class']});
        update();
        dispose = () => {
            observer.disconnect(); theme.disconnect();
            button.removeEventListener('click', toggle); close.removeEventListener('click', hide);
            frame.removeEventListener('load', sendTheme);
        };
    }
    document.addEventListener('DOMContentLoaded', initialize);
    window.addEventListener('ll-page-updated', initialize);
})();
