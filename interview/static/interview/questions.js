'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('.questions-actions');
    const backLink = document.querySelector('.questions-back');
    const batchToken = form?.dataset.batchToken;
    const historyKey = form?.dataset.historyKey;
    if (form && backLink && batchToken && historyKey) {
        try {
            const storedValue = JSON.parse(localStorage.getItem(historyKey) || '[]');
            let batches = Array.isArray(storedValue)
                ? storedValue.filter((item) => typeof item === 'string')
                : [];
            const existingIndex = batches.indexOf(batchToken);
            if (existingIndex >= 0) {
                batches = batches.slice(0, existingIndex + 1);
            } else {
                batches.push(batchToken);
            }
            batches = batches.slice(-20);
            localStorage.setItem(historyKey, JSON.stringify(batches));

            const previousToken = batches.at(-2);
            if (previousToken) {
                const previousUrl = new URL(form.action, window.location.origin);
                previousUrl.searchParams.set('batch', previousToken);
                backLink.href = `${previousUrl.pathname}${previousUrl.search}`;
            }
        } catch (error) {
            // Если браузер запретил локальное хранилище, ссылка ведёт к настройкам.
        }
    }

    const csrfToken = document.querySelector(
        '[name="csrfmiddlewaretoken"]'
    )?.value;

    document.querySelectorAll('.interview-question').forEach((card) => {
        const button = card.querySelector('.interview-question-toggle');
        const status = card.querySelector('.question-action-status');
        if (!button || !status) {
            return;
        }

        const toggleQuestion = async () => {
            if (
                button.disabled
                || !csrfToken
                || !button.dataset.url
                || !card
                || !status
            ) {
                return;
            }

            const isAnswered = button.classList.contains('is-answered');
            const action = isAnswered ? 'repeat' : 'answered';
            button.disabled = true;
            status.classList.remove('is-error');

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
                status.classList.add('is-error');
                status.textContent = error.message || 'Попробуйте ещё раз.';
            } finally {
                button.disabled = false;
            }
        };

        button.addEventListener('click', (event) => {
            event.stopPropagation();
            toggleQuestion();
        });
        card.addEventListener('click', (event) => {
            if (event.target.closest('.question-search')) {
                return;
            }
            toggleQuestion();
        });
    });
});
