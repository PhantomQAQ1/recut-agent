# ReCut Agent

AIGC 视频分镜与提示词工作台：把一句创意变成可直接投喂给即梦 / 可灵 / Runway 的镜头脚本，也能把一段素材反推成分镜。

产品需求文档见 [docs/PRD.md](docs/PRD.md)（范围、功能状态、数据模型、路线图）。
部署到魔搭创空间见 [docs/DEPLOY-modelscope.md](docs/DEPLOY-modelscope.md)（Docker 空间 + 持久化 + 环境变量）。

## 功能

- **正向生成**：创意 + 二创风格 + 角色锚点 → 分镜脚本（景别 / 焦段 / 运镜 / 中英双语提示词）
- **两阶段生成**：先出可编辑的镜头计划，确认后再逐镜并发展开提示词，单镜失败可单独重试
- **单镜微调**：输入指令 → 模型改写 → 新旧字段对比 → 采用或放弃
- **故事板卡片**：提示词为主体内容，支持参考首帧、场景层、8 套调色板、缩略导航
- **编辑效率**：镜头重排（上移/下移）、撤销/重做（50 步）、快捷键（`⌘/Ctrl+Enter` 生成、`↑↓` 切换、`Delete` 删除、`⌘/Ctrl+Z` 撤销）
- **角色一致性**：项目级角色锚点由角色资产派生（不再手打字符串），左侧显示每条锚点在多少镜头里命中；卡片按锚点标黄缺失并可一键补齐；镜头级还可额外绑定角色
- **逆向解析**：上传视频或图片 → 均匀抽帧 → 视觉模型反推视听语言
- **角色资产库**：角色增删改查、标签体系、标签与角色联动、按标签筛选
- **导出**：Markdown / CSV 即时下载；剪映草稿（占位图 + 文字轨，实验性）
- **账号体系**：HttpOnly Cookie 会话、失败锁定、记住我、项目归属与自动保存

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Tailwind CSS |
| 后端 | FastAPI + SQLite（标准库 `sqlite3`，无 ORM） |
| 模型 | 任意 OpenAI 兼容接口（DeepSeek / 通义 / Kimi / OpenAI），视觉模型可单独指向另一家 |

## 快速开始

### 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env        # 填入 LLM_API_KEY；不填也能启动，生成接口会返回 503
.\.venv\Scripts\python -m scripts.manage_user create --email you@example.com --name 你的名字 --role admin
.\.venv\Scripts\python -m uvicorn main:app --reload --port 8000
```

### 前端

```powershell
cd frontend
npm install
npm run dev      # http://127.0.0.1:5173
```

### 可选：本地 mock 模型服务

没有 API Key 时也能联调前后端：

```powershell
cd backend
.\.venv\Scripts\python -m tests.mock_llm --port 8899
# 另一个终端用 mock 启动后端：
$env:LLM_API_KEY="mock-key"; $env:LLM_BASE_URL="http://127.0.0.1:8899/v1"
.\.venv\Scripts\python -m uvicorn main:app --port 8001
```

## 环境变量

完整清单见 [`backend/.env.example`](backend/.env.example)。

| 变量 | 默认 | 说明 |
|---|---|---|
| `LLM_API_KEY` | 空 | 文本模型密钥；为空时生成接口返回 503 |
| `LLM_BASE_URL` / `LLM_MODEL` | DeepSeek | OpenAI 兼容地址与模型名 |
| `VISION_API_KEY` / `VISION_BASE_URL` / `VISION_MODEL` | 复用文本配置 | 视觉模型（视频抽帧理解） |
| `APP_DB_URL` | `sqlite:///./recut.db` | 数据库地址 |
| `APP_SESSION_TTL_HOURS` / `APP_SESSION_REMEMBER_DAYS` | 12 / 30 | 会话时长与"记住我"时长 |
| `APP_MAX_LOGIN_ATTEMPTS` / `APP_LOCKOUT_MINUTES` | 5 / 15 | 连续失败锁定策略 |
| `APP_COOKIE_SECURE` | `false` | 生产环境走 HTTPS 时必须改为 `true` |

## 测试

```powershell
cd backend
.\.venv\Scripts\python -m pytest -q      # 47 项
cd ..\frontend
.\node_modules\.bin\vue-tsc.cmd --noEmit -p tsconfig.app.json
```

## 接口概览

```
GET    /api/health

POST   /api/v1/auth/login | /logout | /password
GET    /api/v1/auth/me

GET    /api/v1/projects                 POST   /api/v1/projects
GET    /api/v1/projects/{id}            PUT    /api/v1/projects/{id}
DELETE /api/v1/projects/{id}

POST   /api/v1/storyboard/generate      POST   /api/v1/storyboard/reverse
POST   /api/v1/storyboard/plan          POST   /api/v1/storyboard/shot
POST   /api/v1/storyboard/refine

POST   /api/v1/uploads                  GET    /api/v1/uploads/{id}
GET    /api/v1/projects/{id}/export/jianying

GET    /api/v1/characters               POST   /api/v1/characters
GET    /api/v1/characters/{id}          PATCH  /api/v1/characters/{id}
DELETE /api/v1/characters/{id}
PATCH  /api/v1/characters/{id}/tags     PUT    /api/v1/characters/{id}/tags

GET    /api/v1/tags                     POST   /api/v1/tags
PATCH  /api/v1/tags/{id}                DELETE /api/v1/tags/{id}
GET    /api/v1/tags/{id}/characters
```

除 `/api/health` 与登录相关接口外，其余均需登录会话。

## 设计要点

- **会话 Cookie 而非 JWT**：可即时吊销；令牌在库中只存 SHA-256
- **鉴权先于读请求体**：上传接口在解析 multipart 之前拦掉未登录请求
- **乐观锁**：角色带 `version`，全量替换标签必须带 `expected_version`，冲突返回 409
- **标签全局唯一**：同一用户内跨分组不允许重名，归一化口径为「全角转半角 + 去空白 + 小写」
- **删除标签默认拒绝**：返回引用者列表，需显式 `force` 解绑或 `reassign_to` 迁移
- **撤销用快照而非命令模式**：故事板编辑入口多（直接输入、微调采用、展开填充、绑定角色），快照能一次覆盖全部
- **绑定关系只信任前端**：模型返回的 `character_ids` 会被 `normalize_shot` 丢弃，不能让模型改写绑定
- **锚点只提示不自动改写**：生成/展开/微调都会把锚点注入请求，但生成后若模型漏写，只标黄提示，不静默修改用户内容
- **旧项目兼容**：`storyboard.anchors`（自由锚点）会自动迁移为 `extras`（项目补充词），注入行为不变

## 部署

镜像为多阶段构建：`node:20` 构建前端 → `python:3.12-slim` 运行后端，
**同一个容器同时提供页面和 `/api`**（同源，登录 cookie 无需跨站配置）。
监听端口固定 `7860`（可用 `PORT` 覆盖）。

### 本地验证

```powershell
docker compose up --build      # 打开 http://127.0.0.1:7860
```

或手动：

```powershell
docker build -t recut-agent .
docker run --rm -p 7860:7860 `
  -e AUTH_BOOTSTRAP_EMAIL=you@example.com `
  -e AUTH_BOOTSTRAP_PASSWORD=你的强密码 `
  -e APP_COOKIE_SECURE=false `
  recut-agent
```

### 魔搭创空间（ModelScope Studio）

| 设置项 | 值 |
|---|---|
| 应用部署框架 | `docker` |
| 云资源 | 免费 CPU（2vCPU / 8G）即可，模型走远程 API，不需要 GPU |
| 监听端口 | `7860` |
| 部署入口文件 | 仓库根目录的 `Dockerfile`（已提供） |

在空间的环境变量里填：

| 变量 | 说明 |
|---|---|
| `LLM_API_KEY` | 模型服务密钥（不填则生成接口返回 503） |
| `LLM_BASE_URL` / `LLM_MODEL` | 默认 `https://api.deepseek.com/v1` / `deepseek-chat` |
| `VISION_API_KEY` / `VISION_MODEL` | 视频/图片反推用，可留空 |
| `APP_COOKIE_SECURE` | 创空间是 HTTPS，**必须设为 `true`** |
| `AUTH_BOOTSTRAP_EMAIL` | 首个管理员的邮箱 |
| `AUTH_BOOTSTRAP_PASSWORD` | 首个管理员的密码（≥10 位；登录后请立刻在界面里改掉） |

> `AUTH_BOOTSTRAP_*` 只在**库中一个用户都没有**时生效，所以本地不填也不会误建账号。

### ⚠️ 免费空间没有持久存储

SQLite 数据库与用户上传的参考首帧都写在容器文件系统里，**空间休眠或重新部署后会清空**
（账号、项目、角色资产、图片全部丢失，只有代码和配置保留）。

因此这个平台适合做**演示站**，不适合长期使用。要真正持久化，需要二选一：

- 换外部数据库（如 RDS / Neon / Supabase），把 `APP_DB_URL` 指过去，图片换对象存储
- 换带持久卷的平台（Fly.io 卷、自有 VPS 挂目录）

## 已知限制

- 数据库为单机 SQLite，`uvicorn --workers > 1` 不可用；多实例部署需换 PostgreSQL
- 账号仅支持管理员用 CLI 创建，找回密码 / 邮箱验证尚未实现
- 造型一致性字段预留但暂未接入真实比对算法
- **剪映草稿是实验性输出**：格式未公开且随版本变化，生成的 zip 里另附 `shots.md` / `shots.csv` 作为兜底

## License

未指定。如需开源请自行添加 LICENSE。
