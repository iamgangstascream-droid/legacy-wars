FROM python:3.11-slim

WORKDIR /code

# Устанавливаем системные зависимости (для сборки некоторых пакетов)
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем код и картинки
COPY . .

# Порт 10000 для Render (по умолчанию)
ENV PORT=10000
EXPOSE 10000

CMD ["python", "bot.py"]
