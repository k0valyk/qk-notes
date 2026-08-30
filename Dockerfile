FROM python:3.12-slim

WORKDIR /app

# Системні залежності (для aiosqlite/uvicorn — мінімум)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Дані зберігаються в /app/data (Volume монтується сюди на Railway)
RUN mkdir -p /app/data

ENV PORT=8000
ENV WEBAPP_URL=https://qk-notes-production.up.railway.app
EXPOSE 8000

CMD ["sh", "-c", "python run.py"]