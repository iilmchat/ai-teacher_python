# =============================================================================
# Образ контейнера-раннера песочницы (S24-001).
#
# Минимальный: stdlib + RestrictedPython + чистое ядро песочницы. Никаких
# зависимостей приложения (pydantic/sqlalchemy/БД) и исходников ученика —
# код приходит по stdin, ответ уходит в stdout.
#
# Сборка (контекст — backend/):
#   docker build -f sandbox_runner/Dockerfile -t ai-teacher-sandbox-runner:latest .
#
# Запуск (все флаги изоляции выставляет приложение, см. container_sandbox.py):
#   docker run --rm -i --network none --read-only --cap-drop ALL \
#     --security-opt no-new-privileges --user 65534:65534 \
#     --tmpfs /tmp:rw,noexec,nosuid,size=64m \
#     --memory 128m --memory-swap 128m --pids-limit 64 \
#     ai-teacher-sandbox-runner:latest
# =============================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Только RestrictedPython: раннер не должен уметь ничего из стека приложения
RUN pip install --no-cache-dir "restrictedpython==8.5"

WORKDIR /app

RUN mkdir -p /app/app/core \
    && touch /app/app/__init__.py /app/app/core/__init__.py

COPY app/core/sandbox_runtime.py /app/app/core/sandbox_runtime.py
COPY app/core/sandbox_limits.py /app/app/core/sandbox_limits.py
COPY sandbox_runner/runner.py /app/runner.py

# Non-root: пользователь nobody (65534). Дополнительно проверяется в
# self-check (uid=65534) и флагами `--user`/`--cap-drop ALL`.
USER 65534:65534

ENTRYPOINT ["python", "/app/runner.py"]
