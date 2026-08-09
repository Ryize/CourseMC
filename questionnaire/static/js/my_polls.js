function showMessage(text, level = "info") {
    const messages = document.getElementById("messages-list");
    if (!messages) {
        return;
    }

    const item = document.createElement("li");
    const alert = document.createElement("div");
    alert.textContent = text;
    alert.className = `alert alert-${level} msg fade show`;
    alert.setAttribute("role", "alert");
    item.appendChild(alert);
    messages.appendChild(item);

    if (typeof window.fadeAlerts === "function") {
        window.fadeAlerts();
    }
}

async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return;
    }

    const field = document.createElement("textarea");
    field.value = text;
    field.setAttribute("readonly", "");
    field.style.position = "fixed";
    field.style.left = "-9999px";
    document.body.appendChild(field);
    field.select();
    const copied = document.execCommand("copy");
    field.remove();

    if (!copied) {
        throw new Error("Clipboard API is unavailable");
    }
}

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".poll-toggle").forEach((button) => {
        button.addEventListener("click", () => {
            const target = document.getElementById(button.dataset.target);
            if (!target) {
                return;
            }

            const shouldOpen = target.hidden;
            target.hidden = !shouldOpen;
            button.setAttribute("aria-expanded", String(shouldOpen));
            button.textContent = shouldOpen
                ? button.dataset.hideLabel
                : button.dataset.showLabel;
        });
    });

    document.querySelectorAll(".poll-copy").forEach((button) => {
        button.addEventListener("click", async () => {
            button.disabled = true;
            try {
                await copyText(button.dataset.url);
                showMessage("Ссылка успешно скопирована!");
            } catch (error) {
                showMessage(
                    "Не удалось скопировать ссылку. Скопируйте её из адресной строки.",
                    "danger",
                );
            } finally {
                button.disabled = false;
            }
        });
    });
});
