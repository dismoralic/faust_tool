import asyncio
from telethon import events
from faust_tool.core.loader import register_command

spam_running = {}
spam_counter_enabled = {}
spam_delay = {}

def register(client):
    @register_command(client, "spam", r"\.spam (\d+)(?: (.+))?", desc="Спамит текстом или сообщением N раз")
    async def spam_handler(event):
        count = int(event.pattern_match.group(1))
        text = event.pattern_match.group(2)
        chat_id = event.chat_id

        spam_running.setdefault(chat_id, True)
        spam_counter_enabled.setdefault(chat_id, False)
        spam_delay.setdefault(chat_id, 0)

        if text:
            message_to_send = text
        else:
            reply_msg = await event.get_reply_message()
            if not reply_msg:
                await event.edit("Нужно либо указать текст после команды, либо ответить на сообщение.")
                return
            message_to_send = reply_msg

        sent_count = 0
        if spam_counter_enabled[chat_id]:
            await event.edit(f"Отправлено: 0/{count}")

        for i in range(count):
            if not spam_running[chat_id]:
                break

            await client.send_message(chat_id, message_to_send)
            sent_count += 1

            if spam_counter_enabled[chat_id]:
                await event.edit(f"Отправлено: {sent_count}/{count}")

            await asyncio.sleep(spam_delay[chat_id] / 1000)

        if not spam_counter_enabled[chat_id]:
            await event.delete()

    @register_command(client, "spam", r"\.spam off", desc="Останавливает текущий спам")
    async def stop_spam(event):
        chat_id = event.chat_id
        spam_running[chat_id] = False
        await event.edit("Спам остановлен.")

    @register_command(client, "spam", r"\.spam counter (on|off)", desc="Включает/выключает счётчик отправленных сообщений")
    async def toggle_counter(event):
        chat_id = event.chat_id
        choice = event.pattern_match.group(1).lower()
        spam_counter_enabled[chat_id] = (choice == "on")
        await event.edit(f"Счётчик {'включен' if spam_counter_enabled[chat_id] else 'выключен'}.")

    @register_command(client, "spam", r"\.spam time (\d+)", desc="Устанавливает задержку между сообщениями в мс")
    async def set_delay(event):
        chat_id = event.chat_id
        spam_delay[chat_id] = int(event.pattern_match.group(1))
        await event.edit(f"Задержка между сообщениями: {spam_delay[chat_id]} мс.")
