from django import forms

from .models import InterviewQuestionCategory, LiveCodingTask, MockInterview


FRAMEWORK_TITLES = ('Django', 'Flask', 'FastAPI')
MAX_SOLUTION_FILES = 5
MAX_SOLUTION_FILE_SIZE = 5 * 1024 * 1024
ALLOWED_SOLUTION_EXTENSIONS = {
    '.py', '.txt', '.md', '.json', '.yaml', '.yml', '.zip',
}


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data]
        return [single_clean(data, initial)] if data else []


class MockInterviewStartForm(forms.Form):
    level = forms.ChoiceField(
        choices=MockInterview.Level.choices,
        widget=forms.RadioSelect,
        label='Уровень собеседования',
        initial=MockInterview.Level.JUNIOR,
    )
    frameworks = forms.ModelMultipleChoiceField(
        queryset=InterviewQuestionCategory.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label='Фреймворки',
        help_text='Можно выбрать один или несколько.',
    )
    live_coding_category = forms.ChoiceField(
        choices=(
            ('random', 'Случайная категория'),
            *LiveCodingTask.Category.choices,
        ),
        widget=forms.RadioSelect,
        label='Категория задачи',
        initial='random',
        required=False,
    )

    def clean_live_coding_category(self):
        return self.cleaned_data.get('live_coding_category') or 'random'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['frameworks'].queryset = (
            InterviewQuestionCategory.objects
            .filter(
                title__in=FRAMEWORK_TITLES,
                interview_questions__use_in_mock=True,
                interview_questions__mock_section='framework',
            )
            .distinct()
            .order_by('title')
        )


class MockLiveCodingForm(forms.Form):
    solution = forms.CharField(
        required=False,
        label='Решение',
        widget=forms.Textarea(attrs={
            'rows': 20,
            'spellcheck': 'false',
            'placeholder': 'Напишите решение или пояснения к приложенным файлам…',
        }),
    )
    files = MultipleFileField(
        required=False,
        label='Файлы решения',
        help_text='До 5 файлов по 5 МБ: Python, текст, JSON, YAML или ZIP.',
    )
    repository_url = forms.URLField(
        required=False,
        label='Ссылка на Git-репозиторий',
        max_length=500,
        widget=forms.URLInput(attrs={
            'placeholder': 'https://github.com/username/project',
            'autocomplete': 'url',
        }),
    )

    def clean_files(self):
        from pathlib import Path

        files = self.cleaned_data['files']
        if len(files) > MAX_SOLUTION_FILES:
            raise forms.ValidationError('Можно прикрепить не более 5 файлов.')
        for uploaded_file in files:
            if uploaded_file.size > MAX_SOLUTION_FILE_SIZE:
                raise forms.ValidationError(
                    f'Файл «{uploaded_file.name}» превышает 5 МБ.',
                )
            if Path(uploaded_file.name).suffix.lower() not in ALLOWED_SOLUTION_EXTENSIONS:
                raise forms.ValidationError(
                    f'Тип файла «{uploaded_file.name}» не поддерживается.',
                )
        return files

    def clean(self):
        cleaned_data = super().clean()
        if (
            not cleaned_data.get('solution', '').strip()
            and not cleaned_data.get('files')
            and not cleaned_data.get('repository_url', '').strip()
        ):
            raise forms.ValidationError(
                'Напишите решение, приложите файл или укажите ссылку на Git-репозиторий.',
            )
        return cleaned_data
