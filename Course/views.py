from django.contrib import messages
from django.contrib.auth import get_user
from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic.edit import FormView
from django.contrib.auth.models import User
from .forms import *
from django.contrib.auth.decorators import login_required
from .models import Student, LearnGroup, Schedule
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView


class StudentRecordView(FormView):
    template_name = 'Course/index.html'
    form_class = StudentForm
    login_url = '/login/'

    def form_valid(self, form):
        form.save()
        name = form.cleaned_data['name']
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        user = User.objects.create_user(name, email, password)
        user.save()
        response = {
            'success': True,
        }
        return JsonResponse(response)

    def form_invalid(self, form):
        response = {
            'success': False,
            'error_message': 'Форма заполнена не верно!'
        }
        return JsonResponse(response)


class TimetableView(ListView):
    model = Schedule
    template_name = 'Course/timetable.html'
    context_object_name = 'schedules'

    def get_queryset(self):
        student = Student.objects.get(name=get_user(self.request).username)
        student_group = Schedule.objects.filter(group=student.groups).order_by('-pk')
        print(student_group)
        return student_group