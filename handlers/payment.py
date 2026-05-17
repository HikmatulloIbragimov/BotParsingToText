import random
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from asgiref.sync import sync_to_async
from quizzes.models import TelegramUser  # Проверь правильность импорта модели!
import os
import logging
from aiogram.filters import Command, StateFilter
from django.utils import timezone
import datetime
router = Router()

# ТВОЙ ТЕЛЕГРАМ ID (Узнай его в @userinfobot)
ADMIN_ID = os.getenv("ADMIN_ID")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
class PaymentStates(StatesGroup):
    wait_screenshot = State()

# --- 1. ВЫБОР ТАРИФА И ВЫВОД ИНСТРУКЦИИ ---
@router.callback_query(F.data.startswith("test_pay_"))
async def process_payment_choice(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    
    # Определяем сумму
    amount = 3000 if "3k" in callback.data else 10000
    await state.update_data(amount=amount)
    
    await send_payment_instruction(callback.message, amount, state)
    await callback.answer()


# --- ФУНКЦИЯ ДЛЯ ПОВТОРНОГО ВЫЗОВА КАРТЫ (ЧТОБЫ НЕ ДУБЛИРОВАТЬ КОД) ---
async def send_payment_instruction(message: Message, amount: int, state: FSMContext):
    text = (
        f"💳 **ПОПОЛНЕНИЕ КОШЕЛЬКА — {amount:,} сум**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Переведи **{amount:,} сум** на карту:\n"
        f"`5614681814089151`(нажмите и оно скопируется)\n\n"
        f"📸 **ШАГ ДЛЯ АКТИВАЦИИ:**\n"
        f"Оплати в Payme/Click, сделай **скриншот чека** и отправь его прямо сюда (картинкой) в этот чат. 👇\n\n"
        f"Я мгновенно перенаправлю его админу на проверку!"
    )
    await message.answer(text, parse_mode="Markdown")
    await state.set_state(PaymentStates.wait_screenshot)


# --- 2. ПРИЕМ СКРИНШОТА И ОТПРАВКА АДМИНУ ---
@router.message(PaymentStates.wait_screenshot, F.photo)
async def handle_screenshot(message: Message, state: FSMContext, bot: Bot):
    user_data = await state.get_data()
    amount = user_data.get("amount", 3000)
    await state.clear()
    
    await message.answer("♻️ **Ваш чек отправлен на проверку админу.**\nЯ проверяю поступления очень быстро. Как только админ подтвердит, баланс обновится автоматически! Побудь на связи ⏳")
    
    # Кнопки для тебя в админ-чате
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"adm_confirm_{message.from_user.id}_{amount}"),
            InlineKeyboardButton(text="❌ Отклонить чек", callback_data=f"adm_decline_{message.from_user.id}_{amount}")
        ]
    ])
    
    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=message.photo[-1].file_id,
        caption=(
            f"💰 **НОВЫЙ ПЛАТЕЖ НА ПРОВЕРКУ!**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Студент:** {message.from_user.full_name}\n"
            f"🆔 **ID:** `{message.from_user.id}`\n"
            f"💵 **Сумма к зачислению:** `{amount:,}` сум\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Проверь пуш/историю в банке и вынеси вердикт: 👇"
        ),
        reply_markup=admin_kb,
        parse_mode="Markdown"
    )


# --- 3. ХЕНДЛЕР ПОДТВЕРЖДЕНИЯ (ДЛЯ ТЕБЯ) ---
@router.callback_query(F.data.startswith("adm_confirm_"))
async def admin_confirm_pay(callback: CallbackQuery, bot: Bot):
    _, _, user_id, amount = callback.data.split("_")
    user_id = int(user_id)
    amount = int(amount)
    
    try:
        user = await sync_to_async(TelegramUser.objects.get)(user_id=user_id)
        
        if amount == 10000:
            user.is_premium = True
            success_text = (
                f"🎉 **ПОЗДРАВЛЯЕМ! ОПЛАТА ПРОШЛА УСПЕШНО!** 👑\n\n"
                f"Вам успешно активирован **ПРЕМИУМ-ДОСТУП**!\n"
                f"Теперь вы можете загружать огромные файлы и генерировать тесты без ограничений. "
                f"Порвите эту сессию на изи! 🎓🚀\n\n"
                f"Проверьте статус в /profile"
            )
        else:
            user.balance += amount
            success_text = (
                f"🎉 **БАЛАНС УСПЕШНО ПОПОЛНЕН!** 🪙\n\n"
                f"На ваш счет зачислено `{amount:,}` сум.\n"
                f"Спасибо за доверие! Скорее загружайте свои документы и готовьтесь к экзаменам в один клик! 🧠🔥\n\n"
                f"Текущий баланс доступен в /profile"
            )
            
        await sync_to_async(user.save)()
        
        # Обновляем сообщение у тебя в админке
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n🟢 **ПРИНЯТО! Баланс/Премиум успешно начислен юзеру.**", 
            reply_markup=None
        )
        
        # Отправляем радостный пуш студенту
        await bot.send_message(chat_id=user_id, text=success_text, parse_mode="Markdown")
        
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при обращении к базе данных Django: {e}")
        
    await callback.answer()


# --- 4. ХЕНДЛЕР ОТКЛОНЕНИЯ С КНОПКОЙ «ПОВТОРИТЬ» (ДЛЯ ТЕБЯ И СТУДЕНТА) ---
@router.callback_query(F.data.startswith("adm_decline_"))
async def admin_decline_pay(callback: CallbackQuery, bot: Bot):
    _, _, user_id, amount = callback.data.split("_")
    user_id = int(user_id)
    amount = int(amount)
    
    # Фиксируем отмену в твоем чате
    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n🔴 **ОТКЛОНЕНО! Юзеру отправлено уведомление об ошибке.**", 
        reply_markup=None
    )
    
    # Создаем кнопку «Заново» для студента
    retry_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Попробовать заново", callback_data=f"retry_pay_{amount}")]
    ])
    
    # Пишем вежливый отлуп студенту
    fail_text = (
        f"⚠️ **Упс! Транзакция не подтвердилась.**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Наш админ проверил выписку, но не нашел платежа на сумму `{amount:,}` сум.\n\n"
        f"❓ **Возможные причины:**\n"
        f"• Деньги еще не дошли (задержка банка).\n"
        f"• Вы прикрепили не тот файл или старый чек.\n"
        f"• Оплата не прошла до конца.\n\n"
        f"Вы уверены, что отправили правильный файл чека? Пожалуйста, проверьте и попробуйте еще раз. 👇"
    )
    
    await bot.send_message(chat_id=user_id, text=fail_text, reply_markup=retry_kb, parse_mode="Markdown")
    await callback.answer()


# --- 5. КРУГ ЗАМЫКАЕТСЯ: ЮЗЕР ТЫКАЕТ «ПОПРОБОВАТЬ ЗАНОВО» ---
@router.callback_query(F.data.startswith("retry_pay_"))
async def retry_payment_process(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    
    # Вытаскиваем сумму из callback_data
    amount = int(callback.data.split("_")[2])
    await state.update_data(amount=amount)
    
    # Снова выводим карту и запускаем стейт ожидания
    await send_payment_instruction(callback.message, amount, state)
    await callback.answer()




# 🔥 Команда компенсации попытки: /give_try [USER_ID] [КОЛИЧЕСТВО]
@router.message(Command("give_try"), F.from_user.id == ADMIN_ID)
async def admin_give_try(message: Message, bot: Bot):
    logging.info(f"Админ-команда give_try вызвана текстом: {message.text}")
    try:
        parts = message.text.split()
        if len(parts) != 3:
            return await message.answer("⚠️ Неверный формат! Используй: `/give_try ID КОЛИЧЕСТВО`", parse_mode="Markdown")
            
        _, user_id, count = parts
        
        user = await sync_to_async(TelegramUser.objects.get)(user_id=int(user_id))
        user.free_attempts_left += int(count)
        await sync_to_async(user.save)()
        
        await message.answer(f"✅ Успешно начислено {count} попыток юзеру `{user_id}`", parse_mode="Markdown")
        
        try:
            await bot.send_message(
                chat_id=int(user_id), 
                text=f"🎁 **Администрация начислила вам {count} бонусных бесплатных попыток!**\nПриносим извинения за временные неудобства. Продолжаем штурм! 🚀",
                parse_mode="Markdown"
            )
        except Exception as push_err:
            await message.answer(f"⚠️ Попытки начислены, но пуш-уведомление не ушло: {push_err}")
            
    except TelegramUser.DoesNotExist:
        await message.answer(f"❌ Ошибка: Пользователь с ID `{user_id}` не найден в базе данных!", parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Критическая ошибка: {e}")


# 🔥 Команда компенсации премиума на ДНИ: /give_premium [USER_ID] [ДНИ]
@router.message(Command("give_premium"), F.from_user.id == ADMIN_ID)
async def admin_give_premium(message: Message, bot: Bot):
    logging.info(f"Админ-команда give_premium вызвана текстом: {message.text}")
    try:
        parts = message.text.split()
        if len(parts) != 3:
            return await message.answer("⚠️ Неверный формат! Используй: `/give_premium ID ДНИ`", parse_mode="Markdown")
            
        _, user_id, days = parts
        
        user = await sync_to_async(TelegramUser.objects.get)(user_id=int(user_id))
        user.premium_until = timezone.now() + datetime.timedelta(days=int(days))
        await sync_to_async(user.save)()
        
        await message.answer(f"✅ Юзеру `{user_id}` успешно выдан Премиум на {days} дней!", parse_mode="Markdown")
        
        try:
            await bot.send_message(
                chat_id=int(user_id), 
                text=f"👑 **ВАМ ВЫДАН PREMIUM НА {days} ДН. в качестве компенсации!** 🎉\nТеперь все ограничения сняты. Удачи на сессии! 🚀",
                parse_mode="Markdown"
            )
        except Exception as push_err:
            await message.answer(f"⚠️ Премиум выдан, но пуш не ушел: {push_err}")
            
    except TelegramUser.DoesNotExist:
        await message.answer(f"❌ Ошибка: Пользователь с ID `{user_id}` не найден в базе данных!", parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Критическая ошибка: {e}")