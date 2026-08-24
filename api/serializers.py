from rest_framework import serializers
from rest_framework.reverse import reverse

from Course.models import (LearnGroup, Schedule, Student, StudentQuestion,
                           ClassesTimetable, ApplicationsForTraining,
                           LessonSolution, LessonSolutionFile)
from codereview.models import ProjectForReview

from interview.models import InterviewQuestion, InterviewQuestionCategory

from ai_assistant.models import QuestionAnswer


class ScheduleListSerializer(serializers.ModelSerializer):
    """ Список всех расписаний. """

    def create(self, validated_data):
        a = validated_data['absent']
        del validated_data['absent']
        schedule = Schedule.objects.creatd(**validated_data)
        schedule.absent.set(a)
        schedule.save()
        return schedule

    class Meta:
        model = Schedule
        fields = '__all__'


class StudentListSerializer(serializers.ModelSerializer):
    """ Список всех студентов. """

    def create(self, validated_data):
        student = Student.objects.create(**validated_data)
        student.save()
        return student

    class Meta:
        model = Student
        fields = (
            'id', 'user', 'contact', 'groups', 'is_learned', 'direction',
            'created_at',
        )


class LearnGroupListSerializer(serializers.ModelSerializer):
    """ Список всех учебных групп. """

    def create(self, validated_data):
        group = LearnGroup.objects.create(**validated_data)
        group.save()
        return group

    class Meta:
        model = LearnGroup
        fields = '__all__'


class StudentQuestionListSerializer(serializers.ModelSerializer):
    """Список всех вопросов учеников."""

    class Meta:
        model = StudentQuestion
        fields = '__all__'


class ClassesTimetableListSerializer(serializers.ModelSerializer):
    """Список всех расписаний занятий. """
    group = serializers.StringRelatedField()

    class Meta:
        model = ClassesTimetable
        fields = ('group', 'weekday', 'time_lesson', 'duration')


class ApplicationsForTrainingSerializer(serializers.ModelSerializer):
    """ Список всех заявок на обучение. """
    name = serializers.ReadOnlyField(source='student.user.username')
    contact = serializers.ReadOnlyField(source='student.contact')
    email = serializers.ReadOnlyField(source='student.user.email')

    class Meta:
        model = ApplicationsForTraining
        fields = '__all__'


class PaymentAmountSerializer(serializers.Serializer):
    """ Сумма оплаты для указанного ученика. """
    student_id = serializers.IntegerField()


class MissingSerializer(serializers.Serializer):
    """ Для пропуска занятий. """
    username = serializers.CharField(max_length=32)
    date = serializers.DateField()


class ProjectForReviewSerializer(serializers.ModelSerializer):
    """ Список проектов отправленных на ревью. """

    class Meta:
        model = ProjectForReview
        fields = '__all__'


class InterviewQuestionCategorySerializer(serializers.ModelSerializer):
    """ Список категорий с 'Твой собес'. """
    class Meta:
        model = InterviewQuestionCategory
        fields = '__all__'


class InterviewQuestionSerializer(serializers.ModelSerializer):
    """ Список всех вопросов с 'Твой собес'. """

    theme = serializers.StringRelatedField()

    class Meta:
        model = InterviewQuestion
        fields = ('id', 'title', 'complexity', 'percent', 'theme')
        

class QuestionAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionAnswer
        fields = ['question', 'answer']


class BotLessonSolutionFileSerializer(serializers.ModelSerializer):
    """Файл решения без раскрытия внутреннего пути хранения."""

    download_url = serializers.SerializerMethodField()
    size = serializers.SerializerMethodField()

    class Meta:
        model = LessonSolutionFile
        fields = ('id', 'original_name', 'size', 'uploaded_at', 'download_url')

    def get_size(self, obj):
        return obj.file.size

    def get_download_url(self, obj):
        request = self.context['request']
        return reverse(
            'bot_lesson_solution_file',
            kwargs={'file_id': obj.pk},
            request=request,
        )


class BotLessonSolutionSerializer(serializers.ModelSerializer):
    """Текущее решение и последняя попытка, подготовленные для бота."""

    submission_id = serializers.IntegerField(source='latest_submission_id')
    attempt_number = serializers.IntegerField(source='latest_attempt_number')
    submitted_at = serializers.DateTimeField(source='latest_submitted_at')
    status_display = serializers.CharField(source='get_status_display')
    student = serializers.SerializerMethodField()
    group = serializers.SerializerMethodField()
    lesson = serializers.SerializerMethodField()
    files = BotLessonSolutionFileSerializer(many=True, read_only=True)

    class Meta:
        model = LessonSolution
        fields = (
            'id', 'submission_id', 'attempt_number', 'student', 'group',
            'lesson', 'status', 'status_display', 'teacher_comment',
            'submitted_at', 'files',
        )

    def get_student(self, obj):
        user = obj.student.user
        return {
            'id': obj.student_id,
            'username': user.username,
            'display_name': user.get_full_name() or user.username,
        }

    def get_group(self, obj):
        return {
            'id': obj.student.groups_id,
            'title': obj.student.groups.title,
        }

    def get_lesson(self, obj):
        return {
            'id': obj.schedule_id,
            'number': obj.schedule.position,
            'title': obj.schedule.theme,
            'direction': obj.schedule.direction.title,
        }


class BotLessonSolutionReviewSerializer(serializers.Serializer):
    """Проверка решения доверенным ботом от имени преподавателя."""

    reviewer_username = serializers.CharField(max_length=150)
    status = serializers.ChoiceField(choices=LessonSolution.Status.choices)
    teacher_comment = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )

    def validate(self, attrs):
        if (
            attrs['status'] == LessonSolution.Status.NEEDS_REVISION
            and not attrs.get('teacher_comment', '')
        ):
            raise serializers.ValidationError({
                'teacher_comment': (
                    'Для статуса «Нужна доработка» добавьте комментарий.'
                ),
            })
        return attrs
