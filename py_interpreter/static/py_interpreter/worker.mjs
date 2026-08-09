import {
    loadPyodide,
} from 'https://cdn.jsdelivr.net/pyodide/v314.0.2/full/pyodide.mjs';

const sendMessage = self.postMessage.bind(self);
let pyodide;

try {
    pyodide = await loadPyodide();
    sendMessage({type: 'ready'});

    self.fetch = undefined;
    self.XMLHttpRequest = undefined;
    self.WebSocket = undefined;
    self.EventSource = undefined;
    self.postMessage = undefined;
} catch (error) {
    sendMessage({
        type: 'init-error',
        text: `Не удалось загрузить Python: ${error.message}`,
    });
}

self.addEventListener('message', async (event) => {
    if (event.data?.type !== 'run' || !pyodide) {
        return;
    }

    const code = String(event.data.code || '').slice(0, 20000);
    let outputLength = 0;
    const outputLimit = 50000;
    const emit = (type, text) => {
        if (outputLength >= outputLimit) {
            return;
        }
        const chunk = `${text}\n`.slice(0, outputLimit - outputLength);
        outputLength += chunk.length;
        sendMessage({type, text: chunk});
    };

    pyodide.setStdout({batched: (text) => emit('stdout', text)});
    pyodide.setStderr({batched: (text) => emit('stderr', text)});

    const globals = pyodide.globals.get('dict')();

    try {
        const result = await pyodide.runPythonAsync(code, {globals});
        const resultText = (
            result === undefined || result === null ? '' : String(result)
        );
        sendMessage({
            type: 'result',
            text: resultText,
        });
        result?.destroy?.();
    } catch (error) {
        sendMessage({type: 'error', text: error.message});
    } finally {
        globals.destroy();
    }
});
