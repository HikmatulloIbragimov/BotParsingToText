import io
import logging
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
# Твои модули
from utils.ai_engine import generate_quiz_with_ai
from utils.db_api import db
from utils.states import QuizCreation
from keyboards.keyboards import (
    get_creation_method_kb, 
    get_file_action_menu
)
from aiogram import types
# Импортируем функции из parsers.py 
# Используем 'as', чтобы оставить логику в коде прежней
from utils.parsers import (
    extract_text_from_docx as get_raw_text_from_docx, 
    extract_text_from_pdf as get_raw_text_from_pdf, 
    parse_text_logic
)

router = Router()

@router.message(Command("newquiz"))
@router.message(F.text == "📝 Создать тест")
async def cmd_new_quiz(message: Message, state: FSMContext):
    # Ставим состояние ожидания имени теста
    await state.set_state(QuizCreation.waiting_for_name)
    
    instruction_text = (
        f"📝 **Шаг 1 из 2: Название теста**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Как мы назовем твой новый пакет вопросов?\n\n"
        f"✍️ *Просто напиши название в ответном сообщении.*\n"
        f"_(Например: Модуль по аудиту, История, Лекция 5)_"
    )
    
    await message.answer(instruction_text, parse_mode="Markdown")

@router.message(QuizCreation.waiting_for_name)
async def process_quiz_name(message: Message, state: FSMContext):
    # Сохраняем имя в FSM (у тебя тут своя логика сохранения)
    await state.update_data(quiz_name=message.text)
    
    # Меняем состояние на ожидание документа
    await state.set_state(QuizCreation.waiting_for_content)
    
    file_instruction = (
        f"📂 **Шаг 2 из 2: Загрузка документа**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Отлично! Пакет назван: *{message.text}*\n\n"
        f"🚀 Теперь отправь мне файл `.docx` или `.pdf` с вопросами.\n\n"
        f"💡 **Важное примечание:**\n"
        f"• Если в файле уже есть варианты, пометь правильный ответ знаком `#` в начале строки и поставь `++++` в конце вопроса.\n"
        f"• Если у тебя 'голый' список вопросов без ответов — кидай так, наш ИИ всё достроит сам! 🤖"
    )
    
    await message.answer(file_instruction, parse_mode="Markdown")

@router.callback_query(QuizCreation.waiting_for_content, F.data == "method_file")
async def choose_file_method(callback: CallbackQuery):
    await callback.message.answer("Пришли файл (.docx или .pdf)")
    await callback.answer()

@router.message(F.document, QuizCreation.waiting_for_content)
async def handle_document(message: Message, state: FSMContext):
    file_name = message.document.file_name.lower()
    if not file_name.endswith(('.docx', '.pdf')):
        return await message.answer("❌ Я понимаю только .docx и .pdf")

    # Получаем данные из базы и состояния
    user = await db.get_user(tg_id=message.from_user.id, username=message.from_user.username)
    data = await state.get_data()
    pack_name = data.get("quiz_name") or message.document.file_name

    status_msg = await message.answer("⏳ Анализирую файл...")
    
    try:
        # Скачиваем файл
        file_io = io.BytesIO()
        file = await message.bot.get_file(message.document.file_id)
        await message.bot.download_file(file.file_path, file_io)
        file_io.seek(0)

        # --- ШАГ 1: Извлекаем сырой текст ---
        if file_name.endswith('.docx'):
            raw_text = get_raw_text_from_docx(file_io)
        else:
            raw_text = get_raw_text_from_pdf(file_io)

        # --- ШАГ 2: Пробуем найти готовую структуру (в файле) ---
        questions = parse_text_logic(raw_text)

        # --- ШАГ 3: Если готовой разметки нет — перехватываем и предлагаем ИИ ---
        if not questions:
            await status_msg.delete() # Удаляем старый текст "Обработка..."
            
            # Сохраняем сырой текст в состояние, чтобы использовать его, если юзер нажмет "Да"
            await state.update_data(raw_text_for_ai=raw_text)
            
            # Картинка робота-аналитика (можешь заменить на свою)
            ai_card_photo = "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?q=80&w=1000"
            
            ai_offer_text = (
                f"🔮 **Обнаружены вопросы без ответов!**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Я внимательно изучил твой файл. Готовых вариантов ответов и разметки (`++++`) внутри нет.\n\n"
                f"🤖 **Подключить ИИ к работе?**\n"
                f"Наш интеллект сам прочитает файл, найдет правильные ответы в интернете/базе и сгенерирует полноценный интерактивный тест за 15 секунд!\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👇 _Выбери действие:_"
            )
            
            # Клавиатура подтверждения вызова ИИ
            ai_choice_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🤖 Да, запустить ИИ", callback_data="confirm_ai_generation")],
                [InlineKeyboardButton(text="🛑 Отмена (В меню)", callback_data="cancel_quiz_creation")]
            ])
            
            return await message.answer_photo(
                photo=ai_card_photo,
                caption=ai_offer_text,
                reply_markup=ai_choice_kb,
                parse_mode="Markdown"
            )

        # --- ШАГ 4: Сохранение (Если разметка БЫЛА в файле изначально) ---
        # Сохраняем пакет в базу
        pack = await db.save_quiz_to_db(user, pack_name, questions)
        
        await status_msg.delete()
        
        # Наш новый красивый чек-успех
        success_card = (
            f"🎉 **ПАКЕТ ТЕСТОВ УСПЕШНО СОЗДАН!**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 **Название пакета:** *{pack_name}*\n"
            f"📊 **Загружено вопросов:** `{len(questions)}` шт.\n"
            f"🔑 **Статус:** `Полностью готов` ✅\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🧠 _Все вопросы успешно извлечены из файла и упакованы. Время проверить свои знания!_"
        )
        
        await message.answer(
            text=success_card,
            reply_markup=get_file_action_menu(),
            parse_mode="Markdown"
        )
        await state.clear()

    except Exception as e:
        logging.error(f"Ошибка при обработке файла: {e}")
        await message.answer(f"❌ Произошла ошибка: {str(e)[:100]}")


@router.callback_query(F.data == "confirm_ai_generation")
async def process_ai_generation(callback: types.CallbackQuery, state: FSMContext):
    # Получаем данные из FSM, которые мы сохранили на предыдущем шаге
    user_data = await state.get_data()
    raw_text = user_data.get("raw_text_for_ai")
    pack_name = user_data.get("quiz_name") # Имя теста, которое юзер ввел на Шаге 1
    
    if not raw_text:
        return await callback.message.answer("❌ Ошибка: данные файла потеряны. Начни создание заново.")
    
    # Отправляем первое сообщение загрузки (20%)
    status_msg = await callback.message.answer(
        "📡 **Устанавливаю соединение с ИИ...**\n"
        "⏳ `[■■□□□□□□□□] 20%` \n\n"
        "ℹ️ _Отправляем запрос на сервера генерации..._",
        parse_mode="Markdown"
    )
    
    # Удаляем карточку с предложением ИИ, чтобы не захламлять чат
    await callback.message.delete()
    
    try:
        # Обрезаем текст для безопасности лимитов
        safe_text = raw_text[:10000]
        
        # Шаг 2 (50%)
        await status_msg.edit_text(
            "🧠 **ИИ проводит глубокий анализ вопросов...**\n"
            "⏳ `[■■■■■□□□□□] 50%` \n\n"
            "ℹ️ _Ищем правильные ответы и генерируем ложные варианты..._",
            parse_mode="Markdown"
        )
        
        # Запуск самого тяжелого процесса генерации ИИ
        ai_output = await generate_quiz_with_ai(safe_text)
        
        # Шаг 3 (80%)
        await status_msg.edit_text(
            "🧪 **Синтезирую вопросы и упаковываю варианты...**\n"
            "⏳ `[■■■■■■■■□□] 80%` \n\n"
            "ℹ️ _Проверяем совместимость с Telegram квизами..._",
            parse_mode="Markdown"
        )
        
        # Парсим то, что вернул ИИ
        questions = parse_text_logic(ai_output)
        
        if not questions:
            await status_msg.delete()
            return await callback.message.answer("❌ ИИ не смог корректно составить вопросы. Попробуй другой файл.")
            
        # Сохраняем готовый ИИ-тест в базу данных
        pack = await db.save_quiz_to_db(callback.from_user, pack_name, questions)
        
        # Удаляем прогресс-бар
        await status_msg.delete()
        
        # Выдаем шикарный финальный чек
        success_card = (
            f"🎉 **ПАКЕТ ТЕСТОВ УСПЕШНО СОЗДАН!**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 **Название пакета:** *{pack_name}*\n"
            f"📊 **Сгенерировано через ИИ:** `{len(questions)}` шт.\n"
            f"🔑 **Статус:** `Полностью готов` ✅\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 _Магия ИИ сработала! Вопросы получили варианты ответов и бережно сохранены в твой профиль._"
        )
        
        await callback.message.answer(
            text=success_card,
            reply_markup=get_file_action_menu(),
            parse_mode="Markdown"
        )
        await state.clear()
        
    except Exception as e:
        logging.error(f"Ошибка ИИ генерации: {e}")
        await status_msg.edit_text(f"❌ Произошла ошибка при работе ИИ: {str(e)[:100]}")
        
    await callback.answer()


@router.callback_query(F.data == "cancel_quiz_creation")
async def cancel_quiz_creation(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("🛑 Создание теста отменено. Ты вернулся в главное меню.")
    await callback.answer()