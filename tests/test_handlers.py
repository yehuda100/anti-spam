from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram import Chat, ChatMember, Message, MessageEntity, Update, User
from telegram.error import TelegramError
from telegram.ext import filters

import config
import core.callbacks as callbacks
import core.mongodb as mongodb
from core.utils import REASON_ALREADY_BANNED, REASON_TEXT


ARABIC = "مرحبا"
LOG_CHAT_ID = -100777


class FakeChat:
    def __init__(self, chat_id, title="Allowed group"):
        self.id = chat_id
        self.title = title
        self.type = "supergroup"
        self.ban_member = AsyncMock()
        self.get_administrators = AsyncMock(return_value=[])


class Member:
    def __init__(self, user, status, is_member=None):
        self.user = user
        self.status = status
        self.is_member = is_member


def _user(user_id=42, first_name="Neta", language_code="en"):
    return SimpleNamespace(
        id=user_id,
        first_name=first_name,
        language_code=language_code,
        full_name=first_name,
        is_bot=False,
    )


def _context(args=None):
    return SimpleNamespace(
        args=args,
        chat_data={},
        bot=SimpleNamespace(
            delete_message=AsyncMock(),
            send_message=AsyncMock(),
            unban_chat_member=AsyncMock(),
        ),
    )


def _allow(chat_id):
    config.allowed_groups.add_chat_ids(chat_id)


def _content_message(chat, user, message_id=10, text=None, caption=None, forward_origin=None):
    return SimpleNamespace(
        message_id=message_id,
        chat=chat,
        from_user=user,
        text=text,
        caption=caption,
        forward_origin=forward_origin,
    )


def _message_update(chat, message, edited=False):
    return SimpleNamespace(
        message=None if edited else message,
        edited_message=message if edited else None,
        effective_message=message,
        effective_chat=chat,
        effective_user=message.from_user,
        chat_member=None,
    )


def _stored(user_id, chat_id, message_id):
    return {
        "expireAt": datetime.now(),
        "user_id": user_id,
        "chat_id": chat_id,
        "message_id": message_id,
    }


@pytest.mark.parametrize("field", ["text", "caption"])
async def test_arabic_message_bans_and_deletes_stored_messages(database, field):
    chat = FakeChat(-100123)
    user = _user()
    _allow(chat.id)
    await mongodb.save_message(_stored(user.id, chat.id, 3))
    await mongodb.save_message(_stored(user.id, -100999, 4))
    message = _content_message(
        chat,
        user,
        message_id=10,
        text=ARABIC if field == "text" else None,
        caption=ARABIC if field == "caption" else None,
    )
    context = _context()
    await callbacks.group_messages(_message_update(chat, message), context)

    chat.ban_member.assert_awaited_once()
    assert chat.ban_member.await_args.args[0] == user.id
    assert chat.ban_member.await_args.kwargs["revoke_messages"] is True
    deleted = {
        (call.kwargs["chat_id"], call.kwargs["message_id"])
        for call in context.bot.delete_message.await_args_list
    }
    assert deleted == {(chat.id, 3), (chat.id, 10)}
    assert await mongodb.get_messages(user.id, -100999) == [
        {"chat_id": -100999, "message_id": 4}
    ]
    assert await mongodb.banned_user_exists(user.id)
    assert await mongodb.get_banned_user_chats(user.id) == {chat.id}
    context.bot.send_message.assert_not_awaited()


async def test_group_admin_is_not_banned_when_snapshot_is_missing(database):
    chat = FakeChat(-100123)
    user = _user()
    _allow(chat.id)
    chat.get_administrators = AsyncMock(return_value=[SimpleNamespace(user=SimpleNamespace(id=user.id))])
    context = _context()
    message = _content_message(chat, user, text=ARABIC)
    await callbacks.group_messages(_message_update(chat, message), context)

    chat.ban_member.assert_not_awaited()
    context.bot.delete_message.assert_not_awaited()
    assert not await mongodb.banned_user_exists(user.id)
    assert await mongodb.get_messages(user.id, chat.id) == []
    assert context.chat_data["chat_admins"] == {user.id}


async def test_known_admin_snapshot_skips_ban_without_refetch(database):
    chat = FakeChat(-100123)
    user = _user()
    _allow(chat.id)
    chat.get_administrators = AsyncMock(side_effect=AssertionError("snapshot should be used"))
    context = _context()
    context.chat_data["chat_admins"] = {user.id}
    await callbacks.group_messages(
        _message_update(chat, _content_message(chat, user, text=ARABIC)),
        context,
    )
    chat.ban_member.assert_not_awaited()
    chat.get_administrators.assert_not_awaited()


async def test_english_message_is_stored_and_not_banned(database):
    chat = FakeChat(-100123)
    user = _user()
    _allow(chat.id)
    context = _context()
    await callbacks.group_messages(
        _message_update(chat, _content_message(chat, user, text="hello")),
        context,
    )
    chat.ban_member.assert_not_awaited()
    assert await mongodb.get_messages(user.id, chat.id) == [
        {"chat_id": chat.id, "message_id": 10}
    ]


async def test_edited_arabic_message_is_banned(database):
    chat = FakeChat(-100123)
    user = _user()
    _allow(chat.id)
    message = _content_message(chat, user, text=ARABIC)
    context = _context()
    await callbacks.group_messages(_message_update(chat, message, edited=True), context)
    chat.ban_member.assert_awaited_once()
    assert chat.ban_member.await_args.kwargs["revoke_messages"] is True


async def test_forwarded_title_on_non_text_message_is_banned(database):
    chat = FakeChat(-100123)
    user = _user()
    _allow(chat.id)
    origin = SimpleNamespace(chat=SimpleNamespace(title=ARABIC))
    message = _content_message(chat, user, text=None, caption=None, forward_origin=origin)
    context = _context()
    await callbacks.group_messages(_message_update(chat, message), context)
    chat.ban_member.assert_awaited_once()
    context.bot.delete_message.assert_awaited()


async def test_ban_posts_one_log_line_without_buttons(database, monkeypatch):
    monkeypatch.setattr(config, "LOG_CHAT_ID", LOG_CHAT_ID)
    chat = FakeChat(-100123, title="Watch group")
    user = _user(first_name="Neta")
    _allow(chat.id)
    context = _context()
    await callbacks.group_messages(
        _message_update(chat, _content_message(chat, user, text=ARABIC)),
        context,
    )
    context.bot.send_message.assert_awaited_once()
    call = context.bot.send_message.await_args
    assert call.kwargs["chat_id"] == LOG_CHAT_ID
    assert "reply_markup" not in call.kwargs
    text = call.kwargs["text"]
    assert text.endswith(f": {REASON_TEXT}")
    assert f"user {user.id}" in text
    assert f"chat {chat.id}" in text
    assert "Watch group" in text
    assert "Neta" in text


async def test_log_failure_does_not_undo_the_ban(database, monkeypatch):
    monkeypatch.setattr(config, "LOG_CHAT_ID", LOG_CHAT_ID)
    chat = FakeChat(-100123)
    user = _user()
    _allow(chat.id)
    context = _context()
    context.bot.send_message = AsyncMock(side_effect=TelegramError("log down"))
    await callbacks.group_messages(
        _message_update(chat, _content_message(chat, user, text=ARABIC)),
        context,
    )
    assert await mongodb.banned_user_exists(user.id)
    chat.ban_member.assert_awaited_once()


async def test_already_banned_join_records_chat_without_a_second_insert(database, monkeypatch):
    monkeypatch.setattr(config, "LOG_CHAT_ID", LOG_CHAT_ID)
    user = _user(user_id=50, first_name="Neta", language_code="en")
    previous = -100111
    chat = FakeChat(-100222, title="Second group")
    _allow(chat.id)
    await mongodb.add_banned_user(user.id, previous)
    banned = database["BannedUsers"]
    assert banned.inserted == 1

    update = SimpleNamespace(
        effective_chat=chat,
        chat_member=SimpleNamespace(
            old_chat_member=Member(user, ChatMember.LEFT),
            new_chat_member=Member(user, ChatMember.MEMBER),
        ),
    )
    context = _context()
    await callbacks.user_updates(update, context)

    chat.ban_member.assert_awaited_once()
    assert chat.ban_member.await_args.kwargs["revoke_messages"] is True
    assert banned.inserted == 1
    assert len(banned.docs) == 1
    assert await mongodb.get_banned_user_chats(user.id) == {previous, chat.id}
    text = context.bot.send_message.await_args.kwargs["text"]
    assert text.endswith(f": {REASON_ALREADY_BANNED}")
    assert "reply_markup" not in context.bot.send_message.await_args.kwargs


async def test_clean_join_is_not_banned(database):
    user = _user()
    chat = FakeChat(-100222)
    _allow(chat.id)
    update = SimpleNamespace(
        effective_chat=chat,
        chat_member=SimpleNamespace(
            old_chat_member=Member(user, ChatMember.LEFT),
            new_chat_member=Member(user, ChatMember.MEMBER),
        ),
    )
    await callbacks.user_updates(update, _context())
    chat.ban_member.assert_not_awaited()
    assert not await mongodb.banned_user_exists(user.id)


async def test_promote_and_demote_do_not_keyerror_when_admin_set_is_missing(database):
    user = _user(user_id=7)
    chat = FakeChat(-100123)
    _allow(chat.id)
    chat.get_administrators = AsyncMock(return_value=[SimpleNamespace(user=SimpleNamespace(id=user.id))])
    context = _context()
    promote = SimpleNamespace(
        effective_chat=chat,
        chat_member=SimpleNamespace(
            old_chat_member=Member(user, ChatMember.MEMBER),
            new_chat_member=Member(user, ChatMember.ADMINISTRATOR),
        ),
    )
    await callbacks.user_updates(promote, context)
    assert user.id in context.chat_data["chat_admins"]
    chat.ban_member.assert_not_awaited()

    context.chat_data.clear()
    chat.get_administrators = AsyncMock(return_value=[SimpleNamespace(user=SimpleNamespace(id=user.id))])
    demote = SimpleNamespace(
        effective_chat=chat,
        chat_member=SimpleNamespace(
            old_chat_member=Member(user, ChatMember.ADMINISTRATOR),
            new_chat_member=Member(user, ChatMember.MEMBER),
        ),
    )
    await callbacks.user_updates(demote, context)
    assert user.id not in context.chat_data["chat_admins"]


async def test_remove_user_unbans_every_stored_chat(database):
    user_id = 42
    chats = {-1001, -1002, -1003}
    for chat_id in chats:
        await mongodb.add_banned_user(user_id, chat_id)
    context = _context(args=[str(user_id)])
    update = SimpleNamespace(
        message=SimpleNamespace(reply_text=AsyncMock(), reply_markdown_v2=AsyncMock())
    )
    await callbacks.remove_user(update, context)

    unbanned = {call.args[0] for call in context.bot.unban_chat_member.await_args_list}
    assert unbanned == chats
    assert all(call.args[1] == user_id for call in context.bot.unban_chat_member.await_args_list)
    assert all(call.kwargs["only_if_banned"] is True for call in context.bot.unban_chat_member.await_args_list)
    assert not await mongodb.banned_user_exists(user_id)
    update.message.reply_markdown_v2.assert_awaited()


async def test_remove_user_continues_when_one_unban_fails(database):
    user_id = 9
    await mongodb.add_banned_user(user_id, -1)
    await mongodb.add_banned_user(user_id, -2)

    async def unban(chat_id, banned_id, only_if_banned=True):
        if chat_id == -1:
            raise TelegramError("already gone")

    context = _context(args=[str(user_id)])
    context.bot.unban_chat_member = AsyncMock(side_effect=unban)
    update = SimpleNamespace(
        message=SimpleNamespace(reply_text=AsyncMock(), reply_markdown_v2=AsyncMock())
    )
    await callbacks.remove_user(update, context)
    assert context.bot.unban_chat_member.await_count == 2
    update.message.reply_markdown_v2.assert_awaited()


@pytest.mark.parametrize("args", [None, []])
async def test_remove_user_without_an_id_does_not_crash(database, args):
    context = _context(args=args)
    update = SimpleNamespace(
        message=SimpleNamespace(reply_text=AsyncMock(), reply_markdown_v2=AsyncMock())
    )
    await callbacks.remove_user(update, context)
    update.message.reply_text.assert_awaited_with("Which one?")
    context.bot.unban_chat_member.assert_not_awaited()


async def test_add_group_without_permissions_does_not_write(database, monkeypatch):
    monkeypatch.setattr(callbacks, "is_bot_authorized", AsyncMock(return_value=False))
    chat = FakeChat(-100555)
    context = _context()
    update = SimpleNamespace(
        effective_chat=chat,
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    await callbacks.add_group(update, context)
    assert not await mongodb.group_exists(chat.id)
    assert chat.id not in config.allowed_groups.chat_ids
    assert "chat_admins" not in context.chat_data
    update.message.reply_text.assert_awaited()
    chat.get_administrators.assert_not_awaited()


async def test_add_group_with_permissions_registers_the_group(database, monkeypatch):
    monkeypatch.setattr(callbacks, "is_bot_authorized", AsyncMock(return_value=True))
    chat = FakeChat(-100555)
    chat.get_administrators = AsyncMock(return_value=[SimpleNamespace(user=SimpleNamespace(id=5))])
    context = _context()
    update = SimpleNamespace(
        effective_chat=chat,
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    await callbacks.add_group(update, context)
    assert await mongodb.group_exists(chat.id)
    assert chat.id in config.allowed_groups.chat_ids
    assert context.chat_data["chat_admins"] == {5}


async def test_check_says_whether_the_group_is_registered(database, monkeypatch):
    monkeypatch.setattr(callbacks, "is_bot_authorized", AsyncMock(return_value=True))
    chat = FakeChat(-100555)
    update = SimpleNamespace(
        effective_chat=chat,
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    await callbacks.check(update, _context())
    update.message.reply_text.assert_awaited_with("This group is not registered.")

    await mongodb.add_group(chat.id)
    await callbacks.check(update, _context())
    update.message.reply_text.assert_awaited_with("This group is registered.")


async def test_remove_group_deletes_only_that_groups_messages(database):
    first, second = -1001, -2001
    assert first % 1000 == second % 1000
    await mongodb.add_group(first)
    await mongodb.add_group(second)
    await mongodb.save_message(_stored(5, first, 1))
    await mongodb.save_message(_stored(5, second, 2))
    config.allowed_groups.add_chat_ids([first, second])
    context = _context()
    context.chat_data["chat_admins"] = {1}
    update = SimpleNamespace(effective_chat=FakeChat(first))
    await callbacks.remove_group(update, context)

    assert context.chat_data == {}
    assert first not in config.allowed_groups.chat_ids
    assert second in config.allowed_groups.chat_ids
    assert not await mongodb.group_exists(first)
    assert await mongodb.group_exists(second)
    assert await mongodb.get_messages(5, first) == []
    assert await mongodb.get_messages(5, second) == [{"chat_id": second, "message_id": 2}]
    assert all(not collection.dropped for collection in database.collections.values())


def _bot_update(chat, member):
    return SimpleNamespace(
        effective_chat=chat,
        my_chat_member=SimpleNamespace(new_chat_member=member),
    )


async def test_bot_removed_deletes_only_that_group(database):
    first, second = -1001, -2001
    await mongodb.add_group(first)
    await mongodb.add_group(second)
    await mongodb.save_message(_stored(5, first, 1))
    await mongodb.save_message(_stored(5, second, 2))
    config.allowed_groups.add_chat_ids([first, second])

    class LeftMember:
        status = ChatMember.LEFT

        @property
        def is_member(self):
            raise AttributeError("left members have no is_member")

    context = _context()
    context.chat_data["chat_admins"] = {1}
    await callbacks.bot_status_changed(_bot_update(FakeChat(first), LeftMember()), context)
    assert not await mongodb.group_exists(first)
    assert await mongodb.group_exists(second)
    assert await mongodb.get_messages(5, second) == [{"chat_id": second, "message_id": 2}]
    assert all(not collection.dropped for collection in database.collections.values())


async def test_bot_with_permissions_is_not_removed_when_is_member_is_absent(database):
    chat_id = -1001
    await mongodb.add_group(chat_id)
    await mongodb.save_message(_stored(5, chat_id, 1))
    config.allowed_groups.add_chat_ids(chat_id)

    class AdminMember:
        status = ChatMember.ADMINISTRATOR
        can_delete_messages = True
        can_restrict_members = True

        @property
        def is_member(self):
            raise AttributeError("administrators have no is_member")

    context = _context()
    await callbacks.bot_status_changed(_bot_update(FakeChat(chat_id), AdminMember()), context)
    assert await mongodb.group_exists(chat_id)
    assert chat_id in config.allowed_groups.chat_ids
    assert await mongodb.get_messages(5, chat_id) == [{"chat_id": chat_id, "message_id": 1}]


async def test_load_allowed_groups_from_storage(database):
    await mongodb.add_group(-100)
    await mongodb.add_group(-200)
    assert -100 not in config.allowed_groups.chat_ids
    await callbacks.load_allowed_groups(None)
    assert -100 in config.allowed_groups.chat_ids
    assert -200 in config.allowed_groups.chat_ids


def test_group_content_filter_matches_edits_and_non_text_not_commands():
    chat_id = -100555
    config.allowed_groups.add_chat_ids(chat_id)
    combined = config.allowed_groups & callbacks.GROUP_CONTENT
    user = User(id=5, is_bot=False, first_name="Ada")
    chat = Chat(id=chat_id, type=Chat.SUPERGROUP)
    now = datetime.now()

    text = Message(message_id=1, date=now, chat=chat, from_user=user, text="hello")
    edited = Update(update_id=1, edited_message=text)
    photo = Message(message_id=2, date=now, chat=chat, from_user=user)
    command = Message(
        message_id=3,
        date=now,
        chat=chat,
        from_user=user,
        text="/add_group",
        entities=(MessageEntity(MessageEntity.BOT_COMMAND, offset=0, length=10),),
    )
    assert combined.check_update(Update(update_id=2, message=text))
    assert combined.check_update(edited)
    assert combined.check_update(Update(update_id=3, message=photo))
    assert not combined.check_update(Update(update_id=4, message=command))
    assert filters.UpdateType.EDITED_MESSAGE.check_update(edited)
