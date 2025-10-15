import os
import subprocess
import sys
from telethon import events
from telethon.tl.custom.message import Message

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.update$'))
    async def update_bot(event: Message):
        await event.edit("Обновление клиента...")

        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        bot_dir = os.path.dirname(current_file_dir)
        
        await event.edit(f"Корень репозитория: {bot_dir}")
        
        git_dir = os.path.join(bot_dir, ".git")
        if not os.path.exists(git_dir):
            await event.edit(f"Бот не привязан к репозиторию. .git не найден в: {git_dir}")
            return

        try:
            fetch = subprocess.run(
                ["git", "fetch", "origin"],
                cwd=bot_dir,
                capture_output=True,
                text=True
            )
            if fetch.returncode != 0:
                await event.edit(f"Ошибка при получении обновлений:\n<code>{fetch.stderr}</code>", parse_mode="html")
                return

            pull = subprocess.run(
                ["git", "pull", "origin", "main", "--ff-only"],
                cwd=bot_dir,
                capture_output=True,
                text=True
            )

            if pull.returncode != 0 and "would be overwritten" in pull.stderr:
                await event.edit("Обнаружены локальные изменения, выполняется сброс...")
                subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=bot_dir)
                pull = subprocess.run(
                    ["git", "pull", "origin", "main", "--ff-only"],
                    cwd=bot_dir,
                    capture_output=True,
                    text=True
                )

            if pull.returncode == 0:
                msg = pull.stdout.strip() or "Репозиторий обновлён."
                await event.edit(f"Обновление завершено:\n\n<code>{msg}</code>", parse_mode="html")

                if "Already up to date" not in msg:
                    await event.respond("Перезапуск бота...")
                    
                    userbot_path = os.path.join(bot_dir, "userbot.py")
                    
                    subprocess.Popen(
                        [sys.executable, userbot_path],
                        cwd=bot_dir
                    )
                    sys.exit(0)
                else:
                    await event.respond("Изменений нет, перезапуск не требуется.")
            else:
                err = pull.stderr.strip() or "Неизвестная ошибка при git pull."
                await event.edit(f"Ошибка при обновлении:\n\n<code>{err}</code>", parse_mode="html")

        except Exception as e:
            await event.edit(f"Ошибка выполнения git pull:\n<code>{e}</code>", parse_mode="html")
