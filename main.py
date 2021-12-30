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
    new_user = update.chat_member.new_chat_member.user
    if check_user(new_user) or new_user.id in db.get_banned_users():
        update.effective_chat.ban_member(new_user.id, revoke_messages=True)
        if not db.banned_user_exists(new_user.id):
            db.add_banned_user(new_user.id)

def group_messages(update: Update, context: CallbackContext) -> None:
    if update.message.sender_chat is not None:
        update.effective_chat.ban_sender_chat(update.message.sender_chat.id)
        update.effective_message.delete()
    if 'messages' not in context.user_data:
        context.user_data['messages'] = []
    if len(context.user_data['messages']) >= 5:
        context.user_data['messages'].pop(0)
    context.user_data['messages'].append({'chat_id': update.effective_chat.id, 'message_id': update.effective_message.message_id})
    if check_message(update.message):
        update.effective_chat.ban_member(update.message.from_user.id, revoke_messages=True)
        if not db.banned_user_exists(update.message.from_user.id):
            db.add_banned_user(update.message.from_user.id)
        if len(context.user_data['messages']) >= 1:
            for message in context.user_data['messages']:
                context.bot.delete_message(**message)
            context.user_data.clear()

def add_group(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id == 258871997:
        if update.effective_chat.id not in db.get_groups():
            db.add_group(update.effective_chat.id)
        Filters.chat().add_chat_ids(chat_id=update.effective_chat.id)

def check(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id == 258871997:
        update.message.reply_text("All Good!", allow_sending_without_reply=True)

def statistics(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id == 258871997:
        update.message.reply_text(f"Groups: {db.count_groups()}.\nBanned Users: {db.count_banned_users()}.", allow_sending_without_reply=True)

def remove_user(update: Update, context: CallbackContext) -> None:
    if context.args[0].isdigit():
        id = int(context.args[0])
        db.remove_banned_user(id)
        update.message.reply_text(f"{id} has been removed.")
    else:
        update.message.reply_text("The id i have received is not an int.")


def main():

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )

    logger = logging.getLogger(__name__)

    updater = Updater(bot_token.TOKEN)
    dp = updater.dispatcher

    dp.add_handler(ChatMemberHandler(new_user_join, ChatMemberHandler.CHAT_MEMBER))
    dp.add_handler(MessageHandler((Filters.chat(db.get_groups()) & Filters.chat_type.supergroup & ~Filters.command & ~Filters.status_update), group_messages, pass_user_data=True))
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