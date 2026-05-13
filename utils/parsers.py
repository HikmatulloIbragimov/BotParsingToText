import fitz  # PyMuPDF
import re
from docx import Document

def parse_text_logic(text):
    questions = []
    # Предварительная чистка: убираем лишние пробелы в строках
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Разбиваем на блоки по ++++ (разделитель вопросов)
    # Регулярка \s*\+{4,}\s* найдет плюсики, даже если вокруг них пробелы или переносы
    blocks = re.split(r'\s*\+{4,}\s*', text)
    
    BAD_START_WORDS = ["группа", "members", "преподаватель", "студент", "фио", "результаты", "дата", "fanidan", "текст", "задание"]

    for block in blocks:
        block = block.strip()
        if not block: continue
        
        # Разбиваем блок на вопрос и варианты по ====
        parts = re.split(r'\s*={4,}\s*', block)
        if len(parts) < 2: continue

        # --- ЧИСТКА ВОПРОСА (parts[0]) ---
        # Мы берем всё, что до первых ==== и чистим от лишних строк
        q_lines = [l.strip() for l in parts[0].split('\n') if l.strip()]
        if not q_lines: continue
        
        # Обычно ИИ пишет вопрос в самом конце вводного блока
        question_text = q_lines[-1] 
        
        # Удаляем "Вопрос №...", цифры в начале и случайные решетки
        question_text = re.sub(r'(?i)вопрос\s*(№|n|#)?\s*\d*', '', question_text).strip()
        question_text = re.sub(r'^\d+[\s.)]+', '', question_text).strip()
        question_text = question_text.replace('#', '').strip()

        # Проверка на длину и стоп-слова
        if len(question_text) < 5: continue
        first_word = question_text.lower().split()[0] if question_text else ""
        if first_word in BAD_START_WORDS and len(question_text) < 40:
            continue

        # --- ЧИСТКА ВАРИАНТОВ (parts[1:]) ---
        options = []
        correct_id = 0
        
        for raw_opt in parts[1:]:
            opt_lines = [l.strip() for l in raw_opt.strip().split('\n') if l.strip()]
            if not opt_lines: continue
            
            clean_opt = opt_lines[0] # Берем только первую строку варианта
            
            if len(options) >= 10: break # Ограничение Telegram на 10 вариантов

            if clean_opt.startswith("#"):
                correct_id = len(options)
                options.append(clean_opt.replace("#", "").strip()[:100])
            else:
                options.append(clean_opt.replace("#", "").strip()[:100])

        if len(options) >= 2:
            questions.append({
                "question": question_text[:255], # Лимит Telegram на длину вопроса
                "options": options,
                "correct_option_id": correct_id
            })
    return questions
# --- ФУНКЦИИ ИЗВЛЕЧЕНИЯ ТЕКСТА (Для отправки в ИИ) ---

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