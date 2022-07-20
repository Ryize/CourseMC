from django.forms import ModelForm, DateTimeInput, Select
from django.http import QueryDict

from .models import *


class DateTimeInput(DateTimeInput):
    input_type = 'datetime-local'


class QuizForm(ModelForm):
    class Meta:
        model = Quiz
        fields = ('title', 'description', 'topic', 'lifetime',)
        widgets = {
            'lifetime': DateTimeInput(),
        }


class QuestionForm(ModelForm):
    def __init__(self, quiz, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['quiz'].empty_label = "Не выбрано!"

        if quiz is not None:
            if isinstance(quiz, QueryDict):
                qs = Quiz.objects.filter(pk=quiz['quiz']).all()
            else:
                qs = Quiz.objects.filter(pk=quiz[0].pk).all()
            self.initial['quiz'] = qs[0].pk
            self.fields['quiz'].queryset = qs

    class Meta:
        model = Question
        fields = ('question', 'quiz',)
        widgets = {
            'quiz': Select(attrs={'class': 'form-control'}),
        }


class AnswerForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['question'].empty_label = "Не выбрано!"
        self.fields['question'].queryset = self.fields['question'].queryset.order_by('-pk')

    class Meta:
        model = AnswerQuestion
        fields = ('answer', 'question', 'correct',)
        widgets = {
            'question': Select(attrs={'class': 'form-control', 'placeholder': 'Не выбрано!'}),
        }
