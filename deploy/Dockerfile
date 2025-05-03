# Dockerfile
FROM python:3.11-slim

# install curl
RUN apt-get update && apt-get install -y curl

WORKDIR /app

# install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# create data dir and non-root user, then set ownership
RUN mkdir /app/data \
 && useradd --no-create-home --shell /usr/sbin/nologin appuser \
 && chown -R appuser:appuser /app/data /app

# now switch
USER appuser

# copy your code as unprivileged user
COPY --chown=appuser:appuser daoc_scraper/ daoc_scraper/

# default is to do nothing
CMD ["bash", "-c", "echo 'Specify a service command.'"]
