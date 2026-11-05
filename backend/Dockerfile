# S33-001: базовый образ закреплён по digest — тег `3.12-slim` перезаписывается
# при каждом обновлении, digest делает сборку воспроизводимой.
FROM python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# S33-002: приложение не работает под root. UID/GID фиксированы (10001), чтобы
# права на volume'ах и в логах были предсказуемы; shell отключён.
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Индекс PyPI параметризован (S25): на машине проекта pypi.org недоступен —
# CI передаёт зеркало через --build-arg PIP_INDEX_URL.
ARG PIP_INDEX_URL=https://pypi.org/simple/

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --index-url $PIP_INDEX_URL -r requirements.txt

# Copy application code
COPY --chown=app:app . .

# S20-006: на чистой БД миграции должны примениться до старта API
COPY --chown=app:app docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh

# S33-002: runtime — только non-root. Запись разрешена в /tmp (tmpfs/1777) и в
# PROMETHEUS_MULTIPROC_DIR, если он задан;
# /app остаётся read-only для процесса.
USER app

# Expose port
EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
