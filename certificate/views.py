from django.shortcuts import render

from certificate.cert import create_certificate


def generate(request):
    create_certificate('Чекашов Матвей', '12.11.2004', '1234567', )


def verify(request):
    pass
