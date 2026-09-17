(() => {
    const card = document.querySelector('.mock-processing-card');
    const message = document.getElementById('mock-processing-message');
    const button = document.getElementById('mock-analysis-button');
    if (!card || !message || !button) return;

    const csrfToken = document.cookie.split('; ')
        .find((item) => item.startsWith('csrftoken='))?.split('=')[1] || '';
    let running = false;
    const run = async () => {
        if (running) return;
        running = true;
        button.hidden = true;
        card.classList.add('is-running');
        message.textContent = 'ИИ оценивает ответы и практическое задание. Обычно это занимает до минуты.';
        try {
            const response = await fetch(card.dataset.analyzeUrl, {
                method: 'POST',
                headers: {'X-CSRFToken': decodeURIComponent(csrfToken)},
                credentials: 'same-origin',
            });
            const contentType = response.headers.get('content-type') || '';
            const data = contentType.includes('application/json')
                ? await response.json()
                : {error: 'Сервер не смог запустить анализ. Обновите страницу и попробуйте снова.'};
            if (!response.ok) throw new Error(data.error || 'Не удалось завершить анализ.');
            window.location.assign(data.redirect_url || card.dataset.resultUrl);
        } catch (error) {
            card.classList.remove('is-running');
            message.textContent = error.message;
            button.hidden = false;
            running = false;
        }
    };
    button.addEventListener('click', run);
    if (button.hidden) run();
})();
