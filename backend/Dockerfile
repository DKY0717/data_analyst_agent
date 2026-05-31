# 后端 Docker 镜像
# 基于 Python slim 镜像，安装依赖并运行 FastAPI 服务

FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（DuckDB 编译需要 gcc）
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，利用 Docker 缓存层
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建数据和日志目录
RUN mkdir -p /app/data /app/logs

# 暴露端口
EXPOSE 8000

# 启动 FastAPI 服务
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
