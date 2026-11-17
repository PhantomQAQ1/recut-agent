# syntax=docker/dockerfile:1

# ---------- 阶段 1：构建前端 ----------
# 用独立的 node 镜像构建，产物是纯静态文件；最终镜像里不会留下 node_modules。
FROM node:20-slim AS frontend
WORKDIR /build
# 国内构建（如魔搭创空间）如果 npm 拉取慢，取消下面一行的注释换镜像源
# RUN npm config set registry https://registry.npmmirror.com
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- 阶段 2：运行时 ----------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖，利用构建缓存：只改业务代码时不会重装依赖
# 国内构建如果 PyPI 慢，可在下面一行前加 --index-url https://mirrors.aliyun.com/pypi/simple/
COPY backend/requirements.txt ./backend/requirements.txt
RUN python -m pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend /build/dist ./frontend/dist

WORKDIR /app/backend

# 创空间固定使用 7860；PORT 可覆盖，方便本机跑别的端口
ENV PORT=7860
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:7860/api/health', timeout=4)"

# 必须监听 0.0.0.0，否则平台的端口探测连不上。
# --proxy-headers：创空间前面有一层反向代理，需要它才能拿到真实的协议与 Host。
CMD ["sh", "-c", "exec python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips=*"]
