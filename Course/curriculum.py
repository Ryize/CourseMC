import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    CurriculumLesson,
    CurriculumVersion,
    DirectionStudy,
    Schedule,
)


SIGNATURE_FIELDS = (
    'pk',
    'position',
    'theme',
    'plan',
    'lesson_materials',
    'lesson_type',
)


def curriculum_signature(direction_id):
    rows = list(
        Schedule.objects
        .filter(direction_id=direction_id, is_archived=False)
        .order_by('position', 'pk')
        .values(*SIGNATURE_FIELDS)
    )
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


@transaction.atomic
def create_curriculum_draft(direction, user):
    direction = DirectionStudy.objects.select_for_update().get(pk=direction.pk)
    if CurriculumVersion.objects.filter(
        direction=direction,
        status=CurriculumVersion.Status.DRAFT,
    ).exists():
        raise ValidationError('У этого направления уже есть черновик программы.')

    version = CurriculumVersion.objects.create(
        direction=direction,
        name=f'Обновление от {timezone.localdate():%d.%m.%Y}',
        status=CurriculumVersion.Status.DRAFT,
        base_signature=curriculum_signature(direction.pk),
        created_by=user,
    )
    source_lessons = list(
        Schedule.objects
        .filter(direction=direction, is_archived=False)
        .order_by('position', 'pk')
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
    return version


@transaction.atomic
def publish_curriculum_version(version, user):
    version = (
        CurriculumVersion.objects
        .select_for_update()
        .select_related('direction')
        .get(pk=version.pk)
    )
    if version.status != CurriculumVersion.Status.DRAFT:
        raise ValidationError('Опубликовать можно только черновик.')
    if curriculum_signature(version.direction_id) != version.base_signature:
        raise ValidationError(
            'Опубликованная программа изменилась после создания черновика. '
            'Создайте новый черновик, чтобы не затереть изменения.',
        )

    lessons = list(version.lessons.select_for_update().order_by('position', 'pk'))
    if not lessons:
        raise ValidationError('Нельзя опубликовать программу без уроков.')

    live_lessons = {
        lesson.pk: lesson
        for lesson in Schedule.objects.select_for_update().filter(
            direction=version.direction,
        )
    }
    used_schedule_ids = []
    for position, lesson in enumerate(lessons, start=1):
        schedule = live_lessons.get(lesson.source_schedule_id)
        if schedule is None:
            schedule = Schedule.objects.create(
                direction=version.direction,
                position=position,
                theme=lesson.theme,
                plan=lesson.plan,
                lesson_materials=lesson.lesson_materials,
                lesson_type=lesson.lesson_type,
                is_archived=False,
            )
            lesson.source_schedule = schedule
            lesson.save(update_fields=('source_schedule',))
        else:
            Schedule.objects.filter(pk=schedule.pk).update(
                position=position,
                theme=lesson.theme,
                plan=lesson.plan,
                lesson_materials=lesson.lesson_materials,
                lesson_type=lesson.lesson_type,
                is_archived=False,
            )
        used_schedule_ids.append(schedule.pk)

    Schedule.objects.filter(
        direction=version.direction,
        is_archived=False,
    ).exclude(pk__in=used_schedule_ids).update(is_archived=True)

    CurriculumVersion.objects.filter(
        direction=version.direction,
        status=CurriculumVersion.Status.PUBLISHED,
    ).update(status=CurriculumVersion.Status.ARCHIVED)
    version.status = CurriculumVersion.Status.PUBLISHED
    version.published_at = timezone.now()
    version.notes = (
        f'{version.notes}\n\nОпубликовал: {user.get_username()}'.strip()
    )
    version.save(update_fields=('status', 'published_at', 'notes', 'updated_at'))
    return version
