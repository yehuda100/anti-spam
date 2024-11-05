from datetime import datetime, timedelta
import re
import logging
import mongodb as m_db
import config
import utils
from filters import filter_chat_anmins
from telegram import Update
from telegram.ext import (
    Application,
    Updater,
    CommandHandler,
    CallbackContext,
    ChatMemberHandler,
    MessageHandler,
    filters,
)


def check_text(text):
    flags = r"(\U0001F1F5\U0001F1F8)+|(\U0001F1EE\U0001F1F7)+"
    pattern = r"[\u0600-\u06ff]+" + r"|" + flags
    return bool(re.search(pattern, text))

def check_user(user):
    if user.language_code in ("ar", "fa") or check_text(user.first_name):
        return True
    return False

def check_message(message):
    if any([
        message.text and check_text(message.text),
        message.caption and check_text(message.caption),
        message.forward_from_chat and check_text(message.forward_from_chat.title),
        message.forward_from and check_text(message.forward_from.first_name)
    ]):
        return True
    return False


async def new_user_joined(update: Update, context: CallbackContext) -> None:
    new_user = update.chat_member.new_chat_member.user
    banned_user = await m_db.banned_user_exists(new_user.id)
    if check_user(new_user) or banned_user:
        await update.effective_chat.ban_member(new_user.id, revoke_messages=True)
        if not banned_user:
            await m_db.add_banned_user(new_user.id)

async def group_messages(update: Update, context: CallbackContext) -> None:
    if update.message is None:
        return 
    collection = f"Chat_{update.effective_chat.id % 1000}"
    data = {
        "expireAt": datetime.now() + timedelta(days=3),
        "user_id": update.effective_user.id,
        "chat_id": update.effective_chat.id,
        "message_id": update.effective_message.message_id
    }
    await m_db.save_message(collection, data)
    if check_message(update.message):
        await update.effective_chat.ban_member(update.message.from_user.id, revoke_messages=False)
        await m_db.add_banned_user(update.message.from_user.id)
        messages = await m_db.get_messages(collection, update.effective_user.id)
        if  len(messages) >= 1:
            for message in messages:
                await context.bot.delete_message(**message)

async def add_group(update: Update, context: CallbackContext) -> None:
    collection = f"Chat_{update.effective_chat.id % 1000}"
    if update.message.from_user.id == config.ADMINS:
        await m_db.add_group(collection, update.effective_chat.id)
        filters.Chat().add_chat_ids(chat_id=update.effective_chat.id)

async def remove_group(update: Update, context: CallbackContext) -> None:
    collection = f"Chat_{update.effective_chat.id % 1000}"
    if update.message.from_user.id == config.ADMINS:
        await m_db.remove_group(collection, update.effective_chat.id)
        filters.Chat().remove_chat_ids(chat_id=update.effective_chat.id)

async def remove_user(update: Update, context: CallbackContext) -> None:
    if context.args[0].isdigit():
        id = int(context.args[0])
        await m_db.remove_banned_user(id)
        await update.message.reply_text(f"{id} has been removed.")
    else:
        await update.message.reply_text("The id i have received is not an int.")


async def check(update: Update, context: CallbackContext) -> None:
    if await m_db.group_exists(update.effective_chat.id):
        await update.message.reply_text("All Good!", allow_sending_without_reply=True)

async def statistics(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id == config.ADMINS:
        await update.message.reply_text(f"Groups: {await m_db.count_groups()}.\nBanned Users: {await m_db.count_banned_users()}.", allow_sending_without_reply=True)


def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )
    logger = logging.getLogger(__name__)
    
    app = Application.builder().token(config.BOT_TOKEN).build()
    

    allowed_groups = utils.run_async(m_db.get_groups)

    app.add_handler(ChatMemberHandler(new_user_joined, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler((filters.Chat(allowed_groups) & ~filter_chat_anmins & ~filters.COMMAND & ~filters.StatusUpdate.ALL), group_messages))
    app.add_handler(CommandHandler('add_group', add_group))
    app.add_handler(CommandHandler('remove_group', remove_group))
    app.add_handler(CommandHandler('check', check, filters.ChatType.GROUPS & filters.User(config.ADMINS)))
    app.add_handler(CommandHandler('stat', statistics, filters.User(config.ADMINS)))
    app.add_handler(CommandHandler('remove_user', remove_user, filters.Chat(config.ADMINS), has_args=1))
    
    app.run_webhook(
        listen="127.0.0.1",
        port=8001,
        url_path=config.BOT_TOKEN,
        webhook_url=config.URL + config.BOT_TOKEN)


if __name__ == "__main__":
    main()

#by t.me/yehuda100