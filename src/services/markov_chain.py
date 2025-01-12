import markovify
import os
from pathlib import Path
from .database import Database
import logging

logger = logging.getLogger(__name__)

class MarkovChainGenerator:
    def __init__(self, state_size=1, min_messages=20):
        """Инициализация генератора"""
        self.db = Database()
        self.state_size = state_size
        self.min_messages = min_messages  # Минимум сообщений для первой модели
        self.rebuild_every = 10  # Перестраивать каждые N сообщений после создания
        self.model = None
        self.models_dir = Path(__file__).parent.parent.parent / 'data' / 'models'
        self.models_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Директория для моделей: {self.models_dir}")
        logger.info("MarkovChainGenerator инициализирован")

    def get_model_path(self, chat_id: int) -> Path:
        """Получение пути к файлу модели для конкретного чата"""
        model_path = self.models_dir / f"model_{chat_id}.json"
        logger.info(f"Путь к модели: {model_path}")
        return model_path

    def is_valid_message(self, message: str) -> bool:
        """Проверка валидности сообщения для обучения"""
        if not message or not isinstance(message, str):
            return False
        # Сообщение должно быть не пустым и содержать хотя бы 2 символа
        return len(message.strip()) > 2

    def add_message(self, chat_id: int, message: str) -> tuple[bool, bool]:
        """
        Добавление нового сообщения и обновление модели при необходимости
        Возвращает: (сообщение_добавлено, сообщение_валидно)
        """
        try:
            if not self.is_valid_message(message):
                logger.info("Сообщение не прошло валидацию")
                return False, False

            # Добавляем сообщение в базу
            if not self.db.add_message(chat_id, message):
                return False, True

            stats = self.db.get_chat_stats(chat_id)
            total_messages = stats['total_messages']
            model_exists = self.get_model_path(chat_id).exists()

            if not model_exists:
                # Модель еще не создана
                if total_messages >= self.min_messages:
                    logger.info(f"Достигнуто {total_messages} сообщений, создаю первую модель...")
                    if self.rebuild_model(chat_id):
                        logger.info("Первая модель успешно создана")
                    else:
                        logger.error("Не удалось создать первую модель")
            else:
                # Модель уже существует, проверяем необходимость перестройки
                if total_messages % self.rebuild_every == 0:
                    logger.info(f"Достигнуто {total_messages} сообщений, обновляю модель...")
                    if self.rebuild_model(chat_id):
                        logger.info("Модель успешно обновлена")
                    else:
                        logger.error("Не удалось обновить модель")

            return True, True

        except Exception as e:
            logger.error(f"Ошибка при добавлении сообщения: {e}")
            return False, False

    def rebuild_model(self, chat_id: int):
        """Перестройка модели на основе всех сообщений чата"""
        try:
            # Получаем сообщения из базы
            messages = self.db.get_messages(chat_id)
            logger.info(f"Получено {len(messages)} сообщений для построения модели")
            
            if not messages:
                logger.warning("Нет сообщений для построения модели")
                self.model = None
                return False

            # Фильтруем пустые сообщения и объединяем в текст
            valid_messages = [msg for msg in messages if self.is_valid_message(msg)]
            logger.info(f"Валидных сообщений: {len(valid_messages)}")
            
            if len(valid_messages) < self.min_messages:
                logger.warning(f"Недостаточно сообщений для построения модели (минимум {self.min_messages})")
                self.model = None
                return False
                
            text = "\n".join(valid_messages)
            
            # Создаем новую модель
            try:
                logger.info(f"Создаю модель с state_size={self.state_size}")
                self.model = markovify.NewlineText(text, state_size=self.state_size, well_formed=False)
                
                # Пробуем сгенерировать тестовое предложение
                test_sentence = None
                for _ in range(5):  # Уменьшаем количество попыток для первой модели
                    test_sentence = self.model.make_short_sentence(
                        max_chars=100,
                        min_chars=1,
                        tries=50
                    )
                    if test_sentence:
                        break
                
                if not test_sentence:
                    logger.warning("Не удалось сгенерировать тестовое предложение")
                    return False
                
                logger.info(f"Тестовое предложение: {test_sentence}")
                if self.save_model(chat_id):
                    logger.info("Модель успешно создана и сохранена")
                    return True
                    
            except Exception as e:
                logger.error(f"Ошибка при создании модели: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при перестройке модели: {e}")
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
        model_path = self.get_model_path(chat_id)
        model_exists = model_path.exists()
        model_size = os.path.getsize(model_path) // 1024 if model_exists else 0
        
        # Проверяем статус модели
        if not model_exists:
            valid_messages = len([msg for msg in self.db.get_messages(chat_id) if self.is_valid_message(msg)])
            model_status = f"⏳ Сбор сообщений ({valid_messages}/{self.min_messages})"
            progress = (valid_messages / self.min_messages) * 100
            progress_bar = "▓" * int(progress/10) + "░" * (10 - int(progress/10))
        else:
            model_status = "✅ Модель готова"
            progress_bar = "▓" * 10
            
        messages_until_action = (
            self.min_messages - stats['total_messages'] 
            if not model_exists 
            else self.rebuild_every - (stats['total_messages'] % self.rebuild_every)
        )
        
        action_type = "создания" if not model_exists else "обновления"
        
        return (
            f"📊 *Статистика чата*\n\n"
            f"*Сообщения:*\n"
            f"└─ Всего в базе: `{stats['total_messages']}`\n"
            f"└─ Средняя длина: `{stats['avg_message_length']:.1f}` символов\n\n"
            f"*Хранилище:*\n"
            f"└─ База данных: `{self.db.get_db_size() // 1024}KB`\n"
            f"└─ Модель: `{model_size}KB`\n\n"
            f"*Состояние модели:*\n"
            f"└─ Статус: {model_status}\n"
            f"└─ Прогресс: [{progress_bar}]\n"
            f"└─ До {action_type}: `{messages_until_action}` сообщений"
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
            logger.info(f"Memory cleared for chat {chat_id}")
            
            return True
        except Exception as e:
            logger.error(f"Error clearing memory: {e}")
            return False
