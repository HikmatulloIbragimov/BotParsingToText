import io
import logging
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

# Твои модули
from utils.ai_engine import generate_quiz_with_ai
from utils.db_api import db
from utils.states import QuizCreation
from keyboards.keyboards import (
    get_creation_method_kb, 
    get_file_action_menu
)

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
        f"📝 **Создание нового теста**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Для начала давай определимся с темой. "
        f"Как мы назовем твой новый пакет тестов?\n\n"
        f"✍️ _Например: Модуль по аудиту, История Узбекистана, Лекция 5._\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 **На следующем шаге ты сможешь скинуть файл:**\n"
        f"• С готовой разметкой (вопросы + ответы)\n"
        f"• Или просто список «голых» вопросов — и тогда мы призовем ИИ! 🤖"
    )
    
    await message.answer(instruction_text, parse_mode="Markdown")

@router.message(QuizCreation.waiting_for_name)
async def process_quiz_name(message: Message, state: FSMContext):
    # Сохраняем имя в FSM (у тебя тут своя логика сохранения)
    await state.update_data(quiz_name=message.text)
    
    # Меняем состояние на ожидание документа
    await state.set_state(QuizCreation.waiting_for_file)
    
    file_instruction = (
        f"🔥 **Отличное название! Теперь дело за малым**\n\n"
        f"📂 Пожалуйста, отправь мне файл документа (`.docx` или `.pdf`).\n\n"
        f"📖 **Как устроен парсер готовых тестов:**\n"
        f"Если в твоем файле уже есть варианты, оформи их так:\n"
        f"```text\n"
        f"Вопрос?\n"
        f"# Правильный ответ\n"
        f"Неверный вариант 1\n"
        f"Неверный вариант 2\n"
        f"++++\n"
        f"```\n"
        f"⚠️ **Важно:** Разделитель `++++` ставится в конце каждого вопроса!\n\n"
        f"🤖 **У тебя просто список вопросов без ответов?**\n"
        f"Ничего страшного! Скидывай файл как есть. Если парсер не найдет разметку `++++`, я автоматически предложу тебе подключить ИИ, чтобы он сам заполнил варианты! ✨"
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

        # --- ШАГ 3: Если структуры нет — зовем ИИ ---
        if not questions:
            await status_msg.edit_text("🤖 Готовых ответов не нашли. Работает ИИ (10-15 сек)...")
            
            # Обрезаем текст для безопасности OpenRouter
            safe_text = raw_text[:10000]
            
            ai_output = await generate_quiz_with_ai(safe_text)
                     
            # Парсим то, что вернул ИИ
            questions = parse_text_logic(ai_output)

        # --- ШАГ 4: Проверка и сохранение ---
        if not questions:
            await status_msg.delete()
            return await message.answer("❌ Не удалось найти или создать вопросы. Проверь формат файла.")

        # Сохраняем пакет в базу
        pack = await db.save_quiz_to_db(user, pack_name, questions)
        
        await status_msg.delete()
        await message.answer(
            f"✅ Пакет «{pack.name}» создан!\n📊 Вопросов загружено: {len(questions)}",
            reply_markup=get_file_action_menu()
        )
        await state.clear()

    except Exception as e:
        logging.error(f"Ошибка при обработке файла: {e}")
        await message.answer(f"❌ Произошла ошибка: {str(e)[:100]}")