# 注意：不要加 `# syntax=docker/dockerfile:1`。
# 那行会让构建器先从 Docker Hub 拉 dockerfile 前端镜像，
# 在创空间的构建网络里可能拉不到导致整次构建失败；本文件也没用到任何高级语法。

# ---------- 阶段 1：构建前端 ----------
# 用独立的 node 镜像构建，产物是纯静态文件；最终镜像里不会留下 node_modules。
FROM node:20-slim AS frontend
WORKDIR /build
# 走国内镜像源，规避构建机访问 registry.npmjs.org 慢/超时（npm 10 会按此配置重写 lockfile 里的域名）
RUN npm config set registry https://registry.npmmirror.com
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
# 走国内 PyPI 镜像，避免构建机访问 pypi.org 超时；如需官方源，删掉 --index-url 参数即可
COPY backend/requirements.txt ./backend/requirements.txt
RUN python -m pip install --no-cache-dir \
        --index-url https://mirrors.aliyun.com/pypi/simple/ \
        -r backend/requirements.txt

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
