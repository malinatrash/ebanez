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
        "🤖 Я умею:\n\n"
        "/start - Начать общение\n"
        "/stats - Показать статистику обучения\n"
        "/gen - Сгенерировать случайное сообщение\n"
        "/clear - Очистить память этого чата\n"
        "/rebuild - Обновить модель\n"
        "/sticker - Отправить случайный стикер\n\n"
        "❗️ Важно: я учусь на ваших сообщениях, поэтому сначала ответы могут быть странными"
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
