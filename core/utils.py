import asyncio
import re


# This function runs an async function within a sync function, while checking the event loop status.
def run_async(async_func, *args, **kwargs):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if not loop.is_running():
        return loop.run_until_complete(async_func(*args, **kwargs))
    else:
        future = asyncio.ensure_future(async_func(*args, **kwargs))
        loop.run_until_complete(future)
        return future.result()
    

# Checks if the bot has the required permissions in a given chat.
async def is_bot_authorized(context, chat_id):
    bot = await context.bot.get_me()
    bot_member = await context.bot.get_chat_member(chat_id, bot.id)
    return bot_member.can_delete_messages and bot_member.can_restrict_members


# These three functions work together to evaluate text, user, and message characteristics.
# They determine if Arabic script or certain flag emojis are present, either in the text content,
# user's language and name, or within various parts of a message. 
def check_text(text):
    flags = r"(\U0001F1F5\U0001F1F8)+|(\U0001F1EE\U0001F1F7)+"
    pattern = r"[\u0600-\u06ff]+" + r"|" + flags
    return bool(re.search(pattern, text))

def check_user(user):
    return user.language_code in ("ar", "fa") or check_text(user.first_name)

def check_message(message):
    if any([
        message.text and check_text(message.text),
        message.caption and check_text(message.caption),
        message.forward_origin and message.forward_origin.chat and check_text(message.forward_origin.chat.title),
        message.forward_origin and message.forward_origin.sender_user and check_text(message.forward_origin.sender_user.first_name)
    ]):
        return True
    return False


    #by t.me/yehuda100