from django.contrib import admin
from .models import Quiz, Question, PassedPolls, Rating

admin.site.register(Quiz)
admin.site.register(Question)
admin.site.register(PassedPolls)
admin.site.register(Rating)
