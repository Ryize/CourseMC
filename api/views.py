import random
from urllib.parse import unquote

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from Course.models import (LearnGroup, Schedule, Student, StudentQuestion,
                           ClassesTimetable, ApplicationsForTraining,
                           LessonSolution, LessonSolutionFile,
                           LessonSolutionSubmission)
from Course.services import lesson_solution_file_response
from billing.models import Absences, InformationPayments
from codereview.models import ProjectForReview
from billing.views import get_cost_classes

from .serializers import (LearnGroupListSerializer, ScheduleListSerializer,
                          StudentListSerializer, StudentQuestionListSerializer,
                          ClassesTimetableListSerializer,
                          ApplicationsForTrainingSerializer,
                          PaymentAmountSerializer, MissingSerializer,
                          ProjectForReviewSerializer,
                          InterviewQuestionCategorySerializer, InterviewQuestionSerializer,
                          QuestionAnswerSerializer,
                          BotLessonSolutionSerializer,
                          BotLessonSolutionReviewSerializer)
from interview.models import InterviewQuestionCategory, InterviewQuestion

from ai_assistant.models import QuestionAnswer

from ai_assistant.interview import InterviewThisOutOfOpenAI

from .permissions import HasCourseMCBotToken


def bot_lesson_solution_queryset():
    """Возвращает решения с данными их последней отправки без N+1 запросов."""
    latest_submission = (
        LessonSolutionSubmission.objects
        .filter(solution_id=OuterRef('pk'))
        .order_by('-attempt_number', '-pk')
    )
    return (
        LessonSolution.objects
        .select_related(
            'student__user',
            'student__groups__teacher__user',
            'schedule__direction',
        )
        .prefetch_related('files')
        .annotate(
            latest_submission_id=Subquery(latest_submission.values('pk')[:1]),
            latest_attempt_number=Subquery(
                latest_submission.values('attempt_number')[:1],
            ),
            latest_submitted_at=Subquery(
                latest_submission.values('submitted_at')[:1],
            ),
        )
    )


class ScheduleViewSet(APIView):
    """
    Вывод всех расписаний
    """

    def get(self, request):
        """
        Возвращает список всех расписаний.
        """
        schedules = Schedule.objects.all()
        serializer = ScheduleListSerializer(schedules, many=True)
        return Response(serializer.data)

    def post(self, request):
        """
        Создаёт новое расписание.

        Возвращает 201 в случае успеха, 401 при неудаче.
        """
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
        """
        Возвращает список расписаний для переданного пользователя.
        """
        username = request.data['username']
        student = Student.objects.for_username(username)
        if not student:
            return Response({'error': 'Student not found'}, status=404)
        group = student.groups
        schedule = Schedule.objects.filter(group=group).values()
        return Response(schedule)


class StudentViewSet(APIView):
    """
    Вывод всех учеников
    """

    permission_classes = (IsAdminUser,)

    def get(self, request):
        """
        Возвращает список всех учеников
        """
        schedules = Student.objects.all()
        serializer = StudentListSerializer(schedules, many=True)
        return Response(serializer.data)

    def post(self, request):
        """
        Создает нового ученика.

        Возвращает 201 в случае успеха, 401 при неудаче.
        """
        serializer = StudentListSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(status=201)
        return Response(status=400)


class BotStudentAuthenticationView(APIView):
    """Проверяет данные ученика, не раскрывая список аккаунтов и пароли."""

    authentication_classes = ()
    permission_classes = (HasCourseMCBotToken,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'bot_auth'

    def post(self, request):
        login = str(request.data.get('login', '')).strip()
        password = str(request.data.get('password', ''))
        if not login or not password:
            return Response(
                {'authenticated': False},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = authenticate(request=request, username=login, password=password)
        student = Student.objects.for_user(user) if user else None
        if not student:
            return Response(
                {'authenticated': False},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response({
            'authenticated': True,
            'username': user.username,
            'group_id': student.groups_id,
        })


class BotGroupStudentsView(APIView):
    """Возвращает боту логины учеников конкретной действующей группы."""

    authentication_classes = ()
    permission_classes = (HasCourseMCBotToken,)

    def get(self, request, group_id):
        usernames = list(
            Student.objects
            .filter(groups_id=group_id, is_learned=True)
            .order_by('user__username', 'pk')
            .values_list('user__username', flat=True)
        )
        return Response({'usernames': usernames})


class BotLessonSolutionListView(APIView):
    """Очередь последних отправок решений для уведомлений в боте."""

    authentication_classes = ()
    permission_classes = (HasCourseMCBotToken,)

    def get(self, request):
        try:
            after = int(request.query_params.get('after', 0))
            limit = int(request.query_params.get('limit', 50))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Параметры after и limit должны быть целыми числами.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if after < 0 or not 1 <= limit <= 100:
            return Response(
                {'detail': 'after не может быть меньше 0, limit — от 1 до 100.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        solutions = bot_lesson_solution_queryset().filter(
            status=LessonSolution.Status.PENDING,
            latest_submission_id__gt=after,
        )
        teacher_username = request.query_params.get('teacher_username', '').strip()
        if teacher_username:
            teacher = User.objects.filter(
                username=teacher_username,
                is_active=True,
                is_staff=True,
            ).first()
            if teacher is None:
                return Response(
                    {'detail': 'Активный преподаватель с таким логином не найден.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if not teacher.is_superuser:
                solutions = solutions.filter(
                    student__groups__teacher__user=teacher,
                )

        solutions = list(solutions.order_by('latest_submission_id')[:limit])
        serializer = BotLessonSolutionSerializer(
            solutions,
            many=True,
            context={'request': request},
        )
        next_cursor = after
        if solutions:
            next_cursor = solutions[-1].latest_submission_id
        return Response({
            'count': len(solutions),
            'next_cursor': next_cursor,
            'results': serializer.data,
        })


class BotLessonSolutionFileView(APIView):
    """Скачивание закрытого файла решения по токену доверенного бота."""

    authentication_classes = ()
    permission_classes = (HasCourseMCBotToken,)

    def get(self, request, file_id):
        solution_file = get_object_or_404(
            LessonSolutionFile.objects.select_related('solution'),
            pk=file_id,
        )
        return lesson_solution_file_response(solution_file)


class BotLessonSolutionReviewView(APIView):
    """Меняет статус и комментарий решения от имени преподавателя."""

    authentication_classes = ()
    permission_classes = (HasCourseMCBotToken,)

    def patch(self, request, solution_id):
        serializer = BotLessonSolutionReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reviewer = User.objects.filter(
            username=serializer.validated_data['reviewer_username'],
            is_active=True,
            is_staff=True,
        ).first()
        if reviewer is None:
            return Response(
                {'detail': 'Активный преподаватель с таким логином не найден.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        with transaction.atomic():
            solution = get_object_or_404(
                bot_lesson_solution_queryset().select_for_update(),
                pk=solution_id,
            )
            group_teacher_id = solution.student.groups.teacher.user_id
            if not reviewer.is_superuser and reviewer.pk != group_teacher_id:
                return Response(
                    {'detail': 'Преподаватель не ведёт группу этого ученика.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

            new_status = serializer.validated_data['status']
            solution.status = new_status
            solution.teacher_comment = serializer.validated_data.get(
                'teacher_comment',
                '',
            )
            if new_status == LessonSolution.Status.PENDING:
                solution.reviewed_by = None
                solution.reviewed_at = None
            else:
                solution.reviewed_by = reviewer
                solution.reviewed_at = timezone.now()
            solution.save(update_fields=(
                'status',
                'teacher_comment',
                'reviewed_by',
                'reviewed_at',
                'updated_at',
            ))

        return Response({
            'id': solution.pk,
            'status': solution.status,
            'status_display': solution.get_status_display(),
            'teacher_comment': solution.teacher_comment,
            'reviewer_username': (
                solution.reviewed_by.username if solution.reviewed_by else None
            ),
            'reviewed_at': solution.reviewed_at,
        })


class BotLessonSolutionDocsView(APIView):
    """Краткая документация интеграции проверки решений с ботом."""

    authentication_classes = ()
    permission_classes = (HasCourseMCBotToken,)

    def get(self, request):
        base_url = request.build_absolute_uri('/api/v1/bot/lesson-solutions/')
        return Response({
            'authentication': {
                'header': 'X-CourseMC-Bot-Token',
                'note': 'Один секрет задаётся в окружении сайта и бота.',
            },
            'workflow': [
                'Запросите очередь GET с сохранённым after.',
                'Скачайте файлы по download_url с тем же заголовком.',
                'Отправьте администраторам уведомления и файлы.',
                'Только после успешной отправки сохраните next_cursor.',
                'После проверки отправьте PATCH со статусом и комментарием.',
            ],
            'endpoints': {
                'queue': f'{base_url}?after=0&limit=50',
                'queue_for_teacher': (
                    f'{base_url}?after=0&teacher_username=teacher'
                ),
                'download': f'{base_url}files/<file_id>/',
                'review': f'{base_url}<solution_id>/review/',
            },
            'review_body': {
                'reviewer_username': 'teacher',
                'status': LessonSolution.Status.NEEDS_REVISION,
                'teacher_comment': 'Исправьте обработку пустого списка.',
            },
            'statuses': dict(LessonSolution.Status.choices),
            'full_documentation': 'docs/BOT_LESSON_SOLUTIONS_API.md',
        })


class LearnGroupViewSet(APIView):
    """
    Вывод всех групп
    """

    def get(self, request):
        """
        Возвращает список всех групп.
        """
        groups = LearnGroup.objects.all()
        serializer = LearnGroupListSerializer(groups, many=True)
        return Response(serializer.data)

    def post(self, request):
        """
        Создаёт новую группу.

        Возвращает 201 в случае успеха, 401 при неудаче.
        """
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
        """
        Возвращает список всех вопросов учеников. Сортирует по дате,
        сначала новые.
        """
        student_question = StudentQuestion.objects.all().order_by(
            '-created_at'
        )
        serializer = StudentQuestionListSerializer(student_question, many=True)
        return Response(serializer.data)


class ClassesTimetableView(APIView):
    """
    Вывод времени занятий.
    """

    def get(self, request, user_name: str):
        """
        Возвращает список со временем занятий для определённого учителя
        """
        class_timetable = ClassesTimetable.objects.filter(
            group__teacher__user__username=user_name,
        ).all()
        serializer = ClassesTimetableListSerializer(class_timetable, many=True)
        return Response(serializer.data)


class ApplicationsForTrainingView(APIView):
    """
    Вывод всех заявок на обучение.
    """

    def get(self, request):
        """
        Возвращает список всех нерассмотренных заявок на обучение
        """
        app_training = ApplicationsForTraining.objects.filter(
            descry=False
        ).all()
        serializer = ApplicationsForTrainingSerializer(app_training, many=True)
        return Response(serializer.data)


class PaymentAmountView(GenericAPIView):
    """
    Позволяет получить кол-во неоплаченных уроков и сумму оплаты.
    """

    def get_serializer(self, *args, **kwargs):
        return PaymentAmountSerializer(*args, **kwargs)

    def get(self, request, username, *args, **kwargs):
        """
        Возвращает сумму оплаты.
        """
        # Если переданное имя пользователя на русском, то она преобразуется в
        # специальный формат. Тут этот формат приводится в обычному utf-8
        if username.find('%') == 0:
            username = unquote(username.upper(), 'utf-8')
        user = User.objects.filter(username=username).first()
        if not user:
            return JsonResponse({'error': 'User not found'})
        if not Student.objects.for_user(user):
            return JsonResponse({'error': 'Student not found'})
        amount = get_cost_classes(user)
        return JsonResponse(
            {
                'amount': amount,
            }
        )

    def post(self, request, username, *args, **kwargs):
        """
        Создает платёж для указанного пользователя
        """
        if username.find('%') == 0:
            username = unquote(username.upper(), 'utf-8')
        user = User.objects.filter(username=username).first()
        if not user:
            return JsonResponse({'error': 'User not found'})
        student = Student.objects.for_user(user)
        if not student:
            return JsonResponse({'error': 'Student not found'})
        amount = get_cost_classes(user)
        InformationPayments.objects.create(user=student, amount=amount)
        return Response(status=201)


class MissingView(GenericAPIView):
    """
    Позволяет добавить пропуск.
    """

    def get_serializer(self, *args, **kwargs):
        return MissingSerializer(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Добавляет пропуск для переданного ученика.

        Возвращает 201 в случае успеха. Статус 401 и описание проблемы
        при неудаче.
        """
        username = request.POST.get('username')
        date = request.POST.get('date')
        serializer = MissingSerializer(data=request.data)
        if not serializer.is_valid():
            return JsonResponse(
                {
                    'status': False,
                    'description': 'Incorrect data'
                },
                status=401
            )
        student = Student.objects.for_username(username)
        if not student:
            return JsonResponse(
                {
                    'status': False,
                    'description': 'Student not found'
                }
            )
        Absences.objects.create(user=student, date=date)
        return JsonResponse({'status': True}, status=201)


class ClassesTimetableGingerView(GenericAPIView):
    """
    Кол-во занятия за месяц (4 недели)
    """

    def get(self, request, group: int):
        """
        Возвращает в виде JsonResponse кол-во занятия за месяц (4 недели)
        """
        amount = ClassesTimetable.objects.filter(group=group).count()
        return JsonResponse({'amount': amount * 4})


class ProjectForReviewView(GenericAPIView):
    """
    Список не проведённых ревью.
    """

    def get(self, request):
        """
        Возвращает в виде JsonResponse список ревью
        """
        reviews = ProjectForReview.objects.filter(status=False).all()
        serialize = ProjectForReviewSerializer(reviews, many=True)
        return JsonResponse({'reviews': serialize.data})


class InterviewQuestionCategoryViewSet(APIView):
    """
    Список категорий вопросов.
    """

    def get(self, request):
        """
        Возвращает в виде Response список всех категорий
        """
        categories = InterviewQuestionCategory.objects.all()
        serializer = InterviewQuestionCategorySerializer(categories, many=True)
        return Response({'categories': serializer.data})


class InterviewQuestionViewSet(APIView):
    """
    Список всех вопросов.
    """

    def get(self, request):
        """
        Возвращает в виде Response список всех вопросов в зависимости от запроса
        """

        category_title = request.query_params.get('category')
        amount = request.query_params.get('amount')
        level = request.query_params.get('level')

        if not category_title or not amount:
            return Response({"error": "Отсутствует параметр «категория» или «количество»"},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = int(amount)
            if not (1 <= amount <= 50):
                return Response({"error": "'Количество' должно быть от 1 до 50"},
                                status=status.HTTP_400_BAD_REQUEST)
        except ValueError:
            return Response({"error": "'Количество' должен быть числом"},
                            status=status.HTTP_400_BAD_REQUEST)

        category = get_object_or_404(InterviewQuestionCategory, title=category_title)

        questions = InterviewQuestion.objects.filter(theme=category)

        if category_title.lower() == 'python' and level:
            try:
                min_level, max_level = map(int, level.split('-'))

                # Проверка диапазона
                if not (1 <= min_level <= 10 and 1 <= max_level <= 10 and min_level <= max_level):
                    return Response({"error": "'Сложность' должен быть в диапазоне 1 до 10"},
                                    status=status.HTTP_400_BAD_REQUEST)
                questions = questions.filter(complexity__range=(min_level, max_level))
            except ValueError:
                return Response({"error": "'Сложность' должен быть в формате «мин-макс» с допустимыми целыми числами"},
                                status=status.HTTP_400_BAD_REQUEST)

        questions = questions.order_by('?')[:amount]

        serializer = InterviewQuestionSerializer(questions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
        
class ClassesTimetableWeekdayView(GenericAPIView):
    """
    Занятия в указанный день недели
    """

    def get(self, request, weekday: str):
        """
        Возвращает в виде JsonResponse список занятий в указанный день недели.
        Формат дня недели: Понедельник, Вторник, Среда и т.д.
        """
        if weekday.find('%') == 0:
            weekday = unquote(weekday, 'utf-8')
        classes_timetable = ClassesTimetable.objects.filter(
            weekday=weekday
        ).all()
        serialize = ClassesTimetableListSerializer(
            classes_timetable, many=True
        )
        return JsonResponse({'timetables': serialize.data})
        
        

class GetQuestionView(APIView):
    """
    Представление для получения случайного вопроса
    """
    def get(self, request):
        """
        Обрабатывает GET запрос для получения случайного вопроса
        """
        #
        question = QuestionAnswer.objects.order_by('?').first()
        if question:
            serializer = QuestionAnswerSerializer(question)
            return Response(serializer.data)  # Возвращаем сериализованные данные
        else:
            return Response({"error": "Нет доступных вопросов"}, status=status.HTTP_404_NOT_FOUND)


# Представление для проверки ответа пользователя
class CheckAnswerView(APIView):
    """
    Представление для проверки ответа пользователя.
    """
    def get(self, request):
        """
        Обрабатывает GET запрос для проверки ответа пользователя.
        """
        # Получаем ответ пользователя и текст вопроса из запроса
        user_answer = request.query_params.get('answer')
        question_text = request.query_params.get('question')

        if user_answer.find('%') == 0:
           user_answer = unquote(user_answer.upper(), 'utf-8')
        if question_text.find('%') == 0:
            question_text = unquote(question_text.upper(), 'utf-8')
        # Как разбить список
        try:
            # Создаем объект InterviewThisOutOfOpenAI для оценки ответа
            interview = InterviewThisOutOfOpenAI(
                question=question_text,
                user_question=user_answer
            )

            # Получаем оценку от OpenAI API
            score = interview.get_response()

            return Response({'score': score})  # Возвращаем оценку ответа пользователя

        except QuestionAnswer.DoesNotExist:
            return Response({'error': 'Вопрос не найден'}, status=status.HTTP_404_NOT_FOUND)
