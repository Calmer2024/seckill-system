FROM python:3.12-slim

# 1. 环境变量配置
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# 2. 优化缓存：先拷贝并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. 拷贝项目代码
COPY ./app /app/app

# 4. 创建非 root 用户并切换 (安全最佳实践)
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# 5. 更新 CMD 路径，适配新的目录结构
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]