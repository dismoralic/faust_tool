import logging
import asyncio
import os
from pathlib import Path
from telethon import events
from telethon.tl.custom.message import Message
from faust_tool.ai import brain
from faust_tool.ai import state

logger = logging.getLogger("faust_assistant")
reply_lock = asyncio.Lock()

def register(client):
    async def init_owner():
        try:
            me = await client.get_me()
            if me:
                state.set_account_user_id(me.id)
                logger.info("Установлен владелец бота: %s (ID: %d)", me.first_name, me.id)
                logger.info("Бот запущен в активном состоянии")
        except Exception as e:
            logger.error("Ошибка установки ID аккаунта: %s", e)

    client.loop.create_task(init_owner())

    @client.on(events.NewMessage(outgoing=True, pattern=r"\.ai (.+)"))
    async def ai_cmd(event: Message):
        user_id = str(event.sender_id)
        if not state.is_owner(user_id):
            await event.edit("Отказано в доступе. Только владелец может использовать команду .ai")
            return

        query = event.pattern_match.group(1).strip()
        logger.info("AI_CMD | user_id=%s query=%r", user_id, query)
        thinking_msg = await event.edit("Думаю…")
        try:
            answer = await brain.analyze(query, user_id)
            if not isinstance(answer, str):
                answer = str(answer)
            await thinking_msg.edit(answer)
            logger.info("Responded to .ai query=%r", query)
        except Exception:
            await thinking_msg.edit("Ошибка при обработке запроса. Смотри логи.")
            logger.exception("Exception while processing .ai query=%r", query)

    @client.on(events.NewMessage(incoming=True))
    async def reply_to_bot(event: Message):
        if not state.is_auto_reply():
            return

        if getattr(event.sender, "bot", False):
            return
        if getattr(event.chat, "forum", False) or getattr(event.message, "is_forum", False):
            return

        me = await client.get_me()
        replied = await event.get_reply_message()
        if not replied or replied.sender_id != me.id:
            return

        query = event.raw_text.strip()
        user_id = str(event.sender_id)

        is_command, response = state.process_state_command(query, user_id)
        if is_command:
            if response.startswith("Отказано в доступе"):
                await event.reply(response)
            else:
                await event.reply(response)
            return

        user_display_name = ""
        if event.sender:
            user_display_name = event.sender.first_name or ""
            if event.sender.last_name:
                user_display_name += f" {event.sender.last_name}"
            if event.sender.username:
                user_display_name += f" (@{event.sender.username})"
            user_display_name = user_display_name.strip()

        logger.info("REPLY_CMD | user_id=%s query=%r display_name=%s", user_id, query, user_display_name)
        async with reply_lock:
            thinking_msg = await event.reply("Думаю…")
            try:
                answer = await brain.analyze(query, user_id, user_display_name=user_display_name)
                if not isinstance(answer, str):
                    answer = str(answer)
                await thinking_msg.edit(answer)
                logger.info("Replied to user query=%r", query)
            except Exception:
                await thinking_msg.edit("Ошибка при обработке запроса. Смотри логи.")
                logger.exception("Exception while processing reply query=%r", query)

    logger.info("Модуль AI зарегистрирован")
