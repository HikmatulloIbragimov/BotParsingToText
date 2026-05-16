import asyncio
import os
import io
import logging
import django
from dotenv import load_dotenv
from keyboards.keyboards import get_stop_confirm_kb, get_main_menu_kb
from aiogram import Router
# 1. ПЕРВЫМ ДЕЛОМ - Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

# 2. ПОСЛЕ ЭТОГО - Импорты из Django и Aiogram
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BotCommand
from aiogram.filters import CommandStart, Command
from handlers.quiz_creation import router as creation_router
from handlers.quiz_process import router as process_router
from aiogram.fsm.context import FSMContext
from aiogram import types

# 3. Настройка окружения и логирования
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
user_sessions = {}
router = Router()
# --- ХЕНДЛЕРЫ ---

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    # На всякий случай чистим старые состояния, если юзер перезапускает бота
    await state.clear()
    
    welcome_text = (
        f"🧠 **QuizMaster AI — Тесты в один клик!**\n\n"
        f"Привет, {message.from_user.first_name}! Сложно создать саморучно опросы с длинными текстами для теста?. 🎓\n\n"
        f"Не проблема , я могу помочь тебе с этим!\n"
        f"🚀 **Что я умею:**\n"
        f"📄 Быстро соберу интерактивный тест из твоих файлов.(`.docx` или `.pdf`)\n"
        f"🤖 Дострою варианты ответов через ИИ, если есть только вопросы.\n\n"
        f"👇 **Жми кнопку ниже**, отправляй документ и погнали!"
    )
    
    await message.answer(
        welcome_text, 
        reply_markup=get_main_menu_kb(),
        parse_mode="Markdown"
    )

@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "📖 **Инструкция по формату:**\n\n"
        "Вопрос?\n"
        "# Правильный ответ\n"
        "Неверный ответ\n"
        "++++",
        parse_mode="Markdown"
    )

@router.message(Command("stop"))
async def cmd_stop_ask(message: Message):
    await message.answer(
        "⚠️ **Вы уверены, что хотите прервать тест?**\n"
        "Ваш текущий прогресс не будет сохранен.",
        reply_markup=get_stop_confirm_kb(),
        parse_mode="Markdown"
    )

### донат

@dp.message(Command("donate"))
async def donate_admin(message: Message):
    await message.answer(
    "Помогите админу чтобы купить кофе\n"
    "986000500343425"
    )

# --- ЗАПУСК ---

async def set_main_menu(bot: Bot):
    commands = [
        BotCommand(command='/start', description='Запустить бота '),
        BotCommand(command='/newquiz', description='создать новый тест'),
        BotCommand(command='/quizzes', description='мои тесты'),
        BotCommand(command='/help', description='Как пользоваться? '),
        BotCommand(command='/stop', description='Остановить тест '),
        BotCommand(command='/donate', description='Донат для админа '),
    ]
    await bot.set_my_commands(commands)
    
    
async def main():
    print("🚀 Бот запущен через Django-контекст!")

    dp.include_router(process_router)
    dp.include_router(creation_router)
    dp.include_router(router)

    await set_main_menu(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен!")