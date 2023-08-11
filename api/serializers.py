from rest_framework import serializers

from Course.models import LearnGroup, Schedule, Student, StudentQuestion, ClassesTimetable, ApplicationsForTraining


class ScheduleListSerializer(serializers.ModelSerializer):
    """ Список всех расписаний. """

    def create(self, validated_data):
        a = validated_data["absent"]
        del validated_data["absent"]
        schedule = Schedule.objects.creatd(**validated_data)
        schedule.absent.set(a)
        schedule.save()
        return schedule

    class Meta:
        model = Schedule
        fields = "__all__"


class StudentListSerializer(serializers.ModelSerializer):
    """ Список всех студентов. """

    def create(self, validated_data):
        student = Student.objects.create(**validated_data)
        student.save()
        return student

    class Meta:
        model = Student
        fields = "__all__"


class LearnGroupListSerializer(serializers.ModelSerializer):
    """ Список всех учебных групп. """

    def create(self, validated_data):
        group = LearnGroup.objects.create(**validated_data)
        group.save()
        return group

    class Meta:
        model = LearnGroup
        fields = "__all__"


class StudentQuestionListSerializer(serializers.ModelSerializer):
    """Список всех вопросов учеников."""

    class Meta:
        model = StudentQuestion
        fields = "__all__"


class ClassesTimetableListSerializer(serializers.ModelSerializer):
    """Список всех расписаний занятий. """

    class Meta:
        model = ClassesTimetable
        fields = "__all__"


class ApplicationsForTrainingSerializer(serializers.ModelSerializer):
    """ Список всех заявок на обучение. """
    name = serializers.ReadOnlyField(source='student.name')
    contact = serializers.ReadOnlyField(source='student.contact')
    email = serializers.ReadOnlyField(source='student.email')

    class Meta:
        model = ApplicationsForTraining
        fields = '__all__'


class PaymentAmountSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
