import asyncio
import os
import io
import logging
import django
from dotenv import load_dotenv

# 1. СТРОГО ПЕРВЫМ ДЕЛОМ - Включаем окружение Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

# ==========================================================
# 2. ПОСЛЕ ЭТОГО - Все остальные импорты (aiogram и файлы проекта)
# ==========================================================
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, BotCommand
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram import types

from keyboards.keyboards import get_stop_confirm_kb, get_main_menu_kb

# Импортируем роутеры из других файлов (теперь Django спит спокойно)
from handlers.payment import router as payment_router
from handlers.quiz_creation import router as creation_router
from handlers.quiz_process import router as process_router

# Настройка окружения и логирования
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Создаем локальный роутер для текущего файла
router = Router()

# --- ХЕНДЛЕРЫ ТЕКУЩЕГО ФАЙЛА (Все строго через @router) ---

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    welcome_text = (
        f"🧠 **QuizMaster AI — Тесты в один клик!**\n\n"
        f"Привет, {message.from_user.first_name}! Сложно создать саморучно опросы с длинными текстами для теста?. 🎓\n\n"
        f"Не проблема , я могу помочь тебе с этим!\n"
        f"🚀 **Что я умею:**\n"
        f"📄 Быстро соберу интерактивный тест из твоих файлов.\n"
        f"🤖 Дострою варианты ответов через ИИ, если есть только вопросы.\n\n"
        f"👇 **Жми кнопку ниже**, отправляй документ и погнали!"
    )
    
    await message.answer(
        welcome_text, 
        reply_markup=get_main_menu_kb(),
        parse_mode="Markdown"
    )

@router.message(Command("help")) # Перевели с @dp на @router
async def help_handler(message: Message):
    await message.answer(
    f"📖 **ИНСТРУКЦИЯ ПО ФОРМАТУ ФАЙЛОВ**\n"
    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    f"Если у тебя есть готовые ответы и ты не хочешь тратить попытки ИИ, "
    f"просто оформи свой `.docx` или `.pdf` файл по этому шаблону:\n\n"
    f"```text\n"
    f"Тут пишется твой вопрос?\n"
    f"# Это вариант правильного ответа\n"
    f"Это обычный неверный ответ\n"
    f"Еще один неверный вариант\n"
    f"++++\n"
    f"```\n\n"
    f"💡 **Важные правила:**\n"
    f"• **`#`** — ставится строго в начале строки перед *правильным* ответом.\n"
    f"• **`++++`** — четыре плюса ставятся на отдельной строке, обозначая *конец* текущего вопроса.\n"
    f"• Если файл пустой или без разметки — просто кидай его, ИИ сделает всё за тебя! 🤖",
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

@router.message(Command("donate")) # Перевели с @dp на @router
async def donate_admin(message: Message):
    await message.answer(
        f"☕ **ПОДДЕРЖКА РАЗРАБОТКИ**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Понравился бот? Ты можешь угостить админа крепким кофе, чтобы "
        f"бот работал еще лучше и быстрее а так же добавить новые возможности для бота!!!, а новые фичи выходили чаще! 🚀\n\n"
        f"💳 **Номер карты (Uzcard/Humo):**\n"
        f"`5614681814089151`\n\n"
        f"✨ _Нажми на номер карты, чтобы он автоматически скопировался! Спасибо за поддержку!_ ❤️",
        parse_mode="Markdown"  # <-- ВОТ ЭТА МАГИЧЕСКАЯ СТРОЧКА ВСЁ ИСПРАВИТ!
    )

# --- НАСТРОЙКА МЕНЮ И ЗАПУСК ---

async def set_main_menu(bot: Bot):
    commands = [
        BotCommand(command='/start', description='Запустить бота'),
        BotCommand(command='/newquiz', description='Создать новый тест'),
        BotCommand(command='/quizzes', description='Мои тесты'),
        BotCommand(command='/help', description='Как пользоваться?'),
        BotCommand(command='/stop', description='Остановить тест'),
        BotCommand(command='/donate', description='Донат для админа'),
    ]
    await bot.set_my_commands(commands)
    
async def main():
    print("🚀 Бот запущен через Django-контекст!")

    # Регистрируем роутеры в правильном порядке
    dp.include_router(process_router)
    dp.include_router(creation_router)
    dp.include_router(router)          # Наш текущий локальный роутер
    dp.include_router(payment_router)  # Роутер платежей Payme
    
    await set_main_menu(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен!")