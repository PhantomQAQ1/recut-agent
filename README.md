# ReCut Agent

AIGC 视频分镜与提示词工作台：把一句创意变成可直接投喂给即梦 / 可灵 / Runway 的镜头脚本，也能把一段素材反推成分镜。

## 功能

- **正向生成**：创意 + 二创风格 + 角色锚点 → 分镜脚本（景别 / 焦段 / 运镜 / 中英双语提示词）
- **两阶段生成**：先出可编辑的镜头计划，确认后再逐镜并发展开提示词，单镜失败可单独重试
- **单镜微调**：输入指令 → 模型改写 → 新旧字段对比 → 采用或放弃
- **故事板卡片**：提示词为主体内容，支持参考首帧、场景层、8 套调色板、缩略导航
- **编辑效率**：镜头重排（上移/下移）、撤销/重做（50 步）、快捷键（`⌘/Ctrl+Enter` 生成、`↑↓` 切换、`Delete` 删除、`⌘/Ctrl+Z` 撤销）
- **角色一致性**：镜头可绑定角色资产，微调时自动带上该角色的锚点；提示词里缺失时卡片高亮提醒，可一键注入
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

## 已知限制

- 数据库为单机 SQLite，`uvicorn --workers > 1` 不可用；多实例部署需换 PostgreSQL
- 账号仅支持管理员用 CLI 创建，找回密码 / 邮箱验证尚未实现
- 造型一致性字段预留但暂未接入真实比对算法
- **剪映草稿是实验性输出**：格式未公开且随版本变化，生成的 zip 里另附 `shots.md` / `shots.csv` 作为兜底

## License

未指定。如需开源请自行添加 LICENSE。
