import random
from urllib.parse import unquote

from django.contrib.auth.models import User
from django.http import JsonResponse
from rest_framework import status
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from Course.models import (LearnGroup, Schedule, Student, StudentQuestion,
                           ClassesTimetable, ApplicationsForTraining)
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
                          QuestionAnswerSerializer)
from interview.models import InterviewQuestionCategory, InterviewQuestion

from ai_assistant.models import QuestionAnswer

from ai_assistant.interview import InterviewThisOutOfOpenAI


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
        student = Student.objects.get(name=username)
        group = student.groups
        schedule = Schedule.objects.filter(group=group).values()
        return Response(schedule)


class StudentViewSet(APIView):
    """
    Вывод всех учеников
    """

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
            teacher__username=user_name,
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
        student = Student.objects.filter(name=username).first()
        user = User.objects.filter(username=username).first()
        if not user:
            return JsonResponse({'error': 'User not found'})
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
        student = Student.objects.filter(name=username).first()
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