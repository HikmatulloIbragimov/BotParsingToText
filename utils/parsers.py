import fitz  # PyMuPDF
import re
from docx import Document

def parse_text_logic(text):
    questions = []
    
    # Разбиваем текст на блоки по разделителю +++++
    # Если в файле нет +++++, будем делить по двойному переносу
    blocks = re.split(r'\+{3,}|\n\n\n', text)
    
    for block in blocks:
        # Убираем лишние пробелы и пустые строки внутри блока
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        
        if len(lines) < 2:
            continue
            
        # ПЕРВАЯ СТРОКА — это всегда вопрос.
        # Убираем нумерацию (типа 212.) и обрезаем до 255 символов (лимит TG)
        question_text = re.sub(r'^\d+[\s.)]+', '', lines[0]).replace('#', '').strip()[:255]
        
        options = []
        correct_id = 0
        
        # ОСТАЛЬНЫЕ СТРОКИ — это варианты
        for raw_line in lines[1:]:
            # Пропускаем технические разделители, если они попали в блок
            if raw_line.startswith('='):
                continue
                
            is_correct = raw_line.startswith('#')
            # КРИТИЧНО: Обрезаем каждый вариант до 100 символов
            clean_opt = raw_line.replace('#', '').strip()[:100]
            
            if clean_opt:
                if is_correct:
                    correct_id = len(options)
                options.append(clean_opt)
                
            # В одном опросе Telegram может быть не более 10 вариантов
            if len(options) >= 10:
                break

        if len(options) >= 2:
            questions.append({
                "question": question_text,
                "options": options,
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