import logging
from asgiref.sync import sync_to_async
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
        try:
            await sync_to_async(connections.close_all)()
            return await sync_to_async(lambda: TestPack.objects.filter(
                user=user, name=name
            ).first())()
        except Exception as e:
            logging.error(f"Ошибка в check_duplicate: {e}")
            raise e

    @staticmethod
    async def save_quiz_to_db(user, pack_name, questions_data):
        """Сохраняет пак и все вопросы в него одним махом"""
        try:
            await sync_to_async(connections.close_all)()
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
        except Exception as e:
            logging.error(f"Ошибка в save_quiz_to_db: {e}")
            raise e

    @staticmethod
    async def get_user_packs_with_count(user):
        """Возвращает список паков с количеством вопросов для каждого"""
        try:
            await sync_to_async(connections.close_all)()
            def _get():
                packs = list(TestPack.objects.filter(user=user))
                results = []
                for p in packs:
                    p.q_count = Question.objects.filter(pack=p).count()
                    results.append(p)
                return results
            return await sync_to_async(_get)()
        except Exception as e:
            logging.error(f"Ошибка в get_user_packs_with_count: {e}")
            raise e

    @staticmethod
    async def create_session(user, pack):
        """Создает или обновляет активную сессию теста"""
        try:
            await sync_to_async(connections.close_all)()
            session, _ = await sync_to_async(TestSession.objects.update_or_create)(
                user=user,
                defaults={'pack': pack, 'current_question_index': 0, 'is_active': True}
            )
            return session
        except Exception as e:
            logging.error(f"Ошибка в create_session: {e}")
            raise e

    @staticmethod
    async def get_active_session(user_id):
        """Находит сессию по ID пользователя (используем в таймерах)"""
        try:
            await sync_to_async(connections.close_all)()
            return await sync_to_async(lambda: TestSession.objects.filter(
                user__user_id=user_id, 
                is_active=True
            ).select_related('pack').first())()
        except Exception as e:
            logging.error(f"Ошибка в get_active_session: {e}")
            raise e

    @staticmethod
    async def close_session(user_id_or_obj):
        try:
            await sync_to_async(connections.close_all)()
            u_id = user_id_or_obj.user_id if hasattr(user_id_or_obj, 'user_id') else user_id_or_obj
            
            def _close():
                session = TestSession.objects.filter(user__user_id=u_id, is_active=True).first()
                if session:
                    session.is_active = False
                    session.save()
                    return True
                return False
                
            return await sync_to_async(_close)()
        except Exception as e:
            logging.error(f"Ошибка в close_session: {e}")
            raise e


# Создаем экземпляр для экспорта во внешние файлы
db = DBApi()