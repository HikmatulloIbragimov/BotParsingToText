import os
from aiogram import Router, F
from aiogram.types import CallbackQuery, LabeledPrice, PreCheckoutQuery, Message
from asgiref.sync import sync_to_async
import random
# Проверь этот импорт! Укажи правильный путь к твоей Django-модели
from quizzes.models import TelegramUser 

router = Router()

# Беру токен из переменных окружения. Если локально его нет, подставится временная заглушка
PAYMENT_TOKEN = os.getenv("PAYME_TEST_TOKEN")
# ==========================================
# 1. ВЫСТАВЛЕНИЕ СЧЕТОВ (ИНВОЙСЫ)
# ==========================================

# Срабатывает при нажатии кнопки "Пополнить баланс на 3 000 сум" в твоем профиле
@router.callback_query(F.data == "test_pay_3k")
async def process_pay_3k(callback: CallbackQuery):
    # Удаляем старое сообщение профиля, чтобы не засорять чат
    await callback.message.delete()
    
    # Генерируем случайный код для проверки
    pay_code = random.randint(1000, 9999)
    
    text = (
        f"💳 **ПОПОЛНЕНИЕ КОШЕЛЬКА — 3 000 сум**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Переведи **3 000 сум** на карту:\n"
        f"`986000500343425` (Карта Uzcard/Humo)\n\n"
        f"⚠️ **КРИТИЧЕСКИ ВАЖНО:**\n"
        f"В комментарии к переводу (в приложении Payme/Click) ОБЯЗАТЕЛЬНО укажи этот код: **{pay_code}**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"После отправки перевода пришли скриншот чека админу: @твой_юзернейм\n"
        f"Баланс зачислится автоматически в течение 5 минут! 🚀"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "test_pay_10k")
async def process_pay_10k(callback: CallbackQuery):
    await callback.message.delete()
    
    pay_code = random.randint(1000, 9999)
    
    text = (
        f"💎 **КУПИТЬ ПРЕМИУМ — 10 000 сум**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Переведи **10 000 сум** на карту:\n"
        f"`986000500343425` (Карта Uzcard/Humo)\n\n"
        f"⚠️ **КРИТИЧЕСКИ ВАЖНО:**\n"
        f"В комментарии к переводу ОБЯЗАТЕЛЬНО укажи этот код: **{pay_code}**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"После отправки перевода пришли скриншот чека админу: @твой_юзернейм\n"
        f"Премиум активируется сразу после проверки! 👑"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

# ==========================================
# 2. СИСТЕМНОЕ ПОДТВЕРЖДЕНИЕ ТЕЛЕГРАМУ (ОК)
# ==========================================
@router.pre_checkout_query()
async def checkout_confirm(pre_checkout_query: PreCheckoutQuery):
    # Обязательно отвечаем Телеграму True, иначе платеж зависнет с ошибкой
    await pre_checkout_query.answer(ok=True)


# ==========================================
# 3. ФИНАЛ: ЛОВИМ УСПЕШНЫЙ ПЛАТЕЖ И ОБНОВЛЯЕМ ДЖАНГО
# ==========================================
@router.message(F.successful_payment)
async def success_payment_handler(message: Message):
    # Извлекаем скрытую метку, которую мы вешали в инвойсе выше
    payload = message.successful_payment.invoice_payload
    
    # Вытаскиваем юзера из Django ORM асинхронно
    user = await sync_to_async(TelegramUser.objects.get)(user_id=message.from_user.id)
    
    # Вариант А: Юзер покупал поштучный баланс
    if payload == "deposit_3000_payload":
        user.balance += 3000
        await sync_to_async(user.save)() # Сохраняем изменения в PostgreSQL
        
        await message.answer(
            f"🎉 **ОПЛАТА ПРОШЛА УСПЕШНО!**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 На твой баланс зачислено `3 000` сум.\n"
            f"💰 Текущий счет в профиле: `{user.balance:,}` сум.",
            parse_mode="Markdown"
        )
        
    # Вариант Б: Юзер купил подписку на месяц
    elif payload == "premium_10000_payload":
        from django.utils import timezone
        from datetime import timedelta
        
        user.is_premium = True
        user.premium_until = timezone.now() + timedelta(days=30)
        await sync_to_async(user.save)() # Сохраняем изменения в PostgreSQL
        
        await message.answer(
            f"💎 **МАГИЯ ИИ АКТИВИРОВАНА!**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎉 Подписка PRO успешно куплена на 30 дней!\n"
            f"🚀 Все ограничения ИИ полностью стерты. Проверяй профиль!",
            parse_mode="Markdown"
        )