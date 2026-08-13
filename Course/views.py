"""
View для приложения Course.

Обрабатывает главную страницу сайта, расписания.
"""
import os

from django.contrib.auth import get_user
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView
from django.views.generic.edit import FormView

from Course.doc import docx_worker, save_report
from Course.forms import LessonSolutionUploadForm, StudentForm
from Course.models import LearnGroup, Schedule, Student, StudentQuestion, \
    ApplicationsForTraining, AdditionalLessons, LessonSolution, \
    LessonSolutionFile, LessonSolutionSubmission
from Course.report import get_content_disposition, get_content_type
from billing.models import Absences
from reviews.models import Review

STATUS_OK = 200
STATUS_FORBIDDEN = 403
STATUS_PRECONDITION_FAILED = 412
LESSON_DURATION = 1.5


def get_accessible_schedule_ids(student):
    """Возвращает уроки, которые доступны ученику по его курсу и группе."""
    group = student.groups
    months = TimetableView._months(timezone.now(), group.created_at)
    amount_schedules = max(1, months) * 22
    additional_lessons = AdditionalLessons.objects.filter(group=group).first()
    amount_schedules = max(
        0,
        amount_schedules + (additional_lessons.amount if additional_lessons else 0),
    )
    available_schedules = (
        Schedule.objects
        .filter(direction__in=student.direction.all(), is_archived=False)
        .distinct()
        .order_by('direction_id', 'position', 'pk')
    )
    start_index = 45 if group.title == 'Денис Особый' else 0
    return list(
        available_schedules.values_list('pk', flat=True)[start_index:amount_schedules]
    )


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
        name = form.cleaned_data.get('name', '')
        contact = form.cleaned_data.get('contact', '')
        email = form.cleaned_data.get('email', '')
        password = form.cleaned_data.get('password', '')
        if '.' not in contact and '@' not in contact and '/' not in contact:
            response = {
                'success': False,
                'error_message': 'Поле "Контакты" должно содержать ссылку на вашу страницу ВК/Телеграм',
            }
            return JsonResponse(response)
        if email.count('coursemc.ru'):
            response = {
                'success': False,
                'error_message': 'Такой тип email запрещён!',
            }
            return JsonResponse(response)
        try:
            with transaction.atomic():
                user = User.objects.create_user(name, email, password)
                student = form.save(commit=False)
                student.user = user
                student.save()
                form.save_m2m()
                ApplicationsForTraining.objects.create(student=student, ip=ip)
        except IntegrityError:
            response = {
                'success': False,
                'error_message': 'Пользователь с таким именем уже существует!',
            }
            return JsonResponse(response)
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
            'error_message': 'Форма заполнена неверно!',
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
        context['can_send_train'] = bool(
            ApplicationsForTraining.objects.filter(ip=ip).first())
        return context


class TimetableView(LoginRequiredMixin, ListView):
    """
    Выводит расписание курса на сайте.

    Расписания выводятся по модели Schedule, по 20 на странице.
    """

    model = Schedule
    template_name = 'Course/timetable.html'
    context_object_name = 'schedules'
    paginate_by = 20

    def get_template_names(self):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ['Course/includes/schedule_results.html']
        return [self.template_name]

    def get_queryset(self):
        """
        Если форма валидна.

        Фильтруем расписания по типу урока, теме.

        Returns:
            Schedule: Отфильтрованный QuerySet.
        """
        student = Student.objects.for_user(self.request.user)
        accessible_ids = get_accessible_schedule_ids(student)
        self.lesson_numbers = {
            schedule_id: number
            for number, schedule_id in enumerate(accessible_ids, start=1)
        }
        schedules = (
            Schedule.objects
            .filter(pk__in=accessible_ids, is_archived=False)
            .select_related('direction')
            .order_by('-position', '-pk')
        )

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
        student = Student.objects.for_user(self.request.user)
        context['absences'] = Absences.objects.filter(user=student).count()
        page_schedules = list(context['schedules'])
        solutions = LessonSolution.objects.filter(
            student=student,
            schedule__in=page_schedules,
        ).prefetch_related('files')
        solutions_by_schedule = {
            solution.schedule_id: solution for solution in solutions
        }
        for schedule in page_schedules:
            schedule.lesson_number = self.lesson_numbers[schedule.pk]
            schedule.lesson_solution = solutions_by_schedule.get(schedule.pk)
        query_params = self.request.GET.copy()
        query_params.pop('page', None)
        context['pagination_query'] = query_params.urlencode()
        context['schedule_return_url'] = self.request.get_full_path()
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
        student = Student.objects.for_user(get_user(self.request))
        if not student or not student.is_learned:
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


class LessonSolutionUploadView(LoginRequiredMixin, View):
    """Принимает прикреплённые к доступному уроку файлы решения."""

    def post(self, request, schedule_id):
        student = Student.objects.for_user(request.user)
        if not student or not student.is_learned:
            raise PermissionDenied('Отправлять решения могут только учащиеся.')

        if schedule_id not in set(get_accessible_schedule_ids(student)):
            raise PermissionDenied('Этот урок недоступен для отправки решения.')
        schedule = get_object_or_404(Schedule, pk=schedule_id)
        form = LessonSolutionUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, ' '.join(form.errors.get('files', [])))
            return redirect(self._get_redirect_url(request))

        with transaction.atomic():
            solution, created = LessonSolution.objects.get_or_create(
                schedule=schedule,
                student=student,
            )
            if not created:
                solution = LessonSolution.objects.select_for_update().get(
                    pk=solution.pk,
                )
            previous_file_ids = list(
                solution.files.values_list('pk', flat=True),
            )
            solution.status = LessonSolution.Status.PENDING
            solution.teacher_comment = ''
            solution.reviewed_by = None
            solution.reviewed_at = None
            solution.save()
            for uploaded_file in form.cleaned_data['files']:
                LessonSolutionFile.objects.create(
                    solution=solution,
                    file=uploaded_file,
                    original_name=uploaded_file.name,
                )
            if previous_file_ids:
                LessonSolutionFile.objects.filter(pk__in=previous_file_ids).delete()
            last_attempt = (
                solution.submissions.aggregate(last=Max('attempt_number'))['last']
                or 0
            )
            LessonSolutionSubmission.objects.create(
                solution=solution,
                attempt_number=last_attempt + 1,
                submitted_at=timezone.now(),
            )

        if created:
            messages.success(request, 'Решение отправлено на проверку.')
        else:
            messages.success(
                request,
                'Решение обновлено и снова отправлено на проверку.',
            )
        return redirect(self._get_redirect_url(request))

    @staticmethod
    def _get_redirect_url(request):
        next_url = request.POST.get('next')
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return next_url
        return reverse('schedule')


class LessonSolutionFileDownloadView(LoginRequiredMixin, View):
    """Отдаёт файл только его автору либо закреплённому преподавателю."""

    def get(self, request, file_id):
        solution_file = get_object_or_404(
            LessonSolutionFile.objects.select_related(
                'solution__student__groups__teacher',
            ),
            pk=file_id,
        )
        solution = solution_file.solution
        if request.user.is_superuser:
            return self._file_response(solution_file, request.GET.get('view') != '1')

        if request.user.is_staff:
            if solution.student.groups.teacher.user_id != request.user.pk:
                raise PermissionDenied('Вы не ведёте группу этого ученика.')
            return self._file_response(solution_file, request.GET.get('view') != '1')

        student = Student.objects.for_user(request.user)
        if (
            not student
            or not student.is_learned
            or student.pk != solution.student_id
        ):
            raise PermissionDenied('Этот файл недоступен.')
        return self._file_response(solution_file, request.GET.get('view') != '1')

    @staticmethod
    def _file_response(solution_file, as_attachment):
        response = FileResponse(
            solution_file.file.open('rb'),
            as_attachment=as_attachment,
            filename=solution_file.original_name,
        )
        if not as_attachment:
            extension = os.path.splitext(solution_file.original_name)[1].lower()
            if extension in {'.py', '.txt', '.md'}:
                response['Content-Type'] = 'text/plain; charset=utf-8'
            elif extension == '.ipynb':
                response['Content-Type'] = 'application/json; charset=utf-8'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


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
    schedules = Schedule.objects.filter(is_archived=False).order_by(
        'direction_id', 'position', 'pk',
    )
    student = Student.objects.for_user(request.user)
    if not student:
        raise PermissionDenied('Учебный профиль не найден.')
    group = student.groups
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
            student_name=student.user.username,
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
    schedules = Schedule.objects.filter(is_archived=False).order_by(
        'direction_id', 'position', 'pk',
    )
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
    student = Student.objects.for_user(request.user)
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


def life(request):
    return render(request, 'Course/life.html')
