# forward_agent

独立的 Python 正向分镜 Agent：

```text
剧情/脑洞 -> 编剧节拍 -> 分镜卡片 -> 平台提示词
```

本包只提供 Python 调用接口，不依赖 FastAPI、Vue、SSE、SQLite 或当前项目的 `app.*` 包。

## 安装

目标项目只需要安装 Pydantic 2：

```powershell
python -m pip install "pydantic>=2,<3"
```

也可以把本目录直接复制到已有 Python 后端中。

## 调用

```python
from forward_agent import ForwardAgent, Platform

agent = ForwardAgent(
    base_url="https://api.deepseek.com/v1",
    api_key="YOUR_API_KEY",
    model="deepseek-chat",
)

plan = await agent.generate(
    "一个普通保洁员在公司年会上突然被认出是前任董事长",
    style="搞笑反转",
    target_duration=15,
    platform=Platform.KLING,
)

for card in plan.cards:
    print(card.id, card.prompts.video.zh)
    print(card.platform_variants.get("kling"))
```

没有配置 API key 时会自动使用确定性的 MockProvider，适合开发和接口联调：

```python
plan = ForwardAgent().generate_sync("一个人在便利店发现收银员是未来的自己")
print(plan.to_dict())
```

## 自定义 Provider

Provider 只需要实现：

```python
async def chat_json(*, model, messages, temperature=0.7) -> dict:
    ...
```

然后注入：

```python
agent = ForwardAgent(provider=my_provider)
```

## 返回结构

`ShotPlan` 包含：

- `title`、`logline`、`scene_type`
- `cards`: 分镜卡片列表
- `ShotCard.prompts.first_frame`: 首帧图提示词，中英双语
- `ShotCard.prompts.video`: 视频动作提示词，中英双语
- `ShotCard.platform_variants`: 目标平台最终提示词
- `CharacterAnchor.immutable/mutable`: 角色一致性锚点

## 当前边界

这是可编辑的分镜提示词生成器，不负责视频生成、音频生成、成片渲染或平台发布。真实模型的输出质量取决于目标视觉/文本模型和平台能力；Mock 只用于验证调用链。
