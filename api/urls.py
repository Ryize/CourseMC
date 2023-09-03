from django.urls import path

from .views import (LearnGroupViewSet, ScheduleGet, ScheduleViewSet,
                    StudentQuestionView, StudentViewSet, ClassesTimetableView,
                    ApplicationsForTrainingView, PaymentAmountView, MissingView, ClassesTimetableGingerView)

urlpatterns = [
    path("schedule/<str:code>/", ScheduleViewSet.as_view()),
    path("schedule/get_by_username/<str:code>/", ScheduleGet.as_view()),
    path("student/<str:code>/", StudentViewSet.as_view()),
    path("groups/<str:code>/", LearnGroupViewSet.as_view()),
    path("student_question/<str:code>/", StudentQuestionView.as_view()),
    path("classes_timetable/<str:user_name>/<str:code>/", ClassesTimetableView.as_view()),
    path("classes_timetable_ginger/<int:group>/<str:code>/", ClassesTimetableGingerView.as_view()),
    path("app_training/<str:code>/", ApplicationsForTrainingView.as_view()),
    path("payment/<int:student_id>/<str:code>/", PaymentAmountView.as_view()),
    path('missing/<str:code>/', MissingView.as_view()),
]
