import os
from typing import List, Optional
import logging
from datetime import datetime
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database as MongoDatabase

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        # Получаем URI из переменной окружения или используем значение по умолчанию
        mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/ebanez')
        self.client = MongoClient(mongodb_uri)
        self.db: MongoDatabase = self.client.get_database()
        self.messages: Collection = self.db.messages
        self.init_db()
        logger.info(f"База данных MongoDB инициализирована: {mongodb_uri}")

    def init_db(self):
        """Инициализация базы данных"""
        try:
            # Создаем индекс для быстрого поиска по chat_id
            self.messages.create_index('chat_id')
            
            # Проверяем подключение
            self.db.command('ping')
            
            # Получаем количество сообщений
            count = self.messages.count_documents({})
            logger.info(f"В коллекции messages {count} документов")
            logger.info("База данных MongoDB успешно инициализирована")
            
        except Exception as e:
            logger.error(f"Ошибка при инициализации базы данных: {e}")

    def add_message(self, chat_id: int, text: str) -> bool:
        """Добавить новое сообщение"""
        try:
            result = self.messages.insert_one({
                'chat_id': chat_id,
                'text': text,
                'created_at': datetime.utcnow()
            })
            logger.info(f"Сообщение успешно добавлено в базу: chat_id={chat_id}, text={text[:20]}...")
            return bool(result.inserted_id)
        except Exception as e:
            logger.error(f"Ошибка при добавлении сообщения: {e}")
            return False

    def get_messages(self, chat_id: int, limit: Optional[int] = None) -> List[str]:
        """Получить список сообщений для чата"""
        try:
            query = {'chat_id': chat_id}
            cursor = self.messages.find(query).sort('created_at', -1)
            
            if limit:
                cursor = cursor.limit(limit)
            
            messages = [doc['text'] for doc in cursor]
            logger.info(f"Получено {len(messages)} сообщений для chat_id={chat_id}")
            return messages
            
        except Exception as e:
            logger.error(f"Ошибка при получении сообщений: {e}")
            return []

    def get_chat_stats(self, chat_id: int) -> dict:
        """Получить статистику чата"""
        try:
            pipeline = [
                {'$match': {'chat_id': chat_id}},
                {'$group': {
                    '_id': None,
                    'total_messages': {'$sum': 1},
                    'avg_message_length': {'$avg': {'$strLenCP': '$text'}}
                }}
            ]
            
            result = list(self.messages.aggregate(pipeline))
            
            if result:
                stats = {
                    'total_messages': result[0]['total_messages'],
                    'avg_message_length': round(result[0]['avg_message_length'], 1)
                }
            else:
                stats = {'total_messages': 0, 'avg_message_length': 0}
                
            logger.info(f"Получена статистика для chat_id={chat_id}: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            return {'total_messages': 0, 'avg_message_length': 0}

    def get_message_count(self, chat_id: int) -> int:
        """Получить количество сообщений в чате"""
        try:
            count = self.messages.count_documents({'chat_id': chat_id})
            logger.info(f"Найдено {count} сообщений для chat_id={chat_id}")
            return count
        except Exception as e:
            logger.error(f"Ошибка при подсчете сообщений: {e}")
            return 0

    def get_database_size(self) -> int:
        """Получить размер базы данных в байтах"""
        try:
            stats = self.db.command('dbStats')
            size = stats.get('dataSize', 0)
            logger.info(f"Размер базы данных: {size} bytes")
            return size
        except Exception as e:
            logger.error(f"Ошибка при получении размера базы данных: {e}")
            return 0

    def clear_chat_history(self, chat_id: int) -> bool:
        """Очистка истории конкретного чата"""
        try:
            result = self.messages.delete_many({'chat_id': chat_id})
            deleted_count = result.deleted_count
            logger.info(f"Удалено {deleted_count} сообщений для chat_id={chat_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при очистке истории чата: {e}")
            return False
