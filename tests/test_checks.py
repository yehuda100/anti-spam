from datetime import datetime
from types import SimpleNamespace

from telegram import Chat, MessageOriginChannel, MessageOriginChat, MessageOriginHiddenUser, MessageOriginUser, User

from core.utils import (
    REASON_FLAG,
    REASON_LANGUAGE,
    REASON_NAME,
    REASON_TEXT,
    check_message,
    check_text,
    check_user,
    message_reason,
    user_reason,
)


ARABIC = "مرحبا"
PERSIAN = "ژاله"
HEBREW = "שלום"
ENGLISH = "hello"
IRAN_FLAG = "🇮🇷"
PALESTINE_FLAG = "🇵🇸"
ISRAEL_FLAG = "🇮🇱"
FRANCE_FLAG = "🇫🇷"


def _user(first_name="Ada", language_code="en"):
    return SimpleNamespace(id=1, first_name=first_name, language_code=language_code, full_name=first_name)


def _message(**kwargs):
    defaults = {"text": None, "caption": None, "forward_origin": None}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_arabic_and_persian_text_match():
    assert check_text(ARABIC)
    assert check_text(PERSIAN)
    assert check_text(f"note {ARABIC}")
    assert message_reason(_message(text=ARABIC)) == REASON_TEXT
    assert message_reason(_message(text=PERSIAN)) == REASON_TEXT


def test_hebrew_and_english_do_not_match():
    assert not check_text(HEBREW)
    assert not check_text(ENGLISH)
    assert not check_text("Hello, world")
    assert not check_text(f"{HEBREW} {ENGLISH}")
    assert not check_message(_message(text=HEBREW))
    assert not check_message(_message(text=ENGLISH, caption=HEBREW))
    assert not check_user(_user(first_name="David", language_code="he"))
    assert not check_user(_user(first_name="David", language_code="en"))


def test_flags_match_only_iran_and_palestine():
    assert check_text(IRAN_FLAG)
    assert check_text(PALESTINE_FLAG)
    assert check_text(f"see {IRAN_FLAG}")
    assert check_text(f"see {PALESTINE_FLAG}")
    assert message_reason(_message(text=IRAN_FLAG)) == REASON_FLAG
    assert message_reason(_message(caption=PALESTINE_FLAG)) == REASON_FLAG
    assert not check_text(ISRAEL_FLAG)
    assert not check_text(FRANCE_FLAG)
    assert not check_text("IR")
    assert not check_text("PS")


def test_arabic_first_name_and_banned_language_codes():
    assert check_user(_user(first_name=ARABIC, language_code="en"))
    assert user_reason(_user(first_name=PERSIAN, language_code="en")) == REASON_NAME
    assert check_user(_user(first_name="Lina", language_code="ar"))
    assert user_reason(_user(first_name="Lina", language_code="fa")) == REASON_LANGUAGE
    assert user_reason(_user(first_name=IRAN_FLAG, language_code="en")) == REASON_FLAG
    assert user_reason(_user(first_name=ARABIC, language_code="ar")) == REASON_LANGUAGE


def test_caption_and_forwarded_chat_title():
    assert check_message(_message(caption=ARABIC))
    assert message_reason(_message(caption=PERSIAN)) == REASON_TEXT

    channel = MessageOriginChannel(
        date=datetime.now(),
        chat=Chat(id=-100, type=Chat.CHANNEL, title=ARABIC),
        message_id=3,
    )
    assert check_message(_message(forward_origin=channel))
    assert message_reason(_message(forward_origin=channel)) == REASON_TEXT

    forwarded_chat = MessageOriginChat(
        date=datetime.now(),
        sender_chat=Chat(id=-200, type=Chat.SUPERGROUP, title=PERSIAN),
    )
    assert check_message(_message(forward_origin=forwarded_chat))

    hebrew_channel = MessageOriginChannel(
        date=datetime.now(),
        chat=Chat(id=-100, type=Chat.CHANNEL, title=HEBREW),
        message_id=4,
    )
    assert not check_message(_message(forward_origin=hebrew_channel))


def test_forwarded_user_name_matches_and_does_not_crash():
    origin = MessageOriginUser(
        date=datetime.now(),
        sender_user=User(id=9, is_bot=False, first_name=ARABIC),
    )
    assert check_message(_message(forward_origin=origin))
    assert message_reason(_message(forward_origin=origin)) == REASON_NAME

    english = MessageOriginUser(
        date=datetime.now(),
        sender_user=User(id=9, is_bot=False, first_name="John"),
    )
    assert not check_message(_message(forward_origin=english))

    hidden = MessageOriginHiddenUser(date=datetime.now(), sender_user_name=PERSIAN)
    assert check_message(_message(forward_origin=hidden))
    assert not check_message(
        _message(forward_origin=MessageOriginHiddenUser(date=datetime.now(), sender_user_name=ENGLISH))
    )


def test_missing_name_or_text_does_not_throw():
    assert check_text(None) is False
    assert check_text("") is False
    assert not check_user(SimpleNamespace(language_code="en"))
    assert not check_user(SimpleNamespace(first_name=None, language_code=None))
    assert not check_user(None)
    assert not check_message(None)
    assert not check_message(SimpleNamespace())
    assert not check_message(_message(forward_origin=SimpleNamespace(chat=SimpleNamespace(title=None))))
    assert not check_message(_message(forward_origin=SimpleNamespace()))
