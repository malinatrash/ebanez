import os
import random
import logging
from typing import Optional, List
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database as MongoDatabase

logger = logging.getLogger(__name__)

class StickerStorage:
    def __init__(self):
        # Получаем URI из переменной окружения или используем значение по умолчанию
        mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/ebanez')
        self.client = MongoClient(mongodb_uri)
        self.db: MongoDatabase = self.client.get_database()
        self.stickers: Collection = self.db.stickers
        self._init_storage()
        logger.info("Инициализация StickerStorage с MongoDB")

    def _init_storage(self):
        """Инициализация хранилища"""
        try:
            # Создаем индекс для быстрого поиска по chat_id
            self.stickers.create_index('chat_id')
            
            # Получаем количество стикеров
            total_stickers = self.stickers.count_documents({})
            logger.info(f"В базе {total_stickers} стикеров")
            
        except Exception as e:
            logger.error(f"Ошибка при инициализации хранилища стикеров: {e}")

    def add_sticker(self, chat_id: int, sticker_id: str) -> bool:
        """Добавить стикер в хранилище"""
        try:
            # Проверяем, существует ли уже такой стикер
            exists = self.stickers.find_one({
                'chat_id': chat_id,
                'sticker_id': sticker_id
            })
            
            if not exists:
                result = self.stickers.insert_one({
                    'chat_id': chat_id,
                    'sticker_id': sticker_id
                })
                logger.info(f"Добавлен новый стикер: chat_id={chat_id}, sticker_id={sticker_id}")
                return bool(result.inserted_id)
            else:
                logger.info(f"Стикер уже существует: chat_id={chat_id}, sticker_id={sticker_id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при добавлении стикера: {e}")
            return False

    def get_random_sticker(self, chat_id: int) -> Optional[str]:
        """Получить случайный стикер из хранилища"""
        try:
            # Получаем все стикеры для чата
            stickers = list(self.stickers.find({'chat_id': chat_id}))
            
            if stickers:
                # Выбираем случайный стикер
                sticker = random.choice(stickers)
                logger.info(f"Получен случайный стикер {sticker['sticker_id']} для chat_id={chat_id}")
                return sticker['sticker_id']
            else:
                logger.info(f"Нет стикеров для chat_id={chat_id}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при получении случайного стикера: {e}")
            return None

    def get_stickers(self, chat_id: int) -> List[str]:
        """Получить все стикеры чата"""
        try:
            stickers = list(self.stickers.find({'chat_id': chat_id}))
            sticker_ids = [s['sticker_id'] for s in stickers]
            logger.info(f"Получено {len(sticker_ids)} стикеров для chat_id={chat_id}")
            return sticker_ids
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка стикеров: {e}")
            return []

    def clear_stickers(self, chat_id: int) -> bool:
        """Очистить все стикеры чата"""
        try:
            result = self.stickers.delete_many({'chat_id': chat_id})
            deleted_count = result.deleted_count
            logger.info(f"Удалено {deleted_count} стикеров для chat_id={chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при очистке стикеров: {e}")
            return False
