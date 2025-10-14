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
            fetch_result = subprocess.run(
                ["git", "fetch", "origin"],
                cwd=bot_dir,
                capture_output=True,
                text=True
            )
            
            if fetch_result.returncode != 0:
                await event.edit(f"Ошибка при получении обновлений:\n<code>{fetch_result.stderr}</code>", parse_mode="html")
                return

            process = subprocess.run(
                ["git", "pull", "origin", "main", "--ff-only"],
                cwd=bot_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if process.returncode == 0:
                msg = process.stdout.strip() or "Репозиторий обновлён."
                await event.edit(f"Обновление завершено:\n\n<code>{msg}</code>", parse_mode="html")
                
                if "Already up to date" not in msg:
                    await event.respond("Перезапуск бота...")
                    os.chdir(bot_dir)
                    sys.path.insert(0, bot_dir)
                    os.execl(sys.executable, sys.executable, "-m", "faust_tool.userbot")
                else:
                    await event.respond("Изменений нет, перезапуск не требуется.")
                
            else:
                err = process.stderr.strip() or "Неизвестная ошибка при git pull."
                await event.edit(f"Ошибка при обновлении:\n\n<code>{err}</code>", parse_mode="html")

        except Exception as e:
            await event.edit(f"Ошибка выполнения git pull:\n<code>{e}</code>", parse_mode="html")
