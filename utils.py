import logging
import httpx
from lxml import html
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from newspaper import Article
import asyncio
import time

logger = logging.getLogger(__name__)

# Константы для retry логики
MAX_RETRIES = 3
RETRY_DELAY = 2  # секунды
RATE_LIMIT_DELAY = 10  # секунды при 429

def try_get_hq_image(url):
    # Попытка получить ссылку на оригинал по шаблону
    if not url:
        return None
    candidates = []
    # Meduza, BBC и др.: small -> original, large, просто убрать
    patterns = [
        (r"/(small|thumb|preview)/", "/original/"),
        (r"/(small|thumb|preview)/", "/large/"),
        (r"/(small|thumb|preview)/", "/"),
    ]
    for pat, repl in patterns:
        if re.search(pat, url):
            candidates.append(re.sub(pat, repl, url))
    # Если есть расширение, пробуем убрать small_ или thumb_ в имени файла
    candidates.append(re.sub(r"(small_|thumb_|preview_)", "", url))
    # Проверяем кандидатов
    for candidate in candidates:
        try:
            resp = httpx.head(candidate, timeout=3)
            if resp.status_code == 200:
                logger.info(f"HQ image found: {candidate}")
                return candidate
        except Exception:
            continue
    return url

def extract_best_image_url_from_entry(entry):
    # 1. media:content
    media_content = entry.get('media_content')
    if media_content and isinstance(media_content, list):
        for media in media_content:
            url = media.get('url')
            if url:
                url = try_get_hq_image(url)
                logger.info(f"Image found in media:content: {url}")
                return url
    # 2. enclosures
    enclosures = entry.get('enclosures')
    if enclosures and isinstance(enclosures, list):
        for enc in enclosures:
            href = enc.get('href')
            type_ = enc.get('type', '')
            if href and type_.startswith('image/'):
                href = try_get_hq_image(href)
                logger.info(f"Image found in enclosure: {href}")
                return href
    # 3. media_thumbnail (BBC)
    media_thumbnail = entry.get('media_thumbnail')
    if media_thumbnail and isinstance(media_thumbnail, list):
        for thumb in media_thumbnail:
            url = thumb.get('url')
            if url:
                url = try_get_hq_image(url)
                logger.info(f"Image found in media_thumbnail: {url}")
                return url
    # 4. links with rel="enclosure" and type image
    links = entry.get('links')
    if links and isinstance(links, list):
        for link in links:
            if link.get('rel') == 'enclosure' and link.get('type', '').startswith('image/'):
                url = link.get('href')
                if url:
                    url = try_get_hq_image(url)
                    logger.info(f"Image found in links: {url}")
                    return url
    # 5. img in summary/content/description
    for key in ['summary', 'content', 'description']:
        html_content = entry.get(key)
        if isinstance(html_content, list):
            html_content = html_content[0].get('value', '')
        if html_content:
            try:
                tree = html.fromstring(html_content)
                img = tree.xpath('//img/@src')
                if img:
                    url = try_get_hq_image(img[0])
                    logger.info(f"Image found in {key}: {url}")
                    return url
            except Exception as e:
                logger.error(f"Error parsing HTML in {key} to find image: {e}")
    # 6. thumbnail/image fields
    for key in ['image', 'thumbnail']:
        url = entry.get(key)
        if url:
            url = try_get_hq_image(url)
            logger.info(f"Image found in {key}: {url}")
            return url
    # 7. (Fallback) Пробуем найти og:image или <img> на странице по ссылке
    link = entry.get('link')
    if link:
        logger.info(f"Trying to fetch image from article page: {link}")
        try:
            from utils import extract_image_from_page
            url = extract_image_from_page(link)
            if url:
                url = try_get_hq_image(url)
                logger.info(f"Image found on article page: {url}")
                return url
        except Exception as e:
            logger.error(f"Error fetching image from article page: {e}")
    logger.info("No image found in entry.")
    return None

async def download_image(url):
    logger.info(f"Downloading image from: {url}")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            logger.info(f"Image downloaded successfully from: {url}")
            return response.content
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None

def extract_image_url(entry, feed_url):
    link = entry.get('link')
    title = entry.get('title', '')
    if link:
        try:
            url = extract_image_from_page(link, title)
            if url:
                logger.info(f"Image found on article page: {url} for news: {title} ({link})")
                return try_get_hq_image(url)
        except Exception as e:
            logger.error(f"Error fetching image from article page: {e}")
    logger.info(f"No image found on article page for news: {title} ({link})")
    return None

def extract_image_from_page(url, title=None):
    """
    Ищет изображение только в основном контенте статьи (article, main, .content, .post, .entry, .article-body).
    Если title передан — ищет совпадения по alt/title картинки и словам из заголовка (длина слова > 3).
    """
    for attempt in range(MAX_RETRIES):
        try:
            # Добавляем задержку между попытками
            if attempt > 0:
                time.sleep(RETRY_DELAY)
            
            resp = requests.get(url, timeout=10)
            
            # Обрабатываем 429 ошибку
            if resp.status_code == 429:
                logger.warning(f"Rate limited (429) for {url}, attempt {attempt + 1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RATE_LIMIT_DELAY)
                    continue
                else:
                    logger.error(f"Rate limit exceeded for {url} after {MAX_RETRIES} attempts")
                    return None
            
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 1. Пробуем найти OpenGraph-изображение
            og = soup.find('meta', property='og:image')
            if og and og.get('content'):
                return og['content']
            
            # 2. Пробуем найти первую картинку в основном контенте, совпадающую по alt/title с заголовком
            main_selectors = ['article', 'main', '.content', '.post', '.entry', '.article-body']
            title_words = []
            if title:
                title_words = [w.lower() for w in re.findall(r'\w+', title) if len(w) > 3]
            
            for selector in main_selectors:
                main = soup.select_one(selector)
                if main:
                    imgs = main.find_all('img')
                    for img in imgs:
                        alt = img.get('alt', '').lower()
                        t = img.get('title', '').lower()
                        if title_words and any(word in alt or word in t for word in title_words):
                            logger.info(f"Image alt/title matched: {img.get('src')} (alt: {alt}, title: {t})")
                            return img.get('src')
            
            logger.info(f"No image in main content matches title words: {title_words}")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error on attempt {attempt + 1} for {url}: {e}")
            if attempt == MAX_RETRIES - 1:
                return None
        except Exception as e:
            logger.error(f"Error parsing HTML to find image on attempt {attempt + 1} for {url}: {e}")
            if attempt == MAX_RETRIES - 1:
                return None
    
    return None

def extract_full_article_text(url):
    """
    Универсальный парсер: извлекает основной текст статьи по ссылке с помощью newspaper3k.
    Возвращает текст или пустую строку, если не удалось.
    """
    for attempt in range(MAX_RETRIES):
        try:
            # Добавляем задержку между попытками
            if attempt > 0:
                time.sleep(RETRY_DELAY)
            
            article = Article(url, language='ru')  # Можно попробовать 'en' для англоязычных
            article.download()
            article.parse()
            text = article.text.strip()
            
            if not text:
                logger.warning(f"No text extracted from article on attempt {attempt + 1}: {url}")
                if attempt < MAX_RETRIES - 1:
                    continue
                else:
                    return ""
            
            return text
            
        except Exception as e:
            logger.error(f"Error extracting article text from {url} on attempt {attempt + 1}: {e}")
            if attempt == MAX_RETRIES - 1:
                return ""
    
    return "" 