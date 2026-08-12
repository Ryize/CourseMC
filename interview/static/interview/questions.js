'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const csrfToken = document.querySelector(
        '[name="csrfmiddlewaretoken"]'
    )?.value;

    document.querySelectorAll('.interview-question-toggle').forEach((button) => {
        button.addEventListener('click', async () => {
            const card = button.closest('.interview-question');
            const status = card?.querySelector('.question-action-status');
            if (!csrfToken || !button.dataset.url || !card || !status) {
                return;
            }

            const isAnswered = button.classList.contains('is-answered');
            const action = isAnswered ? 'repeat' : 'answered';
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
                    body: new URLSearchParams({action}),
                });
                const data = await response.json().catch(() => ({}));
                if (!response.ok) {
                    throw new Error(data.error || 'Не удалось сохранить отметку.');
                }

                const answered = data.status === 'answered';
                card.dataset.progress = data.status;
                card.classList.toggle('is-answered', answered);
                button.classList.toggle('is-answered', answered);
                button.setAttribute('aria-pressed', String(answered));
                button.title = answered
                    ? 'Ответ отмечен. Нажмите ещё раз, чтобы вернуть вопрос на повторение'
                    : 'Нажмите, если ответили на вопрос';
                status.textContent = answered ? 'Отвечено' : '';
            } catch (error) {
                status.textContent = error.message || 'Попробуйте ещё раз.';
            } finally {
                button.disabled = false;
            }
        });
    });
});
