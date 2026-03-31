# BGE-M3 嵌入服务 Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY embedding_service.py .

# 模型缓存目录
ENV HF_HOME=/cache
RUN mkdir -p /cache

# 暴露端口
EXPOSE 8001

# 启动服务
CMD ["python", "embedding_service.py"]
