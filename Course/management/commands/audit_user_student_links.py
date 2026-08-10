from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from Course.models import Student


class Command(BaseCommand):
    help = (
        'Проверяет связи User и Student. Команда только читает данные и не '
        'выводит пароли, контакты или полные адреса электронной почты.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--details', action='store_true')

    def handle(self, *args, **options):
        User = get_user_model()
        students = list(Student.objects.select_related('user').order_by('pk'))
        users = list(User.objects.only('pk', 'username'))
        linked_user_ids = {student.user_id for student in students}
        users_without_profile = [
            user for user in users if user.pk not in linked_user_ids
        ]

        rows = (
            ('Аккаунтов User', len(users)),
            ('Учебных профилей Student', len(students)),
            ('Связанных профилей', len(students)),
            ('User без связанного профиля', len(users_without_profile)),
        )
        for label, value in rows:
            self.stdout.write(f'{label}: {value}')

        if not options['details']:
            return

        self._write_details('User без учебного профиля', (
            f'User #{user.pk}: {user.username}'
            for user in users_without_profile
        ))

    def _write_details(self, title, lines):
        lines = list(lines)
        if not lines:
            return
        self.stdout.write('')
        self.stdout.write(self.style.WARNING(title))
        for line in lines:
            self.stdout.write(f'  {line}')
