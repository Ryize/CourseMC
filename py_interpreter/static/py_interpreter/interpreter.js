'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const root = document.querySelector('.interpreter');
    const codeInput = document.getElementById('python-code');
    const output = document.getElementById('python-output');
    const status = document.getElementById('interpreter-status');
    const runButton = document.getElementById('run-code');
    const stopButton = document.getElementById('stop-code');
    const clearButton = document.getElementById('clear-output');

    if (!root || !window.Worker) {
        status.textContent = 'Web Worker не поддерживается браузером';
        status.className = 'interpreter__status error';
        output.textContent = 'Обновите браузер, чтобы запустить Python.';
        return;
    }

    const workerUrl = root.dataset.workerUrl;
    const executionTimeout = 5000;
    let worker;
    let timeoutId;
    let running = false;
    let outputLength = 0;
    let resetOutputWhenReady = true;

    const setStatus = (text, state = '') => {
        status.textContent = text;
        status.className = `interpreter__status ${state}`.trim();
    };

    const appendOutput = (text) => {
        const outputLimit = 50000;
        if (outputLength >= outputLimit) {
            return;
        }

        const remaining = outputLimit - outputLength;
        const chunk = String(text).slice(0, remaining);
        output.textContent += chunk;
        outputLength += chunk.length;

        if (outputLength >= outputLimit) {
            output.textContent += '\n…Вывод ограничен 50 000 символами.';
        }
        output.scrollTop = output.scrollHeight;
    };

    const setRunning = (value) => {
        running = value;
        runButton.disabled = value;
        stopButton.disabled = !value;
        codeInput.readOnly = value;
    };

    const createWorker = (resetOutput = true) => {
        resetOutputWhenReady = resetOutput;
        setStatus('Загрузка Python…');
        runButton.disabled = true;
        worker = new Worker(workerUrl, {type: 'module'});

        worker.addEventListener('message', (event) => {
            const {type, text} = event.data || {};

            if (type === 'ready') {
                setStatus('Готов', 'ready');
                runButton.disabled = false;
                if (resetOutputWhenReady) {
                    output.textContent = 'Python готов к запуску.';
                    outputLength = output.textContent.length;
                }
                return;
            }

            if (type === 'stdout' || type === 'stderr') {
                appendOutput(text);
                return;
            }

            if (type === 'result') {
                window.clearTimeout(timeoutId);
                if (text) {
                    appendOutput(`${text}\n`);
                }
                setRunning(false);
                setStatus('Готов', 'ready');
                return;
            }

            if (type === 'error') {
                window.clearTimeout(timeoutId);
                appendOutput(`${text}\n`);
                setRunning(false);
                setStatus('Ошибка выполнения', 'error');
                return;
            }

            if (type === 'init-error') {
                setStatus('Не удалось загрузить Python', 'error');
                output.textContent = text;
                runButton.disabled = true;
            }
        });

        worker.addEventListener('error', () => {
            window.clearTimeout(timeoutId);
            setRunning(false);
            setStatus('Не удалось загрузить Python', 'error');
            output.textContent = (
                'Проверьте подключение к интернету и повторите попытку.'
            );
        });
    };

    const stopExecution = (message = 'Выполнение остановлено.') => {
        window.clearTimeout(timeoutId);
        worker.terminate();
        setRunning(false);
        output.textContent += `\n${message}`;
        outputLength = output.textContent.length;
        createWorker(false);
    };

    runButton.addEventListener('click', () => {
        const code = codeInput.value.trim();
        if (!code || running) {
            return;
        }

        output.textContent = '';
        outputLength = 0;
        setRunning(true);
        setStatus('Выполняется…');
        worker.postMessage({type: 'run', code});

        timeoutId = window.setTimeout(() => {
            stopExecution('Превышено максимальное время выполнения — 5 секунд.');
        }, executionTimeout);
    });

    stopButton.addEventListener('click', () => stopExecution());

    clearButton.addEventListener('click', () => {
        output.textContent = '';
        outputLength = 0;
    });

    codeInput.addEventListener('keydown', (event) => {
        if (event.key !== 'Tab') {
            return;
        }

        event.preventDefault();
        const start = codeInput.selectionStart;
        const end = codeInput.selectionEnd;
        codeInput.setRangeText('    ', start, end, 'end');
    });

    createWorker();
});
