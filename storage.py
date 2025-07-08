import logging
import sqlite3

logger = logging.getLogger(__name__)


class Storage:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        logger.info(f"Database connection established to {db_path}")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS articles (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT UNIQUE, published TEXT)"
        )
        logger.info("Table 'articles' initialized.")

    def is_published(self, link):
        cur = self.conn.execute("SELECT 1 FROM articles WHERE link=?", (link,))
        return cur.fetchone() is not None

    def add_article(self, link, published):
        logger.info(f"Adding article to DB: {link}")
        self.conn.execute(
            "INSERT OR IGNORE INTO articles (link, published) VALUES (?, ?)",
            (link, published),
        )
        self.conn.commit() 