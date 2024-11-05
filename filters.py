
from telegram import Update
from telegram.ext.filters import UpdateFilter


class FilterChatAdmins(UpdateFilter):
    async def __call__(self, update: Update) -> bool:
        user_id = update.effective_user.id
        member = await update.effective_chat.get_member(user_id)
        return member.status in ['ADMINISTRATOR', 'OWNER']

        
filter_chat_anmins = FilterChatAdmins()

#by t.me/yehuda100