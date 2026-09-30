from datetime import timedelta

from django import forms
from django.utils import timezone

from Course.models import LearnGroup, Schedule, Student

from .models import LiveLesson


DATETIME_FORMAT = '%Y-%m-%dT%H:%M'


def validate_future_lesson(value):
    if value < timezone.now() - timedelta(minutes=5):
        raise forms.ValidationError('Выберите текущее или будущее время.')
    if value > timezone.now() + timedelta(days=365):
        raise forms.ValidationError('Занятие можно назначить не более чем на год вперёд.')


class LiveLessonCreateForm(forms.ModelForm):
    audience = forms.ChoiceField(
        label='Кто сможет войти', choices=LiveLesson.Audience.choices,
        widget=forms.RadioSelect, initial=LiveLesson.Audience.GROUPS, required=False,
    )
    scheduled_at = forms.DateTimeField(
        label='Дата и время',
        input_formats=[DATETIME_FORMAT],
        widget=forms.DateTimeInput(format=DATETIME_FORMAT, attrs={'type': 'datetime-local'}),
        validators=[validate_future_lesson],
    )

    class Meta:
        model = LiveLesson
        fields = ('audience', 'group', 'additional_groups', 'title', 'scheduled_at', 'duration_minutes')
        widgets = {'title': forms.TextInput(attrs={'placeholder': 'Например, Django ORM: практика'})}

    def __init__(self, *args, teacher_user, **kwargs):
        super().__init__(*args, **kwargs)
        groups = LearnGroup.objects.filter(
            teacher__user=teacher_user, is_studies=True,
        ).order_by('title', 'pk')
        self.fields['group'].queryset = groups
        self.fields['group'].required = False
        self.fields['group'].help_text = 'Для открытого урока группа не нужна.'
        self.fields['additional_groups'].queryset = groups
        self.fields['additional_groups'].widget = forms.CheckboxSelectMultiple()
        self.fields['additional_groups'].help_text = 'Необязательно. Ученики этих групп получат доступ к той же комнате.'
        self.fields['audience'].help_text = 'В открытый урок сможет войти любой, у кого есть ссылка, даже без аккаунта.'
        self.fields['duration_minutes'].help_text = 'От 15 минут до 4 часов.'
        if not self.is_bound:
            self.initial.setdefault('title', 'Урок')
            start = timezone.localtime(timezone.now() + timedelta(minutes=5))
            self.initial.setdefault('scheduled_at', start.strftime(DATETIME_FORMAT))

    def clean(self):
        cleaned = super().clean()
        cleaned['audience'] = cleaned.get('audience') or LiveLesson.Audience.GROUPS
        if cleaned.get('audience') == LiveLesson.Audience.OPEN:
            cleaned['group'] = None
            cleaned['additional_groups'] = LearnGroup.objects.none()
        elif cleaned.get('audience') == LiveLesson.Audience.GROUPS:
            group = cleaned.get('group')
            if not group:
                self.add_error('group', 'Выберите основную группу.')
            elif group in cleaned.get('additional_groups', ()):
                self.add_error('additional_groups', 'Основная группа уже выбрана.')
        return cleaned


class LiveLessonRescheduleForm(forms.Form):
    scheduled_at = forms.DateTimeField(
        label='Новая дата и время', input_formats=[DATETIME_FORMAT],
        widget=forms.DateTimeInput(format=DATETIME_FORMAT, attrs={'type': 'datetime-local'}),
        validators=[validate_future_lesson],
    )
    reason = forms.CharField(label='Причина переноса', max_length=250, required=False)


def archive_targets(lesson, teacher_user):
    """Только уроки направлений учеников из участвовавших групп ведущего."""
    if lesson.audience != LiveLesson.Audience.GROUPS:
        return []
    groups = LearnGroup.objects.filter(
        pk__in=[lesson.group_id, *lesson.additional_groups.values_list('pk', flat=True)],
        teacher__user=teacher_user,
    ).order_by('title', 'pk')
    result = []
    for group in groups:
        directions = Student.objects.filter(
            groups=group, is_learned=True,
        ).values_list('direction', flat=True)
        schedules = Schedule.objects.filter(
            direction_id__in=directions, is_archived=False,
        ).select_related('direction').order_by('direction__title', 'position', 'pk')
        if schedules:
            result.append((group, list(schedules)))
    return result


class LiveLessonChatArchiveForm(forms.Form):
    target = forms.ChoiceField(label='Урок и группа', choices=())

    def __init__(self, *args, lesson, teacher_user, **kwargs):
        super().__init__(*args, **kwargs)
        self.targets = archive_targets(lesson, teacher_user)
        self.allowed_targets = {
            f'{group.pk}:{schedule.pk}': (group, schedule)
            for group, schedules in self.targets for schedule in schedules
        }
        self.fields['target'].choices = [
            ('', 'Выберите урок программы'),
            *[(group.title, [
                (f'{group.pk}:{schedule.pk}', f'{schedule.direction.title} · {schedule.position}. {schedule.theme}')
                for schedule in schedules
            ]) for group, schedules in self.targets],
        ]

    def target_objects(self):
        return self.allowed_targets[self.cleaned_data['target']]
