FROM python:3.12-slim

# PYTHONDONTWRITEBYTECODE — не создавать .pyc внутри примонтированного кода.
# PYTHONUNBUFFERED — логи Django сразу попадают в docker compose logs, без буферизации.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Зависимости ставим отдельным слоем: пока requirements.txt не менялся,
# Docker переиспользует кэш и не переустанавливает пакеты при каждой сборке.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
