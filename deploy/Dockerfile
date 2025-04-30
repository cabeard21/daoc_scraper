# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy your code
COPY daoc_scraper/ daoc_scraper/

# default is to do nothing
CMD ["bash", "-c", "echo 'Specify a service command.'"]
