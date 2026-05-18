import io
import logging
import re
import json  # Добавили стандартный модуль для работы с JSON
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram import types
from asgiref.sync import sync_to_async  

# Импортируем модель для прямого свежего обращения к БД
from quizzes.models import TelegramUser  

# Твои модули
from utils.ai_engine import generate_quiz_with_ai
from utils.db_api import db
from utils.states import QuizCreation
from keyboards.keyboards import (
    get_creation_method_kb, 
    get_file_action_menu
)

# Импортируем функции из parsers.py 
# (parse_text_logic остается здесь, так как он нужен ниже для обработки файлов с готовой разметкой)
from utils.parsers import (
    extract_text_from_docx as get_raw_text_from_docx, 
    extract_text_from_pdf as get_raw_text_from_pdf, 
    parse_text_logic
)

router = Router()

# --- 1. ВХОДНОЙ ФИЛЬТР: ПРОВЕРКА ПРИ СТАРТЕ ---
@router.message(Command("newquiz"))
@router.message(F.text == "📝 Создать тест")
async def cmd_new_quiz(message: Message, state: FSMContext):
    user = await db.get_user(tg_id=message.from_user.id, username=message.from_user.username)
    
    if not user.is_premium and user.free_attempts_left <= 0 and user.balance < 3000:
        await message.answer(
            "❌ **Доступ заблокирован! Недостаточно средств.**\n\n"
            "У вас закончились бесплатные попытки, а на балансе 0 сум.\n"
            "Создание новых тестов через нейросеть требует ресурсов сервера. 🧠\n\n"
            "Перейдите в 👤 **Мой профиль**, чтобы пополнить баланс или приобрести Премиум-доступ!",
            parse_mode="Markdown"
        )
        return  

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
    await state.update_data(quiz_name=message.text)
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

    user = await db.get_user(tg_id=message.from_user.id, username=message.from_user.username)
    data = await state.get_data()
    pack_name = data.get("quiz_name") or message.document.file_name

    status_msg = await message.answer("⏳ Анализирую файл...")
    
    try:
        file_io = io.BytesIO()
        file = await message.bot.get_file(message.document.file_id)
        await message.bot.download_file(file.file_path, file_io)
        file_io.seek(0)

        if file_name.endswith('.docx'):
            raw_text = get_raw_text_from_docx(file_io)
        else:
            raw_text = get_raw_text_from_pdf(file_io)

        # 🔥 ВАЖНОЕ ИСПРАВЛЕНИЕ: ПРОВЕРКА НА ПРЕДВАРИТЕЛЬНЫЙ ПАРСИНГ ТЕКСТА
        if not raw_text or len(raw_text.strip()) < 20:
            await status_msg.delete()
            await message.answer(
                "❌ **Ошибка: Не удалось создать из файла нужный тест пак!**\n\n"
                "Я проверил файл , но там нету нужных информаций*\n\n"
                "ℹ️ **Возможные причины:**\n"
                "1. Внутри нету ни вопросов с опциями или без них чтобы ии смог приняться за дело!!\n"
                "2. Документ зашифрован или поврежден.\n"
                "⚠️ Пожалуйста, отправьте нормальный текстовый документ с лекцией или вопросами.",
                parse_mode="Markdown"
            )
            await state.clear()  # Сбрасываем стейт создания, чтобы не зависать
            return  # Завершаем хендлер, код ниже (вызов ИИ) НЕ СРАБОТАЕТ!

        # Если текст нормальный, пробуем искать там готовую разметку (для ручных файлов пользователей)
        questions = parse_text_logic(raw_text)

        # Если печатный текст есть, но разметки нет — вот тогда честно предлагаем ИИ
        if not questions:
            await status_msg.delete()
            await state.update_data(raw_text_for_ai=raw_text)
            
            ai_card_photo = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=1000"
            
            ai_offer_text = (
                f"🔮 **Обнаружены вопросы без ответов!**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Я внимательно изучил твой файл. Готовых вариантов ответов и разметки (`++++`) внутри нет.\n\n"
                f"🤖 **Подключить ИИ к работе?**\n"
                f"Наш интеллект сам прочитает файл, найдет правильные ответы в интернете/базе и сгенерирует полноценный интерактивный тест за 15 секунд!\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👇 _Выбери действие:_"
            )
            
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

        # Сохраняем тест в базу данных (если разметка была внутри ручного файла)
        pack = await db.save_quiz_to_db(user, pack_name, questions)
        
        # Списание средств за готовый файл
        fresh_user = await sync_to_async(TelegramUser.objects.get)(user_id=message.from_user.id)
        if not fresh_user.is_premium:
            if fresh_user.free_attempts_left > 0:
                fresh_user.free_attempts_left -= 1
                await message.answer(f"📉 Использована 1 бесплатная попытка. Осталось: {fresh_user.free_attempts_left}")
            else:
                fresh_user.balance -= 3000
                await message.answer(f"🪙 С баланса списано 3 000 сум. Оставшийся баланс: {fresh_user.balance:,} сум")
            await sync_to_async(fresh_user.save)()

        await status_msg.delete()
        
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
            reply_markup=get_file_action_menu(pack.id),
            parse_mode="Markdown"
        )
        await state.clear()

    except Exception as e:
        logging.error(f"Ошибка при обработке файла: {e}")
        await message.answer(f"❌ Произошла ошибка: {str(e)[:100]}")


@router.callback_query(F.data == "confirm_ai_generation")
async def process_ai_generation(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    raw_text = user_data.get("raw_text_for_ai")
    pack_name = user_data.get("quiz_name")
    
    if not raw_text:
        await callback.answer()
        return await callback.message.answer("❌ Ошибка: данные файла потеряны. Начни создание заново.")
    
    user = await db.get_user(tg_id=callback.from_user.id, username=callback.from_user.username)
    
    status_msg = await callback.message.answer(
        "📡 **Устанавливаю соединение с ИИ...**\n"
        "⏳ `[■■□□□□□□□□] 20%` \n\n"
        "ℹ️ _Отправляем запрос на сервера генерации..._",
        parse_mode="Markdown"
    )
    
    # Чтобы не ловить ошибки, если сообщение уже удалено
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    try:
        # 🔥 УМНАЯ ОЧИСТКА И ОБРЕЗКА ПО ВОПРОСАМ (СТРОКАМ) 🔥
        all_lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
        
        # Берем только первые 15 вопросов из файла для стабильной генерации
        target_lines = all_lines[:15]
        
        safe_text = "\n".join(target_lines)
        
        await status_msg.edit_text(
            f"🧠 **ИИ проводит глубокий анализ вопросов (Взято первых: {len(target_lines)})...**\n"
            f"⏳ `[■■■■■□□□□□] 50%` \n\n"
            f"ℹ️ _Ищем правильные ответы и генерируем ложные варианты..._",
            parse_mode="Markdown"
        )
        
        # Отправляем этот аккуратный пакет ИИ
        ai_output = await generate_quiz_with_ai(safe_text)
        
        await status_msg.edit_text(
            "🧪 **Синтезирую вопросы и упаковываю варианты...**\n"
            "⏳ `[■■■■■■■■□□] 80%` \n\n"
            "ℹ️ _Проверяем совместимость с Telegram квизами..._",
            parse_mode="Markdown"
        )
        
        # 🔥 ВМЕСТО parse_text_logic ИСПОЛЬЗУЕМ ВСТРОЕННЫЙ JSON ПАРСЕР 🔥
        try:
            # На случай, если ИИ вопреки запрету обернул JSON в теги ```json ... ```, очищаем их
            clean_output = ai_output.replace("```json", "").replace("```", "").strip()
            
            # Превращаем JSON-строку от ИИ сразу в готовый список словарей Python!
            raw_questions = json.loads(clean_output)
            
            if not isinstance(raw_questions, list):
                raw_questions = []
        except Exception as json_e:
            logging.error(f"Ошибка парсинга JSON от ИИ: {json_e}")
            raw_questions = []
        
        if not raw_questions:
            try:
                await status_msg.delete()
            except Exception:
                pass
            return await callback.bot.send_message(
                chat_id=callback.from_user.id, 
                text="❌ ИИ не смог корректно составить вопросы. Попробуй другой файл."
            )

        # 🔥 ВОТ ОН — ФИКС ОШИБКИ ВАЛИДАЦИИ ДАННЫХ ИИ 🔥
        # Принудительно очищаем данные и переводим correct_option_id строго в тип INT
        validated_questions = []
        for q in raw_questions:
            try:
                correct_id = int(q.get("correct_option_id", 0))
            except (ValueError, TypeError):
                correct_id = 0  # Дефолтное значение, если прилетел совсем мусор
                
            validated_questions.append({
                "question": str(q.get("question", ""))[:255].strip(),
                "options": [str(opt)[:100].strip() for opt in q.get("options", []) if opt],
                "correct_option_id": correct_id  # Теперь тут железно целое число!
            })
            
        # Сохраняем уже валидированные и безопасные вопросы в базу
        pack = await db.save_quiz_to_db(user, pack_name, validated_questions)
        
        # Списание попыток / баланса
        fresh_user = await sync_to_async(TelegramUser.objects.get)(user_id=callback.from_user.id)
        if not fresh_user.is_premium:
            if fresh_user.free_attempts_left > 0:
                fresh_user.free_attempts_left -= 1
                await callback.bot.send_message(
                    chat_id=callback.from_user.id, 
                    text=f"📉 Использована 1 бесплатная попытка. Осталось: {fresh_user.free_attempts_left}"
                )
            else:
                fresh_user.balance -= 3000
                await callback.bot.send_message(
                    chat_id=callback.from_user.id, 
                    text=f"🪙 С баланса списано 3 000 сум. Оставшийся баланс: {fresh_user.balance:,} сум"
                )
            await sync_to_async(fresh_user.save)()

        try:
            await status_msg.delete()
        except Exception:
            pass
        
        success_card = (
            f"🎉 **ПАКЕТ ТЕСТОВ УСПЕШНО СОЗДАН!**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 **Название пакета:** *{pack_name}*\n"
            f"📊 **Сгенерировано через ИИ:** `{len(validated_questions)}` шт.\n"
            f"🔑 **Статус:** `Полностью готов` ✅\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 _Магия ИИ сработала! Вопросы получили варианты ответов и бережно сохранены в твой профиль._"
        )
        
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text=success_card,
            reply_markup=get_file_action_menu(pack.id),
            parse_mode="Markdown"
        )
        await state.clear()
        
    except Exception as e:
        logging.error(f"Ошибка ИИ генерации: {e}")
        try:
            await status_msg.edit_text(f"❌ Произошла ошибка при работе ИИ: {str(e)[:100]}")
        except Exception:
            await callback.bot.send_message(
                chat_id=callback.from_user.id, 
                text=f"❌ Произошла ошибка при работе ИИ: {str(e)[:100]}"
            )
        
    await callback.answer()


@router.callback_query(F.data == "cancel_quiz_creation")
async def cancel_quiz_creation(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.bot.send_message(chat_id=callback.from_user.id, text="🛑 Создание теста отменено. Ты вернулся в главное меню.")
    await callback.answer()