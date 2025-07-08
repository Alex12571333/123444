import asyncio
import logging
from aiogram import Bot
from config import TELEGRAM_TOKEN, TELEGRAM_CHANNEL, RSS_FEEDS, RSS_FEED_PRIORITIES, CHECK_INTERVAL, MIN_POST_INTERVAL, MAX_POST_INTERVAL, DB_PATH
from storage import Storage
from rss import fetch_new_articles
from openrouter import rewrite_article, format_article, validate_telegram_html
from utils import extract_best_image_url_from_entry, download_image
from telegram_bot import send_article
from dateutil import parser as date_parser
import datetime
import random
import re

MAX_FORMAT_ATTEMPTS = 3

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_priority_article(articles):
    # Группируем по источнику
    by_source = {}
    for a in articles:
        src = a.get('feed_url') or a.get('source')
        if not src:
            # Попробуем угадать по ссылке
            for feed in RSS_FEED_PRIORITIES:
                if feed.split('/')[2] in a.get('link', ''):
                    src = feed
                    break
        by_source.setdefault(src, []).append(a)
    # Идём по приоритетам
    for feed in RSS_FEED_PRIORITIES:
        if feed in by_source:
            # Сортируем по дате публикации
            def get_date(a):
                try:
                    return date_parser.parse(a.get('published', ''))
                except Exception:
                    return None
            articles_with_date = [a for a in by_source[feed] if get_date(a)]
            if articles_with_date:
                return sorted(articles_with_date, key=get_date, reverse=True)[0]
            return by_source[feed][0]
    # Если ничего не нашли — просто самую свежую
    return get_latest_article(articles)

def get_smart_interval(last_post_time, activity_level=1):
    # activity_level: 1 — мало новостей, 2 — средне, 3 — много
    now = datetime.datetime.now()
    hour = now.hour
    # Днём чаще, ночью реже
    if 8 <= hour < 22:
        base = MIN_POST_INTERVAL
    else:
        base = int((MIN_POST_INTERVAL + MAX_POST_INTERVAL) / 2)
    # Если много новостей — уменьшаем интервал
    if activity_level >= 3:
        base = int(base * 0.7)
    # Если мало — увеличиваем
    if activity_level == 1:
        base = int(base * 1.3)
    # Немного рандома, чтобы не быть похожим на бота
    base += random.randint(-60, 60)
    return max(MIN_POST_INTERVAL, min(base, MAX_POST_INTERVAL))

def get_latest_article(articles):
    # Сортируем по дате публикации (если есть), иначе по порядку
    def get_date(a):
        try:
            return date_parser.parse(a.get('published', ''))
        except Exception:
            return None
    articles_with_date = [a for a in articles if get_date(a)]
    if articles_with_date:
        return sorted(articles_with_date, key=get_date, reverse=True)[0]
    return articles[0] if articles else None

# Проверка полноты и завершённости текста

def is_article_complete(text, title=None, min_len=300):
    return bool(text and len(text.strip()) >= min_len)

# Проверка релевантности картинки статье

def is_image_relevant(image_url, title, summary):
    # Стоп-слова для логотипов и дефолтных картинок
    BAD_IMAGE_PATTERNS = [
        "news.google.com", "logo", "icon", "default", "placeholder"
    ]
    if not image_url:
        return False
    # Новая проверка на стоп-слова
    if any(bad in image_url.lower() for bad in BAD_IMAGE_PATTERNS):
        return False
    text = (title or '') + ' ' + (summary or '')
    words = [w.lower() for w in re.findall(r'\w+', text) if len(w) > 3]
    return any(w in image_url.lower() for w in words)

async def main():
    logging.info("Starting bot...")
    bot = Bot(token=TELEGRAM_TOKEN)
    storage = Storage(DB_PATH)
    last_post_time = None
    global CHECK_INTERVAL

    async def check_and_post():
        nonlocal last_post_time
        try:
            logging.info("Checking for new articles...")
            articles = fetch_new_articles(RSS_FEEDS, storage)
            if not articles:
                logging.info("No new articles found.")
                logging.info(f"Next check in {CHECK_INTERVAL} seconds.")
                return
            # Выбираем статью по приоритету источника
            latest = get_priority_article(articles)
            if not latest:
                logging.info("No valid latest article found.")
                return
            # Создаём объект post_data для передачи на всех этапах
            post_data = dict(latest)
            logging.info(f"Processing latest article: {post_data['title']} | link={post_data.get('link')}")
            # Логируем длину и превью текста статьи перед генерацией
            content_preview = post_data.get('content', '')[:200]
            content_len = len(post_data.get('content', ''))
            logging.info(f"PROMPT DEBUG: article link={post_data.get('link')}, content_len={content_len}, content_preview={content_preview}")
            # Обрезаем текст для нейросети, если он слишком длинный
            short_content = post_data.get('content', '')
            if len(short_content) > 1200:
                short_content = short_content[:1200] + '...'
            post_data['short_content'] = short_content
            logging.info(f"SHORT PROMPT DEBUG: article link={post_data.get('link')}, short_content_len={len(short_content)}, short_content_preview={short_content[:200]}")
            # Генерация и проверка полноты
            logging.info(f"GEN DEBUG: before rewrite_article: title={post_data.get('title')}, link={post_data.get('link')}, summary={post_data.get('summary')}")
            raw_post = None
            for attempt in range(3):
                # Передаём короткий текст в нейросеть
                raw_post = await rewrite_article({**post_data, 'content': short_content})
                if raw_post == 'RATE_LIMIT_429':
                    logging.warning("OpenRouter rate limit reached, waiting 60 seconds before retry...")
                    await asyncio.sleep(60)
                    continue
                if raw_post and is_article_complete(raw_post, post_data.get('title')):
                    break
                logging.warning(f"Article not complete or generation failed, retrying generation ({attempt+1}/3)...")
                await asyncio.sleep(5)
            logging.info(f"GEN DEBUG: after rewrite_article: title={post_data.get('title')}, link={post_data.get('link')}, summary={post_data.get('summary')}, generated_text={raw_post}")
            if not raw_post or not is_article_complete(raw_post, post_data.get('title')):
                logging.error("Failed to generate complete article text. Skipping.")
                return
            await asyncio.sleep(15)
            formatted_post = None
            for attempt in range(3):
                candidate = await format_article(raw_post)
                if candidate and is_article_complete(candidate, post_data.get('title')) and validate_telegram_html(candidate):
                    formatted_post = candidate
                    break
                logging.warning(f"Format attempt {attempt+1} failed Telegram validation or completeness, retrying...")
                await asyncio.sleep(5)
            if not formatted_post:
                logging.error("All format attempts failed. Skipping article.")
                return
            post_data['post_text'] = formatted_post
            # Проверка релевантности картинки
            img_url = post_data.get("image_url")
            # Подробное логирование перед отправкой
            logging.info(f"POST DEBUG: title={post_data.get('title')}, link={post_data.get('link')}, summary={post_data.get('summary')}, image_url={img_url}, post_text={post_data.get('post_text')}")
            img_bytes = await download_image(img_url) if img_url else None
            await send_article(bot, TELEGRAM_CHANNEL, post_data['post_text'], img_bytes)
            logging.info(f"Article sent: {post_data['title']} | link={post_data.get('link')}")
            last_post_time = datetime.datetime.now()
        except Exception as e:
            logging.error(f"An error occurred in check_and_post: {e}")

    async def scheduler():
        global CHECK_INTERVAL
        nonlocal last_post_time
        while True:
            await check_and_post()
            # Умный интервал
            activity_level = 2  # Можно доработать: считать количество новых статей
            CHECK_INTERVAL = get_smart_interval(last_post_time, activity_level)
            logging.info(f"Next check in {CHECK_INTERVAL} seconds.")
            await asyncio.sleep(CHECK_INTERVAL)

    try:
        await scheduler()
    except KeyboardInterrupt:
        logging.info("Bot stopped manually.")

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(main()) 