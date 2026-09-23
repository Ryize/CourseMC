from pathlib import Path

from django.conf import settings
from django.urls import reverse
from django.test import TestCase


class PythonInterpreterViewTests(TestCase):
    def test_interpreter_uses_browser_worker(self):
        response = self.client.get(reverse('py_interpreter'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'py_interpreter/worker.mjs?v=6')
        self.assertContains(response, 'py_interpreter/interpreter.css?v=6')
        self.assertContains(response, 'py_interpreter/interpreter.js?v=5')
        self.assertContains(response, 'Код выполняется только в вашем браузере')
        self.assertContains(response, 'ace-builds@1.44.0')
        self.assertContains(response, 'id="python-stdin"')
        self.assertContains(response, 'id="python-input-form"')
        self.assertNotContains(response, 'Входные данные <span>для input()</span>')
        self.assertNotContains(response, 'pyscript.net')

    def test_interpreter_does_not_accept_server_execution(self):
        response = self.client.post(
            reverse('py_interpreter'),
            {'code': 'print("must not run on server")'},
        )

        self.assertEqual(response.status_code, 405)

    def test_module_worker_has_javascript_mime_type_in_nginx(self):
        nginx_template = (
            Path(settings.BASE_DIR)
            / 'deploy'
            / 'nginx'
            / 'https.conf.template'
        ).read_text(encoding='utf-8')

        self.assertIn(
            'location = /static/py_interpreter/worker.mjs',
            nginx_template,
        )
        self.assertIn('default_type application/javascript;', nginx_template)

    def test_input_is_requested_during_execution_in_console(self):
        static_dir = Path(settings.BASE_DIR) / 'py_interpreter' / 'static' / 'py_interpreter'
        worker = (static_dir / 'worker.mjs').read_text(encoding='utf-8')
        interface = (static_dir / 'interpreter.js').read_text(encoding='utf-8')

        self.assertIn('run_sync(requestInput(str(prompt)))', worker)
        self.assertIn("type: 'input-request'", worker)
        self.assertIn("type: 'stdin-response'", interface)
        self.assertNotIn('stdin: stdinInput.value', interface)

    def test_console_stream_keeps_printed_line_endings(self):
        worker = (
            Path(settings.BASE_DIR)
            / 'py_interpreter'
            / 'static'
            / 'py_interpreter'
            / 'worker.mjs'
        ).read_text(encoding='utf-8')

        self.assertIn('pyodide.setStdout({write:', worker)
        self.assertIn('pyodide.setStderr({write:', worker)
        self.assertIn('decoder.decode(buffer, {stream: true})', worker)
        self.assertIn("sys.stdout.flush(); sys.stderr.flush()", worker)
        self.assertNotIn('setStdout({batched:', worker)
