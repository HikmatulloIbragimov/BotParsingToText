import fitz  # PyMuPDF
import io
import re
from docx import Document

def parse_text_logic(text):
    questions = []
    # 1. Нормализация
    text = re.sub(r'[ \t]+', ' ', text)
    
    # 2. Делим на блоки по ++++
    blocks = re.split(r'\+{4,}', text)
    
    BAD_START_WORDS = ["группа", "members", "преподаватель", "студент", "фио", "результаты", "дата"]

    for block in blocks:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        clean_lines = [l for l in lines if not any(mark in l for mark in ["===", "---"])]

        if len(clean_lines) < 3: 
            continue

        question_text = re.sub(r'^\d+[\s.)]+', '', clean_lines[0]).strip()
        first_word = question_text.lower().split()[0] if question_text else ""
        
        if first_word in BAD_START_WORDS and len(question_text) < 40:
            continue

        if len(question_text) < 8:
            continue

        options = []
        correct_id = 0
        
        for opt in clean_lines[1:]:
            if len(options) >= 10: break
            clean_opt = opt.strip()
            if not clean_opt: continue

            if clean_opt.startswith("#"):
                correct_id = len(options)
                options.append(clean_opt.replace("#", "").strip())
            else:
                options.append(clean_opt)

        if len(options) >= 2:
            questions.append({
                "question": question_text[:500],
                "options": options,
                "correct_option_id": correct_id
            })

    if len(questions) < 3:
        return [] 

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