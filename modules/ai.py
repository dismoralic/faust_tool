import io
import requests
import asyncio
from g4f.client import Client as G4FClient
from faust_tool.core.loader import register_command

g4f_client = G4FClient()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/115.0 Safari/537.36",
    "Accept": "application/json",
}

async def generate_chat_response(question: str) -> str:
    try:
        response = await asyncio.to_thread(
            lambda: g4f_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": question}],
                headers=HEADERS
            )
        )
        if not response.choices or not hasattr(response.choices[0], 'message'):
            return "Ошибка: пустой ответ от модели."
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка генерации, напишите разработчику: {e}"

async def translate_to_english(text: str) -> str:
    try:
        response = await asyncio.to_thread(
            lambda: g4f_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a translator. Translate the following text to English."},
                    {"role": "user", "content": text}
                ],
                headers=HEADERS
            )
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"Ошибка перевода, напишите разработчику1: {e}")

async def generate_image_url(prompt: str) -> str:
    try:
        translated = await translate_to_english(prompt)
        response = await asyncio.to_thread(
            lambda: g4f_client.images.generate(
                model="flux",
                prompt=translated,
                response_format="url",
                headers=HEADERS
            )
        )
        if not response.data:
            raise ValueError("Пустой ответ от генератора.")
        return response.data[0].url
    except Exception as e:
        raise RuntimeError(f"Ошибка генерации изображения, напишите разработчику: {e}")

def register(client):
    @register_command(client, "ai", r'^\.img (.+)', "сгенерировать изображение")
    async def handle_img(event):
        prompt = event.pattern_match.group(1)
        try:
            await event.edit("Генерирую изображение...")
            image_url = await generate_image_url(prompt)
            img_data = requests.get(image_url, headers=HEADERS).content
            image = io.BytesIO(img_data)
            image.name = "generated.png"

            await event.delete()
            await client.send_file(event.chat_id, image, caption="Готово!")
        except Exception as e:
            await event.edit(str(e))
