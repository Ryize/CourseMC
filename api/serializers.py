from rest_framework import serializers

from Course.models import (LearnGroup, Schedule, Student, StudentQuestion,
                           ClassesTimetable, ApplicationsForTraining)
from codereview.models import ProjectForReview

from interview.models import InterviewQuestion, InterviewQuestionCategory

from ai_assistant.models import QuestionAnswer


class ScheduleListSerializer(serializers.ModelSerializer):
    """ Список всех расписаний. """

    def create(self, validated_data):
        a = validated_data['absent']
        del validated_data['absent']
        schedule = Schedule.objects.creatd(**validated_data)
        schedule.absent.set(a)
        schedule.save()
        return schedule

    class Meta:
        model = Schedule
        fields = '__all__'


class StudentListSerializer(serializers.ModelSerializer):
    """ Список всех студентов. """

    def create(self, validated_data):
        student = Student.objects.create(**validated_data)
        student.save()
        return student

    class Meta:
        model = Student
        fields = '__all__'


class LearnGroupListSerializer(serializers.ModelSerializer):
    """ Список всех учебных групп. """

    def create(self, validated_data):
        group = LearnGroup.objects.create(**validated_data)
        group.save()
        return group

    class Meta:
        model = LearnGroup
        fields = '__all__'


class StudentQuestionListSerializer(serializers.ModelSerializer):
    """Список всех вопросов учеников."""

    class Meta:
        model = StudentQuestion
        fields = '__all__'


class ClassesTimetableListSerializer(serializers.ModelSerializer):
    """Список всех расписаний занятий. """
    group = serializers.StringRelatedField()

    class Meta:
        model = ClassesTimetable
        fields = ('group', 'weekday', 'time_lesson', 'duration')


class ApplicationsForTrainingSerializer(serializers.ModelSerializer):
    """ Список всех заявок на обучение. """
    name = serializers.ReadOnlyField(source='student.name')
    contact = serializers.ReadOnlyField(source='student.contact')
    email = serializers.ReadOnlyField(source='student.email')

    class Meta:
        model = ApplicationsForTraining
        fields = '__all__'


class PaymentAmountSerializer(serializers.Serializer):
    """ Сумма оплаты для указанного ученика. """
    student_id = serializers.IntegerField()


class MissingSerializer(serializers.Serializer):
    """ Для пропуска занятий. """
    username = serializers.CharField(max_length=32)
    date = serializers.DateField()


class ProjectForReviewSerializer(serializers.ModelSerializer):
    """ Список проектов отправленных на ревью. """

    class Meta:
        model = ProjectForReview
        fields = '__all__'


class InterviewQuestionCategorySerializer(serializers.ModelSerializer):
    """ Список категорий с 'Твой собес'. """
    class Meta:
        model = InterviewQuestionCategory
        fields = '__all__'


class InterviewQuestionSerializer(serializers.ModelSerializer):
    """ Список всех вопросов с 'Твой собес'. """

    theme = serializers.StringRelatedField()

    class Meta:
        model = InterviewQuestion
        fields = ('id', 'title', 'complexity', 'percent', 'theme')
        

class QuestionAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionAnswer
        fields = ['question', 'answer']