# 部署到魔搭 ModelScope 创空间

> 适用版本：`main` 分支（含 Dockerfile、静态挂载、环境变量建号）
> 官方文档参考：[创空间创建与搭建](https://www.modelscope.cn/docs/studios/create.md)

---

## 0. 先搞清楚：为什么不能选 Static

| SDK 类型 | 平台做什么 | 能否跑本项目 |
|---|---|---|
| **Static** | 只把仓库当静态站点托管，入口文件默认 `index.html` | ❌ 不启动任何进程，FastAPI 无法运行 |
| Gradio / Streamlit | 启动 `app.py` 并等待页面 | ⚠️ 需要改写入口（见文末备选） |
| **Docker** | 用仓库根目录的 `Dockerfile` 构建镜像并运行容器 | ✅ **本项目走这条** |

你当前看到的提示：

```
当前为 static 创空间，默认启动文件为 index.html，需放置在空间根目录。
```

意思是平台在找一个静态入口文件。**不要为了解决这个提示去塞 index.html**——那样只会得到一个没有后端、点登录就报错的空壳页面。

正确做法：**新建一个 Docker 类型的创空间**（或把现有空间的 SDK 改为 Docker，取决于平台是否允许修改）。

---

## 1. 代码侧已具备的能力

| 能力 | 位置 | 说明 |
|---|---|---|
| 多阶段构建 | `Dockerfile` | node 构建前端 → 产物塞进 python 镜像，最终镜像不含 node_modules |
| 同源部署 | `backend/main.py:289` | 检测到 `frontend/dist/index.html` 就在根路径挂载静态文件，前端与 `/api` 同源，登录 cookie 不需要跨站配置 |
| 环境变量建号 | `backend/main.py:89` | 容器里没有终端，用 `AUTH_BOOTSTRAP_EMAIL/PASSWORD` 创建首个管理员 |
| 数据库目录自建 | `backend/db.py:152` | 绝对路径的父目录不存在时会自动 `mkdir -p` |
| 上传目录自建 | `backend/uploads.py:37` | 同上 |
| 端口 | `Dockerfile` | 默认 7860，可用 `PORT` 覆盖 |
| 健康检查 | `Dockerfile` | 每 30s 请求 `/api/health` |

---

## 2. 创建创空间并推送代码

### 2.1 创建

1. 登录魔搭 → 右上角头像 → **创建创空间**
2. **接入 SDK 选 Docker**（不是 Static）
3. 云资源：**免费 CPU 即可**（本项目不推理模型，不占 GPU）
4. 镜像版本：默认最新 Python 3.12 镜像即可——注意我们用的是自己的 Dockerfile，平台镜像对本项目影响很小

### 2.2 推送

平台会给出仓库地址，按官方格式（token 从「个人中心 → 访问令牌」获取）：

```bash
git remote add modelscope https://www.modelscope.cn/studios/<用户名>/<空间名>.git
git push modelscope main
```

首次推送如果要求鉴权，把 remote 写成：

```bash
https://oauth2:<你的ACCESS_TOKEN>@www.modelscope.cn/studios/<用户名>/<空间名>.git
```

### 2.3 ⚠️ master 是保护分支，不能 force push

空间仓库默认分支是 **`master`** 且受保护，`--force` 会被拒：

```
remote: You are not allowed to force push code to a protected branch
```

正确做法：造一个「以 master 为父提交、树用本地代码」的提交，等同一次正常合入：

```bash
git fetch modelscope master
commit=$(git commit-tree "$(git rev-parse 'main^{tree}')" -p FETCH_HEAD -m "chore(deploy): 同步最新代码")
git push modelscope "$commit:master"
```

### 2.4 用 OpenAPI 配置变量并上线

基础地址 `https://modelscope.cn/openapi/v1`，认证 `Authorization: Bearer <令牌>`：

| 操作 | 请求 |
|---|---|
| 列明文变量 | `GET /studios/{o}/{r}/variables` |
| 新增明文变量 | `POST /studios/{o}/{r}/variables`，body `{"key","value"}` |
| 新增密钥 | `POST /studios/{o}/{r}/secrets`，body `{"key","value"}` |
| 触发部署 | `POST /studios/{o}/{r}/deploy` |
| 构建日志 | `GET /studios/{o}/{r}/logs/build` |
| 运行日志 | `GET /studios/{o}/{r}/logs/run` |
| 空间详情 | `GET /studios/{o}/{r}`（含 status） |

`deploy` 后 `status` 依次为 `Building` → `Deploying` → `Running`。

### 2.5 验证：匿名访问 403 是正常的

空间页面 `https://<user>-<repo>.ms.show` 对**匿名访问返回魔搭自己的 403**
（`Code:10011402001`），这不是应用故障。程序化验证要走专用 API 域名，
令牌报错的提示信息里会给出完整地址：

```
https://studio-<user>-<repo>.api-inference.modelscope.net/api/health
```

期望 `{"status":"ok","llm":"configured","vision":"configured"}`。

---

## 3. 环境变量（关键）

在创空间 **设置 → 环境变量** 里添加，**保存后必须重启空间**才生效。

### 必填

| 变量 | 值 | 作用 |
|---|---|---|
| `APP_DB_URL` | `sqlite:////mnt/workspace/data/recut.db` | **注意四个斜杠**：`sqlite:///` + 绝对路径 `/mnt/...`。指向持久卷，否则重启即清库 |
| `APP_UPLOAD_DIR` | `/mnt/workspace/uploads` | 参考首帧图片，同样必须放持久卷 |
| `APP_COOKIE_SECURE` | `true` | 创空间是 HTTPS，cookie 必须带 Secure 才会被浏览器发送 |

### 第一个管理员：两种方式，任选其一

**方式 A（推荐）：页面初始化** —— 不需要任何环境变量。

部署完成后打开空间，如果库里没有任何账号，登录页会自动变成「首次初始化」表单，
填邮箱 + 至少 10 位密码即可创建管理员并直接登录。**创建成功后该入口永久关闭**（再调返回 409）。

> 安全提醒：初始化入口是匿名可访问的。空间是公开的话，建议先设为私密、建完号再公开，
> 或者用方式 B 的固定账号。

**方式 B：环境变量建号** —— 适合不希望开放初始化入口的场景。

| 变量 | 说明 |
|---|---|
| `AUTH_BOOTSTRAP_EMAIL` | 首个管理员邮箱 |
| `AUTH_BOOTSTRAP_PASSWORD` | **至少 10 位**，首尾不能有空格 |
| `AUTH_BOOTSTRAP_NAME` | 显示名，可选 |

只在库里一个账号都没有时生效。配好后**必须重启**。


### 生成能力（不填则生成接口 503，其余功能正常）

| 变量 | 示例 |
|---|---|
| `LLM_API_KEY` | 硅基流动 / 深寻 / 百炼的 Key |
| `LLM_BASE_URL` | `https://api.siliconflow.cn/v1` |
| `LLM_MODEL` | `deepseek-ai/DeepSeek-V3` |
| `VISION_MODEL` | `Qwen/Qwen2.5-VL-72B-Instruct` |

视觉模型默认复用 `LLM_API_KEY` 与 `LLM_BASE_URL`，需要单独供应商时再填 `VISION_API_KEY` / `VISION_BASE_URL`。

### 可选

| 变量 | 说明 |
|---|---|
| `APP_ROOT_PATH` | **打开空间地址返回 `{"detail":"Not Found"}` 时填这个**。有些平台不剥掉访问前缀（形如 `/studios/<用户>/<空间名>/`），把前缀原样填进来（结尾不要带斜杠），路由才会按根路径匹配；平台已剥前缀时留空 |
| `APP_ALLOWED_ORIGINS` | 一般**不需要**填：同源请求会自动放行（Origin 与本请求 host 一致）。只有前端独立部署在别的域名时才填，逗号分隔 |
| `MAX_FRAMES` | 逆向解析抽帧数，默认 6 |
| `PORT` | 默认 7860，一般不用改 |

---

## 4. 数据持久化

官方说明：**除 `/mnt/workspace` 外，容器重启后写入的数据都会丢失**。

因此必须把两个可写路径指到持久卷：

```
/mnt/workspace/data/recut.db     ← 数据库（用户、项目、角色、标签）
/mnt/workspace/uploads/          ← 参考首帧图片
```

> 空间被转移或重命名时 `/mnt/workspace` 仍可能丢；长期可靠方案是外接 OSS 或托管数据库（当前用 SQLite，属于路线图 P3 的 PostgreSQL 迁移项）。

### 为什么本地的角色和分镜没有自动出现在创空间

**因为数据库和上传目录从来没有进入代码仓库**：

| 文件 | 规则 | 结果 |
|---|---|---|
| `.gitignore` | `*.db`、`backend/uploads/` | 数据库和图片不进 git |
| `.dockerignore` | `backend/recut.db*`、`backend/uploads` | 即使本地存在，也不会被打进镜像 |

两条一起作用的结果是：**本地和部署环境是两套完全独立的数据**。
本地有 5 个项目，不代表空间里有；反之亦然。这是有意为之——避免把带密码哈希的库上传到公开仓库。

### 把本地数据搬到创空间（导出 / 导入）

项目、角色、标签都可以通过内置通道迁移（**不含密码哈希**）：

1. **本地**：头像菜单 →「导出数据（JSON）」→ 得到 `recut-workspace-日期.json`
2. **部署环境**：先完成初始化登录 → 头像菜单 →「导入数据」→ 选择刚才的文件
3. 结果是「项目 N、角色 N、标签 N」，同名项会自动跳过，不会产生副本

注意：
- **参考首帧图片不包含在内**，需要在部署环境重新上传（图片体积大，且与 upload id 绑定）
- 反向迁移同样可行：从空间导出、到本地导入
- 导入按名字去重，所以重复导入是安全的

---

## 5. 首次上线流程

```
1. 推送代码
2. 配置环境变量（第 3 节：数据库 / 上传 / cookie 三项必填，建号可跳过）
3. 点「上线」/「立即发布」
4. 看构建日志：npm ci → npm run build → pip install → 启动 uvicorn
5. 打开空间地址 → 若显示「首次初始化」，直接创建管理员（推荐）
6. 建完就能用；之后想改密码走用户菜单
```

### 登录报「邮箱或密码不正确」怎么排查

**先看自检接口**：

```
https://<你的空间域名>/api/bootstrap
```

| `users` | `bootstrap_configured` | 含义 | 处理 |
|---|---|---|---|
| 0 | false | 没有账号，也没配变量 | 用页面「首次初始化」建号，或配 `AUTH_BOOTSTRAP_*` 后重启 |
| 0 | true | 配了但没建成 | 密码**至少 10 位**、首尾不能有空格；或改了变量没重启 |
| ≥1 | — | 账号已存在 | 邮箱/密码记错；用 `scripts/manage_user.py passwd` 重置 |

`db_path` 顺便能验证持久化：指向 `/mnt/workspace/...` 才说明数据能留存。

建号成功的日志：

```
INFO [recut] 已创建初始管理员 you@example.com，请登录后立即修改密码
```

> 注意：如果没配 `APP_DB_URL` 指向 `/mnt/workspace`，每次重启数据库都会重建，
> 初始化入口会**重新出现**——看起来能用，但上次的数据都会消失。

---

## 6. 排错对照表

| 现象 | 可能原因 | 处理 |
|---|---|---|
| 登录时提示「请求来源不被允许」（403） | 部署域名不在 `APP_ALLOWED_ORIGINS` 白名单。旧版代码只放行 localhost | 加 `APP_ALLOWED_ORIGINS=https://<你的空间域名>` 并重启；新版代码已改为同源自动放行 |
| 打开空间返回 `{"detail":"Not Found"}`，但 `/api/health` 正常 | 前端产物没进镜像 | 看构建日志里有没有 `COPY --from=frontend /build/dist`；确认第一阶段 `npm run build` 成功 |
| 打开空间返回 `{"detail":"Not Found"}`，`/api/health` 也是 404 | 平台没有剥掉访问前缀 | 设置 `APP_ROOT_PATH=/studios/<用户>/<空间名>` 后重启 |
| 部署成功但页面 404 | 前端没构建出来 | 看构建日志是否有 `npm run build` 失败；确认 `frontend/package-lock.json` 在仓库里（`npm ci` 需要它） |
| 页面能开但所有请求 404 | `frontend/dist` 没进镜像 | 检查 `.dockerignore` 是否误排除了 `dist`（本项目是构建期生成，正常不该有） |
| 登录成功但立刻又变未登录 | cookie 没带上 | 确认 `APP_COOKIE_SECURE=true` 且通过 **https** 访问；用 http 访问会丢 cookie |
| 重启后数据全没了 | 数据库不在持久卷 | 检查 `APP_DB_URL` 是否是 `sqlite:////mnt/workspace/...`（四个斜杠） |
| 启动即报 `unable to open database file` | 路径写错或权限不足 | 确认是绝对路径；`database_path()` 会自建父目录，但仍需可写 |
| 生成接口 503 | 没配 `LLM_API_KEY` | 配 Key 后重启；`/api/health` 会显示 `llm: missing-key` |
| 逆向解析报 ffmpeg 错误 | 缺少 ffmpeg | 本项目用 `imageio-ffmpeg` 自带二进制，通常是 PATH 问题；可在仓库根加 `packages.txt` 写 `ffmpeg`（仅 Gradio/Streamlit SDK 会读） |
| 端口探测失败 | 平台期望的端口不是 7860 | 设置 `PORT` 为平台要求的端口，或改 `Dockerfile` 的 `EXPOSE` |

---

## 7. 备选方案：只能选 Gradio 时

如果平台不给你 Docker 选项，可以写一个 `app.py` 作为入口，由它启动我们的 FastAPI：

```python
"""创空间入口：把现成的 FastAPI 应用拉到 7860 端口。"""
import os
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "7860")),
        app_dir="backend",
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
```

同时需要：

1. 前端先在本机构建，把 `frontend/dist` 一起提交（`.dockerignore` 不影响它，但仓库默认忽略 `dist`，需要临时调整）
2. `requirements.txt` 放在**仓库根目录**，逐行写依赖
3. README YAML 里配置 `deployspec.entry_file: app.py`

这条路能跑，但比 Docker 方案多两个坑：前端产物要跟着提交、依赖要手工维护两份。**优先争取 Docker。**

---

## 8. 与本地开发的差异

| 项 | 本地 | 创空间 |
|---|---|---|
| 数据库 | `backend/recut.db` | `/mnt/workspace/data/recut.db` |
| 上传 | `backend/uploads/` | `/mnt/workspace/uploads/` |
| 前端 | Vite dev server 5173，代理到 8000 | 由 FastAPI 直接从 `frontend/dist` 提供 |
| Cookie Secure | `false`（http） | `true`（https） |
| 建号 | `python -m scripts.manage_user` | `AUTH_BOOTSTRAP_*` 环境变量 |
