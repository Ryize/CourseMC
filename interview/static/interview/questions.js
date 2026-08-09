'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const csrfToken = document.querySelector(
        '[name="csrfmiddlewaretoken"]'
    )?.value;

    document.querySelectorAll('.interview-question-toggle').forEach((button) => {
        button.addEventListener('click', async () => {
            const card = button.closest('.interview-question');
            const status = card?.querySelector('.question-action-status');
            if (!csrfToken || !button.dataset.url || !button.dataset.action) {
                return;
            }

            button.disabled = true;

            try {
                const response = await fetch(button.dataset.url, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body: new URLSearchParams({action: button.dataset.action}),
                });
                const data = await response.json().catch(() => ({}));
                if (!response.ok) {
                    throw new Error(data.error || 'Не удалось сохранить отметку.');
                }

                card.dataset.progress = data.status;
                card.classList.add('is-answered');
                button.classList.add('is-answered');
                button.setAttribute('aria-pressed', 'true');
                button.title = 'Ответ отмечен. Вопрос не появится 14 дней';
                status.textContent = 'Отвечено';
            } catch (error) {
                status.textContent = error.message || 'Попробуйте ещё раз.';
                button.disabled = false;
            }
        });
    });
});
