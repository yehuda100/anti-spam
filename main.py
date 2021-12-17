import re
import logging
import database as db
import bot_token
from telegram import Update
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    ChatMemberHandler,
    MessageHandler,
    Filters,
)


db.create_tables()
BANNED_USERS = db.get_banned_users()
GROUPS_ALLOWED = db.get_groups()


def check_text(text):
    return bool(re.search(r"[\u0600-\u06ff]+", text))

def check_user(user):
    if user.language_code in ("ar", "fa"):
        return True
    return check_text(user.first_name)

def check_message(message):
    if message.text is not None:
        print(message.text)
        if check_text(message.text):
            return True
    if message.caption is not None:
        if check_text(message.caption):
            return True
    if message.forward_from_chat is not None:
        if check_text(message.forward_from_chat.title):
            return True
    if message.forward_from is not None:
        if check_text(message.forward_from.first_name):
            return True
    return False
    
def new_user_join(update: Update, context: CallbackContext) -> None:
    new_user = update.chat_member.new_chat_member.user
    if check_user(new_user) or new_user.id in BANNED_USERS:
        update.effective_chat.ban_member(new_user.id, revoke_messages=True)
        db.add_banned_user(new_user.id)
        BANNED_USERS.add(new_user.id)

def group_messages(update: Update, context: CallbackContext) -> None:
    if check_message(update.message):
        update.effective_chat.ban_member(update.message.from_user.id, revoke_messages=True)
        update.effective_message.delete()
        db.add_banned_user(update.message.from_user.id)
        BANNED_USERS.add(update.message.from_user.id)

def add_group(update: Update, context: CallbackContext) -> None:
    input_id = context.args[0]
    if input_id.isdigit():
        id = int(input_id)
        db.add_group(id)
        GROUPS_ALLOWED.add(id)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)

def main():
    updater = Updater(bot_token.TOKEN)
    dp = updater.dispatcher

    dp.add_handler(ChatMemberHandler(new_user_join, ChatMemberHandler.CHAT_MEMBER))
    dp.add_handler(MessageHandler(Filters.all, group_messages))
    dp.add_handler(CommandHandler('add_group', add_group, Filters.chat(258871997), pass_args=True))

    updater.start_webhook(listen="127.0.0.1",
                        port=7000,
                        url_path=bot_token.TOKEN,
                        webhook_url=bot_token.URL + bot_token.TOKEN,
                        allowed_updates=Update.ALL_TYPES)
    updater.idle()


if __name__ == "__main__":
    main()


#by t.me/yehuda100