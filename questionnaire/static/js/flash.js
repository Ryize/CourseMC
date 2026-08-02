window.fadeAlerts = function fadeAlerts() {
    const alerts = Array.from(document.getElementsByClassName("alert msg"));
    alerts.forEach((alert, index) => {
        const delay = 3250 + (1000 * (alerts.length - index - 1));
        window.setTimeout(() => {
            alert.style.transition = "opacity 300ms";
            alert.style.opacity = "0";
            window.setTimeout(() => alert.remove(), 300);
        }, delay);
    });
};

window.addEventListener("DOMContentLoaded", window.fadeAlerts);
