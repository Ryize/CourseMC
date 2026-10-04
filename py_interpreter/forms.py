from django import forms
from django.utils import timezone

from live_lessons.forms import archive_targets
from .models import SharedCodeSnapshot


class SharedCodePublishForm(forms.Form):
    snapshot = forms.ModelChoiceField(label='Версия созвона', queryset=SharedCodeSnapshot.objects.none())
    code_target = forms.ChoiceField(label='Урок программы и группа', choices=())
    title = forms.CharField(max_length=100, required=False)

    def __init__(self, *args, lesson, teacher_user, current_code=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['snapshot'].queryset = SharedCodeSnapshot.objects.filter(document__lesson=lesson)
        self.fields['snapshot'].label_from_instance = lambda item: (
            f'{item.title} · {timezone.localtime(item.created_at):%d.%m.%Y %H:%M} · №{item.pk}'
        )
        self.fields['snapshot'].required = not current_code
        self.fields['snapshot'].empty_label = 'Выберите версию созвона'
        self.targets = archive_targets(lesson, teacher_user)
        self.allowed_targets = {
            f'{group.pk}:{schedule.pk}': (group, schedule)
            for group, schedules in self.targets for schedule in schedules
        }
        self.fields['code_target'].choices = [
            ('', 'Выберите урок программы и группу'),
            *[(group.title, [(f'{group.pk}:{item.pk}',
                             f'{item.direction.title} · {item.position}. {item.theme}')
                            for item in schedules]) for group, schedules in self.targets],
        ]

    def clean_title(self):
        return self.cleaned_data['title'].strip() or 'Код занятия'

    def target_objects(self):
        return self.allowed_targets[self.cleaned_data['code_target']]
