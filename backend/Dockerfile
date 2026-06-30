# 后端 Docker 镜像
# 基于 Python slim 镜像，安装依赖并运行 FastAPI 服务

FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（DuckDB 编译需要 gcc）
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，利用 Docker 缓存层
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 复制后端代码和数据库初始化资产；Docker 推荐路径需要空数据卷也能自举演示库。
COPY backend ./backend
COPY database ./database

# 创建数据和日志目录
RUN mkdir -p /app/data /app/logs

WORKDIR /app/backend

# 暴露端口
EXPOSE 8000

# 启动前先初始化空 DuckDB 数据卷，再启动 FastAPI。
CMD ["sh", "-c", "python -m app.db.demo_bootstrap && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
