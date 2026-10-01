import signal
import threading
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, close_old_connections

from live_lessons.lifecycle import sync_lessons


class Command(BaseCommand):
    help = 'Создаёт уроки за 5 минут до графика и закрывает занятия в полночь (TIME_ZONE).'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Выполнить один проход и выйти.')
        parser.add_argument('--interval', type=int, default=10, help='Интервал проверки, 1–60 секунд (по умолчанию 10).')

    def handle(self, *args, **options):
        interval = options['interval']
        if not 1 <= interval <= 60:
            raise CommandError('--interval должен быть от 1 до 60 секунд.')
        if options['once']:
            result = sync_lessons()
            self.stdout.write(str(result))
            if result['media_failures']:
                raise CommandError('Занятия обновлены, но медиакомнаты пока не закрыты. Повторите после восстановления LiveKit.')
            return
        stopped = threading.Event()
        handlers = {}
        for signum in (signal.SIGINT, signal.SIGTERM):
            handlers[signum] = signal.signal(signum, lambda *_: stopped.set())
        self.stdout.write(f'Планировщик онлайн-занятий запущен (интервал {interval} с).')
        try:
            while not stopped.is_set():
                tick = time.monotonic()
                close_old_connections()
                try:
                    result = sync_lessons()
                    if result['created'] or result['ended']:
                        self.stdout.write(str(result))
                except DatabaseError:
                    self.stderr.write('База временно недоступна. Повторяем в следующем проходе.')
                # Просыпаемся на границе секунд, включая 00:00, а не сдвигаемся из-за API-запросов.
                delay = max(0.1, interval - (time.monotonic() - tick))
                boundary = interval - time.time() % interval
                stopped.wait(min(delay, boundary))
        finally:
            close_old_connections()
            for signum, handler in handlers.items():
                signal.signal(signum, handler)
