import markovify
import os
from pathlib import Path
from .database import Database
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class MarkovChainGenerator:
    def __init__(self, state_size=2, min_messages=20):
        """Инициализация генератора"""
        self.db = Database()
        self.state_size = state_size
        self.min_messages = min_messages  # Минимум сообщений для первой модели
        self.rebuild_every = 10  # Перестраивать каждые N сообщений после создания
        self.models: Dict[int, markovify.Text] = {}  # Словарь моделей для каждого чата
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
            
        # Убираем пробелы в начале и конце
        message = message.strip()
        
        # Проверяем минимальную длину (3 символа)
        if len(message) < 3:
            return False
            
        # Проверяем, что сообщение содержит хотя бы одно слово из букв
        has_word = any(word.isalpha() for word in message.split())
        if not has_word:
            return False
            
        # Проверяем, что сообщение не состоит только из повторяющихся символов
        unique_chars = set(message.lower())
        if len(unique_chars) < 2:
            return False
            
        return True

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
                self.models[chat_id] = None
                return False

            # Фильтруем и подготавливаем сообщения
            valid_messages = []
            for msg in messages:
                if self.is_valid_message(msg):
                    # Добавляем маркеры начала и конца предложения
                    processed_msg = f"START {msg.strip()} END"
                    valid_messages.append(processed_msg)
                    
            logger.info(f"Валидных сообщений: {len(valid_messages)}")
            
            if len(valid_messages) < self.min_messages:
                logger.warning(f"Недостаточно сообщений для построения модели (минимум {self.min_messages})")
                return False

            # Объединяем сообщения, добавляя перенос строки между ними
            text = "\n".join(valid_messages)

            try:
                logger.info(f"Создаю модель с state_size={self.state_size}")
                self.models[chat_id] = markovify.NewlineText(
                    text, 
                    state_size=self.state_size,
                    well_formed=True,  # Включаем проверку правильности формирования
                    retain_original=False  # Экономим память
                )
                
                # Пробуем сгенерировать тестовое предложение
                test_sentence = None
                for _ in range(15):  # Больше попыток для лучшего результата
                    try:
                        test_sentence = self.models[chat_id].make_sentence(
                            max_words=20,  # Увеличиваем максимальное количество слов
                            min_words=3,   # Минимум 3 слова для осмысленности
                            tries=150,     # Больше попыток генерации
                            test_output=False
                        )
                        if test_sentence:
                            # Убираем маркеры и лишние пробелы
                            test_sentence = test_sentence.replace("START ", "").replace(" END", "").strip()
                            if len(test_sentence.split()) >= 3:  # Проверяем минимальную длину
                                break
                    except Exception as e:
                        logger.warning(f"Ошибка при генерации тестового предложения: {e}")
                        continue
                
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
        if chat_id not in self.models or not self.models[chat_id]:
            logger.error("No model to save")
            return False
            
        try:
            model_path = self.get_model_path(chat_id)
            # Создаем директорию, если её нет
            model_path.parent.mkdir(parents=True, exist_ok=True)
            
            model_json = self.models[chat_id].to_json()
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
                        
                    self.models[chat_id] = markovify.Text.from_json(model_json)
                    if not self.models[chat_id]:
                        logger.error("Failed to load model from JSON")
                        return False
                        
                    logger.info(f"Model loaded from {model_path}")
                    return True
            else:
                logger.info(f"No existing model found, rebuilding for chat {chat_id}")
                return self.rebuild_model(chat_id)
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self.models[chat_id] = None
            return False

    def generate_response(self, chat_id: int) -> str:
        """Генерация ответа на основе модели"""
        try:
            if chat_id not in self.models or not self.models[chat_id]:
                if not self.load_model(chat_id):
                    return None
                    
            # Пробуем сгенерировать предложение с разными параметрами
            for _ in range(20):  # Больше попыток для лучшего результата
                try:
                    response = self.models[chat_id].make_sentence(
                        max_words=20,  # Увеличиваем максимум слов
                        min_words=3,   # Минимум 3 слова
                        tries=150,     # Больше попыток
                        test_output=False
                    )
                    if response:
                        # Убираем маркеры и лишние пробелы
                        response = response.replace("START ", "").replace(" END", "").strip()
                        if len(response.split()) >= 3:  # Проверяем минимальную длину
                            return response
                except Exception as e:
                    logger.warning(f"Ошибка при генерации ответа: {e}")
                    continue
                    
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
            # Удаляем модель из памяти
            if chat_id in self.models:
                del self.models[chat_id]
            
            # Удаляем файл модели
            model_path = self.get_model_path(chat_id)
            if model_path.exists():
                model_path.unlink()
                
            # Очищаем сообщения в базе данных
            self.db.clear_chat_history(chat_id)
            
            logger.info(f"Память чата {chat_id} очищена")
            return True
        except Exception as e:
            logger.error(f"Ошибка при очистке памяти: {e}")
            return False
