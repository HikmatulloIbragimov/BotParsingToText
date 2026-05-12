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
        "Ты — профессиональный составитель образовательных тестов. "
        "Твоя задача: прочитать текст и создать из него тест. "
        "Для каждого вопроса найди 1 правильный ответ и 2-3 неверных.\n\n"
        "СТРОГИЙ ФОРМАТ ОТВЕТА:\n"
        "Вопрос...\n"
        "# Правильный ответ\n"
        "=====\n"
        "Неверный вариант 1\n"
        "=====\n"
        "Неверный вариант 2\n"
        "+++++\n"
        "ПРАВИЛА:\n"
        "1. Между вопросами СТРОГО +++++\n"
        "2. Между вариантами СТРОГО =====\n"
        "3. Правильный ответ всегда начинается с #\n"
        "4. Ответы должны быть короткими (до 100 символов)."
    )

    try:
        completion = await client.chat.completions.create(
            # Можно использовать "google/gemini-flash-1.5" или "openrouter/auto"
            model="google/gemini-flash-1.5", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Сделай тест из этого текста:\n\n{user_text}"}
            ],
            temperature=0.3 # Ставим низкую температуру для точности
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"ERROR_AI: {e}"