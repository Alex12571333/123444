import logging
from aiogram import Bot
from aiogram.types import BufferedInputFile

logger = logging.getLogger(__name__)


async def send_article(bot: Bot, channel, text, image_bytes=None):
    if image_bytes:
        photo = BufferedInputFile(image_bytes, filename="image.png")
        logger.info(f"Sending photo to channel {channel}")
        await bot.send_photo(
            chat_id=channel, photo=photo, caption=text, parse_mode="HTML"
        )
    else:
        logger.info(f"Sending message to channel {channel}")
        await bot.send_message(chat_id=channel, text=text, parse_mode="HTML") 