FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Индекс PyPI параметризован (S25): на машине проекта pypi.org недоступен —
# CI передаёт зеркало через --build-arg PIP_INDEX_URL.
ARG PIP_INDEX_URL=https://pypi.org/simple/

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --index-url $PIP_INDEX_URL -r requirements.txt

# Copy application code
COPY . .

# S20-006: на чистой БД миграции должны примениться до старта API
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose port
EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
