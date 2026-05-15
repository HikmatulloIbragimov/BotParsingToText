import fitz  # PyMuPDF
import re
from docx import Document

def parse_text_logic(text):
    questions = []
    # Разбиваем по блокам +++++
    blocks = re.split(r'\s*\+{3,}\s*', text)
    
    for block in blocks:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if len(lines) < 2: continue
        
        # Первая строка — всегда вопрос
        q_text = re.sub(r'^\d+[\s.)]+', '', lines[0]).replace('#', '').strip()
        
        options = []
        correct_id = 0
        
        # Все остальные строки — варианты
        for line in lines[1:]:
            if line.startswith('#'):
                correct_id = len(options)
                options.append(line.replace('#', '').strip()[:100])
            else:
                options.append(line.strip()[:100])
        
        if len(options) >= 2:
            questions.append({
                "question": q_text[:255],
                "options": options[:10],
                "correct_option_id": correct_id
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