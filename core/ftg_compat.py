import sys
from telethon.tl.functions.messages import DeleteMessagesRequest
from telethon import events
import asyncio

class Module:
    def __init__(self):
        if not hasattr(self, "strings"):
            self.strings = {"name": self.__class__.__name__}
        self.name = self.strings.get("name", self.__class__.__name__)

def sudo(func):
    return func

def tds(strings: dict):
    return strings

async def group_admin_delete_messages(message_ids, chat=None):
    global client
    if client is None:
        return

    if not isinstance(message_ids, list):
        message_ids = [message_ids]

    if chat is None:
        return

    try:
        await client(DeleteMessagesRequest(chat, message_ids))
    except Exception:
        pass

async def delete_messages(client, chat, message_ids):
    await group_admin_delete_messages(client, chat, message_ids)

def register(func):
    return func

def ratelimit(limit: int = 1):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator

client = None

NewMessage = events.NewMessage
EditedMessage = events.MessageEdited