# 第一阶段：Node 编译打包 (Builder)
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
# 加上之前解决版本冲突的魔法参数
RUN npm install --legacy-peer-deps 
COPY . .
RUN npm run build

# 第二阶段：Nginx 运行环境
FROM nginx:alpine
# 将第一阶段编译好的 dist 里的静态文件，复制到 Nginx 的默认展示目录
COPY --from=builder /app/dist /usr/share/nginx/html
# 暴露内部 80 端口
EXPOSE 80
# 启动 Nginx
CMD ["nginx", "-g", "daemon off;"]