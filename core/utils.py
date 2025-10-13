import os
import re
import typing
from telethon.tl.types import Message

def ensure_folder(path: str):
    if not os.path.exists(path):
        os.makedirs(path)

def clean_text(text: str) -> str:
    return " ".join(text.split())

def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

def get_args_raw(message: Message) -> str:
    return message.raw_text.split(maxsplit=1)[1] if len(message.raw_text.split()) > 1 else ""

def get_args(message: Message) -> typing.List[str]:
    return message.raw_text.split()[1:]

def remove_emoji(text: str) -> str:
    return re.sub(r"[\U00010000-\U0010ffff]", "", text)

async def answer(message: Message, text: str, **kwargs):
    if message.out:
        return await message.edit(text, **kwargs)
    return await message.reply(text, **kwargs)

async def answer_file(message: Message, file, **kwargs):
    if message.out:
        return await message.edit(file=file, **kwargs)
    return await message.reply(file=file, **kwargs)
