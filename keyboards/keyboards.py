from aiogram.types import InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# 1. Твои текущие функции (оставляем как есть)
def get_creation_method_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📁 Файл (.docx/.pdf)", callback_data="method_file"))
    return builder.as_markup()

def get_manual_creation_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Создать вопрос", request_poll={'type': 'quiz'})],
            [KeyboardButton(text="✅ Завершить")]
        ],
        resize_keyboard=True
    )

# 2. ТА САМАЯ НЕДОСТАЮЩАЯ ФУНКЦИЯ (для quiz_creation.py)
def get_file_action_menu():
    # Мы используем InlineKeyboardMarkup, чтобы кнопки были под сообщением
    buttons = [
        [InlineKeyboardButton(text="🚀 Запустить всё", callback_data="run_all")],
        [InlineKeyboardButton(text="⚙️ Настроить пак (скоро)", callback_data="settings_pack")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# 3. Улучшенная версия запуска конкретного теста
def get_start_quiz_kb(pack_id):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🚀 Начать этот тест", callback_data=f"start_test_{pack_id}"))
    return builder.as_markup()

def get_quizzes_list_kb(packs):
    builder = InlineKeyboardBuilder()
    for pack in packs:
        builder.row(InlineKeyboardButton(
            text=f"📊 {pack.name} ({pack.q_count} вопр.)", 
            # МЕНЯЕМ ЗДЕСЬ:
            callback_data=f"view_pack_{pack.id}" 
        ))
    return builder.as_markup()


def get_stop_confirm_kb():
    builder = InlineKeyboardBuilder()
    # Одна кнопка продолжает, другая — закрывает сессию
    builder.row(InlineKeyboardButton(text="✅ Продолжить тест", callback_data="continue_test"))
    builder.row(InlineKeyboardButton(text="🛑 Завершить и выйти", callback_data="confirm_stop"))
    return builder.as_markup()

def get_stop_confirm_kb():
    builder = InlineKeyboardBuilder()
    # Ставим кнопки в один ряд для компактности
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="continue_test"),
        InlineKeyboardButton(text="🛑 Выйти", callback_data="confirm_stop")
    )
    return builder.as_markup()

def get_pack_menu_kb(pack_id):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать тест", callback_data=f"start_quiz_{pack_id}")],
        [InlineKeyboardButton(text="⚙️ Редактировать", callback_data=f"edit_pack_{pack_id}")],
        [InlineKeyboardButton(text="🗑 Удалить пак", callback_data=f"delete_confirm_{pack_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="quizzes")]
    ])
    return kb  


def get_edit_menu_kb(pack_id):
    buttons = [
        [InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"rename_pack_{pack_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"view_pack_{pack_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)