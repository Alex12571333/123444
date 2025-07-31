import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL")  # например, '@your_channel'
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
RSS_FEEDS = [
    "https://feeds.bbci.co.uk/russian/rss.xml",
    "https://meduza.io/rss/all"
]
# Приоритеты: чем меньше индекс, тем выше приоритет
RSS_FEED_PRIORITIES = [
    "https://meduza.io/rss/all",
    "https://www.huffpost.com/section/world-news/feed"
]
CHECK_INTERVAL = 60  # секунд (начальный)
MIN_POST_INTERVAL = 600  # 10 минут
MAX_POST_INTERVAL = 7200  # 2 часа
DB_PATH = os.getenv("DB_PATH", "articles.db")
MODEL = "deepseek/deepseek-chat-v3-0324:free"
PROMPT_STYLE = "Стиль максимально простой и приближённый к человеческому." 