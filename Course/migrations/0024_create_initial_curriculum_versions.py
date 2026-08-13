import hashlib
import json

from django.db import migrations
from django.utils import timezone


SIGNATURE_FIELDS = (
    'pk', 'position', 'theme', 'plan', 'lesson_materials', 'lesson_type',
)


def create_initial_versions(apps, schema_editor):
    CurriculumLesson = apps.get_model('Course', 'CurriculumLesson')
    CurriculumVersion = apps.get_model('Course', 'CurriculumVersion')
    DirectionStudy = apps.get_model('Course', 'DirectionStudy')
    Schedule = apps.get_model('Course', 'Schedule')

    for direction in DirectionStudy.objects.all().iterator():
        source_lessons = list(
            Schedule.objects
            .filter(direction=direction, is_archived=False)
            .order_by('position', 'pk')
        )
        if not source_lessons:
            continue
        signature_rows = [
            {field: getattr(lesson, field) for field in SIGNATURE_FIELDS}
            for lesson in source_lessons
        ]
        signature = hashlib.sha256(
            json.dumps(
                signature_rows,
                ensure_ascii=False,
                sort_keys=True,
            ).encode('utf-8'),
        ).hexdigest()
        version = CurriculumVersion.objects.create(
            direction=direction,
            name='Исходная опубликованная программа',
            status='published',
            base_signature=signature,
            published_at=timezone.now(),
        )
        CurriculumLesson.objects.bulk_create([
            CurriculumLesson(
                version=version,
                source_schedule=lesson,
                position=lesson.position,
                theme=lesson.theme,
                plan=lesson.plan,
                lesson_materials=lesson.lesson_materials,
                lesson_type=lesson.lesson_type,
            )
            for lesson in source_lessons
        ])


class Migration(migrations.Migration):
    dependencies = [
        ('Course', '0023_curriculumversion_curriculumlesson_and_more'),
    ]

    operations = [
        migrations.RunPython(create_initial_versions, migrations.RunPython.noop),
    ]
