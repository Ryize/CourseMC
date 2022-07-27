from django.forms import ModelForm, forms, TextInput

from .models import Student
import random


class StudentForm(ModelForm):
    class Meta:
        model = Student
        fields = ('name', 'contact', 'email', 'password')

    def __init__(self, *args, **kwargs):
        super(StudentForm, self).__init__(*args, **kwargs)
        self.fields['name'].widget.attrs.update({'class': 'form-control', 'placeholder': "Имя*"})
        self.fields['contact'].widget.attrs.update({'class': 'form-control', 'placeholder': "Ссылка на ВК/Телеграм*"})
        self.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': "Почта*"})
        self.fields['password'].widget.attrs.update(
            {'class': 'form-control', 'placeholder': "Необязательно", 'value': random.randint(1111, 9999)})


class AuthForm(ModelForm):
    class Meta:
        model = Student
        fields = ('name', 'password')

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(AuthForm, self).__init__(*args, **kwargs)
        self.fields['name'].widget.attrs.update({'class': 'form-control', 'placeholder': "Логин*"})
        self.fields['password'].widget.attrs.update({'class': 'form-control', 'placeholder': "Необязательно"})
