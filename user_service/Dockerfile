FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY user_service/requirements.txt .
COPY packages/seckill-observability /opt/seckill-observability
RUN pip install --no-cache-dir -r requirements.txt /opt/seckill-observability
COPY user_service/ .
RUN python /opt/seckill-observability/build_version.py
# 暴露 FastAPI 默认的 8000 端口
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
