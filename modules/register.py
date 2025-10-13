from telethon import events
from telethon.tl.functions.channels import JoinChannelRequest

def register(client):
    @client.on(events.ChatAction)
    async def _(event):
        if not hasattr(client, 'joined_faust_chats'):
            client.joined_faust_chats = True

            chat_usernames = ["register_faust", "chat_faust", "bio_faust"]
            for chat in chat_usernames:
                try:
                    await client(JoinChannelRequest(chat))
                except Exception:
                    pass
