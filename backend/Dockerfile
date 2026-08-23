FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY docker-entrypoint.sh ./docker-entrypoint.sh
RUN mkdir -p /data/attachments && chmod 755 docker-entrypoint.sh && chown -R app:app /app /data/attachments
USER app
EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
