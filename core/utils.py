import re


REASON_TEXT = "text"
REASON_NAME = "name"
REASON_LANGUAGE = "language"
REASON_FLAG = "flag"
REASON_ALREADY_BANNED = "already banned"

_BANNED_LANGUAGES = ("ar", "fa")
# Arabic block covers Arabic and Persian letters. Flags are Iran and Palestine only.
_ARABIC_SCRIPT = re.compile(r"[\u0600-\u06ff]")
_FLAGS = re.compile(r"(?:\U0001F1F5\U0001F1F8)+|(?:\U0001F1EE\U0001F1F7)+")


async def is_bot_authorized(context, chat_id):
    bot = await context.bot.get_me()
    bot_member = await context.bot.get_chat_member(chat_id, bot.id)
    return bot_member.can_delete_messages and bot_member.can_restrict_members


def _signal(text):
    """Return 'flag', 'script', or None. Missing text is not a match."""
    if not isinstance(text, str) or not text:
        return None
    if _FLAGS.search(text) is not None:
        return "flag"
    if _ARABIC_SCRIPT.search(text) is not None:
        return "script"
    return None


def check_text(text):
    return _signal(text) is not None


def user_reason(user):
    if user is None:
        return None
    name_signal = _signal(getattr(user, "first_name", None))
    if name_signal == "flag":
        return REASON_FLAG
    language = getattr(user, "language_code", None)
    if language in _BANNED_LANGUAGES:
        return REASON_LANGUAGE
    if name_signal == "script":
        return REASON_NAME
    return None


def check_user(user):
    return user_reason(user) is not None


def _message_fields(message):
    yield "text", getattr(message, "text", None)
    yield "text", getattr(message, "caption", None)
    origin = getattr(message, "forward_origin", None)
    if origin is None:
        return
    for attr in ("chat", "sender_chat"):
        forwarded = getattr(origin, attr, None)
        if forwarded is not None:
            yield "text", getattr(forwarded, "title", None)
    sender = getattr(origin, "sender_user", None)
    if sender is not None:
        yield "name", getattr(sender, "first_name", None)
    hidden_name = getattr(origin, "sender_user_name", None)
    if isinstance(hidden_name, str):
        yield "name", hidden_name


def message_reason(message):
    if message is None:
        return None
    script_reason = None
    for kind, value in _message_fields(message):
        signal = _signal(value)
        if signal == "flag":
            return REASON_FLAG
        if signal == "script" and script_reason is None:
            script_reason = REASON_NAME if kind == "name" else REASON_TEXT
    return script_reason


def check_message(message):
    return message_reason(message) is not None


#by t.me/yehuda100
