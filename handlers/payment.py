# import os
# from aiogram import Router, F
# from aiogram.types import CallbackQuery, LabeledPrice, PreCheckoutQuery, Message
# from asgiref.sync import sync_to_async

# # Проверь этот импорт! Укажи правильный путь к твоей Django-модели
# from quizzes.models import TelegramUser 

# router = Router()

# # Беру токен из переменных окружения. Если локально его нет, подставится временная заглушка
# PAYMENT_TOKEN = os.getenv("PAYME_TEST_TOKEN", "361515438:TEST:ЗАГЛУШКА_ЕСЛИ_ЗАБЫЛ_ДОБАВИТЬ_В_РАИЛВЕЙ")

# # ==========================================
# # 1. ВЫСТАВЛЕНИЕ СЧЕТОВ (ИНВОЙСЫ)
# # ==========================================

# # Срабатывает при нажатии кнопки "Пополнить баланс на 3 000 сум" в твоем профиле
# @router.callback_query(F.data == "test_pay_3k")
# async def process_pay_3k(callback: CallbackQuery):
#     await callback.message.delete() # Стираем сообщение профиля, чтобы красиво вылетел чек
    
#     # Сумма указывается в тийинах (3000 сум * 100)
#     prices = [LabeledPrice(label="Пополнение кошелька (1 тест)", amount=300000)]
    
#     await callback.message.bot.send_invoice(
#         chat_id=callback.message.chat.id,
#         title="🪙 Баланс бота",
#         description="Зачисление 3 000 сум на покупку одной генерации теста.",
#         provider_token=PAYMENT_TOKEN,
#         currency="UZS", # Наш родной сум
#         prices=prices,
#         payload="deposit_3000_payload", # Секретная метка платежа
#         start_parameter="pay_single_quiz"
#     )
#     await callback.answer()


# # Срабатывает при нажатии кнопки "Купить Месячный PRO (10 000 сум)"
# @router.callback_query(F.data == "test_pay_10k")
# async def process_pay_10k(callback: CallbackQuery):
#     await callback.message.delete()
    
#     # 10 000 сум * 100 = 1 000 000 тийинов
#     prices = [LabeledPrice(label="PRO Подписка на 30 дней", amount=1000000)]
    
#     await callback.message.bot.send_invoice(
#         chat_id=callback.message.chat.id,
#         title="💎 Доступ PRO-Безлимит",
#         description="Активация безлимитных запросов к ИИ на 1 месяц.",
#         provider_token=PAYMENT_TOKEN,
#         currency="UZS",
#         prices=prices,
#         payload="premium_10000_payload",
#         start_parameter="pay_premium_month"
#     )
#     await callback.answer()


# # ==========================================
# # 2. СИСТЕМНОЕ ПОДТВЕРЖДЕНИЕ ТЕЛЕГРАМУ (ОК)
# # ==========================================
# @router.pre_checkout_query()
# async def checkout_confirm(pre_checkout_query: PreCheckoutQuery):
#     # Обязательно отвечаем Телеграму True, иначе платеж зависнет с ошибкой
#     await pre_checkout_query.answer(ok=True)


# # ==========================================
# # 3. ФИНАЛ: ЛОВИМ УСПЕШНЫЙ ПЛАТЕЖ И ОБНОВЛЯЕМ ДЖАНГО
# # ==========================================
# @router.message(F.successful_payment)
# async def success_payment_handler(message: Message):
#     # Извлекаем скрытую метку, которую мы вешали в инвойсе выше
#     payload = message.successful_payment.invoice_payload
    
#     # Вытаскиваем юзера из Django ORM асинхронно
#     user = await sync_to_async(TelegramUser.objects.get)(user_id=message.from_user.id)
    
#     # Вариант А: Юзер покупал поштучный баланс
#     if payload == "deposit_3000_payload":
#         user.balance += 3000
#         await sync_to_async(user.save)() # Сохраняем изменения в PostgreSQL
        
#         await message.answer(
#             f"🎉 **ОПЛАТА ПРОШЛА УСПЕШНО!**\n"
#             f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
#             f"🪙 На твой баланс зачислено `3 000` сум.\n"
#             f"💰 Текущий счет в профиле: `{user.balance:,}` сум.",
#             parse_mode="Markdown"
#         )
        
#     # Вариант Б: Юзер купил подписку на месяц
#     elif payload == "premium_10000_payload":
#         from django.utils import timezone
#         from datetime import timedelta
        
#         user.is_premium = True
#         user.premium_until = timezone.now() + timedelta(days=30)
#         await sync_to_async(user.save)() # Сохраняем изменения в PostgreSQL
        
#         await message.answer(
#             f"💎 **МАГИЯ ИИ АКТИВИРОВАНА!**\n"
#             f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
#             f"🎉 Подписка PRO успешно куплена на 30 дней!\n"
#             f"🚀 Все ограничения ИИ полностью стерты. Проверяй профиль!",
#             parse_mode="Markdown"
#         )