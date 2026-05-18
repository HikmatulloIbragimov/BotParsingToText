import os
from openai import AsyncOpenAI

# Берем ключ из переменных окружения
client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"), 
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "https://railway.app", # Для статистики OpenRouter
        "X-Title": "QuizMasterBot"
    }
)

async def generate_quiz_with_ai(user_text):
    """
    Отправляет текст в ИИ и получает структурированный тест.
    """
    system_prompt = (
        "Ты — эксперт-аналитик и профессиональный генератор тестов. Твоя задача: внимательно изучить присланный текст "
        "и превратить его в список тестовых вопросов.\n\n"
        "Для каждого вопроса ты должен сформировать ровно 4 варианта ответа, один из которых является правильным.\n\n"
        "СТРОГИЙ ФОРМАТ ОТВЕТА:\n"
        "Ты должен вернуть ответ СТРОГО в формате валидного JSON-массива объектов. "
        "Не пиши никаких вступлений, пояснений, markdown-разметки (НЕ оборачивай код в ```json ... ```). "
        "В твоем ответе должен быть только чистый JSON-массив.\n\n"
        "Структура одного объекта в массиве:\n"
        "{\n"
        '  "question": "Текст вопроса (без нумерации)?",\n'
        '  "options": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"],\n'
        '  "correct_option_id": 0\n'
        "}\n"
        "Где correct_option_id — это индекс правильного ответа в массиве options (число от 0 до 3).\n\n"
        "ЗАПРЕТЫ:\n"
        "Категорически запрещено добавлять любой текст вне JSON-массива. Никаких приветствий или 'Вот ваши тесты:'."
    )

    try:
        # 1. ОБРЕЗАЕМ ТЕКСТ. Это критично для избежания ошибки 400!
        # Возьмем первые 10 000 символов - этого хватит на 5-10 страниц.
        safe_text = user_text[:10000] 

        completion = await client.chat.completions.create(
            # ИСПОЛЬЗУЙ ТОЛЬКО ЭТИ ВАРИАНТЫ:
            model="openrouter/auto", # Работает всегда
            # ИЛИ конкретную модель: "google/gemini-flash-1.5"
            
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Сделай тест из этого текста:\n\n{safe_text}"}
            ],
            temperature=0.3 # Стандартное значение
        )
        return completion.choices[0].message.content
    except Exception as e:
        # Если будет ошибка, мы хотя бы увидим её текст в боте
        return f"ERROR_AI: {str(e)}"