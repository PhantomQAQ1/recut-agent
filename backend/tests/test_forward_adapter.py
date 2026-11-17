"""适配层测试：运镜映射与 Mock 计划契约。"""

from __future__ import annotations

import asyncio

from forward_adapter import _move, agent_plan
from schemas import GenerateRequest

FRONTEND_MOVES = {
    "固定机位 Static",
    "缓慢横移 Truck",
    "手持跟拍 Handheld",
    "环绕跟拍 Orbit",
    "急速推镜 Crash Zoom",
    "低机位升格 Low angle",
    "缓慢拉远 Pull out",
    "横向摇镜 Pan",
    "升降机位 Crane",
}


def test_move_mapping_targets_frontend_options():
    assert _move("推") == "急速推镜 Crash Zoom"
    assert _move("固定") == "固定机位 Static"
    assert _move("拉") == "缓慢拉远 Pull out"
    # 未知值原样保留，不能被吞掉
    assert _move("滑轨") == "滑轨"
    assert _move(None) == "固定机位 Static"


def test_agent_plan_without_key_is_marked_demo():
    """没有模型 Key 时应走包内 Mock，并把"演示数据"标出来。"""
    plan, demo = asyncio.run(
        agent_plan(GenerateRequest(idea="一个人在便利店发现收银员是未来的自己", style="搞笑反转", model="可灵 Kling"))
    )
    assert demo is True
    assert plan.shots
    assert "演示数据" in plan.narrative
    assert all(item.agent_shot is not None for item in plan.shots)
    assert all(item.move in FRONTEND_MOVES for item in plan.shots)
    # 展开时用的卡片必须与计划索引一一对应
    assert [item.index for item in plan.shots] == list(range(1, len(plan.shots) + 1))
    assert all(item.agent_shot.id == item.index for item in plan.shots)
