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
    # Делим на блоки по +++++ или по тройному переносу
    blocks = re.split(r'\+{3,}|\n\n\n', text)
    
    for block in blocks:
        # Чистим блок от пустых строк
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        
        # В блоке ОБЯЗАТЕЛЬНО должен быть символ '#' (правильный ответ) и хотя бы 2 строки
        if len(lines) < 2 or '#' not in block:
            continue
            
        question_parts = []
        option_lines = []
        
        # Нам нужно понять, где заканчивается вопрос и начинаются ответы.
        # Все строки ДО первой строки, содержащей '#' или явные маркеры ответов — это ВОПРОС.
        is_collecting_question = True
        
        for line in lines:
            if line.startswith('='): 
                continue # Игнорим разделители
                
            # Если мы собирали вопрос, но наткнулись на решетку (#) — значит, вопрос кончился, пошли ответы!
            if is_collecting_question and line.startswith('#'):
                is_collecting_question = False
                
            # Дополнительная эвристика: если строка короткая и мы уже собрали массивный вопрос, 
            # либо если есть маркеры вроде A), B), 1) — можно тоже переключать. Но решетка — главный якорь.
            
            if is_collecting_question:
                question_parts.append(line)
            else:
                option_lines.append(line)
                
        # Склеиваем весь вопрос в одну строку через пробел
        full_question_text = " ".join(question_parts)
        # Очищаем от цифр в начале (например, "5. Вопрос" -> "Вопрос") и режем под лимит TG
        question_text = re.sub(r'^\d+[\s.)]+', '', full_question_text).replace('#', '').strip()[:255]
        
        options = []
        correct_id = 0
        
        # Обрабатываем собранные строки ответов
        for raw_line in option_lines:
            is_correct = raw_line.startswith('#')
            clean_opt = raw_line.replace('#', '').strip()[:100] # Режем до 100 символов (Лимит TG)
            
            if clean_opt:
                if is_correct:
                    correct_id = len(options)
                options.append(clean_opt)
            
            if len(options) >= 10: 
                break # Лимит TG: 10 вариантов

        # Если собрали жизнеспособный тест — добавляем
        if len(options) >= 2:
            questions.append({
                "question": question_text,
                "options": options,
                "correct_option_id": correct_id
            })
            
    return questions