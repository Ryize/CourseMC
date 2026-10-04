import base64
import json
import shutil
import subprocess
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from pycrdt import Doc, Map, Text

from Course.models import DirectionStudy, LearnGroup, Schedule, Student
from live_lessons.models import LiveLessonParticipant, LiveLessonRemoval
from live_lessons.tests import LiveLessonFixture
from .collaboration import DEFAULT_CODE, document_from_state, encoded
from .models import SharedCodeAttachment, SharedCodeDocument, SharedCodeSnapshot


class SharedCodeFixture(LiveLessonFixture):
    def setUp(self):
        super().setUp()
        self.lesson.status = 'live'
        self.lesson.started_at = timezone.now()
        self.lesson.scheduled_at = timezone.now()
        self.lesson.save()
        self.client.force_login(self.teacher_user)
        self.pupil = Client()
        self.pupil.force_login(self.student_user)
        self.identity = f'course-user-{self.student_user.pk}'
        self.participant = LiveLessonParticipant.objects.create(
            lesson=self.lesson, identity=self.identity, name='Ученик', admission='admitted',
        )
        self.url = reverse('shared_code_editor', args=[self.lesson.public_id])
        self.sync_url = reverse('shared_code_sync', args=[self.lesson.public_id])
        self.manage_url = reverse('shared_code_manage', args=[self.lesson.public_id])
        api = patch('py_interpreter.collaboration.participant_in_room', return_value=True)
        self.api = api.start(); self.addCleanup(api.stop)

    def sync(self, client=None, **data):
        return (client or self.client).post(self.sync_url, json.dumps(data), content_type='application/json')

    def manage(self, client=None, **data):
        return (client or self.client).post(self.manage_url, json.dumps(data), content_type='application/json')

    def open_document(self):
        response = self.sync()
        self.assertEqual(response.status_code, 200)
        return document_from_state(base64.b64decode(response.json()['update']))

    def insert(self, doc, value):
        vector = doc.get_state()
        doc['code'].insert(0, value)
        return {'vector': encoded(doc.get_state()), 'update': encoded(doc.get_update(vector))}


class SharedCodeTests(SharedCodeFixture, TestCase):
    def test_page_reuses_local_worker_and_embedded_view_drops_navigation(self):
        response = self.client.get(self.url, {'embedded': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')
        self.assertContains(response, 'worker.mjs?v=6')
        self.assertContains(response, 'data-shared-id=')
        self.assertContains(response, 'vendor/yjs.js')
        self.assertNotContains(response, '<header>')
        self.assertContains(response, 'Сохранить версию созвона')
        self.assertContains(response, 'Прикрепить .py к уроку программы')
        self.assertNotContains(self.pupil.get(self.url), 'id="shared-code-save"')
        self.assertFalse(SharedCodeDocument.objects.exists())

    def test_teacher_starts_document_pupil_readonly_by_default(self):
        self.assertEqual(self.sync(self.pupil).json()['code'], 'not_started')
        teacher = self.sync().json()
        pupil = self.sync(self.pupil).json()
        self.assertTrue(teacher['can_edit'])
        self.assertFalse(pupil['can_edit'])
        self.assertEqual(SharedCodeDocument.objects.get().code, DEFAULT_CODE)
        self.assertEqual(len(teacher['members']), 1)

    def test_permission_enforced_on_server_and_revoke_rejects_stale_update(self):
        doc = self.open_document()
        self.assertEqual(self.sync(self.pupil, **self.insert(doc, '# forbidden\n')).status_code, 403)
        self.assertEqual(self.manage(action='grant', identity=self.identity, enabled=True).status_code, 200)
        doc = document_from_state(SharedCodeDocument.objects.get().state)
        update = self.insert(doc, '# permitted\n')
        self.assertEqual(self.sync(self.pupil, **update).status_code, 200)
        self.assertEqual(self.manage(action='grant', identity=self.identity, enabled=False).status_code, 200)
        self.assertEqual(self.sync(self.pupil, **self.insert(doc, '# stale\n')).status_code, 403)
        self.assertTrue(SharedCodeDocument.objects.get().code.startswith('# permitted'))
        self.assertNotIn('stale', SharedCodeDocument.objects.get().code)
        self.assertEqual(self.manage(self.pupil, action='grant', identity=self.identity, enabled=True).status_code, 403)

    def test_concurrent_edits_merge_without_lost_text_and_retry_is_idempotent(self):
        left = self.open_document()
        right = document_from_state(SharedCodeDocument.objects.get().state)
        self.manage(action='grant', identity=self.identity, enabled=True)
        a, b = self.insert(left, '# преподаватель 🐱\n'), self.insert(right, '# ученик\n')
        self.assertEqual(self.sync(**a).status_code, 200)
        self.assertEqual(self.sync(self.pupil, **b).status_code, 200)
        state = SharedCodeDocument.objects.get().code
        self.assertIn('# преподаватель 🐱\n', state)
        self.assertIn('# ученик\n', state)
        self.assertTrue(state.endswith(DEFAULT_CODE))
        self.assertEqual(self.sync(**a).status_code, 200)
        self.assertEqual(SharedCodeDocument.objects.get().code, state)
        final = self.sync(vector=encoded(left.get_state())).json()
        left.apply_update(base64.b64decode(final['update']))
        self.assertEqual(str(left['code']), state)

    def test_exact_browser_bundle_interoperates_with_python_server(self):
        if not shutil.which('node'):
            self.skipTest('Node is required for browser/server wire compatibility test')
        self.open_document()
        node = subprocess.run([
            'node', str(Path(__file__).parent / 'tests_js' / 'yjs_bridge.cjs'),
        ], input=json.dumps({'state': encoded(SharedCodeDocument.objects.get().state),
                            'insert': '# привет 🐱\n'}), text=True, capture_output=True, check=True)
        update = json.loads(node.stdout)
        self.assertEqual(self.sync(update=update['update']).status_code, 200)
        self.assertEqual(SharedCodeDocument.objects.get().code, update['code'])

    def test_waiting_removed_and_unrelated_students_cannot_get_document(self):
        self.open_document()
        self.participant.admission = 'waiting'; self.participant.save()
        self.assertEqual(self.pupil.get(self.url).status_code, 403)
        self.assertEqual(self.sync(self.pupil).status_code, 403)
        self.participant.admission = 'admitted'; self.participant.save()
        LiveLessonRemoval.objects.create(lesson=self.lesson, identity=self.identity, removed_by=self.teacher_user)
        self.assertEqual(self.sync(self.pupil).status_code, 403)
        other = Client(); other.force_login(self.other_user)
        self.assertEqual(other.get(self.url).status_code, 404)
        self.assertEqual(Client().get(self.url).status_code, 302)

    def test_open_guest_must_be_admitted_and_cannot_impersonate_teacher(self):
        self.lesson.audience = 'open'; self.lesson.group = None; self.lesson.save()
        guest = Client()
        self.assertEqual(guest.get(self.url).status_code, 403)
        saved_guest = guest.session[f'live_lesson_guest_{self.lesson.public_id.hex}']
        identity = f'lesson-guest-{saved_guest["id"]}'
        LiveLessonParticipant.objects.create(lesson=self.lesson, identity=identity,
                                            name=saved_guest['name'], admission='admitted')
        self.open_document()
        response = self.sync(guest, teacher=True, can_edit=True, identity=f'course-user-{self.teacher_user.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['can_edit'])
        self.assertEqual(response.json()['identity'], identity)
        self.assertEqual(self.manage(guest, action='save').status_code, 403)

    def test_not_in_call_cannot_sync_and_presence_rechecked_after_lease(self):
        self.api.return_value = False
        self.assertEqual(self.sync().json()['code'], 'not_connected')
        self.api.return_value = True
        self.sync()
        document = SharedCodeDocument.objects.get()
        own = document.editors.get(identity=f'course-user-{self.teacher_user.pk}')
        verified = own.verified_at
        self.sync()
        own.refresh_from_db(); self.assertEqual(own.verified_at, verified)
        document.editors.update(verified_at=timezone.now() - timedelta(seconds=9))
        self.api.return_value = False
        self.assertEqual(self.sync().status_code, 409)

    def test_bad_or_oversized_crdt_update_and_extra_roots_are_atomic(self):
        doc = self.open_document()
        for bad in ('***', encoded(b'not a yjs update'), 'A' * 200000):
            self.assertEqual(self.sync(update=bad).status_code, 400)
            self.assertEqual(SharedCodeDocument.objects.get().code, DEFAULT_CODE)
        self.assertEqual(self.sync(**self.insert(doc, 'x' * 20001)).status_code, 400)
        doc = document_from_state(SharedCodeDocument.objects.get().state)
        before = doc.get_state(); doc['other'] = Map({'bad': True})
        self.assertEqual(self.sync(update=encoded(doc.get_update(before))).status_code, 400)
        self.assertEqual(SharedCodeDocument.objects.get().code, DEFAULT_CODE)

    def test_saved_version_is_immutable_private_and_survives_end(self):
        doc = self.open_document()
        saved = self.manage(action='save', title='Первый пример')
        self.assertEqual(saved.status_code, 200)
        snapshot = SharedCodeSnapshot.objects.get()
        self.sync(**self.insert(doc, '# changed\n'))
        snapshot.refresh_from_db(); self.assertEqual(snapshot.code, DEFAULT_CODE)
        url = saved.json()['snapshot']['url']
        response = self.pupil.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), DEFAULT_CODE)
        self.assertIn('attachment;', response['Content-Disposition'])
        self.lesson.status = 'ended'; self.lesson.save()
        ended = self.sync(self.pupil).json()
        self.assertFalse(ended['can_edit']); self.assertFalse(ended['active'])
        self.assertEqual(self.sync(**self.insert(doc, '# late\n')).status_code, 409)
        self.assertContains(self.pupil.get(self.detail_url()), 'Первый пример')
        self.assertContains(self.pupil.get(self.detail_url()), 'Открыть в «Твоём Интерпретаторе»')
        outsider = Client(); outsider.force_login(self.other_user)
        self.assertEqual(outsider.get(url).status_code, 404)

    def test_sync_requires_csrf_even_for_anonymous_open_lesson(self):
        strict = Client(enforce_csrf_checks=True); strict.force_login(self.teacher_user)
        self.assertEqual(strict.post(self.sync_url, '{}', content_type='application/json').status_code, 403)
        strict.get(self.url)
        self.assertEqual(strict.post(self.sync_url, '{}', content_type='application/json',
                                     HTTP_X_CSRFTOKEN=strict.cookies['csrftoken'].value).status_code, 200)


class SharedCodePublicationTests(SharedCodeFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.direction = DirectionStudy.objects.create(title='Python для кода')
        self.schedule = Schedule.objects.create(direction=self.direction, theme='Примеры функций', position=1)
        self.student.direction.add(self.direction)
        self.target = f'{self.group.pk}:{self.schedule.pk}'
        self.publish_url = reverse('shared_code_publish', args=[self.lesson.public_id])
        self.open_document()

    def publish(self, client=None, **data):
        return (client or self.client).post(self.publish_url, json.dumps({
            'title': 'Пример с урока', 'code_target': self.target, **data,
        }), content_type='application/json')

    def download_url(self):
        return reverse('shared_code_attachment', args=[SharedCodeAttachment.objects.get().pk])

    def test_current_code_published_to_schedule_for_selected_group(self):
        response = self.publish()
        self.assertEqual(response.status_code, 200)
        attachment = SharedCodeAttachment.objects.get()
        self.assertEqual((attachment.group, attachment.schedule), (self.group, self.schedule))
        self.assertEqual(attachment.snapshot.code, DEFAULT_CODE)
        url = self.download_url()
        self.assertContains(self.pupil.get(reverse('schedule')), url)
        ajax = self.pupil.get(reverse('schedule'), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(ajax, 'Код к уроку')
        self.assertContains(ajax, 'Пример с урока')
        self.assertNotContains(Client().get(self.detail_url()), url, status_code=302)
        teacher = self.client.get(self.detail_url())
        self.assertContains(teacher, 'Прикрепить код к уроку программы')
        self.assertContains(teacher, 'name="snapshot"')
        self.assertContains(teacher, 'name="code_target"')
        self.assertContains(teacher, '<path d="M6 6l12 12M18 6L6 18"/>')

    def test_copy_is_immutable_and_repeat_delivery_does_not_duplicate(self):
        self.assertEqual(self.publish().status_code, 200)
        self.assertEqual(self.publish().status_code, 200)
        self.assertEqual(SharedCodeAttachment.objects.count(), 1)
        self.assertEqual(SharedCodeSnapshot.objects.count(), 1)
        doc = document_from_state(SharedCodeDocument.objects.get().state)
        self.sync(**self.insert(doc, '# new code\n'))
        downloaded = self.pupil.get(self.download_url())
        self.assertEqual(downloaded.content.decode(), DEFAULT_CODE)
        self.assertIn('.py', downloaded['Content-Disposition'])
        self.assertIn('no-store', downloaded['Cache-Control'])
        self.assertEqual(downloaded['X-Content-Type-Options'], 'nosniff')

    def test_existing_saved_version_can_be_attached_without_copying_new_code(self):
        saved = self.manage(action='save', title='Старая версия').json()['snapshot']['id']
        doc = document_from_state(SharedCodeDocument.objects.get().state)
        self.sync(**self.insert(doc, '# later edits\n'))
        response = self.client.post(self.publish_url, {'snapshot': saved, 'code_target': self.target},
                                    HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SharedCodeAttachment.objects.get().snapshot_id, saved)
        self.assertEqual(SharedCodeAttachment.objects.get().snapshot.code, DEFAULT_CODE)
        self.assertEqual(SharedCodeSnapshot.objects.count(), 1)
        missing_version = self.client.post(self.publish_url, {'code_target': self.target},
                                            HTTP_ACCEPT='application/json')
        self.assertEqual(missing_version.status_code, 400)

    def test_open_lesson_hides_publication_but_keeps_call_versions(self):
        self.lesson.audience = 'open'; self.lesson.group = None; self.lesson.save()
        editor = self.client.get(self.url)
        self.assertNotContains(editor, 'Прикрепить .py к уроку программы')
        self.assertNotContains(editor, 'id="shared-code-publish"')
        self.assertContains(editor, 'Сохранить версию созвона')
        self.assertEqual(self.manage(action='save', title='Версия открытого созвона').status_code, 200)
        page = self.client.get(self.detail_url())
        self.assertNotContains(page, 'Прикрепить код к уроку программы')
        self.assertContains(page, 'Версия открытого созвона')
        self.assertEqual(self.publish().status_code, 400)
        self.assertFalse(SharedCodeAttachment.objects.exists())

    def test_previous_materials_are_preserved_when_call_becomes_open(self):
        self.publish()
        url = self.download_url()
        self.lesson.audience = 'open'; self.lesson.group = None; self.lesson.save()
        page = self.client.get(self.detail_url())
        self.assertNotContains(page, 'Прикрепить код к уроку программы')
        self.assertContains(page, url)
        self.assertEqual(self.pupil.get(url).status_code, 200)
        self.assertEqual(SharedCodeAttachment.objects.count(), 1)

    def test_only_host_publishes_and_target_must_be_owned_and_relevant(self):
        self.assertEqual(self.publish(self.pupil).status_code, 403)
        other = Client(); other.force_login(self.other_user)
        self.assertEqual(self.publish(other).status_code, 404)
        self.assertEqual(self.publish(code_target=f'{self.other_group.pk}:{self.schedule.pk}').status_code, 400)
        another = Schedule.objects.create(direction=DirectionStudy.objects.create(title='Чужой курс'),
                                           theme='Чужой урок', position=1)
        self.assertEqual(self.publish(code_target=f'{self.group.pk}:{another.pk}').status_code, 400)
        self.schedule.is_archived = True; self.schedule.save()
        self.assertEqual(self.publish().status_code, 400)
        self.assertFalse(SharedCodeAttachment.objects.exists())
        self.assertFalse(SharedCodeSnapshot.objects.exists())

    def test_version_from_another_call_cannot_be_published(self):
        from live_lessons.models import LiveLesson
        other_lesson = LiveLesson.objects.create(teacher=self.teacher, group=self.group,
                                                 scheduled_at=timezone.now(), title='Другой созвон')
        document = SharedCodeDocument.objects.create(lesson=other_lesson, state=b'', code='foreign')
        snapshot = document.snapshots.create(code='foreign', created_by=self.teacher_user)
        self.assertEqual(self.publish(snapshot=snapshot.pk).status_code, 400)
        self.assertFalse(SharedCodeAttachment.objects.exists())

    def test_material_access_is_independent_of_call_but_obeys_curriculum_access(self):
        self.publish()
        url = self.download_url()
        self.participant.delete()  # A group material does not require having attended this call.
        self.assertEqual(self.pupil.get(url).status_code, 200)
        other = Client(); other.force_login(self.other_user)
        self.assertEqual(other.get(url).status_code, 404)
        self.assertNotContains(other.get(reverse('schedule')), url)
        self.student.direction.clear()
        self.assertEqual(self.pupil.get(url).status_code, 404)
        self.student.direction.add(self.direction)
        self.student.is_learned = False; self.student.save()
        self.assertEqual(self.pupil.get(url).status_code, 404)

    def test_other_group_at_same_call_does_not_see_the_material(self):
        second_group = LearnGroup.objects.create(title='Вторая группа', teacher=self.teacher, is_studies=True)
        from django.contrib.auth import get_user_model
        second_user = get_user_model().objects.create_user('second-code-student')
        second = Student.objects.create(user=second_user, groups=second_group, is_learned=True, contact='second')
        second.direction.add(self.direction)
        self.lesson.additional_groups.add(second_group)
        self.publish(code_target=f'{second_group.pk}:{self.schedule.pk}')
        url = self.download_url()
        self.assertEqual(self.pupil.get(url).status_code, 404)
        self.assertNotContains(self.pupil.get(reverse('schedule')), url)
        client = Client(); client.force_login(second_user)
        self.assertEqual(client.get(url).status_code, 200)
        self.assertContains(client.get(reverse('schedule')), url)

    def test_not_participating_owned_group_cannot_receive_code(self):
        second_group = LearnGroup.objects.create(title='Без участия', teacher=self.teacher, is_studies=True)
        from django.contrib.auth import get_user_model
        second_user = get_user_model().objects.create_user('not-attending-code-student')
        second = Student.objects.create(user=second_user, groups=second_group, is_learned=True, contact='second')
        second.direction.add(self.direction)
        target = f'{second_group.pk}:{self.schedule.pk}'
        self.assertEqual(self.publish(code_target=target).status_code, 400)
        self.lesson.audience = 'open'; self.lesson.group = None; self.lesson.save()
        self.assertEqual(self.publish(code_target=target).status_code, 400)
        self.assertFalse(SharedCodeAttachment.objects.exists())

    def test_ended_call_can_be_published_csrf_enforced_and_regular_form_redirects(self):
        snapshot = self.manage(action='save').json()['snapshot']['id']
        self.lesson.status = 'ended'; self.lesson.save()
        strict = Client(enforce_csrf_checks=True); strict.force_login(self.teacher_user)
        self.assertEqual(strict.post(self.publish_url, {'snapshot': snapshot, 'code_target': self.target}).status_code, 403)
        response = self.client.post(self.publish_url, {'snapshot': snapshot, 'code_target': self.target})
        self.assertRedirects(response, self.detail_url())
        self.assertEqual(self.pupil.get(self.download_url()).status_code, 200)
