from datetime import datetime, timedelta
import re
import logging
import mongodb as m_db
import config
import utils
from telegram import Update, ChatMember, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackContext,
    ChatMemberHandler,
    MessageHandler,
    filters,
    PicklePersistence
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
        message.forward_origin and message.forward_origin.chat and check_text(message.forward_origin.chat.title),
        message.forward_origin and message.forward_origin.sender_user and check_text(message.forward_origin.sender_user.first_name)
    ]):
        return True
    return False

async def check_bot_premissions(chat_id):
    bot_id = await Bot.get_me().id
    bot_member = await Bot.get_chat_member(chat_id, bot_id)
    if bot_member.can_delete_messages and bot_member.can_restrict_members:
        return True
    return False


async def user_updates(update: Update, context: CallbackContext) -> None:
    status_change = update.chat_member.difference().get('status')
    old_is_member, new_is_member = update.chat_member.difference().get('is_member', (None, None))

    if status_change:
        old_status, new_status = status_change
        admins = (ChatMember.ADMINISTRATOR, ChatMember.CREATOR)
        if new_status in admins and old_status not in admins:
            context.chat_data['chat_admins'].add(update.chat_member.new_chat_member.user.id)
        elif old_status in admins and new_status not in admins:
            context.chat_data['chat_admins'].discard(update.chat_member.new_chat_member.user.id)

    if new_is_member and not old_is_member:
        new_user = update.chat_member.new_chat_member.user
        banned_user = await m_db.banned_user_exists(new_user.id)
        if check_user(new_user) or banned_user:
            await update.effective_chat.ban_member(new_user.id, revoke_messages=True)
            if not banned_user:
                await m_db.add_banned_user(new_user.id)

async def group_messages(update: Update, context: CallbackContext) -> None:
    if update.message is None:
        return 
    if update.message.from_user.id in context.chat_data['chat_admins']:
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
    if not await check_bot_premissions(update.effective_chat.id):
        await update.message.reply_text("i don't have premissions in this group.")
    chat_admins = (admin.user.id async for admin in await update.effective_chat.get_administrators())
    context.chat_data['chat_admins'] = chat_admins
    collection = f"Chat_{update.effective_chat.id % 1000}"
    await m_db.add_group(collection, update.effective_chat.id)
    filters.Chat().add_chat_ids(chat_id=update.effective_chat.id)

async def remove_group(update: Update, context: CallbackContext) -> None:
    context.chat_data.clear()
    collection = f"Chat_{update.effective_chat.id % 1000}"
    await m_db.remove_group(collection, update.effective_chat.id)
    filters.Chat().remove_chat_ids(chat_id=update.effective_chat.id)

async def drop_group(update: Update, context: CallbackContext) -> None:
    is_member = update.my_chat_member.difference().get('is_member')
    if is_member is None:
        return
    if is_member[1] == False:
            context.chat_data.clear()
            collection = f"Chat_{update.effective_chat.id % 1000}"
            await m_db.remove_group(collection, update.effective_chat.id)
            filters.Chat().remove_chat_ids(chat_id=update.effective_chat.id)

async def remove_user(update: Update, context: CallbackContext) -> None:
    if context.args[0].isdigit():
        user_id = int(context.args[0])
        await m_db.remove_banned_user(user_id)
        await update.message.reply_text(f"{user_id} has been removed.")
    else:
        await update.message.reply_text("The ID i have received is not an int.")


async def start(update: Update, context: CallbackContext) -> None:
    text = r"""*ברוכים הבאים\!🌟*

בוט זה נועד כדי למנוע מערבים להספים את הקבוצות שלנו\. כל הודעה בערבית או פרסית\, \
משתמש עם שם או שפת אפליקציה בערבית\, או אפילו דגל איראן או פלסטלינה \- המשתמש יוסר וההודעות שלו יימחקו\. 🚫

📌 *כדי להשתמש בבוט:*
1\. הוסיפו את הבוט כמנהל עם הרשאות למחוק הודעות ולחסום משתמשים\.
2\. פנו ל\-@yehuda100\.

עם ישראל חי🇮🇱🇮🇱🇮🇱"""
    await update.message.reply_markdown_v2(text)


async def check(update: Update, context: CallbackContext) -> None:
    if not await check_bot_premissions(update.effective_chat.id):
        await update.message.reply_text("i don't have premissions in this group.")
    if await m_db.group_exists(update.effective_chat.id):
        await update.message.reply_text("All Good!")

async def statistics(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(f"Groups: {await m_db.count_groups()}.\nBanned Users: {await m_db.count_banned_users()}.", allow_sending_without_reply=True)


def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
    )
    logger = logging.getLogger(__name__)

    bot_persistence = PicklePersistence(filepath='anti_spam_persistence')
    
    app = Application.builder().token(config.BOT_TOKEN).persistence(persistence=bot_persistence).build()
    

    allowed_groups = utils.run_async(m_db.get_groups)

    app.add_handler(ChatMemberHandler(user_updates, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(drop_group, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler((filters.Chat(allowed_groups) &  ~filters.COMMAND & ~filters.StatusUpdate.ALL), group_messages))
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