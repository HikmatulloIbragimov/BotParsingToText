import io
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from utils.ai_engine import generate_quiz_with_ai
from utils.db_api import db # Твоя база данных

# Наши инструменты
from utils.db_api import db
from utils.parsers import (
    extract_text_from_docx as get_raw_text_from_docx, 
    extract_text_from_pdf as get_raw_text_from_pdf, 
    parse_text_logic,
    parse_docx_from_memory,
    parse_pdf_from_memory
)
from utils.states import QuizCreation
from keyboards.keyboards import (
    get_creation_method_kb, 
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

    status_msg = await message.answer("⏳ Анализирую файл...")
    
    try:
        file_io = io.BytesIO()
        file = await message.bot.get_file(message.document.file_id)
        await message.bot.download_file(file.file_path, file_io)
        
        # --- ШАГ 1: Извлекаем сырой текст ---
        file_io.seek(0)
        if file_name.endswith('.docx'):
            raw_text = get_raw_text_from_docx(file_io)
        else:
            raw_text = get_raw_text_from_pdf(file_io)

        # --- ШАГ 2: Пробуем найти готовую структуру ---
        questions = parse_text_logic(raw_text)

        # --- ШАГ 3: Если структуры нет — зовем ИИ ---
        if not questions:
            await status_msg.edit_text("🤖 Готовых ответов не нашли. Работает ИИ (10-15 сек)...")
            
            # Обрезаем текст для безопасности (лимит 10к символов)
            safe_text = raw_text[:10000]
            
            ai_output = await generate_quiz_with_ai(safe_text)
            questions = parse_text_logic(ai_output)

        # --- ШАГ 4: Проверка и сохранение ---
        if not questions:
            await status_msg.delete()
            return await message.answer("❌ Не удалось создать тест. Попробуй другой файл.")

        pack = await db.save_quiz_to_db(user, pack_name, questions)
        
        await status_msg.delete()
        await message.answer(
            f"✅ Пакет «{pack.name}» создан!\n📊 Вопросов: {len(questions)}",
            reply_markup=get_file_action_menu()
        )
        await state.clear()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("❌ Произошла ошибка. Проверь логи бота.")