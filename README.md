# Telegram RSS Bot

Автоматический Telegram бот для парсинга RSS лент, переписывания статей с помощью AI и публикации в канал.

## 🚀 Возможности

- 📰 Парсинг RSS лент (BBC, Meduza и др.)
- 🤖 AI переписывание статей в живом стиле
- 🖼️ Автоматическое извлечение изображений
- 📱 Публикация в Telegram канал
- 🔄 Умное планирование постов
- 🛡️ Устойчивость к ошибкам с retry логикой
- 🐳 Docker контейнеризация

## 📋 Требования

- Docker и Docker Compose
- Telegram Bot Token
- OpenRouter API Key
- Telegram Channel ID

## ⚙️ Установка

### 1. Клонирование репозитория
```bash
git clone https://github.com/Alex12571333/123444.git
cd 123444
```

### 2. Настройка переменных окружения
Создайте файл `.env` в корне проекта:
```env
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHANNEL=@your_channel_username
OPENROUTER_API_KEY=your_openrouter_api_key
RSS_FEEDS=["https://feeds.bbci.co.uk/russian/rss.xml","https://meduza.io/rss/all"]
CHECK_INTERVAL=300
DB_PATH=articles.db
MODEL=deepseek/deepseek-chat-v3-0324:free
PROMPT_STYLE=live
RSS_FEED_PRIORITIES={"https://meduza.io/rss/all": 1,"https://feeds.bbci.co.uk/russian/rss.xml": 2}
MIN_POST_INTERVAL=1800
MAX_POST_INTERVAL=7200
```

### 3. Запуск через Docker Compose
```bash
docker-compose up -d
```

## 🐳 Запуск через Portainer

### Метод 1: Docker Compose Stack
1. Откройте Portainer
2. Перейдите в **Stacks**
3. Нажмите **Add stack**
4. Вставьте содержимое `docker-compose.yml`
5. Нажмите **Deploy the stack**

### Метод 2: Docker Image
1. В Portainer перейдите в **Containers**
2. Нажмите **Add container**
3. Настройте:
   - **Name**: `telegram-rss-bot`
   - **Image**: `telegram-rss-bot:latest`
   - **Env file**: загрузите ваш `.env` файл
   - **Volumes**: добавьте `./articles.db:/app/articles.db`
   - **Restart policy**: `Unless stopped`

## 📊 Мониторинг

### Просмотр логов
```bash
# Docker Compose
docker-compose logs -f telegram-rss-bot

# Docker
docker logs -f telegram-rss-bot
```

### Статус контейнера
```bash
docker ps
```

## 🔧 Конфигурация

### RSS ленты
Добавьте RSS ленты в переменную `RSS_FEEDS`:
```env
RSS_FEEDS=["https://feeds.bbci.co.uk/russian/rss.xml","https://meduza.io/rss/all","https://your-rss-feed.com/feed"]
```

### Приоритеты лент
Настройте приоритеты в `RSS_FEED_PRIORITIES`:
```env
RSS_FEED_PRIORITIES={"https://meduza.io/rss/all": 1,"https://feeds.bbci.co.uk/russian/rss.xml": 2}
```

### Интервалы публикации
- `CHECK_INTERVAL`: интервал проверки RSS (в секундах)
- `MIN_POST_INTERVAL`: минимальный интервал между постами
- `MAX_POST_INTERVAL`: максимальный интервал между постами

## 🛠️ Управление

### Остановка
```bash
docker-compose down
```

### Перезапуск
```bash
docker-compose restart
```

### Обновление
```bash
git pull
docker-compose down
docker-compose up -d --build
```

## 📁 Структура проекта

```
├── main.py              # Основной файл бота
├── config.py            # Конфигурация
├── openrouter.py        # AI интеграция
├── utils.py             # Утилиты
├── telegram_bot.py      # Telegram API
├── storage.py           # База данных
├── rss.py               # RSS парсинг
├── docker-compose.yml   # Docker Compose
├── Dockerfile           # Docker образ
├── requirements.txt     # Зависимости
├── .env                 # Переменные окружения
└── README.md           # Документация
```

## 🔍 Логирование

Бот ведет подробные логи:
- `INFO` - информация о работе
- `WARNING` - предупреждения
- `ERROR` - ошибки
- `DEBUG` - отладочная информация

## 🛡️ Обработка ошибок

Бот автоматически:
- Повторяет попытки при 429/500 ошибках
- Ждет при rate limiting
- Обрабатывает таймауты
- Восстанавливается после сбоев

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи: `docker logs telegram-rss-bot`
2. Убедитесь в правильности переменных окружения
3. Проверьте доступность RSS лент
4. Убедитесь в валидности API ключей

## 📄 Лицензия

MIT License
