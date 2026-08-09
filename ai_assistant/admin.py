from django.contrib import admin

from ai_assistant.models import QuestionAnswer


@admin.register(QuestionAnswer)
class QuestionAnswerAdmin(admin.ModelAdmin):
    list_display = ('question', 'answer')
    list_display_links = ('question',)
    search_fields = ('question', 'answer')
