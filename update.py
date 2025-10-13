import os
import subprocess
from telethon import events
from telethon.tl.custom.message import Message

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.update$'))
    async def update_bot(event: Message):
        await event.edit("Обновление клиента...")

        if not os.path.exists(".git"):
            await event.edit("Бот не привязан к репозиторию.")
            return

        try:
            process = subprocess.run(
                ["git", "pull"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if process.returncode == 0:
                msg = process.stdout.strip() or "Репозиторий обновлён."
                await event.edit(f"Обновление завершено:\n\n<code>{msg}</code>", parse_mode="html")
            else:
                err = process.stderr.strip() or "Неизвестная ошибка при git pull."
                await event.edit(f"Ошибка при обновлении:\n\n<code>{err}</code>", parse_mode="html")

        except Exception as e:
            await event.edit(f"Ошибка выполнения git pull:\n<code>{e}</code>", parse_mode="html")
