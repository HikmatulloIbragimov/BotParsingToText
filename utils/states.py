from aiogram.fsm.state import StatesGroup, State

class QuizCreation(StatesGroup):
    waiting_for_name = State()   
    waiting_for_content = State()

class QuizProcess(StatesGroup):
    is_running = State()


class EditPack(StatesGroup):
    waiting_for_name = State()