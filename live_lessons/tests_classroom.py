import base64
from datetime import timedelta
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import jwt
from django.apps import apps
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .classroom import sync_media_policy, retry_media_policies
from .media import LiveKitAPIError
from .models import LiveLesson, LiveLessonMessage, LiveLessonParticipant, LiveLessonRemoval
from .tests import LiveLessonFixture


@override_settings(
    LIVEKIT_URL='wss://media.example.test', LIVEKIT_API_KEY='classroom-test',
    LIVEKIT_API_SECRET='strong-secret-for-testing-classroom-token',
)
class ClassroomTests(LiveLessonFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.lesson.status = 'live'
        self.lesson.started_at = timezone.now()
        self.lesson.scheduled_at = timezone.now()
        self.lesson.save()
        self.client.force_login(self.teacher_user)
        self.pupil = Client()
        self.pupil.force_login(self.student_user)
        self.state_url = reverse('live_lesson_classroom', args=[self.lesson.public_id])
        self.action_url = reverse('live_lesson_classroom_action', args=[self.lesson.public_id])
        self.manage_url = reverse('live_lesson_classroom_manage', args=[self.lesson.public_id])
        self.token_url = reverse('live_lesson_join_token', args=[self.lesson.public_id])
        self.identity = f'course-user-{self.student_user.pk}'

    def waiting(self, client=None):
        self.lesson.waiting_room_enabled = True
        self.lesson.save()
        response = (client or self.pupil).post(self.token_url)
        self.assertEqual(response.status_code, 202)
        self.assertNotIn('participant_token', response.json())
        return response

    def admitted(self):
        self.assertEqual(self.pupil.post(self.token_url).status_code, 200)
        return self.lesson.participants.get(identity=self.identity)

    def test_new_model_defaults_to_waiting_and_keeps_explicit_opt_out(self):
        self.assertTrue(LiveLesson().waiting_room_enabled)
        self.assertFalse(LiveLesson(waiting_room_enabled=False).waiting_room_enabled)

    @patch('live_lessons.classroom.room_service', return_value={})
    def test_fresh_waiting_request_pushes_only_to_teachers_after_commit(self, api):
        with self.captureOnCommitCallbacks(execute=True):
            self.waiting()
        api.assert_called_once()
        lesson, method, payload = api.call_args.args
        self.assertEqual(lesson.pk, self.lesson.pk)
        self.assertEqual(method, 'SendData')
        self.assertEqual(payload['destination_identities'], [f'course-user-{self.teacher_user.pk}'])
        self.assertEqual(payload['kind'], 'RELIABLE')
        self.assertEqual(payload['topic'], 'lesson-waiting-updated')
        self.assertEqual(base64.b64decode(payload['data']), b'refresh')
        with self.captureOnCommitCallbacks(execute=True):
            self.waiting()
        self.assertEqual(api.call_count, 1)
        self.pupil.post(self.action_url, {'action': 'cancel_wait'})
        with self.captureOnCommitCallbacks(execute=True):
            self.waiting()
        self.assertEqual(api.call_count, 2)

    @patch('live_lessons.classroom.room_service', side_effect=LiveKitAPIError('offline'))
    def test_failed_push_never_loses_waiting_request(self, api):
        with self.assertLogs('live_lessons.classroom', level='WARNING'):
            with self.captureOnCommitCallbacks(execute=True):
                self.waiting()
        self.assertEqual(self.lesson.participants.get(identity=self.identity).admission, 'waiting')
        self.assertEqual(len(self.client.get(self.state_url).json()['waiting']), 1)

    def test_waiting_until_teacher_admits_then_rejoins_without_second_approval(self):
        self.waiting()
        self.assertEqual(self.pupil.get(self.state_url).json()['own']['admission'], 'waiting')
        queue = self.client.get(self.state_url).json()['waiting']
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]['identity'], self.identity)
        self.assertEqual(self.pupil.get(self.state_url).json()['waiting'], [])
        self.assertEqual(self.client.post(self.manage_url, {'action': 'admit', 'identity': self.identity}).status_code, 200)
        for _ in range(2):
            self.assertEqual(self.pupil.post(self.token_url).status_code, 200)
        self.assertEqual(self.client.get(self.state_url).json()['waiting'], [])

    def test_teacher_never_needs_admission(self):
        self.lesson.waiting_room_enabled = self.lesson.entry_locked = True
        self.lesson.save()
        self.assertEqual(self.client.post(self.token_url).status_code, 200)
        self.assertEqual(self.client.get(self.state_url).json()['own']['admission'], 'admitted')

    def test_deny_blocks_retry_and_is_not_reversed_by_disabling_waiting(self):
        self.waiting()
        self.assertEqual(self.client.post(self.manage_url, {'action': 'deny', 'identity': self.identity}).status_code, 200)
        self.assertEqual(self.pupil.post(self.token_url).status_code, 403)
        self.client.post(self.manage_url, {'action': 'waiting_room', 'enabled': 'false'})
        self.assertEqual(self.pupil.post(self.token_url).status_code, 403)
        self.assertEqual(self.client.post(self.manage_url, {'action': 'admit', 'identity': self.identity}).status_code, 409)

    def test_cancel_wait_and_retry_creates_a_new_notification_key(self):
        self.waiting()
        old = self.lesson.participants.get(identity=self.identity).requested_at
        self.assertEqual(self.pupil.post(self.action_url, {'action': 'cancel_wait'}).status_code, 200)
        self.assertEqual(self.client.get(self.state_url).json()['waiting'], [])
        self.waiting()
        self.assertGreater(self.lesson.participants.get(identity=self.identity).requested_at, old)
        self.assertEqual(self.lesson.participants.count(), 1)

    def test_waiting_requests_expire_and_return_only_while_student_page_is_present(self):
        self.waiting()
        self.lesson.participants.update(last_seen_at=timezone.now() - timedelta(seconds=46))
        self.assertEqual(self.client.get(self.state_url).json()['waiting'], [])
        self.assertEqual(self.client.post(self.manage_url, {'action': 'admit', 'identity': self.identity}).status_code, 409)
        self.pupil.get(self.state_url)
        self.assertEqual(len(self.client.get(self.state_url).json()['waiting']), 1)

    def test_disabling_waiting_releases_waiting_students(self):
        self.waiting()
        self.assertEqual(self.client.post(self.manage_url, {'action': 'waiting_room', 'enabled': 'false'}).status_code, 200)
        self.assertEqual(self.pupil.post(self.token_url).status_code, 200)

    def test_entry_lock_allows_only_teacher_and_previously_admitted(self):
        self.admitted()
        self.assertEqual(self.client.post(self.manage_url, {'action': 'entry_locked', 'enabled': 'true'}).status_code, 200)
        self.assertEqual(self.pupil.post(self.token_url).status_code, 200)
        self.assertEqual(self.client.post(self.token_url).status_code, 200)
        self.lesson.participants.filter(identity=self.identity).delete()
        self.assertEqual(self.pupil.post(self.token_url).status_code, 409)
        self.assertFalse(self.pupil.get(self.state_url).json()['own']['entry_allowed'])

    def test_nonteacher_cannot_manage_or_see_waiting_names(self):
        self.waiting()
        for action in ('admit', 'deny', 'mute_all', 'microphone', 'screen', 'entry_locked'):
            self.assertEqual(self.pupil.post(self.manage_url, {'action': action, 'identity': self.identity, 'enabled': 'false'}).status_code, 404)
        self.assertEqual(self.pupil.get(self.state_url).json()['waiting'], [])
        outsider = Client()
        outsider.force_login(self.other_user)
        self.assertEqual(outsider.get(self.state_url).status_code, 404)
        self.assertEqual(Client().get(self.state_url).status_code, 302)

    def test_management_requires_post_valid_flags_and_csrf(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.teacher_user)
        self.assertEqual(strict.post(self.manage_url, {'action': 'mute_all'}).status_code, 403)
        self.assertEqual(self.client.get(self.manage_url).status_code, 405)
        self.assertEqual(self.client.post(self.manage_url, {'action': 'screen', 'enabled': 'bad'}).status_code, 400)
        self.assertEqual(self.client.post(self.manage_url, {'action': 'unknown'}).status_code, 400)

    def test_ended_and_expired_rooms_reject_actions(self):
        self.lesson.started_at = timezone.now() - timedelta(days=1)
        self.lesson.save()
        self.assertFalse(self.client.get(self.state_url).json()['active'])
        for client, url, action in ((self.client, self.manage_url, 'mute_all'), (self.pupil, self.action_url, 'raise_hand')):
            self.assertEqual(client.post(url, {'action': action}).status_code, 409)

    def test_removed_user_cannot_be_readmitted_or_raise_hand(self):
        self.waiting()
        LiveLessonRemoval.objects.create(lesson=self.lesson, identity=self.identity, removed_by=self.teacher_user)
        self.assertEqual(self.client.post(self.manage_url, {'action': 'admit', 'identity': self.identity}).status_code, 403)
        self.assertEqual(self.pupil.post(self.token_url).status_code, 403)
        self.assertEqual(self.pupil.post(self.action_url, {'action': 'raise_hand'}).status_code, 403)

    @patch('live_lessons.classroom_views.participant_in_room', return_value=True)
    def test_hand_is_idempotent_persistent_and_lowered_by_owner_or_teacher(self, _present):
        own = self.admitted()
        for _ in range(2):
            self.assertEqual(self.pupil.post(self.action_url, {'action': 'raise_hand'}).status_code, 200)
            own.refresh_from_db()
            if _ == 0:
                first = own.hand_raised_at
        self.assertEqual(own.hand_raised_at, first)
        self.assertEqual(self.client.get(self.state_url).json()['hands'][0]['identity'], self.identity)
        self.assertTrue(self.pupil.get(self.state_url).json()['own']['hand_raised'])
        self.assertEqual(self.client.post(self.action_url, {'action': 'lower_hand', 'identity': self.identity}).status_code, 200)
        self.assertEqual(self.client.get(self.state_url).json()['hands'], [])
        self.pupil.post(self.action_url, {'action': 'raise_hand'})
        self.pupil.post(self.action_url, {'action': 'leave'})
        own.refresh_from_db()
        self.assertIsNone(own.hand_raised_at)

    @patch('live_lessons.classroom_views.participant_in_room', return_value=False)
    def test_hand_requires_real_room_presence_and_cannot_impersonate_another_user(self, _present):
        self.assertEqual(self.pupil.post(self.action_url, {'action': 'raise_hand'}).status_code, 409)
        self.admitted()
        self.assertEqual(self.pupil.post(self.action_url, {'action': 'raise_hand'}).status_code, 409)
        for action in ('raise_hand', 'lower_hand'):
            self.assertEqual(self.pupil.post(self.action_url, {'action': action, 'identity': 'another'}).status_code, 403)
        self.assertEqual(self.client.post(self.action_url, {'action': 'raise_hand', 'identity': self.identity}).status_code, 403)

    def test_hand_heartbeat_requires_connected_flag_and_preserves_order(self):
        own = self.admitted()
        old = timezone.now() - timedelta(minutes=1)
        self.lesson.participants.filter(pk=own.pk).update(hand_raised_at=old, last_seen_at=old)
        LiveLessonParticipant.objects.create(lesson=self.lesson, identity='other', name='Второй', admission='admitted', hand_raised_at=timezone.now())
        self.pupil.get(self.state_url)
        own.refresh_from_db()
        self.assertEqual(own.last_seen_at, old)
        self.pupil.get(self.state_url, {'presence': 'connected'})
        self.assertEqual([item['identity'] for item in self.client.get(self.state_url).json()['hands']], [self.identity, 'other'])

    @patch('live_lessons.classroom.room_service', return_value={'participants': []})
    def test_publish_restrictions_are_in_student_token_but_not_teacher_token(self, _service):
        for setting in ('microphone', 'screen'):
            self.assertEqual(self.client.post(self.manage_url, {'action': setting, 'enabled': 'false'}).status_code, 200)
        def sources(client):
            data = client.post(self.token_url).json()
            return jwt.decode(data['participant_token'], 'strong-secret-for-testing-classroom-token', algorithms=['HS256'])['video']['canPublishSources']
        self.assertEqual(sources(self.pupil), ['camera'])
        self.assertEqual(sources(self.client), ['camera', 'microphone', 'screen_share', 'screen_share_audio'])

    @patch('live_lessons.classroom.room_service')
    def test_mute_all_mutes_only_live_student_microphones_never_teacher_or_camera(self, service):
        service.return_value = {'participants': [
            {'identity': f'course-user-{self.teacher_user.pk}', 'tracks': [{'source': 'MICROPHONE', 'sid': 'host'}]},
            {'identity': self.identity, 'tracks': [{'source': 2, 'sid': 'voice'}, {'source': 1, 'sid': 'camera'},
                                                  {'source': 'MICROPHONE', 'sid': 'muted', 'muted': True}]},
        ]}
        response = self.client.post(self.manage_url, {'action': 'mute_all'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['muted'], 1)
        self.assertEqual([call.args[1] for call in service.call_args_list], ['ListParticipants', 'MutePublishedTrack'])
        self.assertEqual(service.call_args_list[1].args[2]['track_sid'], 'voice')
        self.assertTrue(service.call_args_list[1].args[2]['muted'])
        self.lesson.refresh_from_db()
        self.assertFalse(self.lesson.mute_all_pending)

    @patch('live_lessons.classroom.room_service')
    def test_permission_update_limits_sources_and_mutes_existing_microphone(self, service):
        service.return_value = {'participants': [{'identity': self.identity, 'tracks': [{'source': 'MICROPHONE', 'sid': 'voice'}]}]}
        response = self.client.post(self.manage_url, {'action': 'microphone', 'enabled': 'false'})
        self.assertEqual(response.status_code, 200)
        permission = service.call_args_list[1].args[2]['permission']
        self.assertEqual(permission['can_publish_sources'], ['CAMERA', 'SCREEN_SHARE', 'SCREEN_SHARE_AUDIO'])
        self.assertTrue(permission['can_subscribe'])
        self.assertEqual(service.call_args_list[2].args[1], 'MutePublishedTrack')

    @patch('live_lessons.classroom.room_service', side_effect=LiveKitAPIError('Offline'))
    def test_failed_media_action_is_saved_and_retried_by_worker(self, service):
        response = self.client.post(self.manage_url, {'action': 'screen', 'enabled': 'false'})
        self.assertTrue(response.json()['pending'])
        self.lesson.refresh_from_db()
        self.assertFalse(self.lesson.students_can_share_screen)
        self.assertIsNotNone(self.lesson.policy_sync_until)
        self.assertEqual(retry_media_policies(timezone.now()), 1)
        service.side_effect = None
        service.return_value = {'participants': []}
        self.assertEqual(retry_media_policies(self.lesson.policy_sync_until + timedelta(seconds=1)), 0)
        self.lesson.refresh_from_db()
        self.assertIsNone(self.lesson.policy_sync_until)

    @patch('live_lessons.classroom.room_service')
    def test_screen_restriction_stops_existing_video_and_screen_audio_but_not_camera(self, service):
        service.return_value = {'participants': [{'identity': self.identity, 'tracks': [
            {'source': 'SCREEN_SHARE', 'sid': 'screen'}, {'source': 4, 'sid': 'screen-audio'},
            {'source': 'CAMERA', 'sid': 'camera'}, {'source': 'MICROPHONE', 'sid': 'voice'},
        ]}]}
        response = self.client.post(self.manage_url, {'action': 'screen', 'enabled': 'false'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([call.args[2]['track_sid'] for call in service.call_args_list
                          if call.args[1] == 'MutePublishedTrack'], ['screen', 'screen-audio'])

    @patch('live_lessons.classroom.room_service')
    def test_departing_participant_during_sync_is_not_a_retry_failure(self, service):
        service.side_effect = [{'participants': [{'identity': self.identity}]}, LiveKitAPIError('Gone', status_code=404)]
        response = self.client.post(self.manage_url, {'action': 'screen', 'enabled': 'false'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('pending', response.json())

    @patch('live_lessons.classroom.room_service', side_effect=LiveKitAPIError('Not found', status_code=404))
    def test_empty_media_room_is_not_a_failure(self, _service):
        self.lesson.mute_all_pending = True
        self.lesson.save()
        self.assertEqual(sync_media_policy(self.lesson), 0)

    def test_guest_gets_server_generated_name_cannot_see_queue_or_bypass_history_gate(self):
        self.lesson.audience = 'open'
        self.lesson.group = None
        self.lesson.save()
        guest = Client()
        self.waiting(guest)
        own = guest.get(self.state_url).json()['own']
        waiting = self.client.get(self.state_url).json()['waiting'][0]
        self.assertTrue(own['identity'].startswith('lesson-guest-'))
        self.assertNotEqual(waiting['name'], '')
        LiveLessonParticipant.objects.create(lesson=self.lesson, identity='other', name='Private', admission='admitted', hand_raised_at=timezone.now())
        self.assertEqual(guest.get(self.state_url).json()['hands'], [])
        self.lesson.status = 'ended'
        self.lesson.save()
        url = reverse('live_lesson_chat_messages', args=[self.lesson.public_id])
        self.assertEqual(guest.get(url).status_code, 403)
        self.assertEqual(Client().get(url).status_code, 403)
        self.assertNotContains(guest.get(self.detail_url()), 'id="ll-chat-messages"')
        self.lesson.participants.filter(identity=own['identity']).update(admission='admitted')
        self.assertEqual(guest.get(url).status_code, 200)

    def test_migration_preserves_legacy_chat_participants_without_changing_finished_lessons(self):
        self.lesson.audience = 'open'
        self.lesson.group = None
        self.lesson.save()
        guest_id = uuid4()
        LiveLessonMessage.objects.create(lesson=self.lesson, guest_id=guest_id, guest_name='Лев', body='Ранее участвовал')
        LiveLessonMessage.objects.create(lesson=self.lesson, author=self.student_user, body='Ранее участвовал')
        ended = LiveLesson.objects.create(teacher=self.teacher, audience='open', title='Старый урок',
                                          status='ended', scheduled_at=timezone.now(), waiting_room_enabled=False)
        migrate = import_module('live_lessons.migrations.0007_classroom_controls').enable_open_waiting_rooms
        for _ in range(2):
            migrate(apps, SimpleNamespace(connection=connection))
        self.lesson.refresh_from_db()
        ended.refresh_from_db()
        self.assertTrue(self.lesson.waiting_room_enabled)
        self.assertFalse(ended.waiting_room_enabled)
        self.assertEqual(self.lesson.participants.count(), 2)
        self.assertEqual(self.lesson.participants.get(identity=f'lesson-guest-{guest_id.hex}').admission, 'admitted')
        self.assertEqual(self.lesson.participants.get(identity=self.identity).admission, 'admitted')
