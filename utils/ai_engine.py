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
        "Ты — эксперт-аналитик. Твоя задача: превратить текст в список тестов.\n"
        "Для каждого вопроса выдели 1 ПРАВИЛЬНЫЙ ответ и 3 НЕВЕРНЫХ.\n\n"
        "СТРОГИЙ ФОРМАТ:\n"
        "Текст вопроса без нумерации?\n"
        "#Правильный ответ\n"
        "Неверный вариант 1\n"
        "Неверный вариант 2\n"
        "Неверный вариант 3\n"
        "+++++\n\n"
        "ЗАПРЕТЫ: Не пиши 'Вопрос №', не используй цифры в начале строк, не используй разделитель '====='."
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