import fitz  # PyMuPDF
import re
from docx import Document


def parse_text_logic(text):
    questions = []
    # 1. Очистка от лишних пробелов
    text = re.sub(r'[ \t]+', ' ', text)
    
    # 2. Делим на блоки по ++++ (вопросы)
    blocks = re.split(r'\+{4,}', text)
    
    BAD_START_WORDS = ["группа", "members", "преподаватель", "студент", "фио", "результаты", "дата", "fanidan"]

    for block in blocks:
        if not block.strip():
            continue
            
        # Делим блок на части по =====
        parts = re.split(r'={4,}', block)
        
        if len(parts) < 2:
            continue

        # Берем последнюю осмысленную строку перед первым ===== как вопрос
        raw_question_content = parts[0].strip().split('\n')
        question_text = raw_question_content[-1].strip()
        
        # Убираем цифры в начале "1. ", "2) "
        question_text = re.sub(r'^\d+[\s.)]+', '', question_text).strip()

        # Валидация вопроса
        if len(question_text) < 5:
            continue
        
        first_word = question_text.lower().split()[0] if question_text else ""
        if first_word in BAD_START_WORDS and len(question_text) < 40:
            continue

        options = []
        correct_id = 0
        
        # Обрабатываем варианты (части после первого =====)
        for raw_opt in parts[1:]:
            # Берем только первую строку из части (на случай если там мусор)
            opt_lines = [l.strip() for l in raw_opt.strip().split('\n') if l.strip()]
            if not opt_lines:
                continue
                
            clean_opt = opt_lines[0]
            
            if len(options) >= 10: break # Лимит TG на кол-во кнопок

            if clean_opt.startswith("#"):
                correct_id = len(options)
                # ОБРЕЗАЕМ ДО 100 СИМВОЛОВ (жесткий лимит Telegram)
                options.append(clean_opt.replace("#", "").strip()[:100])
            else:
                # ОБРЕЗАЕМ ДО 100 СИМВОЛОВ
                options.append(clean_opt[:100])

        if len(options) >= 2:
            questions.append({
                # ОБРЕЗАЕМ ВОПРОС ДО 255 СИМВОЛОВ
                "question": question_text[:255],
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