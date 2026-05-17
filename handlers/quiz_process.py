import asyncio
from quizzes.models import TelegramUser
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PollAnswer
from aiogram.filters import Command
from asgiref.sync import sync_to_async
from aiogram import Bot
import random
from aiogram import F
from utils.db_api import db
from typing import Union
from quizzes.models import Question, TestPack, TestSession
from keyboards.keyboards import (
    get_quizzes_list_kb, 
    get_stop_confirm_kb, 
    get_pack_menu_kb,
    get_edit_menu_kb,
)
from aiogram.types import InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
class EditPack(StatesGroup):
    waiting_for_name = State()

router = Router()
processing_users = set()
active_tasks = {}

async def send_next_question(bot, user_id, from_timer=False):
    try:
        # 1. ГАСИМ СТАРЫЙ ТАЙМЕР
        if not from_timer:
            if user_id in active_tasks:
                active_tasks[user_id].cancel()
                del active_tasks[user_id]

        # 2. ПРОВЕРКА СТАТУСА
        session = await db.get_active_session(user_id)
        if not session or not session.is_active:
            return

        # 3. ПОИСК ВОПРОСА
        question = await sync_to_async(lambda: Question.objects.filter(
            pack=session.pack
        ).order_by('id')[session.current_question_index : session.current_question_index + 1].first())()

        if question:
            # --- МАГИЯ ПЕРЕМЕШИВАНИЯ ВАРИАНТОВ ---
            original_options = list(question.options)
            # Берем текст правильного ответа по старому индексу
            correct_text = original_options[int(question.correct_option_id)]
            
            # Создаем копию и мешаем её
            shuffled_options = original_options.copy()
            random.shuffle(shuffled_options)
            
            # Находим новый индекс того же правильного текста
            new_correct_id = shuffled_options.index(correct_text)
            # --- КОНЕЦ МАГИИ ---

            # ОТПРАВЛЯЕМ ОПРОС (уже с новыми данными)
            await bot.send_poll(
                chat_id=user_id,
                question=f"❓ Вопрос №{session.current_question_index + 1}\n\n{question.text}",
                options=shuffled_options, # Шлем перемешанные
                type='quiz',
                correct_option_id=new_correct_id, # Шлем пересчитанный индекс
                is_anonymous=False,
                open_period=40,
                explanation="Варианты перемешаны! Читайте внимательно 🧠"
            )

            # 4. ЕДИНЫЙ ТАЙМЕР ОЖИДАНИЯ
            async def auto_afk_timer(current_index, chat_id):
                try:
                    await asyncio.sleep(42)
                    fresh = await db.get_active_session(chat_id)
                    if fresh and fresh.is_active and fresh.current_question_index == current_index:
                        await bot.send_message(
                            chat_id, 
                            "Вы еще здесь? Тест приостановлен. Нажмите продолжить, когда будете готовы.",
                            reply_markup=get_stop_confirm_kb()
                        )
                except asyncio.CancelledError:
                    pass

            active_tasks[user_id] = asyncio.create_task(auto_afk_timer(session.current_question_index, user_id))

        else:
            # Если вопросы закончились, выводим результат
            # (Тут можно добавить вывод баллов из session.correct_answers)
            await db.close_session(user_id)
            await bot.send_message(user_id, "🏁 Тест завершен! Вы прошли все вопросы.")

    except Exception as e:
        print(f"Ошибка в основном цикле: {e}")

@router.message(Command("stop"))
async def cmd_stop(message: Message):
    user_id = message.from_user.id
    
    # ПЕРВЫМ ДЕЛОМ - ГАСИМ СЕССИЮ В БАЗЕ
    await db.close_session(user_id) # Ставим is_active = False
    if user_id in active_tasks:
        active_tasks[user_id].cancel() # Убиваем спящего "сторожа"
        del active_tasks[user_id]
    
    # ВТОРЫМ ДЕЛОМ - УБИВАЕМ ТАСК В ПАМЯТИ
    if user_id in active_tasks:
        active_tasks[user_id].cancel()
        print(f"DEBUG: Задача для {user_id} принудительно убита через /stop")
        # Не удаляем из словаря здесь, это сделает блок выше или сам таймер
    
    await message.answer("🛑 ТЕСТ ОСТАНОВЛЕН.\nСледующий опрос не придет.", reply_markup=get_stop_confirm_kb())
@router.callback_query(F.data == "continue_test")
async def handle_continue(callback: CallbackQuery):
    user_id = callback.from_user.id
    # Реанимируем сессию в базе
    def _reactivate():
        session = TestSession.objects.filter(user__user_id=user_id).last()
        if session:
            session.is_active = True
            session.save()
    await sync_to_async(_reactivate)()
    
    await callback.message.delete()
    await send_next_question(callback.bot, user_id)
    await callback.answer()

@router.callback_query(F.data == "confirm_stop")
async def handle_confirm_stop(callback: CallbackQuery, state: FSMContext):
    # 1. Закрываем сессию в базе
    await db.close_session(callback.from_user.id)
    
    # 2. ОЧИЩАЕМ СОСТОЯНИЕ (это самое главное, чтобы бот не "тупил")
    await state.clear()
    
    # 3. Редактируем сообщение
    await callback.message.edit_text(
        "🏁 **Тест завершен.**\n"
        "Возвращайся скорее, знания сами себя не проверят! 💪",
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "continue_test")
async def handle_continue_test(callback: CallbackQuery):
    # Просто удаляем сообщение с вопросом "Вы уверены?"
    await callback.message.delete()
    await callback.answer("Продолжаем! 🚀")

@router.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer):
    user_id = poll_answer.user.id
    if user_id in processing_users: return
    processing_users.add(user_id)
    try:
        session = await db.get_active_session(user_id)
        if session and session.is_active:
            session.current_question_index += 1
            await sync_to_async(session.save)()
            await asyncio.sleep(1.5)
            await send_next_question(poll_answer.bot, user_id)
    except Exception as e:
        print(f"Ошибка в ответе: {e}")
    finally:
        processing_users.remove(user_id)

@router.message(Command("quizzes"))
@router.message(F.text == "📂 Мои тесты")
@router.callback_query(F.data == "quizzes")  # <-- Добавили перехват инлайн-кнопки!
async def show_quizzes(event: Union[Message, CallbackQuery]):
    # Определяем, кто вызвал хендлер — кнопка или сообщение
    is_callback = isinstance(event, CallbackQuery)
    
    # Достаем id пользователя и объект сообщения в зависимости от типа события
    user_id = event.from_user.id
    message = event.message if is_callback else event
    
    if is_callback:
        await event.answer()  # Сразу гасим часики на кнопке «Назад»
        
    user = await db.get_user(user_id)
    packs = await db.get_user_packs_with_count(user)
    
    # 1. Если библиотека пуста
    if not packs:
        empty_text = (
            f"📚 **МОЯ БИБЛИОТЕКА**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"❌ Твоя библиотека пока пуста.\n\n"
            f"📝 Нажми кнопку **«Создать тест»** в меню или введи команду /newquiz, "
            f"чтобы загрузить свой первый файл!"
        )
        if is_callback:
            return await message.edit_text(empty_text, parse_mode="Markdown")
        return await message.answer(empty_text, parse_mode="Markdown")
    
    # 2. Если тесты есть — выводим визуал
    quizzes_text = (
        f"📚 **СПИСОК ТВОИХ ТЕСТОВ**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📂 Здесь хранятся все сгенерированные пакеты вопросов. "
        f"Выбери нужный тест ниже, чтобы запустить интерактивный квиз или настроить его:\n\n"
        f"👇 _Доступные пакеты_:"
    )
    
    if is_callback:
        # Если нажали «Назад», плавно меняем текст прямо в старом окне
        await message.edit_text(
            text=quizzes_text, 
            reply_markup=get_quizzes_list_kb(packs),
            parse_mode="Markdown"
        )
    else:
        # If это команда или обычная кнопка меню — шлем новое сообщение
        await message.answer(
            text=quizzes_text, 
            reply_markup=get_quizzes_list_kb(packs),
            parse_mode="Markdown"
        )
@router.callback_query(F.data.startswith("start_test_"))
async def start_test_handler(callback: CallbackQuery):
    pack_id = int(callback.data.split("_")[2])
    user = await db.get_user(callback.from_user.id)
    pack = await sync_to_async(TestPack.objects.get)(id=pack_id)
    await db.create_session(user, pack)
    await callback.message.answer(f"🚀 Запуск: {pack.name}")
    await send_next_question(callback.bot, callback.from_user.id)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith('view_pack_'))
async def view_pack_menu(callback: CallbackQuery):
    pack_id = int(callback.data.split('_')[2])
    
    # Теперь Python знает, что такое QuestionPack
    pack = await sync_to_async(TestPack.objects.get)(id=pack_id)
    count = await sync_to_async(Question.objects.filter(pack=pack).count)()

    await callback.message.edit_text(
        f"📦 Пак: {pack.name}\n📝 Вопросов: {count}",
        reply_markup=get_pack_menu_kb(pack_id) # Вызываем функцию из keyboards.py
    )


@router.callback_query(lambda c: c.data.startswith('start_quiz_'))
async def start_quiz_handler(callback: CallbackQuery, bot: Bot):
    pack_id = int(callback.data.split('_')[2])
    user_id = callback.from_user.id

    # 1. Получаем или создаем сессию для пользователя
    # Используем update_or_create, чтобы старая сессия обнулилась
    session, created = await sync_to_async(TestSession.objects.update_or_create)(
        user_id=user_id,
        defaults={
            'pack_id': pack_id,
            'current_question_index': 0,
            'correct_answers': 0,
            'is_active': True
        }
    )

    await callback.answer("Тест начинается! Удачи 🚀")
    
    # Удаляем меню выбора, чтобы не мешало
    await callback.message.delete()

    # 2. Запускаем цикл отправки вопросов
    await send_next_question(bot, callback.from_user.id)




@router.callback_query(F.data.startswith('edit_pack_'))
async def edit_pack_options(callback: CallbackQuery):
    pack_id = int(callback.data.split('_')[2])
    
    # Просто вызываем готовую клавиатуру из keyboards.py
    await callback.message.edit_text(
        "Что ты хочешь изменить в этом паке?", 
        reply_markup=get_edit_menu_kb(pack_id)
    )

@router.callback_query(F.data.startswith('rename_pack_'))
async def rename_pack_start(callback: CallbackQuery, state: FSMContext):
    pack_id = int(callback.data.split('_')[2])
    
    # Сохраняем ID пака в память FSM, чтобы не потерять
    await state.update_data(edit_pack_id=pack_id)
    # Переключаем бота в режим ожидания текста
    await state.set_state(EditPack.waiting_for_name)
    
    await callback.message.answer("Пришли мне новое название для этого пакета:")
    await callback.answer()

@router.message(EditPack.waiting_for_name)
async def rename_pack_finish(message: Message, state: FSMContext):
    new_name = message.text.strip()
    
    # 1. Проверяем длину, чтобы название не было слишком длинным для кнопок
    if len(new_name) > 50:
        await message.answer("❌ Название слишком длинное (макс. 50 символов). Попробуй еще раз:")
        return

    # 2. Достаем ID пака, который мы сохранили в rename_pack_start
    data = await state.get_data()
    pack_id = data.get('edit_pack_id')

    # 3. Обновляем имя в базе данных Django
    await sync_to_async(TestPack.objects.filter(id=pack_id).update)(name=new_name)

    # 4. Сбрасываем состояние (выходим из режима редактирования)
    await state.clear()

    await message.answer(f"✅ Успешно! Теперь пак называется: **{new_name}**", parse_mode="Markdown")
    
    # 5. Возвращаем пользователя в список тестов (опционально)
    # Здесь можно вызвать твою функцию показа всех тестов



@router.callback_query(F.data == "run_all")
async def run_latest_pack(callback: CallbackQuery):
    # Достаем самый последний созданный пак
    latest_pack = await sync_to_async(lambda: TestPack.objects.order_by('-id').first())()
    
    if not latest_pack:
        await callback.answer("У тебя еще нет созданных паков! 📂", show_alert=True)
        return

    # Сразу запускаем функцию просмотра этого пака, которую мы уже сделали
    # Это откроет меню с кнопкой "Начать тест"
    await view_pack_menu_by_id(callback, latest_pack.id)

# Вспомогательная функция, чтобы не дублировать код
async def view_pack_menu_by_id(callback, pack_id):
    pack = await sync_to_async(TestPack.objects.get)(id=pack_id)
    count = await sync_to_async(Question.objects.filter(pack=pack).count)()
    
    await callback.message.edit_text(
        f"📦 Пакет: {pack.name}\n📝 Вопросов: {count}\n\nВыбери действие:",
        reply_markup=get_pack_menu_kb(pack_id) # Твоя клава с кнопками Начать/Редактировать
    )


@router.callback_query(F.data == "settings_pack")
async def open_editor_list(callback: CallbackQuery):
    # Просто вызываем список всех тестов
    # (Предположим, твоя функция называется show_quizzes_list)
    await show_quizzes_list(callback)



@router.callback_query(F.data.startswith('delete_confirm_'))
async def confirm_delete_pack(callback: CallbackQuery):
    pack_id = int(callback.data.split('_')[2])
    
    # Создаем временную клавиатуру для подтверждения
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, я уверен", callback_data=f"delete_execute_{pack_id}")],
        [InlineKeyboardButton(text="❌ Нет, отмена", callback_data=f"view_pack_{pack_id}")]
    ])
    
    await callback.message.edit_text(
        "⚠️ **Внимание!**\n\nТы действительно хочешь удалить этот пакет? Все вопросы в нем будут безвозвратно стерты.",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith('delete_execute_'))
async def delete_pack_from_db(callback: CallbackQuery):
    pack_id = int(callback.data.split('_')[2])
    user_obj = await db.get_user(callback.from_user.id)
    deleted_count, _ = await sync_to_async(
        lambda: TestPack.objects.filter(id=pack_id, user=user_obj).delete()
    )()
    try:
        # 1. Удаляем из базы
        await sync_to_async(TestPack.objects.filter(id=pack_id).delete)()
        
        # 2. Показываем уведомление
        await callback.answer("Пакет полностью удален! 🗑", show_alert=True)
        
        # 3. Возвращаемся к списку. 
        # Чтобы не было ошибок импорта, вызываем функцию отображения напрямую, 
        # если она в этом же файле, либо импортируем её локально:
        from handlers.quiz_process import show_quizzes_list 
        await show_quizzes_list(callback)
        
    except Exception as e:
        print(f"Ошибка при удалении: {e}")
        await callback.answer("Не удалось удалить пак.", show_alert=True)

# Сама функция отображения (проверь, чтобы она была в этом файле)
async def show_quizzes_list(callback: CallbackQuery):
    # Получаем паки из БД
    user_obj = await db.get_user(callback.from_user.id)
    packs = await sync_to_async(lambda: list(TestPack.objects.filter(user=user_obj)))()
    
    # Считаем вопросы для каждого пака (через твой q_count или фильтром)
    for p in packs:
        p.q_count = await sync_to_async(Question.objects.filter(pack=p).count)()
    
    if not packs:
        await callback.message.edit_text("У тебя пока нет тестов. Загрузи .docx файл!")
        return

    await callback.message.edit_text(
        "Твои тесты:",
        reply_markup=get_quizzes_list_kb(packs) # Та самая функция из keyboards.py
    )





@router.message(Command("profile"))
@router.message(F.text == "👤 Мой профиль")
async def show_profile(message: Message):
    # 🔥 ИСПРАВЛЕНО: Вместо TelegramUser.objects.get используем твой db.get_user
    # Если юзера нет в базе, этот метод сам его создаст без ошибок!
    user = await db.get_user(tg_id=message.from_user.id, username=message.from_user.username)
    
    # 1. Проверка премиума и вывод оставшихся дней
    if user.is_premium:
        if user.premium_days_left > 100:
            status_text = "✨ PRO-Доступ 👑"
        else:
            status_text = f"✨ PRO-Доступ (Осталось дней: {user.premium_days_left}) 👑"
    else:
        status_text = "👁 Обычный"
    
    # 2. Проверка бесплатных попыток
    if user.free_attempts_left > 0:
        free_test_text = f"Доступно: {user.free_attempts_left} ✅"
    else:
        free_test_text = "Использован ❌"
    
    # Шаблон профиля
    profile_card = (
        f"👤 **ТВОЙ ПРОФИЛЬ**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 **ID:** `{user.user_id}`\n"
        f"🪙 **Баланс:** `{user.balance:,}` сум\n"
        f"💎 **Статус:** *{status_text}*\n"
        f"🎁 **Бесплатный тест:** {free_test_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Выбирай нужный тариф ниже, чтобы пополнить баланс и мгновенно переводить лекции в тесты! 👇"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪙 Пополнить на 3 000 сум", callback_data="test_pay_3k")],
        [InlineKeyboardButton(text="💎 Купить Премиум (10 000 сум)", callback_data="test_pay_10k")]
    ])
    
    await message.answer(profile_card, reply_markup=kb, parse_mode="Markdown")