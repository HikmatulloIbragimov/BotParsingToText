import fitz  # PyMuPDF
import re
from docx import Document

def parse_text_logic(text):
    questions = []
    
    current_q = None
    current_options = []
    
    # Разбиваем текст на строки и обрабатываем по одной
    for line in text.split('\n'):
        line = line.strip()
        # Игнорируем пустые строки и разделители ====
        if not line or line.startswith('='): 
            continue
        
        # ЛОГИКА ОПРЕДЕЛЕНИЯ ВОПРОСА
        # Если строка заканчивается на '?' или она длинная и в ней нет '#'
        if ('?' in line or len(line) > 40) and '#' not in line:
            # Если до этого мы уже собрали вопрос и у него есть хотя бы 2 ответа — сохраняем
            if current_q and len(current_options) >= 2:
                questions.append({
                    "question": current_q[:255], # Лимит Telegram: 255 символов
                    "options": current_options[:10], # Лимит Telegram: 10 вариантов
                    "correct_option_id": 0 # В этой логике правильный всегда первый
                })
            
            # Начинаем новый вопрос (чистим от цифр в начале: "1. Вопрос" -> "Вопрос")
            current_q = re.sub(r'^\d+[\s.)]+', '', line).replace('#', '').strip()
            current_options = []
            
        # ЛОГИКА ОПРЕДЕЛЕНИЯ ВАРИАНТОВ ОТВЕТА
        elif current_q and len(current_options) < 10:
            is_correct = line.startswith('#')
            # КРИТИЧЕСКИЙ МОМЕНТ: Обрезаем до 100 символов
            clean_opt = line.replace('#', '').strip()[:100] 
            
            if clean_opt:
                if is_correct:
                    # Ставим правильный ответ на первое место (индекс 0)
                    current_options.insert(0, clean_opt)
                else:
                    current_options.append(clean_opt)

    # Не забываем добавить самый последний вопрос из файла
    if current_q and len(current_options) >= 2:
        questions.append({
            "question": current_q[:255], 
            "options": current_options[:10], 
            "correct_option_id": 0
        })
        
    return questions

def extract_text_from_docx(file_stream):
    """Извлекает текст из DOCX"""
    doc = Document(file_stream)
    return "\n".join([p.text for p in doc.paragraphs])

def extract_text_from_pdf(file_stream):
    """Извлекает текст из PDF"""
    doc = fitz.open(stream=file_stream, filetype="pdf")
    return "".join([page.get_text() for page in doc])

# --- ФУНКЦИИ ПАРСИНГА (Для прямой загрузки без ИИ) ---

def parse_pdf_from_memory(file_stream):
    text = extract_text_from_pdf(file_stream)
    return parse_text_logic(text)

def parse_docx_from_memory(file_stream):
    text = extract_text_from_docx(file_stream)
    return parse_text_logic(text)