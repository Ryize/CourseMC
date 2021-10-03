from rest_framework import serializers
from Course.models import Schedule, Student


class ScheduleListSerializer(serializers.ModelSerializer):
    """Список всех расписаний"""

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
    """Список всех студентов"""

    def create(self, validated_data):
        student = Student.objects.create(**validated_data)
        student.save()
        return student

    class Meta:
        model = Student
        fields = '__all__'