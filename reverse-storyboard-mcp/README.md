# Reverse Storyboard MCP

独立运行的 MCP 服务：本地视频镜头预处理、基于多模态视觉模型的证据式分镜、提示词草稿，以及 JSON/Markdown/CSV/现有工作台 ShotPlan 形状导出。它只做分析，不生成视频。

## 快速开始

要求 Python 3.10+、可用 ffmpeg（或安装 `imageio-ffmpeg` 后使用其内置 ffmpeg）。Windows PowerShell：

```powershell
cd E:\DSH\video\reverse-storyboard-mcp
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
$env:STORYBOARD_MEDIA_ROOTS = 'D:\video-inputs'
$env:STORYBOARD_DATA_DIR = 'D:\storyboard-data'
$env:STORYBOARD_VISION_BASE_URL = 'https://your-vision-provider.example/v1'
$env:STORYBOARD_VISION_API_KEY = '由你的密钥管理器注入'
$env:STORYBOARD_VISION_MODEL = 'your-multimodal-model'
.\.venv\Scripts\reverse-storyboard-mcp.exe
```

MCP 使用 stdio。不要在启动 stdout 上打印 banner 或日志；日志发 stderr。密钥应由目标 Agent 的 secret/env 管理注入，不要提交到仓库或写进项目 JSON。模型端点须兼容 OpenAI Chat Completions 的图片 `image_url` 与 `response_format: json_object`。公网地址只接受 HTTPS；HTTP 仅允许 loopback。HTTP 请求不读取系统代理配置。

## MCP 工具

- `health`: 查询数据目录、允许的视频根目录和视觉模型是否配置。不会返回 key。
- `prepare_video(video_path, sample_fps=2, threshold=0.28, max_shot_seconds=20)`: ffmpeg 本地探测和按采样帧硬切，输出时间轴连续的镜头及每镜头首/中/尾证据 JPEG。默认限制 1 GiB、300 秒、80 个镜头。
- `analyze_shots(project_id, shot_ids?)`: 每次最多 10 镜头；未传时选前 5 个待分析/失败镜头。成功保存观测和提示词，失败镜头标记失败且不伪造观测，可重试。必须配置视觉模型；没有配置时明确报错。
- `get_project(project_id, offset=0, limit=20)`: 分页获取卡片及源媒体 hash/时间轴元数据；单次最多 20 张。不返回图像 base64。
- `export_storyboard(project_id, format)`: 导出 `json`、`markdown`、`csv` 或 `shot-plan`，结果落入项目数据目录下的 exports。

每卡含镜头 [start,end)、边界类型（硬切为启发式，长镜头人为时长拆分会标 artificial）、证据帧路径/时间、analysis 状态、观察字段、置信度、不确定项和提示词草稿。即梦/可灵等平台标签只改变通用措辞提醒，不声称遵循平台私有语法，也不提取原始生成提示词。

## 接入另一个 MCP 客户端

用该项目的可执行入口配置 stdio server：

```json
{
  "mcpServers": {
    "reverse-storyboard": {
      "command": "D:\\path\\to\\reverse-storyboard-mcp\\.venv\\Scripts\\reverse-storyboard-mcp.exe",
      "env": {
        "STORYBOARD_MEDIA_ROOTS": "D:\\video-inputs",
        "STORYBOARD_DATA_DIR": "D:\\storyboard-data",
        "STORYBOARD_VISION_BASE_URL": "https://your-provider.example/v1",
        "STORYBOARD_VISION_MODEL": "your-vision-model"
      }
    }
  }
}
```

把 API key 通过宿主客户端 secret 注入，或在进程环境中设置 `STORYBOARD_VISION_API_KEY`。不同 MCP host 的 secret 字段不统一，配置时避免明文提交密钥。只允许访问 `STORYBOARD_MEDIA_ROOTS` 中的文件；多路径用 Windows `;` 或 POSIX `:` 分隔。结果和 JPEG 写入 `STORYBOARD_DATA_DIR`。

## 导入现有 Python 项目

```python
from reverse_storyboard.media import prepare_video
from reverse_storyboard.exports import build_prompts, to_shot_plan, export_project
```

安装：`pip install -e /path/to/reverse-storyboard-mcp`。视频切分还需 Pillow/numpy/imageio-ffmpeg；MCP 服务还需官方 MCP SDK 与 httpx。

## 现有工作台适配

`shot-plan` 输出字段名与 `backend/app/schemas/shot.py` 的 `ShotPlan` 对齐；缺失的景别/机位/角色/英文文本保留 null 或空值并设 `needs_review=true`。工作台 Pydantic 模型对枚举要求严格，所以导入旧工作台前需把未知 enum 映射到其支持的值并要求人工审核，不能把本服务称作“可直接通过旧 schema 验证”。建议工作台读取 JSON 并基于本项目 `source_start/source_end/source_frames/confidence/evidence/review_flags` 字段做显式映射。

## 能力与限制

- 画面分析来自用户配置的视觉模型，不配置则 MCP tool 明确失败；没有 mock 成功路径。
- 硬切检测基于低分辨率 RGB/颜色直方图抽样，渐变切换、快速运动会产生漏检/误检。采样参数给出检测精度与成本权衡。
- 每个候选镜头首中尾最多三帧。动作/运镜由稀疏帧推断并要求模型说明不确定性；静态/单独时间点不猜动作或运镜。
- 无音轨输入分析，不输出可靠对白/音乐/音效结论。
- 无人物精确框、替换区域分割、原生成提示词提取和视频生成。
- 提示词是基于观察的可编辑草稿，不是第三方平台官方规范或生成成功保证。
- 提供的 Updream 画布链接未向无认证的公开读取返回项目画布数据；实现没有声称逐操作复刻其私有功能。

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
# 安装 MCP 依赖后，验证真实 stdio 初始化、工具列表和 health
.\.venv\Scripts\python.exe tests\smoke_mcp.py
```
