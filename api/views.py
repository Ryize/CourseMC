
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from Course.models import Schedule, Student
from .serializers import ScheduleListSerializer, StudentListSerializer


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