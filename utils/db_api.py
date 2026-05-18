from asgiref.sync import sync_to_async
import logging
from django.db import connections
from quizzes.models import TelegramUser, TestPack, Question, TestSession
class DBApi:
    @staticmethod
    async def get_user(tg_id, username=None):
        try:
            # Принудительно закрываем сломанные/мертвые коннекты перед запросом
            await sync_to_async(connections.close_all)()
            
            numeric_id = int(tg_id) 
            clean_username = str(username) if username else "unknown"

            user, created = await sync_to_async(TelegramUser.objects.get_or_create)(
                user_id=numeric_id,
                defaults={'username': clean_username}
            )
            return user
        except Exception as e:
            logging.error(f"Ошибка в get_user: {e}")
            raise e

    @staticmethod
    async def check_duplicate(user, name):
        """Проверяет, нет ли уже теста с таким названием"""
        return await sync_to_async(lambda: TestPack.objects.filter(
            user=user, name=name
        ).first())()

    @staticmethod
    async def save_quiz_to_db(user, pack_name, questions_data):
        """Сохраняет пак и все вопросы в него одним махом"""
        def _save():
            pack = TestPack.objects.create(user=user, name=pack_name)
            for q in questions_data:
                Question.objects.create(
                    pack=pack,
                    text=q['question'],
                    options=q['options'],
                    correct_option_id=q['correct_option_id']
                )
            return pack
        return await sync_to_async(_save)()

    @staticmethod
    async def get_user_packs_with_count(user):
        """Возвращает список паков с количеством вопросов для каждого"""
        def _get():
            packs = list(TestPack.objects.filter(user=user))
            results = []
            for p in packs:
                # Добавляем количество вопросов прямо в объект, чтобы не дергать базу в цикле потом
                p.q_count = Question.objects.filter(pack=p).count()
                results.append(p)
            return results
        return await sync_to_async(_get)()

    @staticmethod
    async def create_session(user, pack):
        """Создает или обновляет активную сессию теста"""
        session, _ = await sync_to_async(TestSession.objects.update_or_create)(
            user=user,
            defaults={'pack': pack, 'current_question_index': 0, 'is_active': True}
        )
        return session

    @staticmethod
    async def get_active_session(user_id):
        """Находит сессию по ID пользователя (используем в таймерах)"""
        from quizzes.models import TestSession
        return await sync_to_async(lambda: TestSession.objects.filter(
            user__user_id=user_id, 
            is_active=True
        ).select_related('pack').first())()

    @staticmethod
    async def close_session(user_id_or_obj):
        from quizzes.models import TestSession
        # Если пришел объект пользователя, берем его id, иначе используем как есть
        u_id = user_id_or_obj.user_id if hasattr(user_id_or_obj, 'user_id') else user_id_or_obj
        
        def _close():
            # Ищем активную сессию именно этого пользователя
            session = TestSession.objects.filter(user__user_id=u_id, is_active=True).first()
            if session:
                session.is_active = False
                session.save()
                return True
            return False
            
        return await sync_to_async(_close)()


# Создаем экземпляр, чтобы просто импортировать 'db'
db = DBApi()