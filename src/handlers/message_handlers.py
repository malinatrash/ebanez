from telegram import Update, ReactionTypeEmoji
from telegram.ext import ContextTypes
from ..services.markov_chain import MarkovChainGenerator
from ..services.sticker_storage import StickerStorage
import logging
import random

# Настраиваем логирование
logger = logging.getLogger(__name__)

markov_generator = MarkovChainGenerator()
sticker_storage = StickerStorage()

# Эмодзи для реакций
REACTIONS = [
    "👍", "❤️", "🔥", "👏", "🤣", "🤔", "👀", "🎉", "🙈", "🤷‍♂️",
    "🫡", "🗿", "🤨", "🥹", "🫢", "🤌", "💅", "🤡", "🥸", "🤪", "🍌", "🤡", "❤️", "💕", "🤣", "💩"
]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка входящего сообщения"""
    chat_id = update.effective_chat.id
    logger.info(f"Получено сообщение от chat_id={chat_id}")
    
    # Проверяем тип сообщения
    if not update.message:
        logger.info("Сообщение пустое")
        return
        
    logger.info(f"Тип сообщения: {type(update.message)}")
    logger.info(f"Атрибуты сообщения: text={update.message.text}, sticker={update.message.sticker}")
    
    # Сохраняем стикеры, если они есть в сообщении
    if update.message.sticker:
        sticker = update.message.sticker
        logger.info(f"Получен стикер: file_id={sticker.file_id}, set_name={sticker.set_name}")
        
        try:
            # Сохраняем текущий стикер
            if sticker_storage.add_sticker(chat_id, sticker.file_id):
                logger.info(f"Стикер {sticker.file_id} успешно сохранен")
            else:
                logger.info(f"Стикер {sticker.file_id} уже существует или не удалось сохранить")
            
            # Если есть набор стикеров, получаем его
            if sticker.set_name:
                sticker_set = await context.bot.get_sticker_set(sticker.set_name)
                logger.info(f"Получен набор стикеров {sticker_set.name} ({len(sticker_set.stickers)} стикеров)")
                
                # Сохраняем все стикеры из набора
                saved_count = 0
                for s in sticker_set.stickers:
                    if sticker_storage.add_sticker(chat_id, s.file_id):
                        saved_count += 1
                logger.info(f"Сохранено {saved_count} новых стикеров из набора {sticker_set.name}")
            
            # Проверяем количество сохраненных стикеров
            saved_stickers = sticker_storage.get_stickers(chat_id)
            logger.info(f"Всего сохранено стикеров для чата {chat_id}: {len(saved_stickers)}")
            
            # Отправляем тот же стикер в ответ
            await context.bot.send_sticker(chat_id=chat_id, sticker=sticker.file_id)
            logger.info(f"Отправлен стикер {sticker.file_id} в ответ")
            
        except Exception as e:
            logger.error(f"Ошибка при обработке стикера: {str(e)}")
        return

    if not update.message or not update.message.text:
        return

    message = update.message.text.strip()
    logger.info(f"Получено сообщение от chat_id={chat_id}: {message}")
    
    if message.startswith('/'):
        return
    
    # Добавляем реакцию (20% шанс)
    if random.random() < 0.2:
        try:
            reaction = random.choice(REACTIONS)
            await context.bot.set_message_reaction(
                chat_id=chat_id,
                message_id=update.message.message_id,
                reaction=[ReactionTypeEmoji(emoji=reaction)]
            )
            logger.info(f"Добавлена реакция {reaction} к сообщению")
        except Exception as e:
            logger.error(f"Ошибка при добавлении реакции: {str(e)}")
    
    # Отправляем случайный стикер (15% шанс)
    if random.random() < 0.15:
        stickers = sticker_storage.get_stickers(chat_id)
        if stickers:
            try:
                sticker_id = random.choice(stickers)
                logger.info(f"Отправка случайного стикера {sticker_id}")
                await context.bot.send_sticker(chat_id=chat_id, sticker=sticker_id)
            except Exception as e:
                logger.error(f"Ошибка при отправке стикера: {str(e)}")
        else:
            logger.info(f"Нет доступных стикеров для chat_id={chat_id}")
    
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
                            reaction=[ReactionTypeEmoji(emoji=random.choice(REACTIONS))]
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
