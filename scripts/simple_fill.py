import sys
import os
from pathlib import Path
import random

# Добавляем путь к корневой директории проекта
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.services.database import Database

# Базовые слова для генерации сообщений
words = [
    "педики", "аюр", "чмо", "саша", "сосал?", "может", "быдло", "плохо",
    "геи", "блять...", "ого!", "ужас", "норм", "уроды", "токсики", "фу уроды", "погнали в валорант", "господа бизнесмены", "бизнес", 
]

# Эмодзи для добавления в сообщения
emojis = ["😊", "👍", "❤️", "😂", "🤔", "👀", "🔥", "✨", "🙈", "🎉"]

def generate_message():
    """Генерация случайного сообщения"""
    # Выбираем случайное количество слов (от 1 до 4)
    num_words = random.randint(1, 4)
    message = " ".join(random.choice(words) for _ in range(num_words))
    
    # С вероятностью 30% добавляем эмодзи
    if random.random() < 0.1:
        message += " " + random.choice(emojis)
    
    return message

def fill_database(chat_id: int, num_messages: int = 500):
    """Заполнение базы данных сообщениями"""
    db = Database()
    
    print(f"Начинаю заполнение базы данных для чата {chat_id}")
    print(f"Планируется добавить {num_messages} сообщений")
    
    for i in range(num_messages):
        msg = generate_message()
        db.add_message(chat_id, msg)
        if (i + 1) % 50 == 0:
            print(f"Добавлено {i + 1} сообщений")
    
    # Проверяем результат
    stats = db.get_chat_stats(chat_id)
    print("\nГотово!")
    print(f"Всего сообщений в базе: {stats['total_messages']}")
    print(f"Средняя длина сообщения: {stats['avg_message_length']}")

if __name__ == "__main__":
    CHAT_ID = -1002270101072
    NUM_MESSAGES = 100
    
    db = Database()
    db.add_message(CHAT_ID, "педики")
    
    
    # fill_database(CHAT_ID, NUM_MESSAGES)
