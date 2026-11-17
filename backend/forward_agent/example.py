"""Run: python example.py"""
from forward_agent import ForwardAgent, Platform


def main() -> None:
    agent = ForwardAgent()
    plan = agent.generate_sync(
        "一个普通保洁员在公司年会上突然被认出是前任董事长",
        style="搞笑反转",
        target_duration=15,
        platform=Platform.KLING,
    )
    print("标题：", plan.title)
    print("梗概：", plan.logline)
    for card in plan.cards:
        print("\n镜头 %d / %.1fs" % (card.index + 1, card.duration))
        print("视频提示词：", card.prompts.video.zh)
        print("平台提示词：", card.platform_variants.get(Platform.KLING.value, ""))


if __name__ == "__main__":
    main()
