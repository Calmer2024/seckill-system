FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY order_service/requirements.txt .
COPY packages/seckill-observability /opt/seckill-observability
RUN pip install --no-cache-dir -r requirements.txt /opt/seckill-observability

COPY order_service/app /app/app
RUN python /opt/seckill-observability/build_version.py

RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
