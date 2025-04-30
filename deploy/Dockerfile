# Dockerfile
FROM python:3.11-slim

# 1) system deps for Chromium (used by your scraper)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      chromium \
      chromium-driver \
      libnss3 \
      libxss1 \
      libatk1.0-0 \
      libatk-bridge2.0-0 \
      libcups2 \
      libdbus-1-3 \
      libx11-xcb1 \
      libxcomposite1 \
      libxdamage1 \
      libxrandr2 \
      libgbm1 \
      libgtk-3-0 \
      fonts-liberation \
      xdg-utils \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2) install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3) copy your code
COPY daoc_scraper/ daoc_scraper/

# 4) default is to do nothing (we'll override in docker-compose)
CMD ["bash", "-c", "echo 'Specify a service command.'"]
