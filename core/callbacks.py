from datetime import datetime, timedelta
import core.mongodb as db
from core.utils import is_bot_authorized, check_user, check_message
import config
from telegram import Update, ChatMember
from telegram.ext import CallbackContext
from telegram.error import TelegramError


# Commands callback functions
async def start(update: Update, context: CallbackContext) -> None:
    text = r"""*ברוכים הבאים\!🌟*

בוט זה נועד כדי למנוע מערבים להספים את הקבוצות שלנו\. כל הודעה בערבית או פרסית\, \
משתמש עם שם או שפת אפליקציה בערבית\, או אפילו דגל איראן או פלסטלינה \- המשתמש יוסר וההודעות שלו יימחקו\. 🚫

📌 *כדי להשתמש בבוט:*
1\. הוסיפו את הבוט כמנהל עם הרשאות למחוק הודעות ולחסום משתמשים\.
2\. פנו ל\-@yehuda100\.

עם ישראל חי🇮🇱🇮🇱🇮🇱"""
    await update.message.reply_markdown_v2(text)

async def add_group(update: Update, context: CallbackContext) -> None:
    if not await is_bot_authorized(context, update.effective_chat.id):
        await update.message.reply_text("i don't have premissions in this group.")
    chat_admins = {admin.user.id for admin in await update.effective_chat.get_administrators()}
    context.chat_data['chat_admins'] = chat_admins
    collection = f"Chat_{update.effective_chat.id % 1000}"
    await db.add_group(collection, update.effective_chat.id)
    config.allowed_groups.add_chat_ids(chat_id=update.effective_chat.id)

async def remove_group(update: Update, context: CallbackContext) -> None:
    context.chat_data.clear()
    collection = f"Chat_{update.effective_chat.id % 1000}"
    await db.remove_group(collection, update.effective_chat.id)
    config.allowed_groups.remove_chat_ids(chat_id=update.effective_chat.id)

async def remove_user(update: Update, context: CallbackContext) -> None:
    if context.args is None:
        await update.message.reply_text("Which one?")
    if context.args[0].isdigit():
        user_id = int(context.args[0])
        chats = await db.get_banned_user_chats(user_id)
        await db.remove_banned_user(user_id)
        async for chat in chats:
            try:
                await context.bot.unban_chat_member(chat, user_id, only_if_banned=True)
            except TelegramError:
                continue
        await update.message.reply_markdown_v2(f"User [{user_id}](tg://user?id={user_id}) has been removed.")
    else:
        await update.message.reply_text("The ID i have received is not an int.")

async def check(update: Update, context: CallbackContext) -> None:
    if not await is_bot_authorized(context, update.effective_chat.id):
        await update.message.reply_text("I don't have premissions in this group.")
        return
    if await db.group_exists(update.effective_chat.id):
        await update.message.reply_text("All Good!")

async def statistics(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(f"Groups: {await db.count_groups()}.\n\
                                    Banned Users: {await db.count_banned_users()}.", allow_sending_without_reply=True)


# Status update callback function
async def user_updates(update: Update, context: CallbackContext) -> None:
    if update.effective_chat.id not in config.allowed_groups.chat_ids:
        return
    status_change = update.chat_member.difference().get('status')
    old_is_member, new_is_member = update.chat_member.difference().get('is_member', (None, None))

    if status_change:
        old_status, new_status = status_change
        admins = (ChatMember.ADMINISTRATOR, ChatMember.OWNER)
        if new_status in admins and old_status not in admins:
            context.chat_data['chat_admins'].add(update.chat_member.new_chat_member.user.id)
        elif old_status in admins and new_status not in admins:
            context.chat_data['chat_admins'].discard(update.chat_member.new_chat_member.user.id)

    if new_is_member and not old_is_member:
        new_user = update.chat_member.new_chat_member.user
        banned_user = await db.banned_user_exists(new_user.id)
        if check_user(new_user) or banned_user:
            await update.effective_chat.ban_member(new_user.id, revoke_messages=True)
            if not banned_user:
                await db.add_banned_user(new_user.id, update.effective_chat.id)


# Bot status update callback function
async def bot_status_changed(update: Update, context: CallbackContext) -> None:
    if update.effective_chat.id not in config.allowed_groups.chat_ids:
        return
    bot_member = update.my_chat_member.new_chat_member
    if not bot_member.is_member:
        context.chat_data.clear()
        collection = f"Chat_{update.effective_chat.id % 1000}"
        await db.remove_group(collection, update.effective_chat.id)
        config.allowed_groups.remove_chat_ids(chat_id=update.effective_chat.id)
        return
    if not bot_member.can_delete_messages or not bot_member.can_restrict_members:
        context.chat_data.clear()
        config.allowed_groups.remove_chat_ids(chat_id=update.effective_chat.id)


# Group messages callback function
async def group_messages(update: Update, context: CallbackContext) -> None:
    if update.message is None:
        return 
    if update.message.from_user.id in context.chat_data.get('chat_admins', set()):
        return
    collection = f"Chat_{update.effective_chat.id % 1000}"
    data = {
        "expireAt": datetime.now() + timedelta(days=3),
        "user_id": update.effective_user.id,
        "chat_id": update.effective_chat.id,
        "message_id": update.effective_message.message_id
    }
    await db.save_message(collection, data)

    if check_message(update.message):
        await update.effective_chat.ban_member(update.message.from_user.id)
        await db.add_banned_user(update.message.from_user.id, update.effective_chat.id)
        messages = await db.get_messages(collection, update.effective_user.id)
        if  len(messages) >= 1:
            for message in messages:
                await context.bot.delete_message(**message)


#by t.me/yehuda100