import sqlite3
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_path = Path(__file__).parent.parent.parent / 'data' / 'chats.db'
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()
        logger.info(f"База данных инициализирована: {self.db_path}")

    def init_db(self):
        """Инициализация базы данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Создаем таблицу для сообщений
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id INTEGER NOT NULL,
                        text TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Создаем индекс для быстрого поиска по chat_id
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_chat_id 
                    ON messages(chat_id)
                ''')
                
                # Проверяем, что таблица создана
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
                if cursor.fetchone():
                    logger.info("Таблица messages существует")
                    # Проверяем количество записей
                    cursor.execute("SELECT COUNT(*) FROM messages")
                    count = cursor.fetchone()[0]
                    logger.info(f"В таблице {count} записей")
                else:
                    logger.error("Таблица messages не создана!")
                
                conn.commit()
                logger.info("Структура базы данных создана успешно")
        except Exception as e:
            logger.error(f"Ошибка при инициализации базы данных: {e}")
            raise

    def add_message(self, chat_id: int, text: str) -> bool:
        """Добавление нового сообщения"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO messages (chat_id, text) VALUES (?, ?)',
                    (chat_id, text)
                )
                conn.commit()
                # Проверяем, что сообщение добавлено
                cursor.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ? AND text = ?', (chat_id, text))
                count = cursor.fetchone()[0]
                if count > 0:
                    logger.info(f"Сообщение успешно добавлено в базу: chat_id={chat_id}, text={text[:50]}...")
                    return True
                else:
                    logger.error("Сообщение не было добавлено в базу")
                    return False
        except Exception as e:
            logger.error(f"Ошибка при добавлении сообщения в базу: {e}")
            return False

    def get_messages(self, chat_id: int, limit: Optional[int] = None) -> List[str]:
        """Получение сообщений для конкретного чата"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Проверяем наличие сообщений
                cursor.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ?', (chat_id,))
                count = cursor.fetchone()[0]
                logger.info(f"Найдено {count} сообщений для chat_id={chat_id}")
                
                if count == 0:
                    return []
                
                # Получаем сообщения
                if limit:
                    cursor.execute(
                        'SELECT text FROM messages WHERE chat_id = ? ORDER BY created_at DESC LIMIT ?',
                        (chat_id, limit)
                    )
                else:
                    cursor.execute(
                        'SELECT text FROM messages WHERE chat_id = ? ORDER BY created_at DESC',
                        (chat_id,)
                    )
                
                messages = [row[0] for row in cursor.fetchall()]
                logger.info(f"Получено {len(messages)} сообщений для chat_id={chat_id}")
                logger.debug(f"Примеры сообщений: {messages[:3]}")
                return messages
        except Exception as e:
            logger.error(f"Ошибка при получении сообщений из базы: {e}")
            return []

    def clear_chat_history(self, chat_id: int) -> bool:
        """Очистка истории конкретного чата"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM messages WHERE chat_id = ?', (chat_id,))
                conn.commit()
                logger.info(f"История чата {chat_id} очищена")
                return True
        except Exception as e:
            logger.error(f"Ошибка при очистке истории чата: {e}")
            return False

    def get_chat_stats(self, chat_id: int) -> dict:
        """Получение статистики чата"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Общее количество сообщений
                cursor.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ?', (chat_id,))
                total_messages = cursor.fetchone()[0]
                
                # Средняя длина сообщения
                cursor.execute('SELECT AVG(LENGTH(text)) FROM messages WHERE chat_id = ?', (chat_id,))
                avg_length = cursor.fetchone()[0] or 0
                
                stats = {
                    'total_messages': total_messages,
                    'avg_message_length': round(avg_length, 1)
                }
                logger.info(f"Получена статистика для chat_id={chat_id}: {stats}")
                return stats
        except Exception as e:
            logger.error(f"Ошибка при получении статистики чата: {e}")
            return {'total_messages': 0, 'avg_message_length': 0}

    def get_db_size(self) -> int:
        """Получение размера базы данных в байтах"""
        try:
            size = self.db_path.stat().st_size
            logger.info(f"Размер базы данных: {size} bytes")
            return size
        except Exception as e:
            logger.error(f"Ошибка при получении размера базы данных: {e}")
            return 0
