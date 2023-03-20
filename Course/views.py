"""
View для приложения Course.

Обрабатывает главную страницу сайта, расписания.
"""
import datetime
import os

from django.contrib.auth import get_user
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import ListView
from django.views.generic.edit import FormView

from Course.doc import docx_worker, save_report
from Course.forms import StudentForm
from Course.models import LearnGroup, Schedule, Student, StudentQuestion, ApplicationsForTraining
from Course.report import get_content_disposition, get_content_type
from billing.models import Absences
from reviews.models import Review

STATUS_OK = 200
STATUS_FORBIDDEN = 403
STATUS_PRECONDITION_FAILED = 412
LESSON_DURATION = 1.5


class StudentRecordView(FormView):
    """
    View для авторизации в системе.

    Авторизовываются обычные юзеры и персонал.
    Для шаблона используется форма StudentForm.
    """

    template_name = 'Course/index.html'
    form_class = StudentForm
    login_url = '/login/'

    def form_valid(self, form: StudentForm):
        """
        Если форма валидна.

        Сохраняем и создаём ещё один класс User.
        Класс User нужен для авторизации в системе,
        тк модель Student не используется по умолчанию.

        Args:
            form: форма авторизации
                уже хранит все параметры, получение через form.cleaned_data
                (Course.forms.StudentForm).

        Returns:
            JsonResponse: Json ответ со статусом успеха.
        """
        ip = self.request.META.get('REMOTE_ADDR')
        if ApplicationsForTraining.objects.filter(ip=ip).first():
            response = {
                'success': False,
                'error_message': 'Вы уже заполняли форму!',
            }
            return JsonResponse(response)
        student = form.save()
        name = form.cleaned_data['name']
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        try:
            user = User.objects.create_user(name, email, password)
        except IntegrityError:
            response = {
                'success': False,
                'error_message': 'Пользователь с таким именем уже существует!',
            }
            return JsonResponse(response)
        ApplicationsForTraining.objects.create(student=student, ip=ip)
        user.save()
        response = {
            'success': True,
        }
        return JsonResponse(response)

    def form_invalid(self, form: StudentForm):
        """
        Если форма не валидна.

        Отправляем JsonResponse с уведомлением о
        неверно заполненной форме.

        Args:
            form: форма авторизации (Course.forms.StudentForm).

        Returns:
            JsonResponse: Json ответ со статусом неудачи и пояснением.
        """
        response = {
            'success': False,
            'error_message': 'Форма заполнена не верно!',
        }
        return JsonResponse(response)

    def get_context_data(self, *, object_list=None, **kwargs):
        """
        Добавляем кол-во отзывов.

        Для вывода кол-ва отзывов в шаблоне, передаём параметр reviews_count.

        Args:
            object_list: стандартный параметр, не используется.
            kwargs: передаётся через super() в get_context_data

        Returns:
            dict: словарь с объектами моделей.
        """
        context = super().get_context_data(**kwargs)
        ip = self.request.META.get('REMOTE_ADDR')
        context['reviews_count'] = Review.objects.all().count()
        context['can_send_train'] = False
        return context


class TimetableView(LoginRequiredMixin, ListView):
    """
    Выводит расписание курса на сайте.

    Расписания выводятся по модели Schedule, по 16 на странице.
    """

    model = Schedule
    template_name = 'Course/timetable.html'
    context_object_name = 'schedules'
    paginate_by = 16
    queryset = Schedule.objects.all()

    def get_queryset(self):
        """
        Если форма валидна.

        Фильтруем расписания по типу урока, теме.

        Returns:
            Schedule: Отфильтрованный QuerySet.
        """
        group = Student.objects.filter(name=self.request.user.username).first().groups

        d1 = datetime.datetime.now()
        d2 = group.created_at

        months = self._months(d1, d2)
        if months <= 0:
            months = 1
        schedules = Schedule.objects.all()[:months*22:-1]

        theme = self._get_param('theme')
        if theme:
            schedules = schedules.filter(theme__icontains=theme)
        if self._get_param('lesson_type'):
            schedules = schedules.filter(
                lesson_type__icontains=self._get_param('lesson_type'),
            )
        return schedules

    def get_context_data(self, *, object_list=None, **kwargs):
        """
        Добавляем кол-во отзывов, расписание.

        Для вывода кол-ва отзывов в шаблоне, передаём параметр reviews_count.
        Передаём список расписаний, отфильтрованных по дате.

        Args:
            object_list: стандартный параметр, не используется.
            kwargs: передаётся через super() в get_context_data

        Returns:
            dict: словарь с объектами моделей.
        """
        context = super().get_context_data(**kwargs)
        context['reviews_count'] = Review.objects.all().count()
        context['create_report'] = Schedule.objects.all()
        return context

    def dispatch(self, request, *args, **kwargs):
        """
        Проверяем права на заход.

        Если пользователь не студент или не учиться, перекидываем на home.

        Args:
            request: объект HTTP запроса.
            args: передаётся через super() в dispatch
            kwargs: передаётся через super() в dispatch

        Returns:
            bool: можно/нет зайти на страницу (через родительский dispatch).
        """
        student = Student.objects.filter(
            name=get_user(self.request).username, is_learned=True,
        ).first()
        if not student:
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def _get_param(self, name: str) -> str:
        """
        Проверяем права на заход.

        Если пользователь не студент или не учиться, перекидываем на home.

        Args:
            name: название параметра, который необходимо получить.

        Returns:
            str: значение из request.GET.
        """
        return self.request.GET.get(name)

    @staticmethod
    def _months(d1, d2):
        return d1.month - d2.month + 12 * (d1.year - d2.year)


@login_required
def download_report(request):
    """
    Проверяем права на заход.

    Если пользователь не студент или не учиться, перекидываем на home.

    Args:
        request: параметр HTTP запроса, получается автоматически.
        group_id: id группы, отчёт которой надо получить.

    Returns:
        HttpResponse: содержит файл отчёта, загрузка начнётся автоматически.
    """
    schedules = Schedule.objects.all()
    group = Student.objects.filter(name=request.user.username).first().groups
    number_dash_on_line = 64
    result_data = """Отчёт о группе {group_title}
{approximate_string_length}
Количество расписаний: {schedule_count}
Ключевых уроков: {schedules_primary}
Новых тем: {schedules_new_theme}
Практики: {practice_schedules}
Участников ({students_count}):
    """.format(
        group_title=group.title,
        approximate_string_length='-' * number_dash_on_line,
        schedule_count=schedules.count(),
        students_count=group.students.count(),
        schedules_primary=schedules.filter(
            lesson_type='Ключевой урок',
        ).count(),
        schedules_new_theme=schedules.filter(
            lesson_type='Новая тема',
        ).count(),
        practice_schedules=schedules.filter(
            lesson_type='Практика',
        ).count(),
    )
    for student in group.students.all():
        result_data += """
    Имя: {student_name}
    Контакты: {student_contact}
    Пропущенных урока: {student_absents}
        """.format(
            student_name=student.name,
            student_contact=student.contact or 'Не указаны!',
            student_absents=Absences.objects.filter(user=student).count(),
        )
    result_data += '\n\nЧасов обучения: {lesson_hour}'.format(
        lesson_hour=schedules.count() * LESSON_DURATION,
    )

    return save_report(result_data)


def get_training_program(request):
    """
    Для получения программы курса.

    Выводит программу курса группы в виде docx документа.
    Для работы с docx используется модуль docx.

    Args:
        request: стандартный параметр, не используется.

    Returns:
        HttpResponse: с файлом (скачивается автоматически).
    """
    schedules = Schedule.objects.all()
    doc = docx_worker(schedules)

    if not os.path.exists('programCoursePython'):
        os.mkdir('programCoursePython')

    response = HttpResponse(
        content_type=get_content_type(),
    )
    response['Content-Disposition'] = get_content_disposition()
    doc.save(response)
    return response


@login_required
def ask_question(request):
    """
    Задать анонимный вопрос.

    Сохраняет вопрос студента в модель StudentQuestion.

    Args:
        request: стандартный параметр.

    Returns:
        JsonResponse: статус, сохранён/нет вопрос.
    """
    question = request.GET.get('question')
    response = {
        'is_taken': False,
    }
    if not question:
        return JsonResponse(response, status=STATUS_PRECONDITION_FAILED)
    student = Student.objects.filter(name=request.user.username).first()
    if not student:
        return JsonResponse(response, status=STATUS_FORBIDDEN)
    group = student.groups
    student_question = StudentQuestion(group=group, question=question)
    student_question.save()
    response['is_taken'] = True
    return JsonResponse(response, status=STATUS_OK)


@login_required
def get_filter_data(request):
    """
    Пасхалка.

    Выводит нашедшему подсказку надпись.

    Args:
        request: стандартный параметр.

    Returns:
        JsonResponse: статус, текст надписи.
    """
    result_dict = {
        'answer': 'Ты нашёл пасхалку, красавчик!!!',
        'code': 'OK',
    }
    return JsonResponse(result_dict, status=STATUS_OK)


@login_required
def create_group(request):
    """
    Для создания новой группы.

    Создаёт новую группу и заполняет расписаниями группы Вояджер.
    У созданных расписаний параметр is_display равен False.

    Args:
        request: стандартный параметр.

    Returns:
        redirect/render: перенаправляет при успехе/отсутствии прав, выдаёт
        страницу при GET запросе.
    """
    if not request.user.is_staff:
        return redirect('/')
    if request.method == 'GET':
        context = {
            'reviews_count': Review.objects.all().count(),
        }
        return render(request, 'Course/groups.html', context)
    title = request.POST.get('title')
    new_group = LearnGroup(title=title)
    new_group.save()
    all_plan_lessons = Schedule.objects.filter(
        group=LearnGroup.objects.get(id=3),
    ).order_by('weekday')
    for plan in all_plan_lessons:
        Schedule.objects.create(
            group=new_group,
            theme=plan.theme,
            weekday=plan.weekday,
            time_lesson=plan.time_lesson,
            lesson_materials=plan.lesson_materials,
            is_display=False,
        )
    return redirect('/')
