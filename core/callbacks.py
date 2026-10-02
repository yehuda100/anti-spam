from datetime import datetime, timedelta

import core.mongodb as db
import config
from core.utils import (
    REASON_ALREADY_BANNED,
    is_bot_authorized,
    message_reason,
    user_reason,
)
from telegram import ChatMember, Update
from telegram.error import TelegramError
from telegram.ext import CallbackContext, filters


# New messages and edits, including media. Commands stay with CommandHandler.
GROUP_CONTENT = filters.UpdateType.MESSAGES & filters.USER & ~filters.COMMAND

_ADMIN_STATUSES = (ChatMember.ADMINISTRATOR, ChatMember.OWNER)
_PRESENT_STATUSES = (ChatMember.ADMINISTRATOR, ChatMember.OWNER, ChatMember.MEMBER)


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
        return
    chat_admins = {
        admin.user.id
        for admin in await update.effective_chat.get_administrators()
        if getattr(admin, "user", None) is not None
    }
    context.chat_data["chat_admins"] = chat_admins
    await db.add_group(update.effective_chat.id)
    config.allowed_groups.add_chat_ids(chat_id=update.effective_chat.id)


async def remove_group(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    context.chat_data.clear()
    await db.remove_group(chat_id)
    config.allowed_groups.remove_chat_ids(chat_id=chat_id)


async def remove_user(update: Update, context: CallbackContext) -> None:
    if not context.args:
        await update.message.reply_text("Which one?")
        return
    if not str(context.args[0]).isdigit():
        await update.message.reply_text("The ID i have received is not an int.")
        return
    user_id = int(context.args[0])
    chats = await db.get_banned_user_chats(user_id)
    await db.remove_banned_user(user_id)
    for chat_id in chats:
        try:
            await context.bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        except TelegramError:
            continue
    await update.message.reply_markdown_v2(
        f"User [{user_id}](tg://user?id={user_id}) has been removed."
    )


async def check(update: Update, context: CallbackContext) -> None:
    if not await is_bot_authorized(context, update.effective_chat.id):
        await update.message.reply_text("I don't have premissions in this group.")
        return
    if await db.group_exists(update.effective_chat.id):
        await update.message.reply_text("This group is registered.")
    else:
        await update.message.reply_text("This group is not registered.")


async def statistics(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(f"Groups: {await db.count_groups()}.\n\
                                    Banned Users: {await db.count_banned_users()}.", allow_sending_without_reply=True)


def _is_admin(member) -> bool:
    return getattr(member, "status", None) in _ADMIN_STATUSES


def _is_present(member) -> bool:
    status = getattr(member, "status", None)
    if status in _PRESENT_STATUSES:
        return True
    if status == ChatMember.RESTRICTED:
        return bool(getattr(member, "is_member", False))
    return False


def _joined(old, new) -> bool:
    return not _is_present(old) and _is_present(new)


def _bot_in_chat(bot_member) -> bool:
    status = getattr(bot_member, "status", None)
    if status in (ChatMember.LEFT, ChatMember.BANNED):
        return False
    if status == ChatMember.RESTRICTED:
        return bool(getattr(bot_member, "is_member", False))
    return True


def _bot_can_moderate(bot_member) -> bool:
    return bool(getattr(bot_member, "can_delete_messages", False)) and bool(
        getattr(bot_member, "can_restrict_members", False)
    )


async def ensure_chat_admins(context, chat) -> set:
    """Return the admin id set, loading it from Telegram when the snapshot is gone."""
    admins = context.chat_data.get("chat_admins")
    if isinstance(admins, set):
        return admins
    fetched = set()
    try:
        members = await chat.get_administrators()
    except TelegramError:
        context.chat_data["chat_admins"] = fetched
        return fetched
    for member in members:
        user = getattr(member, "user", None)
        user_id = getattr(user, "id", None)
        if user_id is not None:
            fetched.add(user_id)
    context.chat_data["chat_admins"] = fetched
    return fetched


async def log_ban(context, user, chat, reason: str) -> None:
    log_chat_id = config.LOG_CHAT_ID
    if not log_chat_id:
        return
    user_id = getattr(user, "id", None)
    name = (
        getattr(user, "full_name", None)
        or getattr(user, "first_name", None)
        or str(user_id)
    )
    title = getattr(chat, "title", None) or str(chat.id)
    line = f"Banned {name} (user {user_id}) in {title} (chat {chat.id}): {reason}"
    try:
        await context.bot.send_message(chat_id=log_chat_id, text=line)
    except TelegramError:
        return


async def perform_ban(update, context, user, reason: str) -> None:
    chat = update.effective_chat
    # False keeps messages older than the 3-day store. Telegram deletes the
    # user's history in a supergroup when revoke_messages is true or omitted.
    await chat.ban_member(user.id, revoke_messages=False)
    await db.add_banned_user(user.id, chat.id)
    stored = await db.get_messages(user.id, chat.id)
    for message in stored:
        try:
            await context.bot.delete_message(
                chat_id=message["chat_id"],
                message_id=message["message_id"],
            )
        except TelegramError:
            continue
    await log_ban(context, user, chat, reason)


async def user_updates(update: Update, context: CallbackContext) -> None:
    chat = update.effective_chat
    if chat is None or chat.id not in config.allowed_groups.chat_ids:
        return
    updated = update.chat_member
    if updated is None:
        return
    old = updated.old_chat_member
    new = updated.new_chat_member
    user = getattr(new, "user", None)
    if old is None or new is None or user is None:
        return

    if _is_admin(new) != _is_admin(old):
        admins = await ensure_chat_admins(context, chat)
        if _is_admin(new):
            admins.add(user.id)
        else:
            admins.discard(user.id)

    if not _joined(old, new):
        return
    admins = await ensure_chat_admins(context, chat)
    if user.id in admins:
        return

    if await db.banned_user_exists(user.id):
        reason = REASON_ALREADY_BANNED
    else:
        reason = user_reason(user)
    if not reason:
        return
    await perform_ban(update, context, user, reason)


async def bot_status_changed(update: Update, context: CallbackContext) -> None:
    chat = update.effective_chat
    if chat is None or chat.id not in config.allowed_groups.chat_ids:
        return
    bot_member = update.my_chat_member.new_chat_member
    if not _bot_in_chat(bot_member):
        context.chat_data.clear()
        await db.remove_group(chat.id)
        config.allowed_groups.remove_chat_ids(chat_id=chat.id)
        return
    if not _bot_can_moderate(bot_member):
        context.chat_data.clear()
        config.allowed_groups.remove_chat_ids(chat_id=chat.id)


async def group_messages(update: Update, context: CallbackContext) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None or getattr(message, "from_user", None) is None:
        return
    if chat.id not in config.allowed_groups.chat_ids:
        return
    user = message.from_user
    admins = await ensure_chat_admins(context, chat)
    if user.id in admins:
        return

    await db.save_message(
        {
            "expireAt": datetime.now() + timedelta(days=3),
            "user_id": user.id,
            "chat_id": chat.id,
            "message_id": message.message_id,
        }
    )
    reason = message_reason(message)
    if reason:
        await perform_ban(update, context, user, reason)


async def load_allowed_groups(application) -> None:
    await db.ensure_message_index()
    groups = await db.get_groups()
    if groups:
        config.allowed_groups.add_chat_ids(groups)


#by t.me/yehuda100
