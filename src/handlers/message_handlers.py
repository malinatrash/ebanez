from telegram import Update
from telegram.ext import ContextTypes
from ..services.markov_chain import MarkovChainGenerator
import logging
import random

# Настраиваем логирование
logger = logging.getLogger(__name__)

markov_generator = MarkovChainGenerator()

# Эмодзи для реакций
REACTIONS = [
    "👍", "❤️", "🔥", "👏", "🤣", "🤔", "👀", "🎉", "🙈", "🤷‍♂️",
    "🫡", "🗿", "🤨", "🥹", "🫢", "🤌", "💅", "🤡", "🥸", "🤪"
]

# Словарь для хранения стикеров по чатам
chat_stickers = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка входящего сообщения"""
    chat_id = update.effective_chat.id
    
    # Сохраняем стикеры, если они есть в сообщении
    if update.message.sticker:
        if chat_id not in chat_stickers:
            chat_stickers[chat_id] = []
        sticker_id = update.message.sticker.file_id
        if sticker_id not in chat_stickers[chat_id]:
            chat_stickers[chat_id].append(sticker_id)
            logger.info(f"Новый стикер сохранен для chat_id={chat_id}")
        return

    if not update.message or not update.message.text:
        return

    message = update.message.text.strip()
    logger.info(f"Получено сообщение от chat_id={chat_id}: {message}")
    
    if message.startswith('/'):
        return
    
    # Добавляем реакцию
    if random.random() < 1:
        try:
            reaction = random.choice(REACTIONS)
            await context.bot.set_message_reaction(
                chat_id=chat_id,
                message_id=update.message.message_id,
                reaction=[{"type": "emoji", "emoji": reaction}]
            )
            logger.info(f"Добавлена реакция {reaction} к сообщению")
        except Exception as e:
            logger.error(f"Ошибка при добавлении реакции: {e}")
    
    # Отправляем случайный стикер (100% шанс)
    if chat_id in chat_stickers and chat_stickers[chat_id]:
        try:
            sticker_id = random.choice(chat_stickers[chat_id])
            await context.bot.send_sticker(
                chat_id=chat_id,
                sticker=sticker_id
            )
            logger.info(f"Отправлен случайный стикер в chat_id={chat_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке стикера: {e}")
    
    # Добавляем сообщение в базу данных
    if markov_generator.add_message(chat_id, message):
        logger.info(f"Сообщение успешно добавлено в базу")
        
        # Проверяем статистику
        stats = markov_generator.db.get_chat_stats(chat_id)
        logger.info(f"Текущая статистика: {stats}")
        
        # Иногда отвечаем на сообщения (33% шанс)
        if context.bot_data.get('last_response', 0) % 3 == 0:
            response = markov_generator.generate_response(chat_id)
            if response:
                sent_message = await update.message.reply_text(response)
                
                # Иногда добавляем реакцию к своему сообщению (10% шанс)
                if random.random() < 0.1:
                    try:
                        await context.bot.set_message_reaction(
                            chat_id=chat_id,
                            message_id=sent_message.message_id,
                            reaction=[{"type": "emoji", "emoji": random.choice(REACTIONS)}]
                        )
                    except Exception as e:
                        logger.error(f"Ошибка при добавлении реакции к своему сообщению: {e}")
                    
        context.bot_data['last_response'] = context.bot_data.get('last_response', 0) + 1
    else:
        logger.error(f"Не удалось добавить сообщение в базу")

async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка добавления бота в чат"""
    if not update.my_chat_member or not update.my_chat_member.new_chat_member:
        return
        
    # Бот был добавлен в чат
    if update.my_chat_member.new_chat_member.status in ['member', 'administrator']:
        chat_id = update.effective_chat.id
        logger.info(f"Бот добавлен в чат {chat_id}")
        
        # Получаем историю сообщений
        messages = []
        try:
            async for message in context.bot.get_chat_history(chat_id, limit=100):
                if message.text:
                    messages.append(message.text)
            logger.info(f"Получено {len(messages)} сообщений из истории")
        except Exception as e:
            logger.error(f"Ошибка при получении истории: {e}")
            
        # Добавляем сообщения в базу
        added_count = 0
        for message in messages:
            if markov_generator.add_message(chat_id, message):
                added_count += 1
        logger.info(f"Добавлено {added_count} сообщений в базу")
            
        # Отправляем приветственное сообщение
        await context.bot.send_message(
            chat_id=chat_id,
            text="Привет! 👋 Я буду учиться на ваших сообщениях и иногда отвечать. Используйте /help чтобы узнать больше."
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий inline кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'option1':
        response = markov_generator.generate_response()
        await query.message.reply_text(response)
    elif query.data == 'option2':
        stats = markov_generator.get_stats()
        await query.message.reply_text(stats)
