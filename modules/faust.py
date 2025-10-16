import os
import time
from telethon import events
from telethon.tl.custom.message import Message

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.faust$'))
    async def faust_cmd(event: Message):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(base_dir)
        pictures_dir = os.path.join(project_root, 'pictures')
        photo_path = os.path.join(pictures_dir, 'faust.jpg')

        start = time.perf_counter()

        if os.path.exists(photo_path):
            sent = await client.send_file(
                event.chat_id,
                photo_path,
                caption="Отправляю фото..."
            )
        else:
            sent = await event.respond("Фото faust.jpg не найдено в папке pictures")

        ping_ms = (time.perf_counter() - start) * 1000

        text = (
            "𝕱𝖆𝖚𝖘𝖙-𝕿𝖔𝖔𝖑\n"
            "FTG + Native modules userbot client.\n"
            "Version: 1.0.0\n\n"
            f"Ping: {ping_ms:.2f} ms\n\n"
            "Only those who will risk going too far can possibly find out how far one can go\n\n"
            "Dev: @angel_xranytel\n\n"
            "Channel: @bio_faust\n\n"
        )

        await sent.edit(text)
        await event.delete()

