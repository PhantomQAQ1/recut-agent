# FastAPI 适配边界

当前 MCP 服务迁移到目标项目后保持独立运行，使用 stdio MCP 协议；本文件定义未来接入 `E:\hks-AIGC-video\backend` 的边界，不修改现有后端。

## 推荐调用方式

新增一个后端适配层，以 MCP client 启动或连接 `reverse-storyboard-mcp` 子进程，后端路由只负责：

1. 校验当前用户身份和上传文件归属。
2. 将文件放到允许的媒体根目录，并把路径传给 `prepare_video`。
3. 保存返回的 `project_id` 与用户项目的关联。
4. 分页调用 `get_project`，把镜头卡片映射为现有 ShotPlan/ShotCard schema。
5. 对 `analyze_shots` 和 `export_storyboard` 做权限检查、超时控制和错误转换。

## MCP 到 FastAPI 的映射

| MCP 工具 | 适配层职责 | 现有 API 对应方向 |
|---|---|---|
| `health` | 服务可用性和视觉配置状态 | `/api/health` 的扩展信息 |
| `prepare_video` | 上传文件路径、抽样参数、切镜结果 | `/api/v1/storyboard/reverse` 的准备阶段 |
| `analyze_shots` | 逐镜头视觉分析、重试和状态保存 | reverse 的分析阶段 |
| `get_project` | 分页读取证据帧路径和结构化观察 | 新增读取接口或内部服务调用 |
| `export_storyboard` | 导出文件路径和格式白名单 | 现有导出接口的补充 |

## 数据与安全约束

- MCP 独立环境建议使用 `reverse-storyboard-mcp\\.venv`，不要复用 `backend\\.venv`，避免改变现有后端依赖解析结果。
- `STORYBOARD_MEDIA_ROOTS` 只允许目标项目的上传目录或用户授权媒体目录。
- `STORYBOARD_DATA_DIR` 应使用目标项目数据目录下的独立子目录，例如 `E:\\hks-AIGC-video\\data\\storyboard`。
- 后端必须重新检查用户权限，不能把 MCP 返回的路径或 project_id 当成授权证明。
- API key 只注入 MCP 子进程环境，不写入项目 JSON、数据库、导出文件或日志。
- 后端应限制 MCP 子进程生命周期、请求超时和并发数，并将 MCP 错误转换为安全的 HTTP 错误。

## 字段映射注意事项

`shot-plan` 是现有工作台形状的兼容草稿，缺失字段保持 `null` 或空值并标记 `needs_review`。现有 Pydantic 枚举比 MCP 的自由文本观察严格，因此适配层必须显式映射景别、机位和运镜；未知值进入人工审核流程，不能静默猜测。

`source_start`、`source_end`、`source_frames`、`evidence`、`confidence` 和 `review_flags` 应保留为证据字段。MCP 不返回原始生成提示词，也不证明 Updream 私有画布操作。

## 当前验证边界

独立服务的媒体和导出单元测试已通过；目标环境尚未完成 MCP 依赖安装和 stdio 工具连接验证，因为当前 Windows 沙箱阻止在 `E:\\hks-AIGC-video` 创建迁移子目录。目标目录可复用 Python 3.12.8，但缺 MCP、Pillow、numpy 和 httpx。解除目标目录写入限制后，应先创建独立虚拟环境，再执行 README 中的工具列表和 `health` 验证。
