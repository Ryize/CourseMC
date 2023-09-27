from urllib.parse import unquote

from django.contrib.auth.models import User
from django.http import JsonResponse
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from Course.models import LearnGroup, Schedule, Student, StudentQuestion, ClassesTimetable, ApplicationsForTraining
from billing.count_bill_logic import get_lesson_data
from billing.models import Absences, InformationPayments
from billing.views import get_cost_classes

from .serializers import (LearnGroupListSerializer, ScheduleListSerializer,
                          StudentListSerializer, StudentQuestionListSerializer, ClassesTimetableListSerializer,
                          ApplicationsForTrainingSerializer, PaymentAmountSerializer, MissingSerializer)


class ScheduleViewSet(APIView):
    """
    Вывод всех расписаний
    """

    def get(self, request):
        schedules = Schedule.objects.all()
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
        
    def post(self, request, username, *args, **kwargs):
        if username.find("%") == 0:
            username = unquote(username.upper(), "utf-8")
        student = Student.objects.filter(name=username).first()
        user = User.objects.filter(username=username).first()
        if not user:
            return JsonResponse({"error": "User not found"})
        amount = get_cost_classes(user)
        InformationPayments.objects.create(user=student, amount=amount)
        return Response(status=201)
        

    def get(self, request, username, *args, **kwargs):
        if username.find("%") == 0:
            username = unquote(username.upper(), "utf-8")
        user = User.objects.filter(username=username).first()
        if not user:
            return JsonResponse({"error": "User not found"})
        amount = get_cost_classes(user)
        return JsonResponse(
            {
                'amount': amount,
            }
        )



class MissingView(GenericAPIView):
    """
    Позволяет добавить пропуск.
    """

    def get_serializer(self, *args, **kwargs):
        return MissingSerializer(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        username = request.POST.get('username')
        date = request.POST.get('date')
        serializer = MissingSerializer(data=request.data)
        if not serializer.is_valid():
            return JsonResponse(
                {
                    'status': False,
                    'description': 'Incorrect data'
                }
            )
        student = Student.objects.filter(name=username).first()
        if not student:
            return JsonResponse(
                {
                    'status': False,
                    'description': 'Student not found'
                }
            )
        Absences.objects.create(user=student, date=date)
        return JsonResponse({'status': True})


class ClassesTimetableGingerView(GenericAPIView):
    def get(self, request, group: int):
        amount = ClassesTimetable.objects.filter(group=group).count()
        return JsonResponse({'amount': amount * 4})
        