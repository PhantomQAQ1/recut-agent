import asyncio

from forward_agent import ForwardAgent, MockProvider, Platform


def test_mock_generation():
    plan = asyncio.run(ForwardAgent(provider=MockProvider()).generate(
        "一个普通人在便利店发现收银员是未来的自己",
        style="搞笑反转",
        target_duration=15,
        platform=Platform.KLING,
    ))
    assert plan.cards
    assert plan.title
    assert all(card.prompts.video.zh for card in plan.cards)
    assert all(Platform.KLING.value in card.platform_variants for card in plan.cards)
    assert all(card.source == "forward" for card in plan.cards)


if __name__ == "__main__":
    test_mock_generation()
    print("forward_agent: PASS")
