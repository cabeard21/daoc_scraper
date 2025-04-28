# Dockerfile
FROM python:3.11-slim

# 1) system deps for Chromium (used by your scraper)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      chromium-driver chromium-browser \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2) install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3) copy your code
COPY . .

# 4) default is to do nothing (we'll override in docker-compose)
CMD ["bash", "-c", "echo 'Specify a service command.'"]
