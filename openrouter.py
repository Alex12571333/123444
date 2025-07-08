import asyncio
import logging
import re

import httpx
from config import OPENROUTER_API_KEY, MODEL, PROMPT_STYLE

logger = logging.getLogger(__name__)

TELEGRAM_ALLOWED_TAGS = {"b", "i", "u", "s", "code", "a", "tg-spoiler"}


async def _call_openrouter(messages, timeout=60):
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    data = {"model": MODEL, "messages": messages}
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Sending request to OpenRouter model: {MODEL}")
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=data,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            logger.info("Successfully received response from OpenRouter.")
            return content
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"An error occurred while calling OpenRouter: {e}")
            raise


async def rewrite_article(article):
    prompt = f"""
Перепиши новостную статью в живом, разговорном и эмоциональном стиле для Telegram-канала.

- Не упоминай СМИ, источники, ссылки, не используй фразы вроде «по словам», «сообщает», «источник».
- Сделай яркий, цепляющий заголовок с эмодзи, выдели его тегом <b>.
- Разбей текст на короткие абзацы, используй поддерживаемые Telegram HTML-теги: <b>, <i>, <u>.
- Добавь эмоциональные и мотивирующие фразы, обращайся к читателю, делай выводы, добавь финальный мотивирующий абзац (выдели его курсивом с помощью <i>).
- Не используй сухие формулировки, избегай официального стиля.
- Не добавляй никакие ссылки, имена СМИ, имена журналистов, даты, геометки.
- Не используй списки, только абзацы.
- Не пиши ничего вне самой новости.

Пример структуры:
<b>🔥 Яркий заголовок с эмодзи!</b>

Первый абзац — кратко и эмоционально о сути новости.

Второй абзац — детали, мнения, эмоции.

Третий абзац — размышления, выводы, обращение к читателю.

<i>Мотивирующая или обнадёживающая фраза для читателей.</i>

Используй только поддерживаемые Telegram HTML-теги!

Текст статьи:
{article['content']}
"""
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    data = {"model": MODEL, "messages": [{"role": "system", "content": prompt}]}
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Sending request to OpenRouter model: {MODEL}")
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=data,
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            logger.info("Successfully received rewritten article from OpenRouter.")
            return content
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error(f"Error in rewrite_article: Client error '429 Too Many Requests' for url '{e.request.url}'")
                return 'RATE_LIMIT_429'
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Error in rewrite_article: {e}")
            return None


async def format_article(text):
    prompt = (
        """
Проверь и отформатируй текст для публикации в Telegram-канале:

- Сохрани яркий заголовок с эмодзи, выдели его тегом <b>.
- Раздели текст на абзацы для удобства чтения.
- Используй только поддерживаемые Telegram HTML-теги: <b>, <i>, <u>.
- Не добавляй ссылки, имена СМИ, даты, геометки, списки.
- Не меняй смысл, стиль и структуру текста, только улучши читаемость и оформление.
- В конце добавь мотивирующую или обнадёживающую фразу, выдели её курсивом с помощью <i>.

Итоговый текст должен быть полностью готов к публикации в Telegram-канале.

Текст для форматирования:
""" + text
    )
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    data = {"model": MODEL, "messages": [{"role": "system", "content": prompt}]}
    async with httpx.AsyncClient() as client:
        try:
            logger.info("Preparing to format article...")
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=data,
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            logger.info("Successfully received response from OpenRouter.")
            return content
        except Exception as e:
            logger.error(f"Error in format_article: {e}")
            return None


def validate_telegram_html(text):
    # Проверяем, что используются только разрешённые теги Telegram
    tag_pattern = re.compile(r"<(/?)([a-zA-Z0-9\-]+)(?: [^>]*)?>")
    for match in tag_pattern.finditer(text):
        tag = match.group(2).lower()
        if tag not in TELEGRAM_ALLOWED_TAGS:
            logger.warning(f"Validation failed: unsupported HTML tag <{tag}> found.")
            return False
    logger.info("HTML validation successful.")
    return True 