import fitz  # PyMuPDF
import io
import re
from docx import Document

def parse_text_logic(text):
    questions = []
    # 1. Нормализация (убираем лишние пробелы)
    text = re.sub(r'[ \t]+', ' ', text)
    
    # 2. Делим на блоки по ++++ (разделитель вопросов)
    # Используем регулярку, чтобы ловить 4 и более плюсов
    blocks = re.split(r'\+{4,}', text)
    
    BAD_START_WORDS = ["группа", "members", "преподаватель", "студент", "фио", "результаты", "дата"]

    for block in blocks:
        if not block.strip():
            continue
            
        # Сначала отделяем текст вопроса от блока с ответами
        # В твоем файле вопрос идет до первых =====
        parts = re.split(r'={4,}', block)
        
        if len(parts) < 2:
            continue

        # Первая часть — это всегда вопрос (и возможно мусор сверху)
        raw_question_lines = [l.strip() for l in parts[0].split('\n') if l.strip()]
        if not raw_question_lines:
            continue
            
        # Берем последнюю строку из первой части как текст вопроса
        question_text = raw_question_lines[-1]
        
        # Очистка номера вопроса (типа "1. ", "2) ")
        question_text = re.sub(r'^\d+[\s.)]+', '', question_text).strip()

        # Проверки на валидность вопроса
        if len(question_text) < 5:
            continue
        
        first_word = question_text.lower().split()[0] if question_text else ""
        if first_word in BAD_START_WORDS and len(question_text) < 40:
            continue

        # Обработка вариантов ответов (остальные части после =====)
        options = []
        correct_id = 0
        
        for raw_opt in parts[1:]:
            clean_opt = raw_opt.strip().split('\n')[0].strip() # Берем только первую строку варианта
            if not clean_opt: 
                continue
            
            if len(options) >= 10: # Лимит Telegram
                break

            if clean_opt.startswith("#"):
                correct_id = len(options)
                options.append(clean_opt.replace("#", "").strip())
            else:
                options.append(clean_opt)

        if len(options) >= 2:
            questions.append({
                "question": question_text[:255], # Лимит TG на длину вопроса
                "options": options,
                "correct_option_id": correct_id
            })

    return questions
# --- ВОТ ЭТИХ ФУНКЦИЙ У ТЕБЯ НЕ ХВАТАЛО ДЛЯ ИМПОРТА ---

def parse_pdf_from_memory(file_stream):
    """Извлекает текст из PDF и прогоняет через фильтр"""
    doc = fitz.open(stream=file_stream, filetype="pdf")
    full_text = "".join([page.get_text() for page in doc])
    return parse_text_logic(full_text)

def parse_docx_from_memory(file_stream):
    """Извлекает текст из DOCX и прогоняет через фильтр"""
    doc = Document(file_stream)
    full_text = "\n".join([p.text for p in doc.paragraphs])
    return parse_text_logic(full_text)