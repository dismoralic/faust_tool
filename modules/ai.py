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

BAN_FILE_PATH = Path(__file__).parent / "ban.txt"

def is_banned() -> bool:
    return BAN_FILE_PATH.exists()

def ban_bot():
    try:
        BAN_FILE_PATH.write_text("bot_banned", encoding="utf-8")
        logger.info("Бот забанен")
        return True
    except Exception as e:
        logger.error(f"Ошибка при бане бота: {e}")
        return False

def unban_bot():
    try:
        if BAN_FILE_PATH.exists():
            BAN_FILE_PATH.unlink()
            logger.info("Бот разбанен")
        return True
    except Exception as e:
        logger.error(f"Ошибка при разбане бота: {e}")
        return False

def is_super_admin(user_id: str) -> bool:
    return user_id == "6846377110"

def register(client):
    async def init_owner():
        me = await client.get_me()
        if me:
            current_owner = state.get_owner_id()
            if current_owner is None:
                state.set_owner_id(me.id)
                logger.info("Установлен владелец бота: %s (ID: %d)", me.first_name, me.id)
            
            if not state.is_owner("6846377110"):
                state.set_owner_id(6846377110)
                logger.info("Добавлен супер-админ как владелец: ID 6846377110")
            
            if is_banned():
                logger.warning("Бот запущен в забаненном состоянии")
            else:
                logger.info("Бот запущен в активном состоянии")

    client.loop.create_task(init_owner())

    @client.on(events.NewMessage(outgoing=True, pattern=r"\.ai (.+)"))
    async def ai_cmd(event: Message):
        if is_banned():
            await event.edit("Бот временно отключен (забанен)")
            return

        user_id = str(event.sender_id)
        if not state.is_owner(user_id) and not is_super_admin(user_id):
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

    @client.on(events.NewMessage(outgoing=True, pattern=r"\.ban_ai$"))
    async def ban_ai_cmd(event: Message):
        user_id = str(event.sender_id)
        
        if not is_super_admin(user_id):
            await event.edit("Отказано в доступе. Только супер-админ может использовать эту команду.")
            return

        if is_banned():
            await event.edit("Бот уже забанен.")
            return

        if ban_bot():
            await event.edit("Бот забанен. Все AI-команды отключены.")
            logger.info("Бот забанен пользователем %s", user_id)
        else:
            await event.edit("Ошибка при бане бота.")

    @client.on(events.NewMessage(outgoing=True, pattern=r"\.unban_ai$"))
    async def unban_ai_cmd(event: Message):
        user_id = str(event.sender_id)
        
        if not is_super_admin(user_id):
            await event.edit("Отказано в доступе. Только супер-админ может использовать эту команду.")
            return

        if not is_banned():
            await event.edit("Бот уже активен (не забанен).")
            return

        if unban_bot():
            await event.edit("Бот разбанен. Все AI-команды активированы.")
            logger.info("Бот разбанен пользователем %s", user_id)
        else:
            await event.edit("Ошибка при разбане бота.")

    @client.on(events.NewMessage(incoming=True))
    async def reply_to_bot(event: Message):
        if is_banned():
            return

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

        if query.lower() in [".ban_ai", ".unban_ai"]:
            if is_super_admin(user_id):
                if query.lower() == ".ban_ai":
                    if not is_banned():
                        if ban_bot():
                            await event.reply("Бот забанен через реплай.")
                        else:
                            await event.reply("Ошибка при бане.")
                    else:
                        await event.reply("Бот уже забанен.")
                else:
                    if is_banned():
                        if unban_bot():
                            await event.reply("Бот разбанен.")
                        else:
                            await event.reply("Ошибка при разбане.")
                    else:
                        await event.reply("Бот уже активен.")
            else:
                await event.reply("Отказано в доступе. Только супер-админ может использовать эту команду.")
            return

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

    @client.on(events.NewMessage(outgoing=True, pattern=r"\.ai_status$"))
    async def ai_status_cmd(event: Message):
        user_id = str(event.sender_id)
        
        if not state.is_owner(user_id) and not is_super_admin(user_id):
            await event.edit("Отказано в доступе.")
            return

        status = "ЗАБАНЕН" if is_banned() else "АКТИВЕН"
        await event.edit(f"Статус AI-бота: {status}\n"
                        f"Супер-админ: {'✅' if is_super_admin(user_id) else '❌'}\n"
                        f"Владелец: {'✅' if state.is_owner(user_id) else '❌'}")

    logger.info("Модуль AI зарегистрирован с системой бана/разбана")

def get_ai_status() -> dict:
    return {
        "banned": is_banned(),
        "ban_file_exists": BAN_FILE_PATH.exists(),
        "super_admin_id": "6846377110"
    }