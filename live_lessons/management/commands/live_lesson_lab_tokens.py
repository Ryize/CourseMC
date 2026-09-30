import secrets
import time

import jwt
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Создать два короткоживущих токена для локального LiveKit --dev.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Лабораторные токены доступны только при DEBUG=True.')

        now = int(time.time())
        room = f'quality-lab-{secrets.token_hex(6)}'
        self.stdout.write(f'Локальная комната: {room}')
        self.stdout.write('Сервер: ws://127.0.0.1:7880')
        for number in (1, 2):
            identity = f'tester-{number}-{secrets.token_hex(4)}'
            token = jwt.encode(
                {
                    'iss': 'devkey',
                    'sub': identity,
                    'name': f'Тестовый участник {number}',
                    'nbf': now,
                    'exp': now + 30 * 60,
                    'video': {
                        'roomJoin': True,
                        'room': room,
                        'canPublish': True,
                        'canSubscribe': True,
                    },
                },
                'secret',
                algorithm='HS256',
            )
            self.stdout.write(f'Участник {number}: {token}')
