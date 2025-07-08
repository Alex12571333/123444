import logging
import feedparser
from utils import extract_image_url, extract_full_article_text

logger = logging.getLogger(__name__)


def fetch_new_articles(feeds, storage):
    new_articles = []
    for url in feeds:
        logger.info(f"Parsing RSS feed: {url}")
        feed = feedparser.parse(url)
        if feed.bozo:
            logger.warning(f"Error parsing feed {url}: {feed.bozo_exception}")
            continue

        for entry in feed.entries:
            link = entry.get("link")
            if not link:
                logger.warning(
                    f"Skipping entry without link in feed {url}: {entry.get('title')}"
                )
                continue
            published = entry.get("published", "")
            # Универсальный парсер текста статьи
            content = extract_full_article_text(link)
            logger.info(f"ARTICLE DEBUG: title={entry.get('title', '')}, link={link}, content_len={len(content)}, content_preview={content[:200]}")
            if not content.strip():
                logger.info(f"SKIP: No full text extracted for article {link}")
                continue
            if not storage.is_published(link):
                logger.info(f"New article found: {link}")
                image_url = extract_image_url(entry, url)
                new_articles.append({
                    "title": entry.get("title", ""),
                    "link": link,
                    "published": published,
                    "summary": entry.get("summary", ""),
                    "content": content,
                    "image_url": image_url,
                })
                storage.add_article(link, published)
    return new_articles 