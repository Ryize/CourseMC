from django.contrib.auth import get_user_model
from django.db.models import Q
from django.forms import (
    CheckboxSelectMultiple,
    DateTimeInput,
    HiddenInput,
    ModelForm,
    Select,
)

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


class QuizAccessForm(ModelForm):
    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        teachers = (
            get_user_model().objects
            .filter(is_active=True)
            .filter(
                Q(groups__name="Учитель")
                | Q(course_profile__learngroups__isnull=False)
            )
            .distinct()
            .order_by("first_name", "last_name", "username")
        )
        if owner is not None:
            teachers = teachers.exclude(pk=owner.pk)
        access_field = self.fields["teachers_with_access"]
        access_field.queryset = teachers
        access_field.label_from_instance = lambda user: (
            f"{user.get_full_name()} ({user.username})"
            if user.get_full_name()
            else user.username
        )

    class Meta:
        model = Quiz
        fields = ("teachers_with_access",)
        widgets = {
            "teachers_with_access": CheckboxSelectMultiple(),
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


class QuestionEditForm(ModelForm):
    class Meta:
        model = Question
        fields = ("question",)


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
