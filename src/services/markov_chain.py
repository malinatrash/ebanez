import markovify
import os
from pathlib import Path
from .database import Database
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class MarkovChainGenerator:
    def __init__(self, state_size=3, min_messages=50):
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
        
        # Проверяем минимальную длину (2 символа)
        if len(message) < 2:
            return False
            
        # Игнорируем команды и ссылки
        if message.startswith('/') or 'http' in message or 'www.' in message:
            return False
            
        # Разбиваем на слова и проверяем количество значимых слов
        words = [w for w in message.split() if len(w) > 1 or w.isalpha()]
        if len(words) < 1:  # Хотя бы одно значимое слово
            return False
            
        # Проверяем, что сообщение не состоит только из повторяющихся символов
        if len(set(message.lower())) < 2:
            return False
            
        # Игнорируем сообщения, состоящие только из цифр и знаков препинания
        if not any(c.isalpha() for c in message):
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
        """
        Перестройка модели на основе всех сообщений чата
        
        Args:
            chat_id: ID чата для перестройки модели
            
        Returns:
            bool: True если модель успешно перестроена, иначе False
        """
        try:
            logger.info(f"Начало перестройки модели для чата {chat_id}")
            
            # Получаем сообщения из базы
            messages = self.db.get_messages(chat_id)
            logger.info(f"Получено {len(messages)} сообщений для построения модели")
            
            if not messages:
                logger.warning("Нет сообщений для построения модели")
                self.models[chat_id] = None
                self.save_model(chat_id)  # Сохраняем пустую модель
                return False

            # Фильтруем и подготавливаем сообщения
            valid_messages = []
            for msg in messages:
                if self.is_valid_message(msg):
                    # Очищаем и форматируем сообщение
                    msg = msg.strip()
                    # Удаляем упоминания и команды
                    msg = ' '.join(word for word in msg.split() 
                                 if not (word.startswith('@') or word.startswith('/')))
                    if len(msg) > 1:  # Проверяем, что осталось что-то осмысленное
                        # Добавляем маркеры начала и конца предложения
                        processed_msg = f"START {msg} END"
                        valid_messages.append(processed_msg)
                    
            logger.info(f"Валидных сообщений после фильтрации: {len(valid_messages)}")
            
            if len(valid_messages) < self.min_messages:
                logger.warning(f"Недостаточно сообщений для построения модели (минимум {self.min_messages})")
                self.models[chat_id] = None
                self.save_model(chat_id)  # Сохраняем пустую модель
                return False

            # Объединяем сообщения, добавляя перенос строки между ними
            text = "\n".join(valid_messages)
            
            # Сохраняем сырой текст для отладки
            debug_path = self.models_dir / f"debug_{chat_id}.txt"
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(text)
            logger.info(f"Сохранен отладочный файл: {debug_path}")

            try:
                logger.info(f"Создаю модель с state_size={self.state_size}")
                
                # Создаем модель с настройками для лучшей генерации
                model = markovify.NewlineText(
                    text, 
                    state_size=self.state_size,
                    well_formed=False,  # Отключаем строгую проверку для большей гибкости
                    retain_original=True,  # Сохраняем оригинальные предложения
                    max_overlap_ratio=0.7,  # Разрешаем большее перекрытие
                    max_overlap_total=15    # Увеличиваем максимальное перекрытие
                )
                
                # Тестируем модель
                test_success = False
                test_sentences = []
                
                for _ in range(10):  # Делаем несколько попыток генерации
                    try:
                        sentence = model.make_sentence(
                            max_words=25,
                            min_words=3,
                            tries=100,
                            test_output=False
                        )
                        if sentence:
                            sentence = sentence.replace("START ", "").replace(" END", "").strip()
                            if len(sentence.split()) >= 3:  # Проверяем минимальную длину
                                test_sentences.append(sentence)
                                if len(test_sentences) >= 3:  # Нужно минимум 3 валидных предложения
                                    test_success = True
                                    break
                    except Exception as e:
                        logger.warning(f"Ошибка при тестовой генерации: {e}")
                
                if not test_success:
                    logger.error("Не удалось сгенерировать тестовые предложения")
                    if test_sentences:
                        logger.info(f"Полученные тестовые предложения: {test_sentences}")
                    self.models[chat_id] = None
                    self.save_model(chat_id)
                    return False
                
                logger.info(f"Тестовые предложения: {' | '.join(test_sentences[:3])}")
                
                # Сохраняем модель
                self.models[chat_id] = model
                if not self.save_model(chat_id):
                    logger.error("Не удалось сохранить модель")
                    return False
                
                logger.info(f"Модель успешно перестроена и сохранена для чата {chat_id}")
                return True
                
            except Exception as e:
                logger.error(f"Ошибка при создании модели: {e}", exc_info=True)
                self.models[chat_id] = None
                self.save_model(chat_id)
                return False
                
        except Exception as e:
            logger.error(f"Критическая ошибка при перестройке модели: {e}", exc_info=True)
            self.models[chat_id] = None
            self.save_model(chat_id)
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

    def generate_response(self, chat_id: int, input_text: str = None) -> str:
        """
        Генерация ответа на основе модели
        
        Args:
            chat_id: ID чата
            input_text: Опциональный текст для контекста генерации
            
        Returns:
            str: Сгенерированный ответ или None в случае ошибки
        """
        try:
            if chat_id not in self.models or not self.models[chat_id]:
                if not self.load_model(chat_id):
                    return None
            
            # Пробуем разные стратегии генерации
            strategies = [
                # Базовая генерация
                {
                    'max_words': 25,
                    'min_words': 5,
                    'tries': 100,
                    'max_overlap_ratio': 0.7,
                    'max_overlap_total': 15,
                    'max_retries': 30
                },
                # Более длинные ответы
                {
                    'max_words': 40,
                    'min_words': 8,
                    'tries': 150,
                    'max_overlap_ratio': 0.6,
                    'max_overlap_total': 12,
                    'max_retries': 40
                },
                # Короткие реплики
                {
                    'max_words': 15,
                    'min_words': 3,
                    'tries': 80,
                    'max_overlap_ratio': 0.8,
                    'max_overlap_total': 20,
                    'max_retries': 50
                }
            ]
            
            # Если есть входящий текст, пробуем использовать его как основу
            if input_text and len(input_text.split()) > 2:
                try:
                    # Пробуем сгенерировать ответ, начиная с ключевых слов из ввода
                    keywords = [word for word in input_text.split() if len(word) > 3][:3]
                    if keywords:
                        start = random.choice(keywords)
                        response = self.models[chat_id].make_sentence_with_start(
                            start,
                            strict=False,
                            max_words=30,
                            min_words=5,
                            tries=100,
                            max_overlap_ratio=0.7,
                            max_overlap_total=15
                        )
                        if response:
                            response = response.replace("START ", "").replace(" END", "").strip()
                            if len(response.split()) >= 3:
                                return response
                except Exception as e:
                    logger.warning(f"Ошибка при генерации ответа с началом: {e}")
            
            # Пробуем разные стратегии генерации
            for strategy in strategies:
                for _ in range(3):  # Пробуем каждую стратегию несколько раз
                    try:
                        response = self.models[chat_id].make_sentence(
                            max_words=strategy['max_words'],
                            min_words=strategy['min_words'],
                            tries=strategy['tries'],
                            test_output=False,
                            max_overlap_ratio=strategy['max_overlap_ratio'],
                            max_overlap_total=strategy['max_overlap_total'],
                            max_retries=strategy['max_retries']
                        )
                        
                        if response:
                            # Убираем маркеры и лишние пробелы
                            response = response.replace("START ", "").replace(" END", "").strip()
                            words = response.split()
                            
                            # Проверяем минимальную длину и что ответ не совпадает с вводом
                            if len(words) >= 3 and (not input_text or response.lower() != input_text.lower()):
                                # Добавляем знаки препинания, если их нет
                                if not response[-1] in '.!?…':
                                    response += random.choice(['.', '!', '?', '...'])
                                return response
                                
                    except Exception as e:
                        logger.warning(f"Ошибка при генерации ответа: {e}")
                        continue
            
            logger.warning("Не удалось сгенерировать ответ после нескольких попыток")
            return None
            
        except Exception as e:
            logger.error(f"Критическая ошибка при генерации ответа: {e}", exc_info=True)
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
            f"└─ База данных: `{self.db.get_database_size() // 1024}KB`\n"
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
