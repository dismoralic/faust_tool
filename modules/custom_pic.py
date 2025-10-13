import os
from telethon import events
from telethon.tl.custom.message import Message
from PIL import Image

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PICTURES_DIR = os.path.join(BASE_DIR, "pictures")

if not os.path.exists(PICTURES_DIR):
    os.makedirs(PICTURES_DIR)

def register(client):
    @client.on(events.NewMessage(pattern=r'^\.load_(faust|help)\b'))
    async def load_image(event: Message):
        if not event.is_reply:
            await event.edit("Нужно ответить на фотографию.")
            return

        reply = await event.get_reply_message()
        if not reply.media:
            await event.edit("В ответе на сообщение нет фотографии.")
            return

        name = event.pattern_match.group(1)
        final_file = os.path.join(PICTURES_DIR, f"{name}.jpg")
        temp_file = os.path.join(PICTURES_DIR, f"temp_{name}.tmp")

        if os.path.exists(final_file):
            os.remove(final_file)

        await reply.download_media(temp_file)

        if not os.path.exists(temp_file):
            await event.edit("Ошибка: не удалось скачать изображение.")
            return

        try:
            with Image.open(temp_file) as img:
                rgb_img = img.convert("RGB")
                rgb_img.save(final_file, format="JPEG")
        except Exception as e:
            await event.edit(f"Ошибка при обработке изображения: {e}")
            return
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

        await event.edit(f"Картинка `{name}` успешно обновлена!")
