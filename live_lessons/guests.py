import secrets
import uuid


GUEST_ANIMALS = (
    'Лиса', 'Волк', 'Медведь', 'Заяц', 'Белка', 'Ёж',
    'Енот', 'Барсук', 'Выдра', 'Бобр', 'Олень', 'Лось',
    'Рысь', 'Тигр', 'Лев', 'Панда', 'Коала', 'Кенгуру',
    'Жираф', 'Зебра', 'Слон', 'Носорог', 'Бегемот', 'Верблюд',
    'Лама', 'Сурикат', 'Пингвин', 'Сова', 'Сокол', 'Дельфин',
)


def guest_for_lesson(request, lesson):
    """Закрепляем случайное имя за браузерной сессией в конкретном уроке."""
    key = f'live_lesson_guest_{lesson.public_id.hex}'
    guest = request.session.get(key)
    if isinstance(guest, dict) and guest.get('name') in GUEST_ANIMALS:
        try:
            return {'id': uuid.UUID(guest['id']), 'name': guest['name']}
        except (KeyError, TypeError, ValueError, AttributeError):
            pass
    guest = {'id': uuid.uuid4().hex, 'name': secrets.choice(GUEST_ANIMALS)}
    request.session[key] = guest
    return {'id': uuid.UUID(guest['id']), 'name': guest['name']}
