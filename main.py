import logging
import config
from core.callbacks import *
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ChatMemberHandler,
    MessageHandler,
    filters,
    PicklePersistence
)


def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
    )
    logger = logging.getLogger(__name__)

    bot_persistence = PicklePersistence(filepath='anti_spam_persistence')
    
    app = Application.builder().token(config.BOT_TOKEN).persistence(persistence=bot_persistence).build()
    

    app.add_handler(ChatMemberHandler(user_updates, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(bot_status_changed, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler((config.allowed_groups &  ~filters.COMMAND & ~filters.StatusUpdate.ALL), group_messages))
    app.add_handler(CommandHandler('start', start, filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('add_group', add_group, filters.ChatType.GROUPS & filters.User(config.ADMINS)))
    app.add_handler(CommandHandler('remove_group', remove_group, filters.ChatType.GROUPS & filters.User(config.ADMINS)))
    app.add_handler(CommandHandler('check', check, filters.ChatType.GROUPS & filters.User(config.ADMINS)))
    app.add_handler(CommandHandler('stat', statistics, filters.Chat(config.ADMINS) | filters.User(config.ADMINS)))
    app.add_handler(CommandHandler('remove_user', remove_user, filters.Chat(config.ADMINS), has_args=True))
    
    app.run_webhook(
        listen="127.0.0.1",
        port=8001,
        url_path=config.BOT_TOKEN,
        webhook_url=config.URL + config.BOT_TOKEN,
        allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()


#by t.me/yehuda100