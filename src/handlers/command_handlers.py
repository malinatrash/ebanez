from telegram import Update
from telegram.ext import ContextTypes
from .message_handlers import markov_generator, sticker_storage
import logging
import random

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "Привет! 👋\n"
        "Я бот, который учится общаться, анализируя ваши сообщения.\n"
        "Напишите /help чтобы узнать, как со мной работать."
    )
    
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать справку"""
    await update.message.reply_text(
        "*🤖 Команды бота:*\n\n"
        "*Основные:*\n"
        "└─ /start - Начать общение\n"
        "└─ /help - Показать это сообщение\n\n"
        "*Обучение:*\n"
        "└─ /stats - Статистика обучения\n"
        "└─ /gen - Сгенерировать сообщение\n"
        "└─ /clear - Очистить память чата\n"
        "└─ /rebuild - Пересобрать модель\n\n"
        "*Развлечения:*\n"
        "└─ /sticker - Случайный стикер\n"
        "└─ /top - Топ используемых слов\n"
        "└─ /mood - Настроение чата\n\n"
        "❗️ Бот учится на ваших сообщениях.\n"
        "Первая модель создается после 20 сообщений.",
        parse_mode='Markdown'
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику"""
    chat_id = update.effective_chat.id
    stats = markov_generator.get_stats(chat_id)
    await update.message.reply_text(stats)

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сгенерировать сообщение"""
    chat_id = update.effective_chat.id
    response = markov_generator.generate_response(chat_id)
    await update.message.reply_text(response)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистить память чата"""
    chat_id = update.effective_chat.id
    if markov_generator.clear_memory(chat_id):
        await update.message.reply_text(
            "🧹 Память чата очищена!\n"
            "Бот начнет обучение заново."
        )
    else:
        await update.message.reply_text(
            "❌ Произошла ошибка при очистке памяти."
        )

async def rebuild_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принудительное обновление модели"""
    chat_id = update.effective_chat.id
    
    # Проверяем наличие сообщений
    messages = markov_generator.db.get_messages(chat_id)
    if not messages:
        await update.message.reply_text(
            "❌ Нет сообщений для построения модели!\n"
            "Напишите несколько сообщений, чтобы бот мог учиться."
        )
        return
        
    # Проверяем количество валидных сообщений
    valid_messages = [msg for msg in messages if msg and len(msg.strip()) > 2]
    if len(valid_messages) < markov_generator.min_messages:
        await update.message.reply_text(
            f"❌ Недостаточно сообщений для построения модели!\n"
            f"Нужно минимум {markov_generator.min_messages} сообщений, "
            f"а у вас только {len(valid_messages)}."
        )
        return
    
    # Начинаем обновление
    status = await update.message.reply_text("🔄 Обновляю модель...")
    
    try:
        if markov_generator.rebuild_model(chat_id):
            await status.edit_text("✅ Модель успешно обновлена!")
            logger.info(f"Модель для chat_id={chat_id} успешно обновлена")
        else:
            await status.edit_text("❌ Не удалось обновить модель")
            logger.error(f"Не удалось обновить модель для chat_id={chat_id}")
    except Exception as e:
        error_msg = f"❌ Ошибка при обновлении модели: {e}"
        logger.error(error_msg)
        await status.edit_text(error_msg)

async def sticker_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить случайный стикер"""
    if not update.message:
        return
        
    chat_id = update.effective_chat.id
    stickers = sticker_storage.get_stickers(chat_id)
    
    if not stickers:
        await update.message.reply_text("❌ В этом чате пока нет сохраненных стикеров!")
        return
        
    try:
        sticker_id = random.choice(stickers)
        await context.bot.send_sticker(chat_id=chat_id, sticker=sticker_id)
    except Exception as e:
        logger.error(f"Ошибка при отправке стикера: {e}")
        await update.message.reply_text("❌ Не удалось отправить стикер")

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать топ используемых слов"""
    chat_id = update.effective_chat.id
    messages = markov_generator.db.get_messages(chat_id)
    
    if not messages:
        await update.message.reply_text("❌ История сообщений пуста")
        return
        
    # Собираем статистику слов
    word_stats = {}
    for msg in messages:
        for word in msg.lower().split():
            if len(word) > 2:  # Игнорируем короткие слова
                word_stats[word] = word_stats.get(word, 0) + 1
                
    # Сортируем и берем топ-10
    top_words = sorted(word_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Форматируем ответ
    response = "*📈 Топ-10 слов в чате:*\n\n"
    for i, (word, count) in enumerate(top_words, 1):
        response += f"{i}. `{word}`: {count} раз\n"
        
    await update.message.reply_text(response, parse_mode='Markdown')

async def mood_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Анализ настроения чата"""
    chat_id = update.effective_chat.id
    messages = markov_generator.db.get_messages(chat_id)
    
    if not messages:
        await update.message.reply_text("❌ История сообщений пуста")
        return
        
    # Простой анализ настроения по эмодзи и ключевым словам
    positive = ['😊', '😄', '👍', '❤️', 'круто', 'класс', 'супер', 'отлично']
    negative = ['😢', '😠', '👎', '💔', 'плохо', 'ужас', 'отстой']
    
    pos_count = 0
    neg_count = 0
    
    for msg in messages:
        msg_lower = msg.lower()
        for word in positive:
            pos_count += msg_lower.count(word)
        for word in negative:
            neg_count += msg_lower.count(word)
            
    total = pos_count + neg_count
    if total == 0:
        mood = "😐 Нейтральное"
        mood_bar = "▓" * 5 + "░" * 5
    else:
        mood_ratio = pos_count / total
        if mood_ratio > 0.8:
            mood = "🤩 Прекрасное"
        elif mood_ratio > 0.6:
            mood = "😊 Хорошее"
        elif mood_ratio > 0.4:
            mood = "🙂 Нормальное"
        elif mood_ratio > 0.2:
            mood = "😕 Так себе"
        else:
            mood = "😢 Грустное"
        mood_bar = "▓" * int(mood_ratio * 10) + "░" * (10 - int(mood_ratio * 10))
    
    response = (
        f"*🎭 Анализ настроения чата*\n\n"
        f"*Текущее настроение:* {mood}\n"
        f"*Настроение:* [{mood_bar}]\n\n"
        f"*Статистика:*\n"
        f"└─ Позитив: `{pos_count}`\n"
        f"└─ Негатив: `{neg_count}`"
    )
    
    await update.message.reply_text(response, parse_mode='Markdown')
