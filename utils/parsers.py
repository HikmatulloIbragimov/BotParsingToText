import re
import fitz
from docx import Document

def extract_text_from_docx(file_stream):
    """Извлекает текст из DOCX"""
    doc = Document(file_stream)
    return "\n".join([p.text for p in doc.paragraphs])

def extract_text_from_pdf(file_stream):
    """Извлекает текст из PDF"""
    doc = fitz.open(stream=file_stream, filetype="pdf")
    return "".join([page.get_text() for page in doc])

def parse_text_logic(text):
    questions = []
    # Делим на блоки по +++++ (как просим ИИ) или по тройному переносу
    blocks = re.split(r'\+{3,}|\n\n\n', text)
    
    for block in blocks:
        # Чистим блок от пустых строк
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        
        # КРИТИЧНО: Блок должен содержать минимум 1 вопрос и 2 ответа
        # И в блоке ОБЯЗАТЕЛЬНО должен быть символ '#' (правильный ответ)
        if len(lines) < 2 or '#' not in block:
            continue
            
        # ПЕРВАЯ СТРОКА — Вопрос (чистим от цифр и режем до 255 символов)
        question_text = re.sub(r'^\d+[\s.)]+', '', lines[0]).replace('#', '').strip()[:255]
        
        options = []
        correct_id = 0
        
        # ОСТАЛЬНЫЕ СТРОКИ — Варианты
        for raw_line in lines[1:]:
            if raw_line.startswith('='): continue # Игнорим старые разделители
                
            is_correct = raw_line.startswith('#')
            clean_opt = raw_line.replace('#', '').strip()[:100] # Режем до 100 символов (Лимит TG)
            
            if clean_opt:
                if is_correct:
                    correct_id = len(options)
                options.append(clean_opt)
            
            if len(options) >= 10: break # Лимит TG: 10 вариантов

        if len(options) >= 2:
            questions.append({
                "question": question_text,
                "options": options,
                "correct_option_id": correct_id
            })
            
    return questions