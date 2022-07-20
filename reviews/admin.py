from ckeditor_uploader.widgets import CKEditorUploadingWidget
from django import forms
from django.contrib import admin
from .models import *


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    content = forms.CharField(widget=CKEditorUploadingWidget())
    fields = ('author_id', 'content', 'pub_date')
    list_display = ('author_id', 'content', 'pub_date')
    list_display_links = ('author_id', 'content', 'pub_date')
    list_filter = ('author_id', 'content', 'pub_date')
    # readonly_fields = ('author_id', 'content', 'pub_date')
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8
    search_fields = ['author_id', 'content', 'pub_date']