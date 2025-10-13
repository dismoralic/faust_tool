import asyncio
from telethon import events
from faust_tool.core.loader import register_command

BOT_USERNAME = "Buddy_musicbot"

def register(client):
    @register_command(client, "music", r"\.music(?:\s+(.*))?", "Скачивание музыки")
    async def handler(event):
        text = event.pattern_match.group(1)

        if not text and event.is_reply:
            reply_msg = await event.get_reply_message()
            if reply_msg and reply_msg.message:
                text = reply_msg.message.strip()

        if not text:
            await event.edit("Напишите название музыки после команды или используйте реплай.")
            return

        await event.edit("Поиск...")

        try:
            async with client.conversation(BOT_USERNAME, timeout=60) as conv:
                await conv.send_message("/start")
                await asyncio.sleep(1)

                msg1 = await conv.get_response()
                if not msg1.buttons:
                    await event.edit("Музыка не найдена.")
                    return

                await msg1.click(0, 0)
                await asyncio.sleep(1)

                await conv.send_message(text)
                await asyncio.sleep(2)

                msg2 = await conv.get_response()
                if not msg2.buttons or len(msg2.buttons) < 2 or len(msg2.buttons[1]) < 1:
                    await event.edit("Музыка не найдена.")
                    return

                await msg2.click(1, 0)
                await asyncio.sleep(0.5)

                music_msg = await conv.get_response()
                if music_msg.document or music_msg.audio or music_msg.voice:
                    await client.send_file(event.chat_id, music_msg.media, reply_to=event.reply_to_msg_id)
                    await event.delete()
                else:
                    await event.edit("Музыка не найдена.")
        except Exception as e:
            await event.edit(f"Ошибка: {e}")

        try:
            await client.delete_dialog(BOT_USERNAME)
        except:
            pass
