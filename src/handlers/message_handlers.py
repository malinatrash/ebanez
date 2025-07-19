from telegram import Update, ReactionTypeEmoji
from telegram.ext import ContextTypes
from ..services.markov_chain import MarkovChainGenerator
from ..services.sticker_storage import StickerStorage
from ..services.weather_service import WeatherService
import logging
import random
import asyncio

# Настраиваем логирование
logger = logging.getLogger(__name__)

markov_generator = MarkovChainGenerator()
sticker_storage = StickerStorage()
weather_service = WeatherService()

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
    logger.info(
        f"Атрибуты сообщения: text={update.message.text}, sticker={update.message.sticker}")

    # Сохраняем стикеры, если они есть в сообщении
    if update.message.sticker:
        sticker = update.message.sticker
        logger.info(
            f"Получен стикер: file_id={sticker.file_id}, set_name={sticker.set_name}")

        try:
            # Сохраняем текущий стикер
            if sticker_storage.add_sticker(chat_id, sticker.file_id):
                logger.info(f"Стикер {sticker.file_id} успешно сохранен")
            else:
                logger.info(
                    f"Стикер {sticker.file_id} уже существует или не удалось сохранить")

            # Если есть набор стикеров, получаем его
            if sticker.set_name:
                sticker_set = await context.bot.get_sticker_set(sticker.set_name)
                logger.info(
                    f"Получен набор стикеров {sticker_set.name} ({len(sticker_set.stickers)} стикеров)")

                # Сохраняем все стикеры из набора
                saved_count = 0
                for s in sticker_set.stickers:
                    if sticker_storage.add_sticker(chat_id, s.file_id):
                        saved_count += 1
                logger.info(
                    f"Сохранено {saved_count} новых стикеров из набора {sticker_set.name}")

            # Проверяем количество сохраненных стикеров
            saved_stickers = sticker_storage.get_stickers(chat_id)
            logger.info(
                f"Всего сохранено стикеров для чата {chat_id}: {len(saved_stickers)}")

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

    # Обрабатываем текстовое сообщение
    if update.message.text:
        message_text = update.message.text.strip()

        # Пропускаем команды и короткие сообщения
        if message_text.startswith('/') or len(message_text.split()) < 2:
            return

        # Добавляем сообщение в базу для обучения
        message_added, is_valid = markov_generator.add_message(
            chat_id, message_text)
        model_path = markov_generator.get_model_path(chat_id)

        # Проверяем, нужно ли обновить модель
        stats = markov_generator.db.get_chat_stats(chat_id)
        total_messages = stats['total_messages'] if stats else 0

        # Реагируем на валидные сообщения
        if message_added and is_valid:
            try:
                # Если модель еще не создана, показываем прогресс
                if not model_path.exists():
                    progress = (total_messages / 50) * 100  # 50 - min_messages
                    progress = min(int(progress), 100)
                    progress_bar = "▓" * (progress // 10) + \
                        "░" * (10 - (progress // 10))

                    if total_messages % 5 == 0:  # Каждые 5 сообщений
                        await update.message.reply_text(
                            f"Собираю сообщения для обучения... {progress}%\n"
                            f"[{progress_bar}]\n"
                            f"Нужно еще {max(0, 50 - total_messages)} сообщений"
                        )
                else:
                    # Если модель уже есть, иногда реагируем эмодзи
                    if random.random() < 0.1:  # 10% шанс на реакцию
                        await update.message.set_reaction([ReactionTypeEmoji(random.choice(REACTIONS))])

            except Exception as e:
                logger.error(f"Ошибка при обработке сообщения: {e}")

        # Отвечаем на сообщения только если модель существует
        if model_path.exists():
            # Определяем вероятность ответа на основе длины сообщения
            message_length = len(message_text.split())
            # 5-15% в зависимости от длины
            reply_chance = 0.05 + (0.01 * min(message_length, 10))

            # Увеличиваем шанс ответа, если бота упомянули
            if update.message.entities and any(e.type == 'mention' for e in update.message.entities):
                reply_chance = 1  # 100% шанс ответа при упоминании

            # Случайным образом решаем, отвечать ли на сообщение
            if random.random() < reply_chance:
                # Показываем статус "печатает..."
                status_msg = await update.message.reply_chat_action('typing')

                try:
                    # Генерируем ответ с учетом контекста сообщения
                    response = markov_generator.generate_response(
                        chat_id, message_text)

                    if response:
                        # Добавляем небольшую задержку для естественности
                        await asyncio.sleep(1 + random.random() * 2)

                        # Отвечаем на сообщение
                        await update.message.reply_text(
                            response,
                            reply_to_message_id=update.message.message_id
                        )
                except Exception as e:
                    logger.error(f"Ошибка при генерации ответа: {e}")

            # 15% шанс добавить реакцию
            elif response_type < 0.10:
                try:
                    reaction = random.choice(REACTIONS)
                    await update.message.set_reaction([ReactionTypeEmoji(reaction)])
                    logger.info(f"Добавлена реакция {reaction} к сообщению")
                except Exception as e:
                    logger.error(f"Ошибка при добавлении реакции: {e}")

            # 10% шанс отправить стикер
            elif response_type < 0.10:
                sticker_id = sticker_storage.get_random_sticker(chat_id)
                if sticker_id:
                    try:
                        await update.message.reply_sticker(sticker_id)
                        logger.info(f"Отправлен стикер {sticker_id}")
                    except Exception as e:
                        logger.error(f"Ошибка при отправке стикера: {str(e)}")
                else:
                    logger.info(
                        f"Нет доступных стикеров для chat_id={chat_id}")


async def handle_weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /weather - отправляет информацию о погоде"""
    chat_id = update.effective_chat.id
    logger.info(f"Получена команда /weather в чате {chat_id}")

    try:
        weather_message = await weather_service.get_weather_and_traffic()
        await update.message.reply_text(weather_message)
        logger.info(f"Отправлена информация о погоде в чат {chat_id}")
    except Exception as e:
        error_message = "Произошла ошибка при получении информации о погоде 😔"
        await update.message.reply_text(error_message)
        logger.error(f"Ошибка при обработке команды /weather: {e}")


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
            async with context.application.bot.get_chat(chat_id) as chat:
                async for message in chat.get_messages(limit=100):
                    if message.text and not message.text.startswith('/'):
                        messages.append(message)
            logger.info(f"Получено {len(messages)} сообщений из истории")
        except Exception as e:
            logger.error(f"Ошибка при получении истории: {e}")

        # Добавляем сообщения в базу
        added_count = 0
        for message in messages:
            if markov_generator.add_message(chat_id, message.text):
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


async def send_weather_updates(context: ContextTypes.DEFAULT_TYPE):
    """Отправляет обновления погоды в активированные группы"""
    while True:
        try:
            weather_message = await weather_service.get_weather_and_traffic()

            for chat_id in weather_service.weather_enabled_groups:
                try:
                    await context.bot.send_message(chat_id=chat_id, text=weather_message)
                    logger.info(
                        f"Отправлено сообщение о погоде в чат {chat_id}")
                except Exception as e:
                    logger.error(
                        f"Ошибка при отправке погоды в чат {chat_id}: {e}")

            # Ждем 3 часа перед следующим обновлением
            await asyncio.sleep(10800)  # 3 часа в секундах

        except Exception as e:
            logger.error(f"Ошибка в цикле отправки погоды: {e}")
            # Подождем 5 минут перед повторной попыткой
            await asyncio.sleep(300)
