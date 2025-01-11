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
    sticker_command
)
from src.handlers.message_handlers import handle_message, handle_my_chat_member

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():
    load_dotenv()    
    token = os.getenv('BOT_TOKEN')
    if not token:
        raise ValueError("Не найден токен бота. Создайте файл .env с переменной BOT_TOKEN")
    
    logging.info(f"Token starts with: {token[:10]}...")
    
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("gen", generate_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("rebuild", rebuild_command))
    application.add_handler(CommandHandler("sticker", sticker_command))
    
    application.add_handler(ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logging.info("Starting bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
