from django.contrib.auth.models import User
from django.db import models


class Quiz(models.Model):
    title = models.CharField(max_length=64, verbose_name="Название")
    description = models.CharField(max_length=256, verbose_name="Описание")
    topic = models.CharField(max_length=64, verbose_name="Тема")
    lifetime = models.DateTimeField(verbose_name="Действует до")
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name="Пользователь",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    def __str__(self):
        return f"{self.title}, {self.topic}"

    class Meta:
        verbose_name = "Опрос"
        verbose_name_plural = "Опросы"


class Question(models.Model):
    question = models.CharField(max_length=64, verbose_name="Вопрос")
    quiz = models.ForeignKey(
        "Quiz", on_delete=models.CASCADE, verbose_name="Опрос", related_name="questions"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    def __str__(self):
        return f"{self.question}"

    class Meta:
        verbose_name = "Вопрос"
        verbose_name_plural = "Вопросы"


class AnswerQuestion(models.Model):
    answer = models.CharField(max_length=64, verbose_name="Ответ")
    question = models.ForeignKey(
        "Question",
        on_delete=models.CASCADE,
        verbose_name="Вопрос",
        related_name="answers",
    )
    correct = models.BooleanField(default=False, verbose_name="Это правильный ответ?")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    def __str__(self):
        return f"{self.answer}"

    class Meta:
        verbose_name = "Ответ"
        verbose_name_plural = "Ответы"


class UserAnswer(models.Model):
    quiz = models.ForeignKey(
        "Quiz",
        on_delete=models.CASCADE,
        verbose_name="Опрос",
        related_name="user_quiz",
        null=True,
    )
    question = models.ForeignKey(
        "Question",
        on_delete=models.CASCADE,
        verbose_name="Вопрос",
        related_name="user_question",
        null=True,
    )
    answers = models.ForeignKey(
        "AnswerQuestion",
        on_delete=models.CASCADE,
        verbose_name="Ответ",
        related_name="user_answer",
        null=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name="Пользователь",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")


class PassedPolls(models.Model):
    quiz = models.ForeignKey(
        "Quiz",
        on_delete=models.CASCADE,
        verbose_name="Опрос",
        related_name="passed_quiz",
    )
    passed_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name="Пользователь",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Закончил опрос")

    def __str__(self):
        return f"{self.quiz}, {self.passed_user}"

    class Meta:
        verbose_name = "Пройденный опрос"
        verbose_name_plural = "Пройденные опросы"


class Rating(models.Model):
    answer_number = models.IntegerField(verbose_name="Число звёзд")
    comment = models.CharField(
        max_length=750,
        blank=True,
        default="Комментарий не добавлен!",
        verbose_name="Комментарий",
    )
    quiz = models.ForeignKey(
        "Quiz", on_delete=models.CASCADE, verbose_name="Опрос", related_name="rating"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name="Пользователь",
    )

    class Meta:
        verbose_name = "Рейтинг"
        verbose_name_plural = "Рейтинг"

    def __str__(self):
        return f"{self.quiz}, {self.answer_number} звёзд. {self.comment}"
