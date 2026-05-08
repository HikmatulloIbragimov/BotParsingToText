from django.contrib import admin
from .models import TelegramUser, TestPack, Question

admin.site.register(TelegramUser)
admin.site.register(TestPack)
admin.site.register(Question)