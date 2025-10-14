import os
import subprocess
import sys
from telethon import events
from telethon.tl.custom.message import Message

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.update$'))
    async def update_bot(event: Message):
        await event.edit("Обновление клиента...")

        bot_dir = os.getcwd()
        
        if not os.path.exists(os.path.join(bot_dir, ".git")):
            await event.edit("Бот не привязан к репозиторию.")
            return

        try:
            process = subprocess.run(
                ["git", "reset", "--hard", "origin/main"],
                cwd=bot_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if process.returncode == 0:
                msg = "Репозиторий обновлён до последней версии."
                await event.edit(f"Обновление завершено:\n\n<code>{msg}</code>", parse_mode="html")
                await event.respond("Перезапуск бота...")
                
                script_path = os.path.join(bot_dir, "faust_tool", "userbot.py")
                subprocess.Popen([sys.executable, script_path], cwd=bot_dir)
                sys.exit(0)
                
            else:
                err = process.stderr.strip() or "Неизвестная ошибка при обновлении."
                await event.edit(f"Ошибка при обновлении:\n\n<code>{err}</code>", parse_mode="html")

        except Exception as e:
            await event.edit(f"Ошибка выполнения git pull:\n<code>{e}</code>", parse_mode="html")
