(() => {
    const timer = document.querySelector('.mock-timer');
    const output = document.getElementById('mock-timer-value');
    if (!timer || !output) return;
    const storageKey = `mock-interview-timer-${location.pathname}`;
    const savedDeadline = Number(sessionStorage.getItem(storageKey));
    const duration = Number(timer.dataset.minutes || 30) * 60 * 1000;
    const deadline = savedDeadline > Date.now() ? savedDeadline : Date.now() + duration;
    sessionStorage.setItem(storageKey, String(deadline));
    const render = () => {
        const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
        const minutes = String(Math.floor(remaining / 60)).padStart(2, '0');
        const seconds = String(remaining % 60).padStart(2, '0');
        output.textContent = `${minutes}:${seconds}`;
        timer.classList.toggle('is-expired', remaining === 0);
        if (remaining) window.setTimeout(render, 1000);
    };
    render();
})();
