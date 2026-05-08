from django.db import models

class TelegramUser(models.Model):
    user_id = models.BigIntegerField(unique=True, primary_key=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"@{self.username}" if self.username else str(self.user_id)

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