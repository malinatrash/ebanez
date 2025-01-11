import markovify
import os
from pathlib import Path
from typing import List, Optional
from .database import Database
import logging

logger = logging.getLogger(__name__)

class MarkovChainGenerator:
    def __init__(self, state_size=1, min_messages=5):
        """Инициализация генератора"""
        self.db = Database()
        self.state_size = state_size
        self.min_messages = min_messages
        self.model = None
        self.message_counter = 0
        self.rebuild_threshold = 10
        self.models_dir = Path(__file__).parent.parent.parent / 'data' / 'models'
        self.models_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Директория для моделей: {self.models_dir}")
        logger.info("MarkovChainGenerator инициализирован")

    def get_model_path(self, chat_id: int) -> Path:
        """Получение пути к файлу модели для конкретного чата"""
        model_path = self.models_dir / f"model_{chat_id}.json"
        logger.info(f"Путь к модели: {model_path}")
        return model_path

    def add_message(self, chat_id: int, message: str) -> bool:
        """Добавление нового сообщения и обновление модели при необходимости"""
        try:
            if self.db.add_message(chat_id, message):
                # Получаем текущий счетчик сообщений для этого чата
                stats = self.db.get_chat_stats(chat_id)
                total_messages = stats['total_messages']
                
                # Проверяем, нужно ли обновить модель
                if total_messages >= self.min_messages and total_messages % 10 == 0:
                    logger.info(f"Достигнуто {total_messages} сообщений, обновляю модель...")
                    if self.rebuild_model(chat_id):
                        logger.info("Модель успешно обновлена")
                    else:
                        logger.error("Не удалось обновить модель")
                else:
                    logger.info(f"Сообщение добавлено, счетчик: {total_messages % 10}/10")
                return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении сообщения: {e}")
            return False
        return False

    def rebuild_model(self, chat_id: int):
        """Перестройка модели на основе всех сообщений чата"""
        try:
            # Получаем сообщения из базы
            messages = self.db.get_messages(chat_id)
            logger.info(f"Получено {len(messages)} сообщений для построения модели")
            logger.debug(f"Примеры сообщений: {messages[:5]}")
            
            if not messages:
                logger.warning("Нет сообщений для построения модели")
                self.model = None
                return False

            # Фильтруем пустые сообщения и объединяем в текст
            valid_messages = [msg for msg in messages if msg and len(msg.strip()) > 2]
            logger.info(f"Валидных сообщений: {len(valid_messages)}")
            
            if not valid_messages:
                logger.warning("Нет валидных сообщений для построения модели")
                self.model = None
                return False
                
            text = "\n".join(valid_messages)
            
            # Создаем новую модель
            try:
                logger.info(f"Создаю модель с state_size={self.state_size}")
                self.model = markovify.NewlineText(text, state_size=self.state_size, well_formed=False)
                
                for _ in range(10):  # Пробуем 10 раз
                    test_sentence = self.model.make_short_sentence(
                        max_chars=100,
                        min_chars=1,
                        tries=50
                    )
                    if test_sentence:
                        logger.info(f"Тестовое предложение: {test_sentence}")
                        if self.save_model(chat_id):
                            logger.info("Модель успешно создана и сохранена")
                            return True
                        break
                
                logger.error("Не удалось сгенерировать тестовое предложение")
                return False
                    
            except Exception as e:
                logger.error(f"Ошибка при создании модели: {e}")
                self.model = None
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при перестройке модели: {e}")
            self.model = None
            return False
            
    def save_model(self, chat_id: int) -> bool:
        """Сохранение модели в файл"""
        if not self.model:
            logger.error("No model to save")
            return False
            
        try:
            model_path = self.get_model_path(chat_id)
            # Создаем директорию, если её нет
            model_path.parent.mkdir(parents=True, exist_ok=True)
            
            model_json = self.model.to_json()
            if not model_json:
                logger.error("Failed to convert model to JSON")
                return False
                
            with open(model_path, 'w', encoding='utf-8') as f:
                f.write(model_json)
            logger.info(f"Model saved to {model_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            return False

    def load_model(self, chat_id: int) -> bool:
        """Загрузка модели для конкретного чата"""
        try:
            model_path = self.get_model_path(chat_id)
            if model_path.exists():
                with open(model_path, 'r', encoding='utf-8') as f:
                    model_json = f.read()
                    if not model_json:
                        logger.error("Model file is empty")
                        return False
                        
                    self.model = markovify.Text.from_json(model_json)
                    if not self.model:
                        logger.error("Failed to load model from JSON")
                        return False
                        
                    logger.info(f"Model loaded from {model_path}")
                    return True
            else:
                logger.info(f"No existing model found, rebuilding for chat {chat_id}")
                return self.rebuild_model(chat_id)
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self.model = None
            return False

    def generate_response(self, chat_id: int) -> str:
        """Генерация ответа на основе модели"""
        try:
            if not self.model:
                if not self.load_model(chat_id):
                    return None
                    
            # Пробуем сгенерировать предложение несколько раз
            for _ in range(10):
                response = self.model.make_short_sentence(
                    max_chars=100,
                    min_chars=1,
                    tries=50
                )
                if response:
                    return response
                    
            logger.error("Не удалось сгенерировать ответ")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при генерации ответа: {e}")
            return None

    def get_stats(self, chat_id: int) -> str:
        """Получение статистики чата"""
        stats = self.db.get_chat_stats(chat_id)
        model_size = os.path.getsize(self.get_model_path(chat_id)) // 1024 if self.get_model_path(chat_id).exists() else 0
        
        return (
            f"📊 Статистика обучения:\n"
            f"• Сообщений в базе: {stats['total_messages']}\n"
            f"• Новых сообщений до перестройки: {self.rebuild_threshold - self.message_counter}\n"
            f"• Средняя длина сообщения: {stats['avg_message_length']} слов\n"
            f"• Размер базы: {self.db.get_db_size() // 1024}KB\n"
            f"• Размер модели: {model_size}KB\n"
            f"• Готовность к генерации: {'✅' if stats['total_messages'] >= self.min_messages else '❌'}"
        )

    def clear_memory(self, chat_id: int) -> bool:
        """Очистка памяти чата"""
        try:
            # Удаляем сообщения из базы
            self.db.clear_chat_history(chat_id)
            
            # Удаляем файл модели
            model_path = self.get_model_path(chat_id)
            if model_path.exists():
                model_path.unlink()
                logger.info(f"Model file deleted: {model_path}")
            
            self.model = None
            self.message_counter = 0
            logger.info(f"Memory cleared for chat {chat_id}")
            
            return True
        except Exception as e:
            logger.error(f"Error clearing memory: {e}")
            return False
