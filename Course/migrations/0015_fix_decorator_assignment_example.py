from django.db import migrations


INCORRECT_EXAMPLE = '''<li>Напишите функцию сортировки списка по последней цифре числа:
                из <code>[691, 547]</code> должен получиться
                <code>[691, 547]</code>, потому что 1 меньше 7. Добавьте
                декоратор, который запускает сортировку 100 раз и выводит
                среднее время выполнения.</li>'''
CORRECT_EXAMPLE = '''<li>Напишите функцию сортировки списка по убыванию последней
                цифры числа: из <code>[691, 547]</code> должен получиться
                <code>[547, 691]</code>, потому что 7 больше 1. Для этой
                задачи добавьте отдельный декоратор, который запускает
                сортировку 100 раз и выводит среднее время выполнения.</li>'''


def fix_decorator_assignment_example(apps, schema_editor):
    DirectionStudy = apps.get_model('Course', 'DirectionStudy')
    Schedule = apps.get_model('Course', 'Schedule')
    backend_direction = DirectionStudy.objects.filter(title='Backend 2024').first()
    if not backend_direction:
        return

    schedule = Schedule.objects.filter(
        direction_id=backend_direction.pk,
        position=55,
    ).first()
    if not schedule:
        return

    materials = (schedule.lesson_materials or '').replace(
        INCORRECT_EXAMPLE,
        CORRECT_EXAMPLE,
    )
    if materials != schedule.lesson_materials:
        schedule.lesson_materials = materials
        schedule.save(update_fields=('lesson_materials',))


class Migration(migrations.Migration):

    dependencies = [
        ('Course', '0014_clarify_beginner_assignments'),
    ]

    operations = [
        migrations.RunPython(
            fix_decorator_assignment_example,
            migrations.RunPython.noop,
        ),
    ]
