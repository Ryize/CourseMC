from django.contrib.auth.models import User
from django.http import JsonResponse
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from Course.models import LearnGroup, Schedule, Student, StudentQuestion, ClassesTimetable, ApplicationsForTraining
from billing.count_bill_logic import get_lesson_data

from .serializers import (LearnGroupListSerializer, ScheduleListSerializer,
                          StudentListSerializer, StudentQuestionListSerializer, ClassesTimetableListSerializer,
                          ApplicationsForTrainingSerializer, PaymentAmountSerializer)


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
        schedule = Schedule.objects.filter(group=group).order_by("weekday").values()
        return Response(schedule)


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


class ClassesTimetableView(APIView):
    def get(self, request, user_name: str):
        class_timetable = ClassesTimetable.objects.filter(teacher__username=user_name).all()
        serializer = ClassesTimetableListSerializer(class_timetable, many=True)
        return Response(serializer.data)


class ApplicationsForTrainingView(APIView):
    def get(self, request):
        app_training = ApplicationsForTraining.objects.filter(descry=False).all()
        serializer = ApplicationsForTrainingSerializer(app_training, many=True)
        return Response(serializer.data)


class PaymentAmountView(GenericAPIView):
    """
    Позволяет получить кол-во неоплаченных уроков и сумму для оплаты.
    """
    def get_serializer(self, *args, **kwargs):
        return PaymentAmountSerializer(*args, **kwargs)

    def get(self, request, student_id, *args, **kwargs):
        student = Student.objects.filter(pk=student_id).first()
        if not student:
            return JsonResponse({'error': 'Пользователь не найден!'})
        user = User.objects.get(username=student.name)
        _, amount_occupations, amount = get_lesson_data(user)
        return JsonResponse(
            {
                'amount': amount,
                'amount_occupations': amount_occupations,
            }
        )
