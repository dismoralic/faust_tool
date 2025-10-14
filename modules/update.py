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
            tracking_check = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                cwd=bot_dir,
                capture_output=True,
                text=True
            )
            
            if tracking_check.returncode != 0:
                subprocess.run(
                    ["git", "branch", "--set-upstream-to=origin/main", "main"],
                    cwd=bot_dir,
                    capture_output=True
                )
            
            process = subprocess.run(
                ["git", "pull"],
                cwd=bot_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if process.returncode == 0:
                msg = process.stdout.strip() or "Репозиторий обновлён."
                await event.edit(f"Обновление завершено:\n\n<code>{msg}</code>", parse_mode="html")
                
                await event.respond("Перезапуск бота...")
                os.execl(sys.executable, sys.executable, *sys.argv)
                
            else:
                err = process.stderr.strip() or "Неизвестная ошибка при git pull."
                await event.edit(f"Ошибка при обновлении:\n\n<code>{err}</code>", parse_mode="html")

        except Exception as e:
            await event.edit(f"Ошибка выполнения git pull:\n<code>{e}</code>", parse_mode="html")