import random
from pathlib import Path

from django import forms
from django.forms import ModelForm, TextInput

from CourseMC.widgets import RichTextEditorWidget

from .models import Schedule, Student


class StudentForm(ModelForm):
    name = forms.CharField(max_length=150, label='Имя')
    email = forms.EmailField(max_length=254, label='Почта')
    password = forms.CharField(max_length=128, label='Пароль')

    class Meta:
        model = Student
        fields = ("name", "contact", "email", "password")

    def __init__(self, *args, **kwargs):
        super(StudentForm, self).__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Имя*"}
        )
        self.fields["contact"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Ссылка на ВК/Телеграм*"}
        )
        self.fields["email"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Почта*"}
        )
        self.fields["password"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Необязательно",
                "value": random.randint(1111, 9999),
            }
        )


class AuthForm(forms.Form):
    name = forms.CharField(max_length=150, label='Логин')
    password = forms.CharField(max_length=128, label='Пароль')

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super(AuthForm, self).__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Логин*"}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Необязательно"}
        )


class ScheduleChoiceField(forms.ModelChoiceField):
    """Показывает урок в списке вставки вместе с его местом в программе."""

    def label_from_instance(self, schedule):
        return (
            f'{schedule.direction.title} · '
            f'{schedule.position}. {schedule.theme}'
        )


class ScheduleAdminForm(forms.ModelForm):
    """Форма редактора урока с безопасной вставкой в середину программы."""

    insert_after = ScheduleChoiceField(
        queryset=Schedule.objects.none(),
        required=False,
        label='Вставить после урока',
        help_text=(
            'Оставьте поле пустым, чтобы добавить урок в конец программы. '
            'Выбирать можно только урок того же направления.'
        ),
    )

    class Meta:
        model = Schedule
        fields = '__all__'
        widgets = {
            'plan': RichTextEditorWidget(),
            'lesson_materials': RichTextEditorWidget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['insert_after'].queryset = (
            Schedule.objects
            .filter(is_archived=False)
            .select_related('direction')
            .order_by('direction__title', 'position', 'pk')
        )

    def clean(self):
        cleaned_data = super().clean()
        direction = cleaned_data.get('direction')
        insert_after = cleaned_data.get('insert_after')

        if insert_after and direction and insert_after.direction_id != direction.pk:
            self.add_error(
                'insert_after',
                'Можно выбрать только урок из того же направления.',
            )
        if insert_after and self.instance.pk == insert_after.pk:
            self.add_error(
                'insert_after',
                'Нельзя вставить урок после самого себя.',
            )
        return cleaned_data


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        return files.getlist(name)


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not isinstance(data, (list, tuple)):
            data = [data]
        cleaned_files = []
        for uploaded_file in data:
            cleaned_files.append(super().clean(uploaded_file, initial))
        return cleaned_files


class LessonSolutionUploadForm(forms.Form):
    """Проверяет файлы решения, не пытаясь их исполнять или распаковывать."""

    allowed_extensions = {
        '.py', '.ipynb', '.txt', '.md', '.pdf', '.zip', '.rar',
        '.png', '.jpg', '.jpeg', '.docx',
    }
    max_files = 10
    max_file_size = 15 * 1024 * 1024

    files = MultipleFileField(
        label='Файлы решения',
        help_text='До 10 файлов по 15 МБ: код, архив, PDF, изображение или документ.',
        widget=MultipleFileInput(attrs={
            'accept': ','.join(sorted(allowed_extensions)),
            'multiple': True,
        }),
    )

    def clean_files(self):
        files = self.cleaned_data['files']
        if len(files) > self.max_files:
            raise forms.ValidationError(
                f'За одну отправку можно приложить не больше {self.max_files} файлов.'
            )

        for uploaded_file in files:
            extension = Path(uploaded_file.name).suffix.lower()
            if extension not in self.allowed_extensions:
                raise forms.ValidationError(
                    f'Файл «{uploaded_file.name}» нельзя прикрепить. '
                    'Поддерживаются код, архивы, PDF, изображения и DOCX.'
                )
            if uploaded_file.size > self.max_file_size:
                raise forms.ValidationError(
                    f'Файл «{uploaded_file.name}» превышает лимит 15 МБ.'
                )
        return files
