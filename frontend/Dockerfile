# 前端 Docker 镜像
# 多阶段构建：先用 Node 构建，再用 Nginx 托管静态文件

# 构建阶段
FROM node:20-alpine AS build

WORKDIR /app

# 先复制依赖文件，利用缓存层
COPY package.json package-lock.json ./
RUN npm install

# 复制源码并构建
COPY . .
RUN npm run build

# 运行阶段
FROM nginx:alpine

# 复制构建产物
COPY --from=build /app/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
