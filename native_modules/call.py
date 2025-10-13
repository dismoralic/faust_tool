from faust_tool.core.loader import register_command

async def get_users(client, chat_id, limit=100):
    users = []
    async for user in client.iter_participants(chat_id):
        if user.bot:
            continue
        users.append(f"[{user.first_name or 'Без имени'}](tg://user?id={user.id})")
        if len(users) >= limit:
            break
    return users

def register(client):
    @register_command(client, "call", r"\.call(?: (\d+))?", "позвать пользователей (лимит)")  
    async def call_command(event):
        me = await event.client.get_me()
        if event.sender_id != me.id:
            return

        chat = await event.get_chat()
        match = event.pattern_match.group(1)
        limit = int(match) if match else 100

        users = await get_users(event.client, chat.id, limit)

        if not users:
            await event.reply("Не удалось собрать пользователей.")
            return

        message = " ".join(users)
        if len(message) > 4096:
            parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for part in parts:
                await event.respond(part)
        else:
            await event.reply(message)

        await event.delete()
