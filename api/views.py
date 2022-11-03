from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from Course.models import LearnGroup, Schedule, Student, StudentQuestion

from .serializers import (LearnGroupListSerializer, ScheduleListSerializer,
                          StudentListSerializer, StudentQuestionListSerializer)


class ScheduleViewSet(APIView):
    """
    Вывод всех расписаний
    """

    def get(self, request):
        schedules = Schedule.objects.all().order_by("weekday")
        serializer = ScheduleListSerializer(schedules, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ScheduleListSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(status=201)
        return Response(status=400)


class ScheduleGet(APIView):
    """
    Вывод расписаний с определённым пользователем
    """

    def post(self, request):
        username = request.data["username"]
        student = Student.objects.get(name=username)
        group = student.groups
        sсhedule = Schedule.objects.filter(group=group).order_by("weekday").values()
        return Response(sсhedule)


class StudentViewSet(APIView):
    """
    Вывод всех учеников
    """

    def get(self, request):
        schedules = Student.objects.all()
        serializer = StudentListSerializer(schedules, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = StudentListSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(status=201)
        return Response(status=400)


class LearnGroupViewSet(APIView):
    """
    Вывод всех групп
    """

    def get(self, request):
        groups = LearnGroup.objects.all()
        serializer = LearnGroupListSerializer(groups, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = LearnGroupListSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(status=201)
        return Response(status=400)


class StudentQuestionView(APIView):
    """
    Вывод всех вопросов пользователя
    """

    def get(self, request):
        student_question = StudentQuestion.objects.all().order_by("-created_at")
        serializer = StudentQuestionListSerializer(student_question, many=True)
        return Response(serializer.data)
