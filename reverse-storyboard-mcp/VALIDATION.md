# 验证记录

2026-11-17，本工作区验证结果：

- 系统 Python 3.9 可运行无 Pydantic 的媒体/导出模块。真实 ffmpeg 合成红蓝红 6 秒视频、短于抽样间隔视频；10 项媒体测试通过（切镜、连续覆盖、JPEG 颜色、短片、人工分段、预算拒绝）。
- 5 项导出测试通过（2026-11-18 再次执行，含实际引用证据帧索引回归测试）；11 个 Python 文件语法解析通过。视觉分析已改为仅按模型引用帧的独立时间点判断是否允许动作/运镜，并在镜头保存模型、prompt 版本和完成时间；该视觉修改仍待合适依赖环境运行测试。
- 原 4 项导出测试通过（中文 BOM CSV、Markdown 转义、未知不编造、工作台字段形状）。短片接近片尾无帧时继续回退的 bug 已修复。
- 项目声明 Python >=3.10；系统 Python 3.9 无法加载 Pydantic 的 `str | None` 注解，不能用于完整 MCP 服务。
- 打包 Python 3.12 存在，但缺 MCP、Pydantic、httpx、imageio-ffmpeg；新建 .venv 3.12 因 ensurepip 写权限问题没有 pip。
- 官方 MCP 1.30.0 可在 confined PyPI 解析，但 pip 写入 wheel.metadata 被沙箱拒绝。unconfined 同命令返回无候选包。未成功安装完整运行依赖。
- 权限技能检查发现项目目录和 .tmp 缺当前用户 WRITE_OWNER，已添加当前用户完全控制并验证通过；内容与所有者未变。后续 pip 子目录仍受阻，未宣称环境已修复。
- 服务测试用例已实现，但本机缺 SDK，不能用跳过测试声称 MCP 协议通过。视觉适配测试使用 httpx MockTransport 固定响应，尚未在合适环境执行；不等于真实模型准确率验证。
- 无真实视觉模型请求、付费 API 或认证 Updream 画布测试。因此可确认本地切镜与导出实现，完整 MCP 和真实视觉链路仍需下列验证。

## 在可安装依赖的 Python 3.10+ 环境验证

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

启动 MCP host 后：list_tools 应有 health/prepare_video/analyze_shots/get_project/export_storyboard。先 health；准备一段获授权的视频；核对镜头时间/证据图；无配置时 analyze_shots 应报清楚配置错误；配置视觉模型后分析一镜头并审核，再分析其余镜头；导出四种格式后重新启动服务读取同一 project_id，确认落盘恢复。

## 权限恢复记录

报告位于 `../permission-recovery/acl-report-cd88f1a5f41842d092afc75f8cbe6733.jsonl`，每项变更的恢复脚本与备份均在同一目录。需要撤销时按报告 rollbackCommands 的顺序执行。不要手工递归重写文件权限。
