import fitz  # PyMuPDF
import re
from docx import Document

def parse_text_logic(text):
    """Универсальная логика: превращает текст с ++++ и ==== в список словарей"""
    questions = []
    text = re.sub(r'[ \t]+', ' ', text)
    blocks = re.split(r'\+{4,}', text)
    
    BAD_START_WORDS = ["группа", "members", "преподаватель", "студент", "фио", "результаты", "дата", "fanidan"]

    for block in blocks:
        if not block.strip(): continue
        parts = re.split(r'={4,}', block)
        if len(parts) < 2: continue

        raw_question_content = parts[0].strip().split('\n')
        question_text = raw_question_content[-1].strip()
        question_text = re.sub(r'^\d+[\s.)]+', '', question_text).strip()

        if len(question_text) < 5: continue
        
        first_word = question_text.lower().split()[0] if question_text else ""
        if first_word in BAD_START_WORDS and len(question_text) < 40:
            continue

        options = []
        correct_id = 0
        
        for raw_opt in parts[1:]:
            opt_lines = [l.strip() for l in raw_opt.strip().split('\n') if l.strip()]
            if not opt_lines: continue
            clean_opt = opt_lines[0]
            
            if len(options) >= 10: break

            if clean_opt.startswith("#"):
                correct_id = len(options)
                options.append(clean_opt.replace("#", "").strip()[:100])
            else:
                options.append(clean_opt[:100])

        if len(options) >= 2:
            questions.append({
                "question": question_text[:255],
                "options": options,
                "correct_option_id": correct_id
            })
    return questions

# --- ФУНКЦИИ ИЗВЛЕЧЕНИЯ ТЕКСТА (Для ИИ) ---

def get_raw_text_from_docx(file_stream):
    """Просто достает текст из DOCX для отправки в ИИ"""
    doc = Document(file_stream)
    return "\n".join([p.text for p in doc.paragraphs])

def get_raw_text_from_pdf(file_stream):
    """Просто достает текст из PDF для отправки в ИИ"""
    doc = fitz.open(stream=file_stream, filetype="pdf")
    return "".join([page.get_text() for page in doc])

# --- ФУНКЦИИ ПАРСИНГА (Для прямой загрузки) ---

def parse_pdf_from_memory(file_stream):
    text = get_raw_text_from_pdf(file_stream)
    return parse_text_logic(text)

def parse_docx_from_memory(file_stream):
    text = get_raw_text_from_docx(file_stream)
    return parse_text_logic(text)