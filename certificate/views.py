import os
import random

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404

from Course.models import Student
from certificate.cert import create_certificate
from certificate.models import Certificate


def generate(request):
    students = Student.objects.exclude(
        pk__in=Certificate.objects.all().values_list('student__pk'))[::-1]
    if not request.user.is_staff:
        raise PermissionDenied()
    if request.method == 'GET':
        return render(request, 'certificate/generate.html',
                      {'students': students})
    name = request.POST.get('name')
    student = get_object_or_404(Student, name=name)
    fio = request.POST.get('fio')
    number = f'{student.pk}{random.randint(1000, 9999)}'
    certificate = Certificate(student=student, number=number, fio=fio)
    try:
        certificate.save()
    except IntegrityError:
        return render(
            request,
            'certificate/generate.html',
            {
                'students': students,
                'msg': 'Сертификат для этого пользователя уже существует!'
            }
        )
    date = str(certificate.date).split(' ')[0].split('-')[::-1]
    file_path = create_certificate(fio, '.'.join(date), number, )
    with open(file_path, 'rb') as fh:
        response = HttpResponse(fh.read(),
                                content_type="application/vnd.ms-word")
        response[
            'Content-Disposition'] = 'inline; filename=' + os.path.basename(
            file_path)
        return response


def verify(request):
    if request.method == 'GET':
        return render(request, 'certificate/verify.html')
    number = int(request.POST.get('number'))
    certificate = Certificate.objects.filter(number=number).first()
    if not certificate:
        return render(request, 'certificate/verify.html', {'fio': False})
    return render(request,
                  'certificate/verify.html',
                  {
                      'fio': certificate.fio,
                      'recommendation': certificate.comment,
                  }
                  )
