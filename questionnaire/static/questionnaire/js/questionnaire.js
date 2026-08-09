'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const toast = document.createElement('div');
    toast.className = 'questionnaire-toast';
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    document.body.appendChild(toast);

    let toastTimer;
    const showToast = (message) => {
        window.clearTimeout(toastTimer);
        toast.textContent = message;
        toast.classList.add('is-visible');
        toastTimer = window.setTimeout(() => {
            toast.classList.remove('is-visible');
        }, 2600);
    };

    const copyText = async (text) => {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
            return;
        }

        const field = document.createElement('textarea');
        field.value = text;
        field.setAttribute('readonly', '');
        field.style.position = 'fixed';
        field.style.left = '-9999px';
        document.body.appendChild(field);
        field.select();
        const copied = document.execCommand('copy');
        field.remove();
        if (!copied) {
            throw new Error('copy-unavailable');
        }
    };

    document.querySelectorAll('[data-questionnaire-copy]').forEach((button) => {
        button.addEventListener('click', async () => {
            const value = button.dataset.questionnaireCopy;
            if (!value) {
                return;
            }

            button.disabled = true;
            try {
                await copyText(value);
                showToast('Ссылка на опрос скопирована.');
            } catch (error) {
                showToast('Не удалось скопировать ссылку.');
            } finally {
                button.disabled = false;
            }
        });
    });
});
