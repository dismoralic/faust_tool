import pytesseract
from PIL import Image
from io import BytesIO
from faust_tool.core.loader import register_command

def register(client):
    @register_command(
        client,
        "text",
        r"^\.text$",
        "Распознаёт текст на изображении (OCR). Использование: .text (в ответ на фото/стикер/файл)"
    )
    async def recognize_text(event):
        await event.edit('Обрабатываю...')

        reply_msg = await event.get_reply_message()
        if not reply_msg:
            await event.edit('Команда работает только в ответ на изображение.')
            return

        if not (reply_msg.photo or reply_msg.sticker or reply_msg.file):
            await event.edit('Ответь на изображение или стикер.')
            return

        try:
            image_bytes = await event.client.download_media(reply_msg, bytes)
            text = pytesseract.image_to_string(Image.open(BytesIO(image_bytes)), lang='eng+rus')
            await event.edit(text or 'Текст не распознан.')
        except Exception as e:
            await event.edit(f'Ошибка распознавания: {e}')
