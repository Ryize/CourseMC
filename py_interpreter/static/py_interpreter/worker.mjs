import {
    loadPyodide,
} from 'https://cdn.jsdelivr.net/pyodide/v314.0.2/full/pyodide.mjs';

const sendMessage = self.postMessage.bind(self);
let pyodide;
let pendingInput = null;
let inputRequestId = 0;

try {
    pyodide = await loadPyodide();
    pyodide.registerJsModule('coursemc_terminal', {
        requestInput(prompt) {
            return new Promise((resolve) => {
                const id = ++inputRequestId;
                pendingInput = {id, resolve};
                sendMessage({type: 'input-request', id, prompt});
            });
        },
    });
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
    if (event.data?.type === 'stdin-response') {
        if (pendingInput?.id === event.data.id) {
            const {resolve} = pendingInput;
            pendingInput = null;
            resolve(String(event.data.value || '').slice(0, 10000));
        }
        return;
    }
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
        const chunk = String(text).slice(0, outputLimit - outputLength);
        outputLength += chunk.length;
        sendMessage({type, text: chunk});
    };

    // Batched handlers can discard line endings. Forward the original UTF-8
    // bytes instead, so print(), blank lines and partial writes keep their form.
    const makeWriter = (type) => {
        const decoder = new TextDecoder();
        return {
            write(buffer) {
                const text = decoder.decode(buffer, {stream: true});
                if (text) emit(type, text);
                return buffer.length;
            },
            finish() {
                const text = decoder.decode();
                if (text) emit(type, text);
            },
        };
    };
    const stdoutWriter = makeWriter('stdout');
    const stderrWriter = makeWriter('stderr');
    const flushStreams = () => {
        // Python may still buffer print(..., end='') when the script returns.
        try {
            pyodide.runPython('import sys; sys.stdout.flush(); sys.stderr.flush()');
        } catch (_) {
            // Preserve the original execution error if a user replaced a stream.
        }
        stdoutWriter.finish();
        stderrWriter.finish();
    };
    pyodide.setStdout({write: (buffer) => stdoutWriter.write(buffer)});
    pyodide.setStderr({write: (buffer) => stderrWriter.write(buffer)});
    pyodide.setStdin({error: true});

    const globals = pyodide.globals.get('dict')();

    try {
        await pyodide.runPythonAsync(`
import sys
from pyodide.ffi import run_sync, can_run_sync
from coursemc_terminal import requestInput

def input(prompt=''):
    if not can_run_sync():
        raise RuntimeError('Интерактивный ввод не поддерживается этим браузером. Обновите браузер.')
    sys.stdout.flush()
    return run_sync(requestInput(str(prompt)))
`, {globals});
        const result = await pyodide.runPythonAsync(code, {globals});
        const resultText = (
            result === undefined || result === null ? '' : String(result)
        );
        flushStreams();
        sendMessage({
            type: 'result',
            text: resultText,
        });
        result?.destroy?.();
    } catch (error) {
        flushStreams();
        sendMessage({type: 'error', text: error.message});
    } finally {
        pendingInput = null;
        globals.destroy();
    }
});
