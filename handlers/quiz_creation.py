import io
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

# Наши инструменты
from utils.db_api import db
from utils.parsers import parse_pdf_from_memory, parse_docx_from_memory
from utils.states import QuizCreation
from keyboards.keyboards import (
    get_creation_method_kb, 
    get_manual_creation_kb, 
    get_file_action_menu
)

router = Router()

@router.message(Command("newquiz"))
async def cmd_new_quiz(message: Message, state: FSMContext):
    await message.answer("📝 Как назовем твой новый тест?")
    await state.set_state(QuizCreation.waiting_for_name)

@router.message(QuizCreation.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(quiz_name=message.text)
    await message.answer(
        f"Отличное название: *{message.text}*!\nВыбери способ добавления:",
        reply_markup=get_creation_method_kb(),
        parse_mode="Markdown"
    )
    await state.set_state(QuizCreation.waiting_for_content)

@router.callback_query(QuizCreation.waiting_for_content, F.data == "method_file")
async def choose_file_method(callback: CallbackQuery):
    await callback.message.answer("Пришли файл (.docx или .pdf)")
    await callback.answer()

@router.message(F.document, QuizCreation.waiting_for_content)
async def handle_document(message: Message, state: FSMContext):
    file_name = message.document.file_name.lower()
    if not file_name.endswith(('.docx', '.pdf')):
        return await message.answer("❌ Я понимаю только .docx и .pdf")

    user = await db.get_user(tg_id=message.from_user.id, username=message.from_user.username)
    data = await state.get_data()
    pack_name = data.get("quiz_name") or message.document.file_name

    await message.answer("⏳ Анализирую структуру файла...")
    
    try:
        file_io = io.BytesIO()
        file = await message.bot.get_file(message.document.file_id)
        await message.bot.download_file(file.file_path, file_io)
        file_io.seek(0)

        # Здесь вызывается твоя логика с "Интеллектуальным ситом"
        questions = parse_docx_from_memory(file_io) if file_name.endswith('.docx') else parse_pdf_from_memory(file_io)

        # --- ВОТ ЭТОТ УЧАСТОК МЫ УСИЛИЛИ ---
        if not questions:
            return await message.answer(
                "❌ **Файл отклонен!**\n\n"
                "Бот не смог распознать тест. Проверь следующее:\n"
                "1. Блоки разделены `++++`.\n"
                "2. В тесте должно быть **минимум 3 вопроса**.\n"
                "3. У каждого вопроса должно быть **минимум 2 варианта**.\n"
                "4. Правильный ответ помечен символом `#`.\n\n"
                "Попробуй исправить файл и скинуть его еще раз."
            )
        # ----------------------------------

        # Если дошли сюда — значит файл качественный и его можно в БД
        pack = await db.save_quiz_to_db(user, pack_name, questions)
        
        await message.answer(
            f"✅ Пакет «{pack.name}» успешно создан!\n📊 Проверено и загружено вопросов: {len(questions)}",
            reply_markup=get_file_action_menu()
        )
        await state.clear()

    except Exception as e:
        logging.error(f"Ошибка парсинга: {e}")
        await message.answer("❌ Произошла ошибка при обработке. Попробуй другой файл.")