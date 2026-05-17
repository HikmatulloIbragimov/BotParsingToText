from django.db import models
from django.utils import timezone
import datetime

class TelegramUser(models.Model):
    user_id = models.BigIntegerField(unique=True, primary_key=True, verbose_name="Telegram ID")
    username = models.CharField(max_length=255, null=True, blank=True, verbose_name="Юзернейм")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")
    
    # --- БАЛАНС И ПОПЫТКИ ---
    balance = models.IntegerField(default=0, verbose_name="Баланс (сум)")
    has_free_attempt = models.BooleanField(default=True, verbose_name="Есть бесплатная попытка") # Оставляем для старого кода
    free_attempts_left = models.IntegerField(default=1, verbose_name="Оставшиеся бесплатные попытки") # Наша новая номерация

    # --- ПРЕМИУМ СТАТУС ---
    is_premium_bool = models.BooleanField(default=False, db_column="is_premium", verbose_name="Премиум статус (устарело)")
    premium_until = models.DateTimeField(null=True, blank=True, verbose_name="Премиум активен до")

    @property
    def is_premium(self):
        """
        Умная проверка премиума: 
        Если включен старый флаг ИЛИ дата premium_until еще не прошла — значит у юзера PRO-доступ.
        """
        if self.is_premium_bool:
            return True
        if self.premium_until and self.premium_until > timezone.now():
            return True
        return False

    @property
    def premium_days_left(self):
        """Считает, сколько дней подписки осталось"""
        if self.premium_until and self.premium_until > timezone.now():
            delta = self.premium_until - timezone.now()
            return delta.days + 1  # Округляем в большую сторону, чтобы если осталось 12 часов, писало 1 день
        if self.is_premium_bool:
            return 999 # Если ты руками в админке включил старый флаг — это вечный премиум
        return 0

    def __str__(self):
        return f"@{self.username}" if self.username else str(self.user_id)

    class Meta:
        verbose_name = "Пользователь Telegram"
        verbose_name_plural = "Пользователи Telegram"

class TestPack(models.Model):
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='packs')
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Question(models.Model):
    pack = models.ForeignKey(TestPack, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    options = models.JSONField()  # Будем хранить список ["Ответ 1", "Ответ 2"]
    correct_option_id = models.IntegerField()

    def __str__(self):
        return self.text[:50]

class TestSession(models.Model):
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE)
    pack = models.ForeignKey(TestPack, on_delete=models.CASCADE)
    current_question_index = models.IntegerField(default=0) # На каком мы номере
    correct_answers = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.pack.name}"