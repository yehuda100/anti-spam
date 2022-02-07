from datetime import datetime, timedelta
import re
import logging
import mongodb as m_db
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


def check_text(text):
    return bool(re.search(r"[\u0600-\u06ff]+", text))

def check_user(user):
    if user.language_code in ("ar", "fa"):
        return True
    return check_text(user.first_name)

def check_message(message):
    if message.text is not None:
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
    db = m_db.db_connection()
    new_user = update.chat_member.new_chat_member.user
    banned_user = m_db.banned_user_exists(db, new_user.id)
    if check_user(new_user) or banned_user:
        update.effective_chat.ban_member(new_user.id, revoke_messages=True)
        if not banned_user:
            m_db.add_banned_user(db, new_user.id)

def group_messages(update: Update, context: CallbackContext) -> None:
    if update.message is None:
        return 
    if update.message.sender_chat is not None:
        if update.message.is_automatic_forward:
            return
        if update.message.sender_chat.id == update.effective_chat.id:
            return
        update.effective_chat.ban_sender_chat(update.message.sender_chat.id)
        update.effective_message.delete()
        return
    collection = f"Chat_{update.effective_chat.id % 1000}"
    data = {
        "expireAt": datetime.now() + timedelta(days=3),
        "user_id": update.effective_user.id,
        "chat_id": update.effective_chat.id,
        "message_id": update.effective_message.message_id
    }
    db = m_db.db_connection()
    m_db.save_message(db, collection, data)
    if check_message(update.message):
        update.effective_chat.ban_member(update.message.from_user.id, revoke_messages=True)
        if not m_db.banned_user_exists(db, update.message.from_user.id):
            m_db.add_banned_user(db, update.message.from_user.id)
        messages = m_db.get_messages(db, collection, update.effective_user.id)
        if  len(messages) >= 1:
            for message in messages:
                context.bot.delete_message(**message)

def add_group(update: Update, context: CallbackContext) -> None:
    db = m_db.db_connection()
    if update.message.from_user.id == 258871997:
        if not m_db.group_exists(db, update.effective_chat.id):
            m_db.add_group(db, update.effective_chat.id)
        Filters.chat().add_chat_ids(chat_id=update.effective_chat.id)

def check(update: Update, context: CallbackContext) -> None:
    db = m_db.db_connection()
    if update.message.from_user.id == 258871997 and m_db.group_exists(db, update.effective_chat.id):
        update.message.reply_text("All Good!", allow_sending_without_reply=True)

def statistics(update: Update, context: CallbackContext) -> None:
    db = m_db.db_connection()
    if update.message.from_user.id == 258871997:
        update.message.reply_text(f"Groups: {m_db.count_groups(db)}.\nBanned Users: {m_db.count_banned_users(db)}.", allow_sending_without_reply=True)

def remove_user(update: Update, context: CallbackContext) -> None:
    if context.args[0].isdigit():
        db = m_db.db_connection()
        id = int(context.args[0])
        m_db.remove_banned_user(db, id)
        update.message.reply_text(f"{id} has been removed.")
    else:
        update.message.reply_text("The id i have received is not an int.")


def main():

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
    )

    logger = logging.getLogger(__name__)

    db = m_db.db_connection()

    updater = Updater(bot_token.TOKEN)
    dp = updater.dispatcher

    dp.add_handler(ChatMemberHandler(new_user_join, ChatMemberHandler.CHAT_MEMBER))
    dp.add_handler(MessageHandler((Filters.chat(m_db.get_groups(db)) & Filters.chat_type.supergroup & ~Filters.command & ~Filters.status_update), group_messages, pass_user_data=True))
    dp.add_handler(CommandHandler('add_group', add_group))
    dp.add_handler(CommandHandler('check', check))
    dp.add_handler(CommandHandler('stat', statistics))
    dp.add_handler(CommandHandler('remove_user', remove_user, Filters.chat(258871997), pass_args=True))

    updater.start_webhook(listen="127.0.0.1",
                        port=7000,
                        url_path=bot_token.TOKEN,
                        webhook_url=bot_token.URL + bot_token.TOKEN,
                        allowed_updates=Update.ALL_TYPES)
    #updater.start_polling(allowed_updates=Update.ALL_TYPES)

    updater.idle()


if __name__ == "__main__":
    main()


#by t.me/yehuda100
