# Используем официальный slim-образ Python
FROM python:3.11-slim

# Устанавливаем системные зависимости для lxml, newspaper3k и других
RUN apt-get update && \
    apt-get install -y gcc build-essential python3-dev libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev libffi-dev libssl-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем только requirements.txt для кэширования слоёв
COPY requirements.txt .

# Устанавливаем зависимости Python без кэша
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Копируем всё приложение
COPY . .

# Отключаем буферизацию вывода Python
ENV PYTHONUNBUFFERED=1

# Запускаем основной скрипт
CMD ["python", "main.py"] 