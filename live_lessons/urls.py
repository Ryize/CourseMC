from django.urls import path

from . import classroom_views, views


urlpatterns = [
    path('', views.lesson_list, name='live_lesson_list'),
    path('new/', views.lesson_create, name='live_lesson_create'),
    path('quality-lab/', views.quality_lab, name='live_lesson_quality_lab'),
    path('<uuid:public_id>/', views.lesson_detail, name='live_lesson_detail'),
    path('<uuid:public_id>/reschedule/', views.lesson_reschedule, name='live_lesson_reschedule'),
    path('<uuid:public_id>/chat/archive/', views.lesson_save_chat_archive, name='live_lesson_save_chat_archive'),
    path('chat/archives/<int:archive_id>/', views.lesson_chat_archive_view,
         name='live_lesson_chat_archive_view'),
    path('chat/archives/<int:archive_id>/download/', views.lesson_chat_archive_download,
         name='live_lesson_chat_archive_download'),
    path('chat/archives/<int:archive_id>/files/<int:attachment_id>/',
         views.lesson_chat_archive_attachment, name='live_lesson_archive_attachment'),
    path('<uuid:public_id>/join-token/', views.lesson_join_token, name='live_lesson_join_token'),
    path('<uuid:public_id>/state/', views.lesson_state, name='live_lesson_state'),
    path('<uuid:public_id>/classroom/', classroom_views.classroom_state, name='live_lesson_classroom'),
    path('<uuid:public_id>/classroom/action/', classroom_views.classroom_action, name='live_lesson_classroom_action'),
    path('<uuid:public_id>/classroom/manage/', classroom_views.classroom_manage, name='live_lesson_classroom_manage'),
    path('<uuid:public_id>/moderate/', views.lesson_moderate_participant, name='live_lesson_moderate'),
    path('<uuid:public_id>/chat/messages/', views.lesson_chat_messages, name='live_lesson_chat_messages'),
    path('<uuid:public_id>/chat/send/', views.lesson_chat_send, name='live_lesson_chat_send'),
    path('<uuid:public_id>/chat/files/<int:attachment_id>/', views.lesson_chat_attachment,
         name='live_lesson_chat_attachment'),
    path('<uuid:public_id>/<str:action>/', views.lesson_change_status, name='live_lesson_change_status'),
]
