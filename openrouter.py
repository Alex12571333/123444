import asyncio
import logging
import re

import httpx
from config import OPENROUTER_API_KEY, MODEL, PROMPT_STYLE

logger = logging.getLogger(__name__)

# Константы для retry логики
MAX_RETRIES = 3
RETRY_DELAY = 2  # секунды
RATE_LIMIT_DELAY = 10  # секунды при 429

TELEGRAM_ALLOWED_TAGS = {"b", "i", "u", "code", "pre"}


async def _call_openrouter(messages, timeout=60):
    """
    Централизованная функция для вызовов OpenRouter API с retry логикой
    """
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    data = {"model": MODEL, "messages": messages}
    
    for attempt in range(MAX_RETRIES):
        try:
            # Добавляем задержку между попытками
            if attempt > 0:
                await asyncio.sleep(RETRY_DELAY)
            
            async with httpx.AsyncClient() as client:
                logger.info(f"Sending request to OpenRouter model: {MODEL} (attempt {attempt + 1}/{MAX_RETRIES})")
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=data,
                    headers=headers,
                    timeout=timeout,
                )
                
                # Обрабатываем 429 ошибку
                if response.status_code == 429:
                    logger.warning(f"Rate limited (429) on attempt {attempt + 1}/{MAX_RETRIES}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RATE_LIMIT_DELAY)
                        continue
                    else:
                        logger.error(f"Rate limit exceeded after {MAX_RETRIES} attempts")
                        return 'RATE_LIMIT_429'
                
                # Обрабатываем 500 ошибку
                if response.status_code == 500:
                    logger.warning(f"Server error (500) on attempt {attempt + 1}/{MAX_RETRIES}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY * 2)  # Увеличиваем задержку для 500 ошибок
                        continue
                    else:
                        logger.error(f"Server error persisted after {MAX_RETRIES} attempts")
                        return None
                
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                logger.info(f"Successfully received response from OpenRouter on attempt {attempt + 1}")
                return content
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            if attempt == MAX_RETRIES - 1:
                return None
        except httpx.TimeoutException as e:
            logger.error(f"Timeout error on attempt {attempt + 1}: {e}")
            if attempt == MAX_RETRIES - 1:
                return None
        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
            if attempt == MAX_RETRIES - 1:
                return None
    
    return None

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
    
    messages = [{"role": "system", "content": prompt}]
    result = await _call_openrouter(messages, timeout=60)
    
    if result == 'RATE_LIMIT_429':
        logger.error(f"Error in rewrite_article: Rate limit exceeded")
        return 'RATE_LIMIT_429'
    
    if result:
        logger.info("Successfully received rewritten article from OpenRouter.")
    else:
        logger.error("Failed to rewrite article after all retries")
    
    return result

async def format_article(text):
    prompt = f"""
Проверь и отформатируй текст для публикации в Telegram-канале:

- Сохрани яркий заголовок с эмодзи, выдели его тегом <b>.
- Раздели текст на абзацы для удобства чтения.
- Используй только поддерживаемые Telegram HTML-теги: <b>, <i>, <u>.
- Не добавляй ссылки, имена СМИ, даты, геометки, списки.
- Не меняй смысл, стиль и структуру текста, только улучши читаемость и оформление.
- В конце добавь мотивирующую или обнадёживающую фразу, выдели её курсивом с помощью <i>.

Итоговый текст должен быть полностью готов к публикации в Telegram-канале.

Текст для форматирования:
{text}
"""
    
    messages = [{"role": "system", "content": prompt}]
    result = await _call_openrouter(messages, timeout=60)
    
    if result == 'RATE_LIMIT_429':
        logger.error(f"Error in format_article: Rate limit exceeded")
        return 'RATE_LIMIT_429'
    
    if result:
        logger.info("Successfully received formatted article from OpenRouter.")
    else:
        logger.error("Failed to format article after all retries")
    
    return result

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