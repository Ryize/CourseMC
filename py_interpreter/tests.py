from pathlib import Path

from django.conf import settings
from django.urls import reverse
from django.test import TestCase


class PythonInterpreterViewTests(TestCase):
    def test_interpreter_uses_browser_worker(self):
        response = self.client.get(reverse('py_interpreter'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'py_interpreter/worker.mjs?v=2')
        self.assertContains(response, 'Код выполняется только в вашем браузере')
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
