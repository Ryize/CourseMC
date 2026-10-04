'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const root = document.querySelector('.interpreter');
    if (!root) return;

    const codeInput = document.getElementById('python-code');
    const editorNode = document.getElementById('python-editor');
    const stdinInput = document.getElementById('python-stdin');
    const inputForm = document.getElementById('python-input-form');
    const inputPrompt = document.getElementById('python-input-prompt');
    const terminal = document.getElementById('python-terminal');
    const output = document.getElementById('python-output');
    const status = document.getElementById('interpreter-status');
    const runButton = document.getElementById('run-code');
    const stopButton = document.getElementById('stop-code');
    const retryButton = document.getElementById('retry-python');
    const position = document.getElementById('editor-position');
    const draftStatus = document.getElementById('draft-status');
    const solutionFileId = root.dataset.solutionFileId;
    const shared = !!root.dataset.sharedId;
    let sharedEditable = !shared;
    let draftStorage = null;
    try {
        draftStorage = shared ? null : solutionFileId ? window.sessionStorage : window.localStorage;
    } catch (_) {
        draftStatus.textContent = 'Черновик не сохраняется в этом браузере';
    }
    const draftKey = solutionFileId
        ? `coursemc.pythonInterpreter.solution.${solutionFileId}`
        : 'coursemc.pythonInterpreter.code.v1';
    const maxCodeLength = 20000;
    const outputLimit = 50000;
    const executionTimeout = 10000;
    let editor = null;
    let worker = null;
    let timeoutId = null;
    let saveTimer = null;
    let running = false;
    let outputLength = 0;
    let pendingInput = null;

    const setStatus = (message, state = '') => {
        status.textContent = message;
        status.className = `interpreter__status ${state}`.trim();
    };
    const getCode = () => editor ? editor.getValue() : codeInput.value;

    const updatePosition = () => {
        const code = getCode();
        let row;
        let column;
        if (editor) {
            const cursor = editor.getCursorPosition();
            row = cursor.row + 1;
            column = cursor.column + 1;
        } else {
            const lines = code.slice(0, codeInput.selectionStart).split('\n');
            row = lines.length;
            column = lines[lines.length - 1].length + 1;
        }
        position.textContent = `Строка ${row}, столбец ${column} · ${code.length.toLocaleString('ru-RU')} / ${maxCodeLength.toLocaleString('ru-RU')} символов`;
    };
    const saveDraft = () => {
        if (shared) return;
        try {
            if (!draftStorage) throw new Error('Хранилище недоступно');
            draftStorage.setItem(draftKey, getCode());
            draftStatus.textContent = solutionFileId
                ? 'Правки сохранены в этой вкладке'
                : 'Черновик сохранён в браузере';
        } catch (_) {
            draftStatus.textContent = 'Не удалось сохранить черновик';
        }
    };
    const scheduleSave = () => {
        if (shared) {
            updatePosition();
            root.dispatchEvent(new Event('interpreter-code-change'));
            return;
        }
        draftStatus.textContent = 'Сохранение…';
        window.clearTimeout(saveTimer);
        saveTimer = window.setTimeout(saveDraft, 350);
        updatePosition();
    };
    try {
        if (!draftStorage) throw new Error('Хранилище недоступно');
        const savedCode = draftStorage.getItem(draftKey);
        if (savedCode !== null) codeInput.value = savedCode;
    } catch (_) {
        if (!shared) draftStatus.textContent = 'Черновик не сохраняется в этом браузере';
    }

    const syncEditorTheme = () => {
        if (!editor) return;
        editor.setTheme(document.body.classList.contains('black')
            ? 'ace/theme/tomorrow_night'
            : 'ace/theme/chrome');
    };
    const setRunning = (value) => {
        running = value;
        runButton.disabled = value || !worker;
        stopButton.disabled = !value;
        codeInput.readOnly = value || !sharedEditable;
        editor?.setReadOnly(value || !sharedEditable);
        document.getElementById('clear-code').disabled = value || !sharedEditable;
        if (!value) {
            pendingInput = null;
            inputForm.hidden = true;
            stdinInput.value = '';
        }
    };
    const appendOutput = (text) => {
        if (outputLength >= outputLimit) return;
        const chunk = String(text).slice(0, outputLimit - outputLength);
        output.textContent += chunk;
        outputLength += chunk.length;
        if (outputLength >= outputLimit) output.textContent += '\n…Вывод ограничен 50 000 символами.';
        terminal.scrollTop = terminal.scrollHeight;
    };
    const failRuntime = (message) => {
        window.clearTimeout(timeoutId);
        worker?.terminate();
        worker = null;
        setRunning(false);
        runButton.disabled = true;
        retryButton.hidden = false;
        setStatus('Не удалось загрузить Python', 'error');
        output.textContent = message || 'Проверьте подключение к интернету и повторите попытку.';
        outputLength = output.textContent.length;
    };
    const createWorker = (resetOutput = true) => {
        retryButton.hidden = true;
        setStatus('Загрузка Python…');
        runButton.disabled = true;
        try {
            worker = new Worker(root.dataset.workerUrl, {type: 'module'});
        } catch (_) {
            failRuntime('Этот браузер не поддерживает запуск Python. Обновите браузер и попробуйте снова.');
            return;
        }
        const currentWorker = worker;
        currentWorker.addEventListener('message', (event) => {
            if (worker !== currentWorker) return;
            const {type, text} = event.data || {};
            if (type === 'ready') {
                setStatus('Готов к запуску', 'ready');
                runButton.disabled = false;
                if (resetOutput) {
                    output.textContent = 'Python готов. Запустите код, чтобы увидеть результат.';
                    outputLength = output.textContent.length;
                }
            } else if (type === 'stdout' || type === 'stderr') {
                appendOutput(text);
            } else if (type === 'input-request') {
                window.clearTimeout(timeoutId);
                pendingInput = {
                    id: event.data.id,
                    prompt: String(event.data.prompt || ''),
                };
                inputPrompt.textContent = pendingInput.prompt;
                inputForm.hidden = false;
                setStatus('Ожидание ввода…');
                terminal.scrollTop = terminal.scrollHeight;
                stdinInput.focus();
            } else if (type === 'result' || type === 'error') {
                window.clearTimeout(timeoutId);
                if (text) appendOutput(`${text}\n`);
                setRunning(false);
                setStatus(type === 'result' ? 'Готов к запуску' : 'Ошибка выполнения',
                    type === 'result' ? 'ready' : 'error');
            } else if (type === 'init-error') {
                failRuntime(text);
            }
        });
        currentWorker.addEventListener('error', () => {
            if (worker === currentWorker) failRuntime();
        });
    };
    const stopExecution = (message = 'Выполнение остановлено.') => {
        if (!running || !worker) return;
        window.clearTimeout(timeoutId);
        worker.terminate();
        worker = null;
        setRunning(false);
        appendOutput(`\n${message}\n`);
        createWorker(false);
    };
    const runCode = () => {
        const code = getCode();
        if (running || !worker || runButton.disabled) return;
        if (!code.trim()) {
            setStatus('Напишите код перед запуском', 'error');
            editor ? editor.focus() : codeInput.focus();
            return;
        }
        if (code.length > maxCodeLength) {
            setStatus('Код слишком длинный: максимум 20 000 символов', 'error');
            editor ? editor.focus() : codeInput.focus();
            return;
        }
        saveDraft();
        output.textContent = '';
        outputLength = 0;
        setRunning(true);
        setStatus('Выполняется…');
        worker.postMessage({type: 'run', code});
        timeoutId = window.setTimeout(() => {
            stopExecution('Время выполнения превысило 10 секунд.');
        }, executionTimeout);
    };

    if (window.ace) {
        try {
            window.ace.config.set('basePath', root.dataset.aceBaseUrl);
            editorNode.hidden = false;
            editor = window.ace.edit(editorNode);
            editor.setOptions({
                mode: 'ace/mode/python',
                fontSize: '15px',
                showPrintMargin: false,
                highlightActiveLine: true,
                enableBasicAutocompletion: true,
                enableLiveAutocompletion: true,
                liveAutocompletionDelay: 250,
                liveAutocompletionThreshold: 2,
                enableSnippets: true,
            });
            editor.session.setUseWorker(false);
            editor.session.setTabSize(4);
            editor.session.setUseSoftTabs(true);
            editor.session.setUseWrapMode(false);
            // Ace normally inserts only enough spaces to reach the next tab stop.
            // Keep its selection/snippet handling, but make a plain Tab four spaces.
            const indentCommand = editor.commands.commands.indent;
            const defaultIndent = indentCommand.exec;
            indentCommand.exec = (activeEditor, ...args) => {
                if (!activeEditor.selection.isEmpty()) {
                    return defaultIndent(activeEditor, ...args);
                }
                activeEditor.insert('    ');
            };
            editor.setValue(codeInput.value, -1);
            codeInput.hidden = true;
            syncEditorTheme();
            new MutationObserver(syncEditorTheme).observe(document.body, {
                attributes: true,
                attributeFilter: ['class'],
            });
            const languageTools = window.ace.require('ace/ext/language_tools');
            languageTools.addCompleter({
                getCompletions(_editor, _session, _pos, _prefix, callback) {
                    callback(null, [
                        ['print', 'Вывести значение', 'print(${1:value})'],
                        ['input', 'Прочитать строку', 'input(${1:prompt})'],
                        ['range', 'Последовательность чисел', 'range(${1:stop})'],
                        ['len', 'Длина коллекции', 'len(${1:items})'],
                        ['enumerate', 'Индекс и элемент', 'enumerate(${1:items})'],
                        ['zip', 'Объединить коллекции', 'zip(${1:a}, ${2:b})'],
                        ['sorted', 'Отсортировать', 'sorted(${1:items})'],
                        ['sum', 'Сумма элементов', 'sum(${1:items})'],
                    ].map(([caption, meta, snippet]) => ({
                        caption, value: caption, snippet, meta, score: 1000,
                    })));
                },
            });
            editor.commands.addCommand({
                name: 'runPythonCode',
                bindKey: {win: 'Ctrl-Enter', mac: 'Command-Enter'},
                exec: runCode,
            });
            editor.session.on('change', scheduleSave);
            editor.selection.on('changeCursor', updatePosition);
            window.addEventListener('resize', () => editor.resize());
        } catch (_) {
            editor?.destroy();
            editor = null;
            editorNode.hidden = true;
            codeInput.hidden = false;
        }
    }

    const setCode = (code) => {
        if (editor) editor.setValue(code, -1);
        else codeInput.value = code;
        scheduleSave();
    };
    const flashButton = (button, message) => {
        const original = button.textContent;
        button.textContent = message;
        window.setTimeout(() => { button.textContent = original; }, 1700);
    };
    const copyText = async (text, button) => {
        try {
            await navigator.clipboard.writeText(text);
            flashButton(button, 'Скопировано');
        } catch (_) {
            flashButton(button, 'Не удалось скопировать');
        }
    };
    document.getElementById('copy-code').addEventListener('click', (event) => {
        copyText(getCode(), event.currentTarget);
    });
    document.getElementById('copy-output').addEventListener('click', (event) => {
        copyText(output.textContent, event.currentTarget);
    });
    document.getElementById('download-code').addEventListener('click', () => {
        const blobUrl = URL.createObjectURL(new Blob([getCode()], {type: 'text/x-python;charset=utf-8'}));
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = root.dataset.downloadName || 'main.py';
        link.click();
        window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    });
    document.getElementById('clear-code').addEventListener('click', () => {
        if (!sharedEditable || running) return;
        if (getCode().trim() && !window.confirm('Очистить весь код в редакторе?')) return;
        setCode('');
        editor ? editor.focus() : codeInput.focus();
    });
    document.getElementById('clear-output').addEventListener('click', () => {
        output.textContent = '';
        outputLength = 0;
    });
    runButton.addEventListener('click', runCode);
    stopButton.addEventListener('click', () => stopExecution());
    retryButton.addEventListener('click', () => createWorker(false));
    inputForm.addEventListener('submit', (event) => {
        event.preventDefault();
        if (!running || !worker || !pendingInput) return;
        const {id, prompt} = pendingInput;
        const value = stdinInput.value;
        appendOutput(`${prompt}${value}\n`);
        pendingInput = null;
        inputForm.hidden = true;
        stdinInput.value = '';
        setStatus('Выполняется…');
        worker.postMessage({type: 'stdin-response', id, value});
        timeoutId = window.setTimeout(() => {
            stopExecution('Время выполнения превысило 10 секунд.');
        }, executionTimeout);
    });
    codeInput.addEventListener('input', scheduleSave);
    codeInput.addEventListener('click', updatePosition);
    codeInput.addEventListener('keyup', updatePosition);
    codeInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
            event.preventDefault();
            runCode();
        } else if (event.key === 'Tab') {
            event.preventDefault();
            if (codeInput.readOnly) return;
            codeInput.setRangeText('    ', codeInput.selectionStart, codeInput.selectionEnd, 'end');
            scheduleSave();
        }
    });
    window.addEventListener('beforeunload', saveDraft);
    updatePosition();
    if (shared) {
        setRunning(false);
        root.dispatchEvent(new CustomEvent('interpreter-ready', {detail: {
            root, editor, codeInput, getCode, updatePosition,
            setEditable(value) { sharedEditable = !!value; setRunning(running); },
            setCode(value) { if (editor) editor.setValue(value, -1); else codeInput.value = value; updatePosition(); },
        }}));
    }
    if (window.Worker) createWorker();
    else failRuntime('Этот браузер не поддерживает запуск Python. Обновите браузер и попробуйте снова.');
});
