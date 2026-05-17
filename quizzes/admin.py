from django.contrib import admin
from .models import TelegramUser, TestPack, Question

admin.site.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    # Разворачиваем красивую таблицу со всеми цифрами и знаками!
    list_display = (
        'user_id',             # Показывает числовой Telegram ID
        'get_username_display',# Красивый юзернейм со знаком @
        'free_attempts_left',  # Количество бонусных попыток (цифры)
        'premium_until',       # Дата, до которой выдан премиум
    )
    
    # Добавляем фильтры справа, чтобы можно было быстро отсеять премиум-пользователей
    list_filter = ('premium_until', 'free_attempts_left')
    
    # Добавляем строку поиска. Теперь в админке можно искать юзера по ID или юзернейму!
    search_fields = ('user_id', 'username')
    
    # Кастомный метод, чтобы в таблице не ломались пустые юзернеймы
    @admin.display(description="Telegram Юзернейм")
    def get_username_display(self, obj):
        if obj.username:
            return f"@{obj.username}"
        return f"🆔 ID: {obj.user_id} (Нет юзернейма)"
admin.site.register(TestPack)
admin.site.register(Question)