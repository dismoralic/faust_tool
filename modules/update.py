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
        bot_dir = os.path.abspath(os.path.join(current_file_dir, "..", ".."))

        await event.edit(f"Корень репозитория: {bot_dir}")

        git_dir = os.path.join(bot_dir, ".git")
        
        if not os.path.exists(git_dir):
            await event.edit("Репозиторий не найден. Привязываю к GitHub...")
            
            try:
                init = subprocess.run(
                    ["git", "init"],
                    cwd=bot_dir,
                    capture_output=True,
                    text=True
                )
                if init.returncode != 0:
                    await event.edit(f"Ошибка инициализации git: {init.stderr}")
                    return
                
                remote = subprocess.run(
                    ["git", "remote", "add", "origin", "https://github.com/dismoralic/faust_tool.git"],
                    cwd=bot_dir,
                    capture_output=True,
                    text=True
                )
                if remote.returncode != 0:
                    await event.edit(f"Ошибка добавления remote: {remote.stderr}")
                    return
                
                await event.edit("Репозиторий привязан! Получаю обновления...")
                
            except Exception as e:
                await event.edit(f"Ошибка привязки к репозиторию: {e}")
                return

        try:
            remote_check = subprocess.run(
                ["git", "remote", "-v"],
                cwd=bot_dir,
                capture_output=True,
                text=True
            )
            
            await event.edit(f"Remote: {remote_check.stdout}")
            
            if "dismoralic/faust_tool" not in remote_check.stdout:
                subprocess.run(
                    ["git", "remote", "add", "origin", "https://github.com/dismoralic/faust_tool.git"],
                    cwd=bot_dir
                )
            
            fetch = subprocess.run(
                ["git", "fetch", "origin"],
                cwd=bot_dir,
                capture_output=True,
                text=True
            )
            
            if fetch.returncode != 0:
                await event.edit("Пробую принудительно установить связь...")
                pull = subprocess.run(
                    ["git", "pull", "origin", "main", "--allow-unrelated-histories"],
                    cwd=bot_dir,
                    capture_output=True,
                    text=True
                )
            else:
                pull = subprocess.run(
                    ["git", "pull", "origin", "main", "--ff-only"],
                    cwd=bot_dir,
                    capture_output=True,
                    text=True
                )

            if pull.returncode != 0 and "would be overwritten" in pull.stderr:
                await event.edit("Обнаружены локальные изменения, выполняется сброс...")
                subprocess.run(["git", "reset", "--hard", "origin/main"], cwd=bot_dir)
                pull = subprocess.run(
                    ["git", "pull", "origin", "main"],
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
                    subprocess.Popen([sys.executable, userbot_path], cwd=bot_dir)
                    sys.exit(0)
                else:
                    await event.respond("Изменений нет, перезапуск не требуется.")
            else:
                await event.edit("Пробую принудительное обновление...")
                subprocess.run(["git", "reset", "--hard", "origin/main"], cwd=bot_dir)
                
                await event.edit("Бот обновлен принудительно! Перезапуск...")
                userbot_path = os.path.join(bot_dir, "userbot.py")
                subprocess.Popen([sys.executable, userbot_path], cwd=bot_dir)
                sys.exit(0)

        except Exception as e:
            await event.edit(f"Ошибка выполнения git pull:\n<code>{e}</code>", parse_mode="html")
