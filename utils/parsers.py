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
    # Делим на блоки по +++++ или по тройному переносу строки
    blocks = re.split(r'\+{3,}|\n\n\n', text)
    
    for block in blocks:
        # Чистим блок от пустых строк
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        
        # В блоке ОБЯЗАТЕЛЬНО должен быть символ '#' (правильный ответ) и хотя бы 2 строки
        if len(lines) < 2 or '#' not in block:
            continue
            
        question_parts = []
        option_lines = []
        
        # Флаг сбора: True — собираем вопрос, False — пошли ответы
        is_collecting_question = True
        
        for line in lines:
            # Если строка — это разделитель ответов =====, то вопрос ТОЧНО закончился
            if line.startswith('='):
                is_collecting_question = False
                continue # Сам разделитель нам в ответах не нужен
                
            # Если разделителя не было, но строка начинается с # — это тоже стопроцентный ответ
            if is_collecting_question and line.startswith('#'):
                is_collecting_question = False

            if is_collecting_question:
                question_parts.append(line)
            else:
                option_lines.append(line)
                
        # Склеиваем весь вопрос в одну строку через пробел
        full_question_text = " ".join(question_parts)
        
        # Очищаем от цифр в начале (например, "5. Вопрос" -> "Вопрос")
        question_text = re.sub(r'^\d+[\s.)]+', '', full_question_text).replace('#', '').strip()
        
        # Красиво режем под лимит Telegram (300 символов для обычных опросов, но лучше с запасом 255), 
        # добавляя три точки в конце, если текст оборвался
        if len(question_text) > 255:
            question_text = question_text[:252] + "..."
        
        options = []
        correct_id = 0
        
        # Обрабатываем собранные строки ответов
        for raw_line in option_lines:
            is_correct = raw_line.startswith('#')
            clean_opt = raw_line.replace('#', '').strip()
            
            # Лимит Telegram на длину одного ответа — строго 100 символов
            if len(clean_opt) > 100:
                clean_opt = clean_opt[:97] + "..."
            
            if clean_opt:
                if is_correct:
                    correct_id = len(options)
                options.append(clean_opt)
            
            if len(options) >= 10: 
                break # Лимит Telegram: максимум 10 вариантов в одном опреосе

        # Если собрали жизнеспособный тест (есть вопрос и хотя бы 2 ответа) — добавляем
        if len(options) >= 2 and question_text:
            questions.append({
                "question": question_text,
                "options": options,
                "correct_option_id": correct_id
            })
            
    return questions