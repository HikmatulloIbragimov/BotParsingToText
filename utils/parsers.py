import fitz  # PyMuPDF
import re
from docx import Document

def parse_text_logic(text):
    questions = []
    # Разбиваем текст на блоки по плюсикам или двойным переносам
    raw_blocks = re.split(r'\+{2,}|\n\n', text)
    
    current_q = None
    current_options = []
    
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('='): continue
        
        # Если строка заканчивается на '?' или это длинное предложение без '#'
        if ('?' in line or len(line) > 40) and '#' not in line:
            # Если у нас уже был накоплен вопрос — сохраняем его
            if current_q and len(current_options) >= 2:
                questions.append({
                    "question": current_q[:255],
                    "options": current_options[:10],
                    "correct_option_id": 0
                })
            
            # Начинаем новый вопрос
            current_q = re.sub(r'^\d+[\s.)]+', '', line).replace('#', '').strip()
            current_options = []
            
        # Если строка — это ответ (с решеткой или после вопроса)
        elif current_q and len(current_options) < 10:
            is_correct = line.startswith('#')
            clean_opt = line.replace('#', '').strip()
            
            if clean_opt:
                if is_correct:
                    current_options.insert(0, clean_opt) # Правильный всегда первый
                else:
                    current_options.append(clean_opt)

    # Добавляем последний вопрос
    if current_q and len(current_options) >= 2:
        questions.append({"question": current_q[:255], "options": current_options, "correct_option_id": 0})
        
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