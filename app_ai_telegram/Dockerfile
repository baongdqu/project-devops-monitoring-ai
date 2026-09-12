FROM python:3.11-slim

# Cài đặt curl và các công cụ cơ bản
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn
COPY . /app

# Thiết lập biến môi trường mặc định
ENV PYTHONUNBUFFERED=1 \
    PORT=80 \
    HOST=0.0.0.0

EXPOSE 80

# Chạy Dual Runner: FastAPI Healthcheck + Telegram Polling
CMD ["python", "bot/telegram_runner.py"]
