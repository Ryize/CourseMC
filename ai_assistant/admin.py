from django.contrib import admin
from unfold.admin import ModelAdmin

from ai_assistant.models import QuestionAnswer


@admin.register(QuestionAnswer)
class QuestionAnswerAdmin(ModelAdmin):
    list_display = ('question', 'answer')
    list_display_links = ('question',)
    search_fields = ('question', 'answer')
