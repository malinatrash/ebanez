import os
import logging
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, ChatMemberHandler, filters

from src.handlers.command_handlers import (
    start_command,
    help_command,
    stats_command,
    generate_command,
    clear_command,
    rebuild_command,
    sticker_command,
    top_command,
    mood_command
)
from src.handlers.message_handlers import (
    handle_message, 
    handle_my_chat_member, 
    handle_weather_command
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():
    load_dotenv()    
    token = os.getenv('BOT_TOKEN')
    if not token:
        raise ValueError("Не найден токен бота. Создайте файл .example.env с переменной BOT_TOKEN")
    
    logging.info(f"Token starts with: {token[:10]}...")
    
    # Configure application with timeout settings
    application = (
        Application.builder()
        .token(token)
        .connect_timeout(30.0)  # 30 seconds connection timeout
        .read_timeout(30.0)     # 30 seconds read timeout
        .write_timeout(30.0)    # 30 seconds write timeout
        .pool_timeout(30.0)     # 30 seconds pool timeout
        .build()
    )
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("gen", generate_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("rebuild", rebuild_command))
    application.add_handler(CommandHandler("sticker", sticker_command))
    application.add_handler(CommandHandler("top", top_command))
    application.add_handler(CommandHandler("mood", mood_command))
    application.add_handler(CommandHandler("weather", handle_weather_command))
    
    application.add_handler(ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    
    # Обработка текстовых сообщений и стикеров
    application.add_handler(MessageHandler(
        (filters.TEXT | filters.Sticker.ALL) & ~filters.COMMAND,
        handle_message
    ))
    
    # Add error handler
    async def error_handler(update, context):
        logging.error(f"Exception while handling an update: {context.error}")
        if update and update.message:
            await update.message.reply_text(
                "⚠️ Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже."
            )
    
    application.add_error_handler(error_handler)
    
    logging.info("Starting bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
