from django.contrib import admin
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from .admin import StudentCardAdmin, StudentCardAdminForm
from .models import LearnGroup, Student, StudentCard, StudentNote


class StudentCardTests(TestCase):
    def create_teacher(self, suffix, group_id):
        user = User.objects.create_user(
            f'teacher-{suffix}',
            password='password',
            is_staff=True,
        )
        teacher = Student.objects.create(
            user=user,
            contact=f'@teacher-{suffix}',
            groups_id=group_id,
            is_learned=False,
        )
        group = LearnGroup.objects.create(
            pk=group_id,
            title=f'Группа {suffix}',
            teacher=teacher,
        )
        return user, group

    def create_student(self, group, suffix):
        user = User.objects.create_user(suffix, password='password')
        return Student.objects.create(
            user=user,
            contact=f'@{suffix}',
            groups=group,
            is_learned=True,
        )

    def test_card_and_notes_exist_before_registration(self):
        card = StudentCard.objects.create(
            full_name='Анна Смирнова',
            telegram='@anna',
            learning_goals='Хочет сменить профессию',
        )
        note = StudentNote.objects.create(
            card=card,
            kind=StudentNote.Kind.INTRO_CALL,
            text='Обсудили формат занятий',
        )

        self.assertIsNone(card.student)
        self.assertEqual(card.primary_contact, '@anna')
        self.assertEqual(list(card.notes.all()), [note])

    def test_only_one_card_can_be_linked_to_student(self):
        _, group = self.create_teacher('main', 9701)
        student = self.create_student(group, 'linked-student')
        StudentCard.objects.create(full_name='Первая', student=student)

        with self.assertRaises(IntegrityError), transaction.atomic():
            StudentCard.objects.create(full_name='Вторая', student=student)

    def test_registered_status_requires_linked_student_in_admin_form(self):
        form = StudentCardAdminForm(data={
            'full_name': 'Кандидат без аккаунта',
            'status': StudentCard.Status.STUDYING,
        })

        self.assertFalse(form.is_valid())
        self.assertIn('student', form.errors)

    def test_link_field_contains_only_active_students_without_card(self):
        _, group = self.create_teacher('available', 9708)
        available = self.create_student(group, 'available-student')
        already_linked = self.create_student(group, 'linked-elsewhere')
        inactive = self.create_student(group, 'inactive-student')
        inactive.is_learned = False
        inactive.save(update_fields=('is_learned',))
        StudentCard.objects.create(
            full_name='Занятая карточка',
            student=already_linked,
        )

        form = StudentCardAdminForm()

        self.assertQuerySetEqual(
            form.fields['student'].queryset,
            [available],
        )

    def test_link_field_orders_newest_students_first(self):
        _, group = self.create_teacher('ordering', 9710)
        older = self.create_student(group, 'older-student')
        newer = self.create_student(group, 'newer-student')

        form = StudentCardAdminForm()

        self.assertQuerySetEqual(
            form.fields['student'].queryset,
            [newer, older],
        )

    def test_link_autocomplete_filters_and_orders_students(self):
        admin_user = User.objects.create_superuser(
            'autocomplete-admin',
            email='autocomplete@example.com',
            password='password',
        )
        _, group = self.create_teacher('autocomplete', 9711)
        older = self.create_student(group, 'autocomplete-older')
        newer = self.create_student(group, 'autocomplete-newer')
        linked = self.create_student(group, 'autocomplete-linked')
        inactive = self.create_student(group, 'autocomplete-inactive')
        inactive.is_learned = False
        inactive.save(update_fields=('is_learned',))
        StudentCard.objects.create(full_name='Связанная', student=linked)
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin:autocomplete'), {
            'app_label': 'Course',
            'model_name': 'studentcard',
            'field_name': 'student',
            'term': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item['id'] for item in response.json()['results']],
            [str(newer.pk), str(older.pk)],
        )

    def test_edit_form_keeps_current_linked_student_available(self):
        _, group = self.create_teacher('current-link', 9709)
        current_student = self.create_student(group, 'current-student')
        other_student = self.create_student(group, 'other-student')
        current_card = StudentCard.objects.create(
            full_name='Текущая карточка',
            student=current_student,
        )
        StudentCard.objects.create(
            full_name='Другая карточка',
            student=other_student,
        )

        form = StudentCardAdminForm(instance=current_card)

        self.assertIn(current_student, form.fields['student'].queryset)
        self.assertNotIn(other_student, form.fields['student'].queryset)

    def test_admin_assigns_author_teacher_and_updates_status_on_link(self):
        teacher_user, group = self.create_teacher('responsible', 9702)
        student = self.create_student(group, 'new-account')
        request = RequestFactory().post('/coursemc_control/Course/studentcard/add/')
        request.user = teacher_user
        model_admin = StudentCardAdmin(StudentCard, admin.site)
        card = StudentCard(
            full_name='Новый ученик',
            student=student,
            status=StudentCard.Status.READY_TO_START,
        )

        model_admin.save_model(request, card, form=None, change=False)

        self.assertEqual(card.created_by, teacher_user)
        self.assertEqual(card.responsible_teacher, teacher_user)
        self.assertEqual(card.status, StudentCard.Status.REGISTERED)

    def test_teacher_sees_assigned_and_group_cards_only(self):
        first_user, first_group = self.create_teacher('first', 9703)
        second_user, second_group = self.create_teacher('second', 9704)
        first_student = self.create_student(first_group, 'first-student')
        second_student = self.create_student(second_group, 'second-student')
        assigned = StudentCard.objects.create(
            full_name='Назначенная карточка',
            responsible_teacher=first_user,
        )
        group_card = StudentCard.objects.create(
            full_name='Ученик группы',
            student=first_student,
        )
        StudentCard.objects.create(
            full_name='Чужая карточка',
            student=second_student,
            responsible_teacher=second_user,
        )
        request = RequestFactory().get('/coursemc_control/Course/studentcard/')
        request.user = first_user
        model_admin = StudentCardAdmin(StudentCard, admin.site)

        visible_ids = set(
            model_admin.get_queryset(request).values_list('pk', flat=True),
        )

        self.assertSetEqual(visible_ids, {assigned.pk, group_card.pk})

    def test_admin_pages_show_card_fields_and_student_link(self):
        admin_user = User.objects.create_superuser(
            'student-card-admin',
            email='admin@example.com',
            password='password',
        )
        _, group = self.create_teacher('admin-page', 9705)
        student = self.create_student(group, 'profile-student')
        self.client.force_login(admin_user)

        add_response = self.client.get(reverse('admin:Course_studentcard_add'))
        student_response = self.client.get(
            reverse('admin:Course_student_change', args=(student.pk,)),
        )

        self.assertEqual(add_response.status_code, 200)
        self.assertContains(add_response, 'Информация с первого созвона')
        self.assertContains(add_response, 'Следующий шаг и договорённости')
        self.assertContains(add_response, 'Заметки и созвоны')
        self.assertContains(student_response, 'Создать и связать карточку')

    def test_responsible_teacher_uses_local_select_without_user_permission(self):
        teacher_user, _ = self.create_teacher('field-choice', 9706)
        other_teacher, _ = self.create_teacher('field-option', 9707)
        request = RequestFactory().get(
            '/coursemc_control/Course/studentcard/add/',
        )
        request.user = teacher_user
        model_admin = StudentCardAdmin(StudentCard, admin.site)

        form_class = model_admin.get_form(request)
        form = form_class()
        field = form.fields['responsible_teacher']
        inner_widget = getattr(field.widget, 'widget', field.widget)

        self.assertEqual(inner_widget.__class__.__name__, 'UnfoldAdminSelectWidget')
        self.assertQuerySetEqual(
            field.queryset,
            User.objects.filter(is_staff=True, is_active=True).order_by(
                'first_name',
                'last_name',
                'username',
            ),
        )
        self.assertIn(other_teacher, field.queryset)

    def test_completed_reminder_is_not_left_in_attention_queue(self):
        admin_user = User.objects.create_superuser(
            'reminder-admin',
            email='reminder@example.com',
            password='password',
        )
        card = StudentCard.objects.create(
            full_name='Ученик с напоминанием',
            next_contact_at=timezone.now(),
        )
        active_note = StudentNote.objects.create(
            card=card,
            text='Написать после вводного созвона',
            remind_at=timezone.now(),
        )
        StudentNote.objects.create(
            card=card,
            text='Уже выполнено',
            remind_at=timezone.now(),
            reminder_done=True,
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Контакты с учениками')
        self.assertContains(response, active_note.text)
        self.assertNotContains(response, 'Уже выполнено')
