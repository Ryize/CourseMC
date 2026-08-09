from django.forms import DateTimeInput, HiddenInput, ModelForm, Select

from .models import AnswerQuestion, Question, Quiz


class DateTimeInput(DateTimeInput):
    input_type = "datetime-local"


class QuizForm(ModelForm):
    class Meta:
        model = Quiz
        fields = (
            "title",
            "description",
            "topic",
            "lifetime",
        )
        widgets = {
            "lifetime": DateTimeInput(),
        }


class QuestionForm(ModelForm):
    def __init__(self, quiz, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["quiz"].queryset = Quiz.objects.filter(pk=quiz.pk)
        self.fields["quiz"].initial = quiz.pk

    class Meta:
        model = Question
        fields = (
            "question",
            "quiz",
        )
        widgets = {
            "quiz": HiddenInput(),
        }


class AnswerForm(ModelForm):
    def __init__(self, quiz, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["question"].empty_label = "Не выбрано!"
        self.fields["question"].queryset = Question.objects.filter(
            quiz=quiz
        ).order_by(
            "-pk",
        )

    class Meta:
        model = AnswerQuestion
        fields = (
            "answer",
            "question",
            "correct",
        )
        widgets = {
            "question": Select(
                attrs={"class": "form-control", "placeholder": "Не выбрано!"}
            ),
        }
