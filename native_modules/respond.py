from datetime import datetime, timedelta
from telethon import events
from faust_tool.core.loader import register_command

last_response = {}
response_text = ""
cooldown_time = timedelta(days=1)

exclude_contacts = False
excluded_ids = set()

def register(client):
    @register_command(client, "respond_onoff", r"\.respond (on|off)(?:\s+(.*))?", "Автоответчик: включить/выключить")
    async def toggle_responder(event):
        global response_text
        command = event.pattern_match.group(1)
        text = event.pattern_match.group(2)

        if command == "on" and text:
            response_text = text
            await event.edit("Автоответчик включен.")
        elif command == "off":
            response_text = ""
            await event.edit("Автоответчик отключен.")
        else:
            await event.edit("Использование:\n.respond on <текст>\n.respond off")

    @register_command(client, "respond_time", r"\.respond time (\d+) (h|m|s)", "Установить перезарядку автоответчика")
    async def set_cooldown(event):
        global cooldown_time
        value = int(event.pattern_match.group(1))
        unit = event.pattern_match.group(2)

        if unit == "h":
            cooldown_time = timedelta(hours=value)
        elif unit == "m":
            cooldown_time = timedelta(minutes=value)
        elif unit == "s":
            cooldown_time = timedelta(seconds=value)

        await event.edit(f"Перезарядка автоответчика установлена на {value} {unit}.")

    @register_command(client, "respond_contacts", r"\.respond ([+-])contacts", "Вкл/выкл ответы контактам")
    async def toggle_contacts_exclusion(event):
        global exclude_contacts
        sign = event.pattern_match.group(1)
        exclude_contacts = (sign == "-")
        status = "не отвечать контактам" if exclude_contacts else "снова отвечать контактам"
        await event.edit(f"Автоответчик теперь будет {status}.")

    @register_command(client, "respond_id", r"\.respond ([+-])id (\d+)", "Вкл/выкл ответы конкретному ID")
    async def toggle_id_exclusion(event):
        global excluded_ids
        sign = event.pattern_match.group(1)
        user_id = int(event.pattern_match.group(2))

        if sign == "-":
            excluded_ids.add(user_id)
            await event.edit(f"Автоответчик отключен для пользователя с ID {user_id}.")
        else:
            excluded_ids.discard(user_id)
            await event.edit(f"Автоответчик включен для пользователя с ID {user_id}.")

    @client.on(events.NewMessage(incoming=True))
    async def auto_respond(event):
        global last_response, response_text, cooldown_time
        if not response_text or not event.is_private:
            return

        sender = await event.get_sender()
        if sender is None or sender.bot:
            return

        user_id = sender.id

        if user_id in excluded_ids:
            return
        if exclude_contacts and sender.contact:
            return

        now = datetime.now()
        if user_id not in last_response or now - last_response[user_id] >= cooldown_time:
            last_response[user_id] = now
            await event.reply(response_text)
