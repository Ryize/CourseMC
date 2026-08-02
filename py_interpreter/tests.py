from django.urls import reverse
from django.test import TestCase


class PythonInterpreterViewTests(TestCase):
    def test_interpreter_uses_browser_worker(self):
        response = self.client.get(reverse('py_interpreter'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'py_interpreter/worker.mjs')
        self.assertContains(response, 'Код выполняется только в вашем браузере')
        self.assertNotContains(response, 'pyscript.net')

    def test_interpreter_does_not_accept_server_execution(self):
        response = self.client.post(
            reverse('py_interpreter'),
            {'code': 'print("must not run on server")'},
        )

        self.assertEqual(response.status_code, 405)
