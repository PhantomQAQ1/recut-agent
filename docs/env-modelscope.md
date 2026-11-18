# 魔搭创空间环境变量清单

> 适用：`https://www.modelscope.cn/studios/PhantomcatQAQ/Recut_Agent`
> 位置：创空间 → **设置 → 环境变量**，逐条添加；**保存后必须重启空间**才生效。
> 图片规格：CPU 资源即可，不需要 GPU。

---

## 一、必填（不配这两个功能都不可用）

| 变量名 | 值 | 说明 |
|---|---|---|
| `LLM_API_KEY` | `ms-...`（你本地 `backend/.env` 里的值） | 魔搭访问令牌，**唯一密钥，正向和逆向共用** |
| `LLM_BASE_URL` | `https://api-inference.modelscope.cn/v1` | 必须是这个地址 |
| `LLM_MODEL` | `Qwen/Qwen3.5-27B` | 正向生成（文本） |
| `VISION_MODEL` | `Qwen/Qwen3.5-35B-A3B` | 逆向解析（多模态），**必须与上面不同**的模型 ID |

## 二、持久化（不配则每次重启数据清空）

| 变量名 | 值 | 说明 |
|---|---|---|
| `APP_DB_URL` | `sqlite:////mnt/workspace/data/recut.db` | **四个斜杠**＝`sqlite:///` + 绝对路径 `/mnt/...` |
| `APP_UPLOAD_DIR` | `/mnt/workspace/uploads` | 参考首帧图片 |
| `APP_COOKIE_SECURE` | `true` | 创空间是 HTTPS，不设会导致登录后 cookie 丢失 |

## 三、建议（不配也能跑）

| 变量名 | 值 | 说明 |
|---|---|---|
| `REVERSE_ENGINE` | `builtin` | 先保持默认。`mcp` 是逐镜证据式分析，更准但每镜一次视觉调用，吃配额快 |
| `REVERSE_MAX_SHOTS` | `8` | 只在 `REVERSE_ENGINE=mcp` 时生效 |
| `MAX_UPLOAD_MB` | `200` | 默认 50。你之前两次逆向失败就是素材超 50MB；上传是流式落盘，改大不占内存 |
| `APP_ALLOWED_ORIGINS` | `https://phantomcatqaq-recut-agent.ms.show` | 新版代码同源会自动放行，可留空；部署旧代码时必须配，否则登录报「请求来源不被允许」 |

## 四、**不要**单独设置的变量（陷阱）

| 变量名 | 原因 |
|---|---|
| `VISION_API_KEY` | 一旦单独设置，`VISION_BASE_URL` 会回退到阿里云默认地址，逆向会调错服务。除非你同时设 `VISION_BASE_URL`，否则**不设**，让它复用 `LLM_API_KEY` |
| `VISION_BASE_URL` | 同上，留空即复用 `LLM_BASE_URL` |
| `AUTH_BOOTSTRAP_*` | 现在空库时登录页会自动变成「首次初始化」，不需要环境变量建号 |

---

## 五、一次性对照块（.env 格式，仅供本地核对）

```ini
LLM_API_KEY=ms-你的令牌
LLM_BASE_URL=https://api-inference.modelscope.cn/v1
LLM_MODEL=Qwen/Qwen3.5-27B
VISION_MODEL=Qwen/Qwen3.5-35B-A3B

APP_DB_URL=sqlite:////mnt/workspace/data/recut.db
APP_UPLOAD_DIR=/mnt/workspace/uploads
APP_COOKIE_SECURE=true

REVERSE_ENGINE=builtin
REVERSE_MAX_SHOTS=8
MAX_UPLOAD_MB=200
```

## 五之二、创空间部署 JSON（设置页的「JSON 配置」）

新版设置页用一份部署描述文件管理，环境变量写在 `environment_variables` 数组里
（字段定义见 `https://www.modelscope.cn/api/v1/studios/deploy_schema.json`）。
直接整段替换：

```json
{
  "$schema": "https://www.modelscope.cn/api/v1/studios/deploy_schema.json",
  "sdk_type": "docker",
  "resource_configuration": "platform/2v-cpu-16g-mem",
  "port": 7860,
  "environment_variables": [
    { "name": "LLM_API_KEY", "value": "ms-你的令牌" },
    { "name": "LLM_BASE_URL", "value": "https://api-inference.modelscope.cn/v1" },
    { "name": "LLM_MODEL", "value": "Qwen/Qwen3.5-27B" },
    { "name": "VISION_MODEL", "value": "Qwen/Qwen3.5-35B-A3B" },
    { "name": "APP_DB_URL", "value": "sqlite:////mnt/workspace/data/recut.db" },
    { "name": "APP_UPLOAD_DIR", "value": "/mnt/workspace/uploads" },
    { "name": "APP_COOKIE_SECURE", "value": "true" },
    { "name": "REVERSE_ENGINE", "value": "builtin" },
    { "name": "REVERSE_MAX_SHOTS", "value": "8" },
    { "name": "MAX_UPLOAD_MB", "value": "200" }
  ]
}
```

注意：

- `value` 必须是**字符串**，布尔和数字也要加引号
- `resource_configuration` 的合法值只有 `platform/2v-cpu-16g-mem`（免费）和两个 `xgpu/*`；
  如果原配置是 `platform/2v-cpu-8g-mem`，它不在 schema 枚举里，建议一并改成 16g
- `port` 对 docker 类型必须正好是 `7860`，且不能是平台保留端口（5000/8080/9090 等）

> 控制台是逐条 key/value 添加，不是粘贴整个文件；上面这块只用于和本地 `.env` 比对。
> 密钥由控制台保存后**不可再查询**，粘贴前先确认复制正确。

---

## 六、保存后怎么确认

1. **重启创空间**
2. 打开 `https://phantomcatqaq-recut-agent.ms.show/api/health`

正确结果：

```json
{"status":"ok","llm":"configured","vision":"configured","auth":"cookie-session"}
```

- `missing-key` → 对应的 Key 没生效（变量名拼错或没重启）
- 整个返回 403 且带 `Code:10011402001` → 是**魔搭平台**的访问限制（空间非公开），不是应用错误
- 404 → 空间跑的还是旧代码（缺新路由），需要重新部署

3. 打开 `https://phantomcatqaq-recut-agent.ms.show/api/bootstrap`

```json
{"users":0,"bootstrap_configured":false,"db_path":"/mnt/workspace/data/recut.db",...}
```

- `db_path` 指向 `/mnt/workspace/...` 才算持久化生效；显示 `/app/backend/...` 说明 `APP_DB_URL` 没生效
- `users: 0` 时会话页会自动显示「首次初始化」，建完即可登录

---

## 七、常见现象对照

| 现象 | 原因 | 处理 |
|---|---|---|
| 正向生成出来是「【演示数据：固定 Mock】」 | 容器里没有 `LLM_API_KEY` | 补 key 后重启 |
| 正向生成报 502 且提到 `limit_burst_rate` | 免费额度突发限流 | 等 10 秒重试；新版已有自动退避 |
| 逆向 503「需要视觉模型配置」 | `VISION_MODEL` 没配，或 Key 没复用成功 | 补 `VISION_MODEL`；不要单独设 `VISION_API_KEY` |
| 逆向 400 `has no provider supported` | 视觉模型 ID 不在架 | 换成模型页带 API-Inference 闪电标的 |
| 逆向 422「素材超过 50MB」 | 上传超限 | 调大 `MAX_UPLOAD_MB` 或压缩素材 |
| 登录报「请求来源不被允许」 | 旧代码 + 未配白名单 | 升级代码，或配 `APP_ALLOWED_ORIGINS` |
| 重启后账号和项目全没了 | 未配持久卷 | 检查 `APP_DB_URL` 是否四斜杠指向 `/mnt/workspace` |
