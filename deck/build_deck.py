# -*- coding: utf-8 -*-
"""生成 ReCut Agent 黑客松路演 PPT。

运行：python build_deck.py
输出：../ReCut-Agent-黑客松路演.pptx
"""
from __future__ import annotations

import os

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

# ---------------------------------------------------------------- 设计系统
W, H = 13.333, 7.5
M = 0.85
CW = W - 2 * M

BG_TOP = "0A0D13"
BG_BOT = "121A27"
CARD = "141A25"
CARD2 = "1A2130"
CARD3 = "202839"
LINE = "2B3446"
TEXT = "F2F5FA"
BODY = "C7CFDE"
MUTED = "8E9AB0"
DIM = "5F6B7F"
AMBER = "F0A32E"
AMBER_SOFT = "FFD08A"
TEAL = "57D3C0"
RED = "E8705F"

LATIN = "Segoe UI"
EA = "Microsoft YaHei"
MONO = "Consolas"

TOTAL = 14


def C(hexv):
    return RGBColor.from_string(hexv)


def _set_alpha(shape, opacity):
    spPr = shape._element.spPr
    solid = spPr.find(qn("a:solidFill"))
    if solid is None or len(solid) == 0:
        return
    clr = solid[0]
    for old in clr.findall(qn("a:alpha")):
        clr.remove(old)
    alpha = etree.SubElement(clr, qn("a:alpha"))
    alpha.set("val", str(int(max(0.0, min(1.0, opacity)) * 100000)))


def _set_line_alpha(shape, opacity):
    ln = shape._element.spPr.find(qn("a:ln"))
    if ln is None:
        return
    solid = ln.find(qn("a:solidFill"))
    if solid is None or len(solid) == 0:
        return
    clr = solid[0]
    alpha = etree.SubElement(clr, qn("a:alpha"))
    alpha.set("val", str(int(max(0.0, min(1.0, opacity)) * 100000)))


def rect(s, x, y, w, h, fill=None, line=None, lw=0.75, radius=None,
         alpha=None, line_alpha=None, shape=MSO_SHAPE.RECTANGLE):
    if radius is not None:
        shape = MSO_SHAPE.ROUNDED_RECTANGLE
    sh = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sh.adjustments[0] = radius if radius is not None else 0.06
        except Exception:
            pass
    if fill:
        sh.fill.solid()
        sh.fill.fore_color.rgb = C(fill)
        if alpha is not None:
            _set_alpha(sh, alpha)
    else:
        sh.fill.background()
    if line:
        sh.line.color.rgb = C(line)
        sh.line.width = Pt(lw)
        if line_alpha is not None:
            _set_line_alpha(sh, line_alpha)
    else:
        sh.line.fill.background()
    sh.text_frame.word_wrap = True
    return sh


def textbox(s, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    return tf


def para(tf, first=False, align=PP_ALIGN.LEFT, space_before=0, space_after=0,
         line=None):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    if space_before:
        p.space_before = Pt(space_before)
    if space_after:
        p.space_after = Pt(space_after)
    if line:
        p.line_spacing = line
    return p


def run(p, text, size=12, color=TEXT, bold=False, latin=LATIN, ea=EA,
        spc=None, italic=False):
    r = p.add_run()
    r.text = text
    f = r.font
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = C(color)
    f.name = latin
    rPr = r._r.get_or_add_rPr()
    ea_el = rPr.find(qn("a:ea"))
    if ea_el is None:
        ea_el = etree.SubElement(rPr, qn("a:ea"))
    ea_el.set("typeface", ea)
    cs_el = rPr.find(qn("a:cs"))
    if cs_el is None:
        cs_el = etree.SubElement(rPr, qn("a:cs"))
    cs_el.set("typeface", latin)
    if spc:
        rPr.set("spc", str(int(spc * 100)))
    return r


def simple(s, x, y, w, h, text, size=12, color=TEXT, bold=False,
           align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, latin=LATIN, ea=EA,
           line=1.25, spc=None, mono=False):
    tf = textbox(s, x, y, w, h, anchor)
    p = para(tf, True, align, line=line)
    run(p, text, size, color, bold, MONO if mono else latin, ea, spc)
    return tf


# ---------------------------------------------------------------- 页面骨架
def background(s):
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(W), Inches(H))
    bg.shadow.inherit = False
    bg.line.fill.background()
    bg.fill.gradient()
    bg.fill.gradient_angle = 45.0
    stops = bg.fill.gradient_stops
    stops[0].color.rgb = C(BG_TOP)
    stops[0].position = 0.0
    stops[1].color.rgb = C(BG_BOT)
    stops[1].position = 1.0

    g = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(W - 5.2), Inches(-2.6),
                           Inches(7.2), Inches(6.4))
    g.shadow.inherit = False
    g.line.fill.background()
    g.fill.solid()
    g.fill.fore_color.rgb = C(AMBER)
    _set_alpha(g, 0.055)

    g2 = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(-2.8), Inches(H - 2.6),
                            Inches(6.0), Inches(5.0))
    g2.shadow.inherit = False
    g2.line.fill.background()
    g2.fill.solid()
    g2.fill.fore_color.rgb = C("2C6E8F")
    _set_alpha(g2, 0.10)


def frame(s, page, footer="ReCut Agent · AIGC 视频分镜工作台"):
    rect(s, M, 6.93, CW, 0.008, fill="FFFFFF", alpha=0.07)
    simple(s, M, 7.05, 6.0, 0.24, footer, 8.5, DIM, spc=0.4)
    tf = textbox(s, W - M - 1.3, 7.05, 1.3, 0.24)
    p = para(tf, True, PP_ALIGN.RIGHT)
    run(p, "%02d" % page, 9, AMBER, True, spc=0.8)
    run(p, " / %d" % TOTAL, 9, DIM, False, spc=0.8)


def head(s, kicker, title, page, title_size=31, subtitle=None):
    rect(s, M, 0.60, 0.055, 0.24, fill=AMBER)
    simple(s, M + 0.20, 0.585, 7.0, 0.26, kicker, 9.5, AMBER, True, spc=1.9)
    tf = textbox(s, M, 0.95, CW, 0.95)
    p = para(tf, True, line=1.12)
    run(p, title, title_size, TEXT, True, spc=-0.2)
    if subtitle:
        simple(s, M, 1.68, CW - 1.0, 0.3, subtitle, 11, MUTED, line=1.3)
    frame(s, page)


def chip(s, x, y, w, h, label, fill=None, color=TEXT, size=9.5, bold=False,
         line=None, alpha=None):
    rect(s, x, y, w, h, fill=fill or CARD2, line=line, radius=0.32, alpha=alpha)
    tf = textbox(s, x, y, w, h, MSO_ANCHOR.MIDDLE)
    p = para(tf, True, PP_ALIGN.CENTER, line=1.0)
    run(p, label, size, color, bold)


def arrow(s, x, y, w=0.30, h=0.30, color=DIM):
    sh = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y),
                            Inches(w), Inches(h))
    sh.shadow.inherit = False
    sh.line.fill.background()
    sh.fill.solid()
    sh.fill.fore_color.rgb = C(color)
    _set_alpha(sh, 0.85)


# ---------------------------------------------------------------- 第 1 页 封面
def slide_cover(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s)

    fx, fw = 9.72, 3.10
    frames = [
        ("镜 01", "全景 · 固定机位", "3.5s", "年会上，保洁员推着清洁车穿过人群。", "全景，平视，固定机位，暖色顶光"),
        ("镜 02", "中近景 · 推", "3.5s", "主持人念出他的名字，他停下动作。", "中近景，平视，镜头缓慢推近"),
        ("镜 03", "特写 · 固定", "3.5s", "眼神短暂睁大，随后恢复平静。", "特写，平视，均匀面光，背景虚化"),
    ]
    fy = 0.45
    for i, (no, meta, dur, desc, prompt) in enumerate(frames):
        y = fy + i * 1.84
        rect(s, fx - 0.26, y, 0.16, 1.80, fill="000000", alpha=0.45)
        rect(s, fx - 0.245, y + 0.05, 0.045, 1.70, fill=DIM, alpha=0.5)
        rect(s, fx, y, fw - 0.28, 1.80, fill=CARD, line=LINE, lw=0.75, radius=0.05)
        simple(s, fx + 0.20, y + 0.14, 1.4, 0.2, no, 7.5, AMBER, True, spc=1.2)
        simple(s, fx + fw - 0.76, y + 0.14, 0.5, 0.2, dur, 7.5, DIM,
               align=PP_ALIGN.RIGHT, mono=True)
        simple(s, fx + 0.20, y + 0.36, fw - 0.70, 0.22, meta, 8.6, TEXT, True)
        tf = textbox(s, fx + 0.20, y + 0.62, fw - 0.72, 0.5)
        p = para(tf, True, line=1.35)
        run(p, desc, 8.2, BODY)
        tf2 = textbox(s, fx + 0.20, y + 1.14, fw - 0.72, 0.5)
        p2 = para(tf2, True, line=1.3)
        run(p2, prompt, 7.4, DIM)
        rect(s, fx + 0.20, y + 1.64, fw - 0.72, 0.03, fill=AMBER, alpha=0.55)

    simple(s, M, 0.62, 7.0, 0.26, "2026 AIGC 视频黑客松 · 路演", 10, AMBER, True, spc=1.6)
    rect(s, M, 0.98, 1.55, 0.008, fill=AMBER, alpha=0.8)

    tf = textbox(s, M, 1.30, 8.4, 1.15)
    p = para(tf, True, line=0.95)
    run(p, "ReCut ", 62, TEXT, True, "Segoe UI", EA, spc=-1.0)
    run(p, "Agent", 62, AMBER, True, "Segoe UI", EA, spc=-1.0)

    tf = textbox(s, M, 2.62, 8.2, 1.5)
    p = para(tf, True, line=1.28)
    run(p, "把一句创意，变成能直接开拍的", 25, TEXT, True)
    p2 = para(tf, False, line=1.28)
    run(p2, "镜头清单", 25, AMBER_SOFT, True)
    run(p2, "。", 25, TEXT, True)

    tf = textbox(s, M, 4.20, 7.9, 1.0)
    p = para(tf, True, line=1.55)
    run(p, "从 1 条梗概到 N 镜分镜提示词包，直接投喂 ", 12, BODY)
    run(p, "即梦 / 可灵 / Runway", 12, TEXT, True)
    run(p, "，", 12, BODY)
    p2 = para(tf, False, line=1.55)
    run(p2, "再导出剪映草稿。", 12, BODY)

    chip(s, M, 5.42, 1.95, 0.38, "三段式 Agent 管线", CARD2, BODY, 9.5, False, LINE)
    chip(s, M + 2.05, 5.42, 1.95, 0.38, "6 平台提示词适配", CARD2, BODY, 9.5, False, LINE)
    chip(s, M + 4.10, 5.42, 1.62, 0.38, "剪映草稿导出", CARD2, BODY, 9.5, False, LINE)

    rect(s, M, 6.20, CW, 0.008, fill="FFFFFF", alpha=0.07)
    simple(s, M, 6.38, 7.5, 0.26, "独立开发 · 全栈闭环 · 已容器化，可在免费 CPU 空间运行", 9.5, DIM)
    simple(s, W - M - 2.6, 6.38, 2.6, 0.26, "2026.11  ·  v1.0", 9.5, DIM,
           align=PP_ALIGN.RIGHT, spc=0.6)

    s.notes_slide.notes_text_frame.text = (
        "开场 20 秒：大家好，我是 ReCut Agent 的作者。\n"
        "我们做的事情一句话就能说完：把一句创意，变成能直接开拍的镜头清单。\n"
        "右边这 3 张卡片就是产品的输出物——不是一段话，而是带景别、运镜、时长、中英双语提示词的镜头。"
    )
    return s


# ---------------------------------------------------------------- 第 2 页 问题
def slide_problem(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s)
    head(s, "01 / THE GAP", "AI 会拍画面，但没人告诉它「怎么拍」", 2)

    cards = [
        ("01", "直出 = 失控",
         "一句话生成 5 秒很爽；到 60 秒长片，节奏、景别、机位全凭运气。",
         "一处不满意，整段重来，返工成本随镜头数线性上涨。",
         "返工成本 × N"),
        ("02", "分镜表 = 不懂模型",
         "Excel 里写着「缓慢推近、气氛压抑」，模型读不懂这种描述。",
         "人还得逐条翻译成 prompt，专业经验卡在格式转换里。",
         "手工翻译 2 遍"),
        ("03", "多平台 = 重复劳动",
         "即梦吃中文自然语言，Runway 吃结构化英文，同一镜头写两套。",
         "换平台就要重写全部提示词，素材资产无法复用。",
         "6 平台 = 6 套文案"),
    ]
    cw, gap = 3.55, 0.49
    for i, (no, title, l1, l2, stat) in enumerate(cards):
        x = M + i * (cw + gap)
        rect(s, x, 1.82, cw, 3.62, fill=CARD, line=LINE, radius=0.045)
        simple(s, x + 0.34, 2.10, 0.9, 0.44, no, 22, AMBER, True, latin="Segoe UI",
               spc=-0.5, line=1.0)
        rect(s, x + 0.34, 2.62, 0.62, 0.035, fill=AMBER, alpha=0.7)
        simple(s, x + 0.34, 2.82, cw - 0.68, 0.36, title, 16.5, TEXT, True, line=1.05)
        tf = textbox(s, x + 0.34, 3.32, cw - 0.68, 1.55)
        p = para(tf, True, line=1.45)
        run(p, l1, 11, BODY)
        p2 = para(tf, False, line=1.45, space_before=8)
        run(p2, l2, 11, MUTED)
        simple(s, x + 0.34, 4.86, cw - 0.68, 0.26, stat, 9.5, AMBER_SOFT, True, spc=0.6)

    rect(s, M, 5.72, CW, 0.92, fill=AMBER, alpha=0.10, line=AMBER, lw=0.75,
         radius=0.06, line_alpha=0.35)
    simple(s, M + 0.34, 5.90, 10.4, 0.3,
           "真正稀缺的不是生成能力，而是「从想法到可执行镜头」的中间层。", 14.5, TEXT, True)
    simple(s, M + 0.34, 6.22, 10.4, 0.26,
           "这一段今天靠人肉完成：写分镜表 → 翻译成 prompt → 逐平台粘贴。", 10, MUTED)

    s.notes_slide.notes_text_frame.text = (
        "先讲问题。AI 视频模型已经很强，但创作者卡在两头之间：\n"
        "一头是一句想法，一头是可执行的镜头清单；这个中间层今天靠人肉填。\n"
        "直出不可控、Excel 模型读不懂、多平台要重写。我们做的正是这一段。"
    )
    return s


# ---------------------------------------------------------------- 第 3 页 洞察
def slide_insight(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s)
    head(s, "02 / INSIGHT", "分镜不是文档，是可校验的中间表示", 3)

    lx, lw = M, 5.30
    rect(s, lx, 1.80, lw, 4.32, fill=CARD, line=LINE, radius=0.04)
    simple(s, lx + 0.32, 2.02, lw - 0.64, 0.24, "A · 一句话直出", 9.5, DIM, True, spc=1.2)
    rect(s, lx + 0.32, 2.36, lw - 0.90, 1.36, fill=CARD2, line=LINE, radius=0.08)
    tf = textbox(s, lx + 0.52, 2.50, lw - 1.30, 1.10)
    p = para(tf, True, line=1.45)
    run(p, "「一个保洁员在公司年会上被认出是前任董事长，电影感，暖光，"
           "镜头缓慢推近，情绪克制，要有反转……」", 10.5, BODY)

    rows = [
        "没有镜头边界，长片节奏不可控",
        "改一处 = 整段重新生成",
        "换平台要重写一遍，资产不可复用",
    ]
    for i, text in enumerate(rows):
        y = 3.98 + i * 0.56
        simple(s, lx + 0.34, y, 0.24, 0.28, "×", 12, RED, True)
        simple(s, lx + 0.64, y, lw - 1.0, 0.3, text, 10.5, MUTED)

    rx, rw = 6.42, 6.06
    rect(s, rx, 1.80, rw, 4.32, fill="101722", line="3A465C", lw=0.9, radius=0.04)
    simple(s, rx + 0.32, 2.02, rw - 0.64, 0.24,
           "B · 结构化分镜（ReCut 的输出）", 9.5, AMBER, True, spc=1.2)

    json_lines = [
        '{',
        '  "index": 2,',
        '  "duration": 3.5,',
        '  "shot_size": "中近景",',
        '  "camera_angle": "平视",',
        '  "camera_move": "推",',
        '  "action": "左手停在杯柄上，抬头看向画面右侧",',
        '  "anchors": ["黑色短发", "深色外套"],',
        '  "prompt_zh": "中近景，平视，镜头缓慢推近……",',
        '  "prompt_en": "Medium close-up, eye level, slow push-in…"',
        '}',
    ]
    tf = textbox(s, rx + 0.34, 2.38, rw - 0.66, 3.2)
    for i, raw in enumerate(json_lines):
        p = para(tf, i == 0, line=1.32)
        if '":' in raw and raw.strip().startswith('"'):
            idx = raw.index('":') + 2
            run(p, raw[:idx], 8.4, AMBER_SOFT, False, MONO, MONO)
            run(p, raw[idx:], 8.4, BODY, False, MONO, MONO)
        elif raw.strip() in ("{", "}"):
            run(p, raw, 8.4, DIM, False, MONO, MONO)
        elif raw.strip().startswith('"'):
            run(p, raw, 8.4, AMBER_SOFT, False, MONO, MONO)
        else:
            run(p, raw, 8.4, BODY, False, MONO, MONO)

    for i, label in enumerate(["可校验", "可重试", "跨平台复用"]):
        chip(s, rx + 0.32 + i * 1.42, 5.62, 1.30, 0.32, label, "16232C", TEAL, 9, True, TEAL)

    rect(s, M, 6.36, CW, 0.008, fill="FFFFFF", alpha=0.06)
    tf = textbox(s, M, 6.48, CW, 0.34)
    p = para(tf, True, line=1.2)
    run(p, "模型会越来越强，但「结构」不会自己出现。", 13, AMBER_SOFT, True)
    run(p, "  我们要做的，是把创意编译成模型能执行、人能编辑的那一层。", 11, MUTED)

    s.notes_slide.notes_text_frame.text = (
        "这是核心判断：分镜的价值不在「看起来专业」，而在于它是结构化的。\n"
        "有结构，就能校验、能局部重试、能换平台复用；没有结构，每次生成都是一次性消耗。\n"
        "所以 ReCut 的定位是「中间表示」，不是又一个对话框。"
    )
    return s


# ---------------------------------------------------------------- 第 4 页 产品
def slide_product(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s)
    head(s, "03 / PRODUCT", "ReCut Agent：把创意编译成镜头", 4,
         subtitle="输入一句创意，输出一份可编辑、可校验、可投喂的分镜包。")

    steps = [
        ("01", "写创意", "20–500 字梗概；选二创风格；勾选项目角色，锚点自动派生。", "输入 1 条梗概"),
        ("02", "出计划", "几镜、每镜几秒、景别 / 机位 / 运镜 / 叙事功能，全部可改。", "10 秒拿到骨架"),
        ("03", "展开", "确认后逐镜并发（3 路）生成中英双语提示词，失败只重试那一镜。", "N 张镜头卡"),
        ("04", "导出", "Markdown / CSV 直接下载；剪映草稿打包，含占位首帧与文字轨。", "进剪辑台"),
    ]
    cw, gap = 2.55, 0.47
    for i, (no, title, body, out) in enumerate(steps):
        x = M + i * (cw + gap)
        rect(s, x, 2.10, cw, 2.86, fill=CARD, line=LINE, radius=0.05)
        simple(s, x + 0.28, 2.30, 1.0, 0.32, no, 15, AMBER, True, latin="Segoe UI",
               spc=-0.3, line=1.0)
        simple(s, x + 0.28, 2.68, cw - 0.56, 0.34, title, 16, TEXT, True, line=1.05)
        tf = textbox(s, x + 0.28, 3.12, cw - 0.56, 1.35)
        p = para(tf, True, line=1.5)
        run(p, body, 10.2, BODY)
        simple(s, x + 0.28, 4.56, cw - 0.56, 0.24, out, 8.8, DIM, spc=0.4)
        if i < 3:
            arrow(s, x + cw + 0.09, 3.36, 0.28, 0.28)

    rect(s, M, 5.26, 8.6, 0.86, fill=CARD2, line=LINE, radius=0.05)
    tf = textbox(s, M + 0.30, 5.40, 8.0, 0.6)
    p = para(tf, True, line=1.35)
    run(p, "每一镜 = 一张卡片：", 10.5, TEXT, True)
    run(p, "提示词是主体，可复制、可微调、可重排；卡片之间靠角色锚点保持一致。", 10.5, BODY)

    rect(s, 9.62, 5.26, 2.86, 0.86, fill=AMBER, alpha=0.12, line=AMBER, lw=0.75,
         radius=0.05, line_alpha=0.4)
    tf = textbox(s, 9.80, 5.34, 2.5, 0.72, MSO_ANCHOR.MIDDLE)
    p = para(tf, True, line=1.3)
    run(p, "15 秒 / 3 镜\n", 13, AMBER_SOFT, True)
    run(p, "约 1 分钟出完整分镜", 9.5, MUTED)

    s.notes_slide.notes_text_frame.text = (
        "产品只有四步：写创意、出计划、展开、导出。\n"
        "关键设计是第 2 步和第 3 步分开：先用很少的 token 把「镜头结构」定下来，人改满意了再展开提示词。\n"
        "这让创作过程可迭代、成本可控。"
    )
    return s


# ---------------------------------------------------------------- 第 5 页 引擎
def slide_engine(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s)
    head(s, "04 / ENGINE", "三段式 Agent：编剧 → 导演 → 适配", 5,
         subtitle="每一段只做一件事，只输出严格 JSON；失败带错误回灌重试。")

    cols = [
        ("A", "编剧 Screenwriter", "把梗概拆成节拍",
         ["输入：梗概 / 风格 / 目标时长",
          "输出：title、logline、3 段 beats、角色锚点",
          "锚点拆成 immutable（发型、瞳色、服装）与 mutable（表情、姿态）"],
         "不确定的设定写「待核实」，不编造"),
        ("B", "导演 Director", "把节拍排成镜头",
         ["8 景别 × 6 机位 × 9 运镜 的封闭枚举",
          "动作必须写身体部位、方向、幅度、节奏",
          "first_frame 只写静态起点，video 只写镜头内运动"],
         "Pydantic 校验，失败回灌错误重试 2 次"),
        ("C", "适配 Adapter", "把镜头改成平台语言",
         ["可灵：中文自然语言，动作运镜清楚",
          "Runway / Sora：英文，动词优先、简洁",
          "Midjourney：英文逗号标签，只适合首帧"],
         "6 平台语法隔离，禁止混用"),
    ]
    cw, gap = 3.55, 0.49
    for i, (tag, name, sub, bullets, contract) in enumerate(cols):
        x = M + i * (cw + gap)
        rect(s, x, 1.90, cw, 3.96, fill=CARD, line=LINE, radius=0.045)
        chip(s, x + 0.30, 2.10, 0.40, 0.30, tag, AMBER, BG_TOP, 10, True)
        simple(s, x + 0.82, 2.11, cw - 1.05, 0.28, name, 13, TEXT, True)
        simple(s, x + 0.30, 2.48, cw - 0.6, 0.24, sub, 9.5, MUTED)
        tf = textbox(s, x + 0.30, 2.90, cw - 0.56, 1.85)
        for j, b in enumerate(bullets):
            p = para(tf, j == 0, line=1.42, space_after=7)
            run(p, "· ", 10, AMBER)
            run(p, b, 9.8, BODY)
        rect(s, x + 0.30, 4.92, cw - 0.60, 0.008, fill="FFFFFF", alpha=0.08)
        simple(s, x + 0.30, 5.02, 0.62, 0.2, "契约", 8, DIM, spc=1.0)
        simple(s, x + 0.30, 5.20, cw - 0.56, 0.5, contract, 9, AMBER_SOFT, line=1.3)
        if i < 2:
            arrow(s, x + cw + 0.10, 3.66, 0.28, 0.28)

    tf = textbox(s, M, 6.06, CW, 0.66)
    p = para(tf, True, line=1.3)
    run(p, "契约先行：", 12, AMBER_SOFT, True)
    run(p, "三段都是「严格 JSON in / 严格 JSON out」，所以 Agent 可被单测、可换模型、可单独复用。", 11, TEXT)
    p2 = para(tf, False, line=1.5)
    run(p2, "forward_agent 是一个不依赖 FastAPI / Vue / 数据库的纯 Python 包，别人可以直接 copy 走。", 9.8, MUTED)

    s.notes_slide.notes_text_frame.text = (
        "技术上我们不是一个大 prompt，而是三段职责清晰的 Agent。\n"
        "编剧负责叙事，导演负责视听语言（枚举约束在这里），适配负责平台方言。\n"
        "每段都输出严格 JSON，用 Pydantic 校验；校验失败把报错回灌给模型重试，最多两次。"
    )
    return s


# ---------------------------------------------------------------- 第 6 页 演示
def slide_demo(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s)
    head(s, "05 / DEMO", "一条梗概，15 秒，三个镜头", 6)

    wx, wy, ww, wh = M, 1.64, 8.75, 4.86
    rect(s, wx, wy, ww, wh, fill="0D1119", line="39455A", lw=0.9, radius=0.02)
    rect(s, wx, wy, ww, 0.32, fill="111722", line=None)
    for i, col in enumerate(["E06C5E", "E0B341", "57C08A"]):
        dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(wx + 0.16 + i * 0.17),
                                 Inches(wy + 0.115), Inches(0.09), Inches(0.09))
        dot.shadow.inherit = False
        dot.line.fill.background()
        dot.fill.solid()
        dot.fill.fore_color.rgb = C(col)
    simple(s, wx + 0.82, wy + 0.055, 4.6, 0.22, "recut.local / workspace", 8, DIM)
    simple(s, wx + ww - 1.5, wy + 0.055, 1.3, 0.22, "已保存 · 刚刚", 8, TEAL, align=PP_ALIGN.RIGHT)

    lx, lw = wx + 0.20, 2.02
    simple(s, lx, wy + 0.48, lw, 0.2, "剧情梗概", 7.8, DIM, True, spc=0.8)
    rect(s, lx, wy + 0.72, lw, 0.96, fill=CARD, line=LINE, radius=0.06)
    tf = textbox(s, lx + 0.12, wy + 0.82, lw - 0.24, 0.78)
    p = para(tf, True, line=1.4)
    run(p, "公司年会上，一个普通保洁员被同事认出是前任董事长。", 8.2, BODY)

    simple(s, lx, wy + 1.82, lw, 0.2, "二创风格", 7.8, DIM, True, spc=0.8)
    chip(s, lx, wy + 2.06, 0.92, 0.26, "搞笑反转", AMBER, BG_TOP, 7.6, True)
    chip(s, lx + 1.00, wy + 2.06, 0.84, 0.26, "燃向踩点", CARD2, MUTED, 7.6, False, LINE)

    simple(s, lx, wy + 2.46, lw, 0.2, "角色锚点（由资产派生）", 7.8, DIM, True, spc=0.8)
    for i, (name, hit, ok) in enumerate([("保洁员", "3/3", True), ("年会主持", "1/3", False)]):
        y = wy + 2.70 + i * 0.42
        rect(s, lx, y, lw, 0.34, fill=CARD, line=LINE, radius=0.1)
        simple(s, lx + 0.10, y + 0.07, 0.8, 0.2, name, 7.6, TEXT)
        simple(s, lx + lw - 0.52, y + 0.07, 0.42, 0.2, hit, 7.6, TEAL if ok else AMBER,
               align=PP_ALIGN.RIGHT, mono=True)
        rect(s, lx, y + 0.34, lw, 0.02, fill=TEAL if ok else AMBER, alpha=0.75)

    rect(s, lx, wy + 3.66, lw, 0.40, fill=AMBER, radius=0.12)
    tf = textbox(s, lx, wy + 3.66, lw, 0.40, MSO_ANCHOR.MIDDLE)
    p = para(tf, True, PP_ALIGN.CENTER, line=1.0)
    run(p, "生成镜头计划  →", 8.4, BG_TOP, True)

    mx, mw = wx + 2.38, 3.55
    rect(s, mx - 0.10, wy + 0.42, mw, wh - 0.58, fill="0F141D", line=LINE, lw=0.6, radius=0.03)
    simple(s, mx, wy + 0.52, mw, 0.2, "镜头计划", 8.2, TEXT, True)
    simple(s, mx + 1.05, wy + 0.53, 1.6, 0.2, "3 镜 · 10.5 秒", 7.4, DIM)
    for i, h in enumerate(["镜", "景别", "运镜", "时长"]):
        simple(s, mx + [0, 0.30, 1.00, 1.90][i], wy + 0.80, 0.75, 0.18, h, 6.8, DIM, spc=0.6)

    rows = [
        ("01", "全景", "固定", "3.5s", "年会上，保洁员推车穿过人群"),
        ("02", "中近景", "推", "3.5s", "主持人念出名字，他停下手"),
        ("03", "特写", "固定", "3.5s", "眼神短暂睁大后恢复平静"),
    ]
    for i, (no, size, move, dur, purpose) in enumerate(rows):
        y = wy + 1.00 + i * 0.78
        rect(s, mx, y, mw - 0.14, 0.68, fill=CARD, line=LINE, lw=0.6, radius=0.06)
        simple(s, mx + 0.08, y + 0.09, 0.3, 0.2, no, 7.2, AMBER, True, mono=True)
        simple(s, mx + 0.38, y + 0.08, 0.68, 0.22, size, 7.6, TEXT, True)
        simple(s, mx + 1.08, y + 0.09, 0.7, 0.22, move, 7.4, BODY)
        simple(s, mx + 1.98, y + 0.09, 0.45, 0.22, dur, 7.4, BODY, mono=True)
        simple(s, mx + 0.38, y + 0.36, mw - 0.60, 0.22, purpose, 7.0, MUTED)

    rect(s, mx, wy + 3.48, mw - 0.14, 0.36, fill=CARD3, line=AMBER, lw=0.6,
         line_alpha=0.5, radius=0.12)
    tf = textbox(s, mx, wy + 3.48, mw - 0.14, 0.36, MSO_ANCHOR.MIDDLE)
    p = para(tf, True, PP_ALIGN.CENTER, line=1.0)
    run(p, "确认并展开提示词", 8.0, AMBER_SOFT, True)

    rx2, rw2 = wx + 6.10, 2.42
    simple(s, rx2, wy + 0.48, rw2, 0.2, "故事板", 8.2, TEXT, True)
    simple(s, rx2 + 0.62, wy + 0.49, 1.4, 0.2, "中英双语", 7.4, DIM)
    for i, (badge, prompt, en) in enumerate([
        ("01 全景", "全景，平视，固定机位，暖色顶光，年会现场人群虚化", "Wide shot, eye level, locked-off…"),
        ("02 中近景", "中近景，平视，镜头缓慢推近，人物停下手部动作", "Medium close-up, slow push-in…"),
    ]):
        y = wy + 0.70 + i * 1.95
        rect(s, rx2, y, rw2, 1.78, fill=CARD, line=LINE, lw=0.6, radius=0.05)
        simple(s, rx2 + 0.12, y + 0.10, 1.0, 0.2, badge, 7.2, AMBER, True, spc=0.4)
        tf = textbox(s, rx2 + 0.12, y + 0.36, rw2 - 0.24, 0.72)
        p = para(tf, True, line=1.4)
        run(p, prompt, 7.4, BODY)
        tf2 = textbox(s, rx2 + 0.12, y + 1.10, rw2 - 0.24, 0.44)
        p2 = para(tf2, True, line=1.35)
        run(p2, en, 6.8, DIM)
        simple(s, rx2 + 0.12, y + 1.56, rw2 - 0.24, 0.2, "复制 · 微调 · 展开", 6.8, DIM)

    notes = [
        ("1", 1.14, 5.31),
        ("2", 6.16, 2.02),
        ("3", 3.20, 5.10),
        ("4", 8.96, 2.06),
    ]
    for no, x, y in notes:
        c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(0.26), Inches(0.26))
        c.shadow.inherit = False
        c.line.color.rgb = C(AMBER)
        c.line.width = Pt(1.4)
        c.fill.solid()
        c.fill.fore_color.rgb = C("10151F")
        tf = c.text_frame
        tf.margin_left = 0
        tf.margin_right = 0
        tf.margin_top = 0
        tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run(p, no, 8, AMBER_SOFT, True, "Segoe UI")

    ex, ew = 9.72, 2.76
    items = [
        ("1", "输入只有三样", "梗概、风格、角色；锚点从角色资产自动派生。"),
        ("2", "先给结构，不给文案", "计划阶段可以改时长、删镜、加镜，不消耗提示词。"),
        ("3", "确认后才展开", "逐镜并发 3 路，失败的镜头单独重试。"),
        ("4", "每镜一张卡", "中英双语提示词，复制进即梦 / 可灵 / Runway。"),
    ]
    for i, (no, title, body) in enumerate(items):
        y = 1.68 + i * 1.22
        simple(s, ex, y, 0.3, 0.24, no, 9, AMBER, True, latin="Segoe UI")
        simple(s, ex + 0.26, y - 0.02, ew - 0.26, 0.26, title, 11, TEXT, True)
        tf = textbox(s, ex + 0.26, y + 0.28, ew - 0.26, 0.72)
        p = para(tf, True, line=1.45)
        run(p, body, 9.2, MUTED)

    s.notes_slide.notes_text_frame.text = (
        "这是工作台的实际布局：左边创作，中间计划，右边故事板。\n"
        "演示时讲这条 15 秒的梗概：3 个镜头，从全景到特写，1 分钟左右拿到完整分镜。\n"
        "重点强调第 3 步——计划确认之前，一分提示词 token 都没花。"
    )
    return s


# ---------------------------------------------------------------- 第 7 页 成本
def slide_cost(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s)
    head(s, "06 / COST CONTROL", "先结构，后提示词：把 token 花在刀刃上", 7)

    lx, lw = M, 7.10
    rect(s, lx, 1.80, lw, 2.10, fill=CARD, line=LINE, radius=0.04)
    simple(s, lx + 0.30, 1.98, 4.6, 0.24, "×  一次性生成全部分镜", 11, RED, True)
    tf = textbox(s, lx + 0.30, 2.32, lw - 0.60, 1.4)
    for i, t in enumerate(["N 镜 × 长提示词 一次烧完，计划阶段也在写文案",
                           "改一个镜头，全部重新生成，之前的花费作废",
                           "失败没有边界，只能整段重跑"]):
        p = para(tf, i == 0, line=1.5, space_after=6)
        run(p, "·  ", 10, RED)
        run(p, t, 10, MUTED)

    rect(s, lx, 4.02, lw, 2.32, fill="131B26", line=AMBER, lw=0.9, radius=0.04,
         line_alpha=0.45)
    simple(s, lx + 0.30, 4.20, 5.6, 0.24, "√  先出计划，再展开提示词", 11, AMBER_SOFT, True)
    tf = textbox(s, lx + 0.30, 4.56, lw - 0.60, 1.7)
    for i, t in enumerate(["计划阶段只产出结构（十几行 JSON），不写提示词",
                           "人改满意后，才并发 3 路逐镜展开",
                           "单镜失败只重试那一镜，已完成的镜头不重复请求",
                           "计划随项目保存，关掉浏览器再回来可以继续"]):
        p = para(tf, i == 0, line=1.45, space_after=5)
        run(p, "·  ", 10, AMBER)
        run(p, t, 10, BODY)

    mx, mw = 8.32, 4.16
    metrics = [
        ("0", "计划阶段的提示词消耗"),
        ("3", "并发展开的并发上限"),
        ("1 镜", "失败重试的最小粒度"),
        ("8 字段", "每镜可编排的维度"),
    ]
    for i, (num, label) in enumerate(metrics):
        col, row = i % 2, i // 2
        x = mx + col * (mw / 2 + 0.10)
        y = 1.80 + row * 1.62
        rect(s, x, y, mw / 2 - 0.10, 1.46, fill=CARD, line=LINE, radius=0.05)
        simple(s, x + 0.24, y + 0.24, mw / 2 - 0.5, 0.5, num, 23, AMBER, True,
               latin="Segoe UI", spc=-0.8)
        tf = textbox(s, x + 0.24, y + 0.84, mw / 2 - 0.46, 0.5)
        p = para(tf, True, line=1.25)
        run(p, label, 8.8, MUTED)

    simple(s, mx, 5.22, mw, 0.7, "两阶段不是为了省钱，\n是为了让「改」这件事变便宜。",
           9.5, DIM, line=1.6)

    s.notes_slide.notes_text_frame.text = (
        "成本是我们特意设计的。一次性生成看起来很爽，但每次修改都要重跑全部。\n"
        "我们把它拆成两段：结构阶段几乎不花钱，人随便改；满意了再展开提示词并发生成。\n"
        "加上单镜重试，返工成本从 N 镜降到 1 镜。"
    )
    return s


# ---------------------------------------------------------------- 第 8 页 一致性
def slide_consistency(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s)
    head(s, "07 / CONSISTENCY", "角色一致性，靠度量和补齐", 8,
         subtitle="锚点由角色资产派生，逐镜统计命中，缺了就提示，绝不静默改写。")

    lx, lw = M, 6.10
    rect(s, lx, 1.90, lw, 3.88, fill=CARD, line=LINE, radius=0.04)
    simple(s, lx + 0.30, 2.08, lw - 0.6, 0.24, "锚点是怎么来的", 9, DIM, True, spc=1.0)

    rect(s, lx + 0.30, 2.42, 1.62, 0.62, fill=CARD2, line=LINE, radius=0.08)
    simple(s, lx + 0.30, 2.54, 1.62, 0.22, "角色资产库", 9.2, TEXT, True, align=PP_ALIGN.CENTER)
    simple(s, lx + 0.30, 2.78, 1.62, 0.2, "保洁员 · 深色外套", 7.4, DIM, align=PP_ALIGN.CENTER)
    arrow(s, lx + 2.00, 2.60, 0.26, 0.26)
    rect(s, lx + 2.34, 2.42, 1.62, 0.62, fill=CARD2, line=LINE, radius=0.08)
    simple(s, lx + 2.34, 2.54, 1.62, 0.22, "prompt_anchor", 8.6, AMBER_SOFT, True,
           align=PP_ALIGN.CENTER, mono=True)
    simple(s, lx + 2.34, 2.78, 1.62, 0.2, "项目级自动注入", 7.4, DIM, align=PP_ALIGN.CENTER)
    arrow(s, lx + 4.04, 2.60, 0.26, 0.26)
    rect(s, lx + 4.38, 2.42, 1.42, 0.62, fill=CARD2, line=LINE, radius=0.08)
    simple(s, lx + 4.38, 2.54, 1.42, 0.22, "每一镜", 9.2, TEXT, True, align=PP_ALIGN.CENTER)
    simple(s, lx + 4.38, 2.78, 1.42, 0.2, "生成 / 展开 / 微调", 7.4, DIM, align=PP_ALIGN.CENTER)

    simple(s, lx + 0.30, 3.24, 2.6, 0.22, "immutable · 不许变", 8.6, TEAL, True, spc=0.8)
    for i, t in enumerate(["黑色短发", "深色外套", "左眉旧疤"]):
        chip(s, lx + 0.30 + i * 1.18, 3.50, 1.08, 0.30, t, "16232C", TEAL, 8.6, False, TEAL)

    simple(s, lx + 0.30, 3.96, 2.8, 0.22, "mutable · 每镜可调", 8.6, AMBER_SOFT, True, spc=0.8)
    for i, t in enumerate(["表情幅度", "手持道具", "姿态"]):
        chip(s, lx + 0.30 + i * 1.18, 4.22, 1.08, 0.30, t, CARD2, AMBER_SOFT, 8.6, False, AMBER)

    tf = textbox(s, lx + 0.30, 4.74, lw - 0.60, 0.9)
    p = para(tf, True, line=1.5)
    run(p, "旧项目里的自由锚点会迁移成「项目补充词」，注入行为保持不变——升级不打断已有创作。", 9, MUTED)

    rx, rw = 7.22, 5.26
    rect(s, rx, 1.90, rw, 3.88, fill="101722", line="3A465C", lw=0.9, radius=0.04)
    simple(s, rx + 0.30, 2.08, rw - 0.6, 0.24, "命中统计 · 一眼看出哪镜掉了", 9, AMBER, True, spc=1.0)

    stats = [("保洁员", "3 / 3", 1.0, TEAL, "全部命中"),
             ("年会主持", "1 / 3", 0.33, AMBER, "2 镜缺失")]
    for i, (name, val, ratio, color, note) in enumerate(stats):
        y = 2.48 + i * 0.86
        simple(s, rx + 0.30, y, 1.5, 0.24, name, 9.6, TEXT, True)
        simple(s, rx + rw - 1.34, y, 1.0, 0.24, val, 9.6, color, True,
               align=PP_ALIGN.RIGHT, mono=True)
        rect(s, rx + 0.30, y + 0.34, rw - 0.60, 0.10, fill=CARD3, radius=0.5)
        rect(s, rx + 0.30, y + 0.34, max(0.12, (rw - 0.60) * ratio), 0.10, fill=color, radius=0.5)
        simple(s, rx + 0.30, y + 0.50, rw - 0.60, 0.2, note, 8, DIM)

    rect(s, rx + 0.30, 4.26, 2.10, 0.40, fill=AMBER, radius=0.12)
    tf = textbox(s, rx + 0.30, 4.26, 2.10, 0.40, MSO_ANCHOR.MIDDLE)
    p = para(tf, True, PP_ALIGN.CENTER, line=1.0)
    run(p, "补齐 2 个锚点", 8.8, BG_TOP, True)

    tf = textbox(s, rx + 2.56, 4.26, rw - 2.86, 0.72)
    p = para(tf, True, line=1.4)
    run(p, "只提示，不改写", 8.8, TEXT, True)
    p2 = para(tf, False, line=1.4)
    run(p2, "用户点一下才注入", 8.4, DIM)

    tf = textbox(s, rx + 0.30, 4.96, rw - 0.60, 0.62)
    p = para(tf, True, line=1.45)
    run(p, "模型返回的 character_ids 一律丢弃，绑定关系只信前端——不让模型改用户数据。", 8.4, MUTED)

    tf = textbox(s, M, 6.02, CW, 0.6)
    p = para(tf, True, line=1.3)
    run(p, "一致性不是「写更长的提示词」，而是被度量、被补齐、被绑定。", 13, AMBER_SOFT, True)
    p2 = para(tf, False, line=1.4)
    run(p2, "这条链路已经跑通；下一步接角色参考图，把一致性从文字锚点升级到图像评分。", 9.6, MUTED)

    s.notes_slide.notes_text_frame.text = (
        "一致性是二创和短剧最痛的点。我们的做法不是靠模型记住，而是工程化：\n"
        "锚点从角色资产派生，分成不能变和可以变的；每镜生成后统计命中率，缺了标黄，用户点一下补齐。\n"
        "而且我们绝不静默改写用户的提示词，也不信模型返回的绑定。"
    )
    return s


# ---------------------------------------------------------------- 第 9 页 交付
def slide_delivery(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s)
    head(s, "08 / DELIVERY", "生成不是终点，交付才是", 9)

    simple(s, M, 1.66, 6.0, 0.24, "6 个平台的提示词方言", 9, DIM, True, spc=1.0)
    platforms = [("可灵 Kling", "中文 · 动作清楚"), ("即梦 Jimeng", "中文 · 场景氛围"),
                 ("Runway", "英文 · 动词优先"), ("Sora", "英文 · 电影化"),
                 ("Seedance", "中英皆可"), ("Midjourney", "英文标签 · 首帧")]
    pw, pgap = 2.10, 0.075
    for i, (name, desc) in enumerate(platforms):
        col, row = i % 3, i // 3
        x = M + col * (pw + pgap)
        y = 1.94 + row * 0.68
        rect(s, x, y, pw, 0.60, fill=CARD, line=LINE, radius=0.08)
        simple(s, x + 0.16, y + 0.07, pw - 0.3, 0.22, name, 9.6, TEXT, True)
        simple(s, x + 0.16, y + 0.31, pw - 0.3, 0.22, desc, 7.6, DIM)

    simple(s, M, 3.44, 6.0, 0.24, "三种交付格式", 9, DIM, True, spc=1.0)
    exports = [
        ("Markdown", "镜头表 + 双语提示词，直接贴进文档或群聊。"),
        ("CSV", "进表格、进项目管理系统、进 Excel 排期。"),
        ("剪映草稿 zip", "draft_content.json + materials/ + 占位文字轨，附 md/csv 兜底。"),
    ]
    for i, (name, desc) in enumerate(exports):
        y = 3.72 + i * 0.76
        last = i == 2
        rect(s, M, y, 7.30, 0.66, fill="17202C" if last else CARD2,
             line=AMBER if last else LINE, lw=0.75, radius=0.06,
             line_alpha=0.4 if last else None)
        simple(s, M + 0.22, y + 0.10, 1.7, 0.24, name, 9.4,
               AMBER_SOFT if last else TEXT, True)
        simple(s, M + 1.92, y + 0.11, 4.10, 0.24, desc, 8.2, MUTED)
        if last:
            chip(s, M + 6.30, y + 0.18, 0.78, 0.30, "实验性", "2A2214", AMBER, 7.2, True, AMBER)

    rx, rw = 8.48, 4.00
    rect(s, rx, 1.66, rw, 4.40, fill="111A24", line="3A465C", lw=0.9, radius=0.04)
    simple(s, rx + 0.28, 1.86, rw - 0.5, 0.24, "反方向也成立", 9, TEAL, True, spc=1.0)
    tf = textbox(s, rx + 0.28, 2.18, rw - 0.56, 0.6)
    p = para(tf, True, line=1.35)
    run(p, "逆向解析：把参考片变成模板", 11.2, TEXT, True)

    steps = [("上传", "视频或图片"), ("抽帧", "均匀 6 帧，间隔自适应"),
             ("反推", "视觉模型读景别 / 运镜 / 情绪"), ("回填", "变成可编辑的镜头计划")]
    for i, (k, v) in enumerate(steps):
        y = 2.80 + i * 0.78
        rect(s, rx + 0.28, y, 0.52, 0.24, fill=CARD3, radius=0.2)
        tf2 = textbox(s, rx + 0.28, y, 0.52, 0.24, MSO_ANCHOR.MIDDLE)
        p2 = para(tf2, True, PP_ALIGN.CENTER, line=1.0)
        run(p2, str(i + 1), 7.6, AMBER, True)
        simple(s, rx + 0.92, y - 0.01, 0.9, 0.24, k, 9.2, TEXT, True)
        simple(s, rx + 1.52, y, rw - 1.80, 0.24, v, 8.2, MUTED)

    tf = textbox(s, rx + 0.28, 5.54, rw - 0.56, 0.5)
    p = para(tf, True, line=1.4)
    run(p, "拆别人的片子，比自己想镜头快得多。", 9.2, TEAL)

    tf = textbox(s, M, 6.34, CW, 0.4)
    p = para(tf, True, line=1.2)
    run(p, "不把最后一公里甩给用户：", 11.2, AMBER_SOFT, True)
    run(p, "从生成到剪辑台，中间那一步我们也做了。", 10.6, TEXT)

    s.notes_slide.notes_text_frame.text = (
        "生成完不是结束。我们做了 6 个平台的方言适配，和 3 种导出，包括剪映草稿。\n"
        "剪映草稿还是实验性的，格式没公开，所以我们同时附了 md 和 csv 兜底。\n"
        "另外反方向也能用：传一段参考片，反推出分镜，当作模板。"
    )
    return s


# ---------------------------------------------------------------- 第 10 页 架构
def slide_arch(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s)
    head(s, "09 / ARCHITECTURE", "一个人也能维护的架构", 10,
         subtitle="没有微服务、没有消息队列、没有 GPU —— 单容器同源，免费 CPU 就能跑。")

    layers = [
        ("前端", "Vue 3 + TS + Vite + Tailwind", "快照式撤销 50 步 · 8 套调色板 · 3 类场景层"),
        ("接口", "FastAPI", "HttpOnly 会话 · Origin 校验 · 乐观锁 409 · 上传 sha256 去重"),
        ("Agent", "forward_agent（纯 Python，不依赖框架）", "三段管线 · Pydantic 校验 · 缺 Key 可切确定性 Mock"),
        ("模型", "OpenAI 兼容接口", "当前配置魔搭 API-Inference（Qwen3.5-27B）；400 自动降级 + 括号配对"),
        ("存储", "SQLite WAL + 文件系统", "标准库 sqlite3，无 ORM；单文件可备份、可迁移"),
    ]
    for i, (tag, name, desc) in enumerate(layers):
        y = 1.86 + i * 0.86
        rect(s, M, y, 7.24, 0.74, fill=CARD, line=LINE, radius=0.06)
        rect(s, M, y + 0.10, 0.035, 0.54, fill=AMBER if i in (1, 2) else DIM, alpha=0.9)
        simple(s, M + 0.24, y + 0.24, 0.62, 0.24, tag, 8.4, DIM, True, spc=0.8)
        simple(s, M + 0.86, y + 0.10, 6.2, 0.26, name, 10.4, TEXT, True)
        simple(s, M + 0.86, y + 0.40, 6.2, 0.24, desc, 8.2, MUTED)

    rx, rw = 8.42, 4.06
    simple(s, rx, 1.76, rw, 0.24, "四个刻意的技术选择", 9, AMBER, True, spc=1.0)
    decisions = [
        ("会话 Cookie，不是 JWT", "服务端存 SHA-256，可即时吊销；登出就是真登出。"),
        ("绑定只信前端", "模型返回的 character_ids 全部丢弃，防止模型改写用户数据。"),
        ("撤销用快照", "编辑入口太多（输入 / 微调 / 展开 / 绑定），快照一次全覆盖。"),
        ("同源单容器", "node:20 构建 → python:3.12-slim 运行，7860 端口，cookie 不用跨站。"),
    ]
    for i, (title, body) in enumerate(decisions):
        y = 2.08 + i * 1.12
        simple(s, rx, y, rw, 0.24, title, 10, TEXT, True)
        tf = textbox(s, rx, y + 0.26, rw, 0.62)
        p = para(tf, True, line=1.4)
        run(p, body, 8.6, MUTED)

    rect(s, rx, 6.24, rw, 0.36, fill=AMBER, alpha=0.10, line=AMBER, lw=0.6,
         radius=0.1, line_alpha=0.3)
    simple(s, rx, 6.30, rw, 0.24, "71 项后端测试 · 已容器化部署", 8.6, AMBER_SOFT, True,
           align=PP_ALIGN.CENTER)

    s.notes_slide.notes_text_frame.text = (
        "架构刻意做得很朴素：单容器、同源、SQLite。\n"
        "因为是一个人维护，每多一个组件都是负债。\n"
        "右边四个选择都是被真实问题逼出来的：会话可吊销、模型不能改数据、撤销要覆盖所有入口。"
    )
    return s


# ---------------------------------------------------------------- 第 11 页 差异化
def slide_diff(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s)
    head(s, "10 / WHY US", "我们做「生成之前的那 5 分钟」", 11)

    cols = ["", "通用对话模型", "文生视频平台", "传统分镜表", "ReCut Agent"]
    rows = [
        ("结构化镜头数据", "弱（一段话）", "无（只出片）", "有（人写）", "强（JSON 契约）"),
        ("跨平台提示词", "每次重写", "锁定自家", "无", "6 平台一键适配"),
        ("角色一致性", "靠上下文记忆", "靠运气", "人工校对", "锚点 + 命中统计"),
        ("编辑与重试", "只能重新问", "整段重生成", "手改文档", "计划可改 · 单镜重试"),
        ("交付到剪辑", "复制粘贴", "下载 mp4", "复制粘贴", "MD / CSV / 剪映草稿"),
    ]
    widths = [2.55, 2.16, 2.16, 2.16, 2.60]
    x0, y0 = M, 1.82
    row_h = 0.82
    xs = [0]
    for w in widths[:-1]:
        xs.append(xs[-1] + w)

    rect(s, x0 + xs[4], y0 - 0.14, widths[4], row_h * 5 + 0.30,
         fill=AMBER, alpha=0.06, line=AMBER, lw=0.75, radius=0.03, line_alpha=0.35)

    for i in range(1, 5):
        simple(s, x0 + xs[i] + 0.06, y0 - 0.02, widths[i] - 0.12, 0.26, cols[i],
               9.2, AMBER if i == 4 else DIM, True, align=PP_ALIGN.CENTER, spc=0.5)

    for r, (label, a, b, c, d) in enumerate(rows):
        y = y0 + 0.34 + r * row_h
        if r % 2 == 0:
            rect(s, x0, y - 0.12, xs[4], row_h - 0.04, fill=CARD, alpha=0.55)
        if r:
            rect(s, x0, y - 0.12, xs[4], 0.008, fill="FFFFFF", alpha=0.05)
        simple(s, x0 + 0.14, y + 0.06, widths[0] - 0.2, 0.26, label, 9.4, TEXT, True)
        for i, val in enumerate([a, b, c]):
            simple(s, x0 + xs[i + 1] + 0.06, y + 0.06, widths[i + 1] - 0.12, 0.26,
                   val, 9, MUTED, align=PP_ALIGN.CENTER)
        simple(s, x0 + xs[4] + 0.06, y + 0.06, widths[4] - 0.12, 0.26,
               d, 9, AMBER_SOFT, True, align=PP_ALIGN.CENTER)

    tf = textbox(s, M, 6.34, CW, 0.42)
    p = para(tf, True, line=1.2)
    run(p, "别人在卷「生成得更真」，我们在补「拍得更可控」。", 12.5, AMBER_SOFT, True)
    run(p, "  这两件事不冲突，而且后者没人认真做。", 10.6, MUTED)

    s.notes_slide.notes_text_frame.text = (
        "这张表回答「凭什么不是别人」。\n"
        "对话模型没有结构，视频平台锁定自家，分镜表不懂模型。\n"
        "我们站在三者之间，做的是生成之前那五分钟的决策层。"
    )
    return s


# ---------------------------------------------------------------- 第 12 页 商业
def slide_business(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s)
    head(s, "11 / BUSINESS", "先服务「一个人做一部片」的创作者", 12)

    simple(s, M, 1.64, 9.0, 0.24, "用户：二创 UP 主、短剧试拍团队、广告 / 电商分镜", 9, DIM, True, spc=0.8)

    tiers = [
        ("免费", "¥0", ["3 个项目", "全部生成能力", "Markdown 导出"], CARD, LINE, MUTED),
        ("Pro", "¥39", ["不限项目", "剪映草稿导出", "逆向解析 + 6 平台适配"], "1B2330", AMBER, AMBER_SOFT),
        ("团队", "¥199", ["5 个席位", "共享角色与标签库", "项目版本历史"], CARD, LINE, MUTED),
    ]
    for i, (name, price, feats, fill, line, accent) in enumerate(tiers):
        x = M + i * 3.78
        y = 1.96
        rect(s, x, y, 3.50, 2.86, fill=fill, line=line, lw=0.9 if i == 1 else 0.7, radius=0.045)
        simple(s, x + 0.28, y + 0.22, 1.6, 0.26, name, 10.4, accent, True, spc=0.8)
        tf = textbox(s, x + 0.28, y + 0.52, 2.4, 0.5)
        p = para(tf, True, line=1.0)
        run(p, price, 26, TEXT, True, "Segoe UI", EA, spc=-0.8)
        run(p, " / 月", 9, DIM)
        rect(s, x + 0.28, y + 1.14, 2.94, 0.008, fill="FFFFFF", alpha=0.08)
        tf = textbox(s, x + 0.28, y + 1.28, 2.94, 1.4)
        for j, f in enumerate(feats):
            p = para(tf, j == 0, line=1.4, space_after=5)
            run(p, "· ", 9.4, accent)
            run(p, f, 9.4, BODY if i == 1 else MUTED)

    rect(s, M, 5.04, CW, 1.18, fill=CARD2, line=LINE, radius=0.05)
    simple(s, M + 0.28, 5.16, 4.0, 0.22, "单位经济（自测算 · 假设待验证）", 8.2, DIM, True, spc=0.8)
    calc = [("1 万 Pro 用户", "≈ 39 × 12 × 10,000 ≈ ¥468 万 / 年"),
            ("单条 15 秒分镜", "3 次模型调用 ≈ ¥0.02–0.05"),
            ("毛利率", "> 95%（模型成本按次计）")]
    for i, (k, v) in enumerate(calc):
        x = M + 0.28 + i * 3.78
        simple(s, x, 5.44, 3.5, 0.22, k, 8.4, MUTED)
        simple(s, x, 5.68, 3.6, 0.26, v, 9.8, TEXT, True)

    tf = textbox(s, M, 6.38, CW, 0.34)
    p = para(tf, True, line=1.2)
    run(p, "增长路径：", 9.4, AMBER_SOFT, True)
    run(p, "免费创空间 Demo → 导出作品带来源标记 → 社区风格包 / 角色包 → Pro 付费。", 9.4, MUTED)

    s.notes_slide.notes_text_frame.text = (
        "商业模式很直白：免费引流，Pro 订阅，团队版做协作。\n"
        "成本侧极轻——一条分镜只要三次模型调用，毛利很高。\n"
        "下面的数字是自测算，假设还需要真实数据验证，我们不假装它是市场规模报告。"
    )
    return s


# ---------------------------------------------------------------- 第 13 页 路线图
def slide_roadmap(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s)
    head(s, "12 / ROADMAP", "已完成，与接下来要做的", 13)

    y_axis = 2.20
    rect(s, M, y_axis, CW, 0.02, fill="3A465C")
    nodes = [("黑客松 · 现在", 0.08, AMBER), ("+1 个月", 0.50, "7C8AA0"), ("+3 个月", 0.88, "7C8AA0")]
    for label, ratio, color in nodes:
        x = M + CW * ratio
        dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x - 0.07), Inches(y_axis - 0.07),
                                 Inches(0.16), Inches(0.16))
        dot.shadow.inherit = False
        dot.line.fill.background()
        dot.fill.solid()
        dot.fill.fore_color.rgb = C(color)
        simple(s, x - 0.55, y_axis - 0.42, 1.5, 0.24, label, 9.2, color, True, spc=0.6)

    cols = [
        ("已交付", AMBER,
         ["三段式 Agent 管线（编剧 / 导演 / 适配）",
          "两阶段生成 + 单镜失败重试",
          "角色锚点派生与命中统计",
          "6 平台提示词适配",
          "剪映草稿 / MD / CSV 导出",
          "容器化 + 创空间部署",
          "71 项后端测试"]),
        ("P1 · 稳定性", "8C99AE",
         ["本地草稿兜底（localStorage）",
          "场景切分替代等距抽帧",
          "剪映真机导入验证",
          "计划中的「叙事功能」保留到展开后"]),
        ("P2 · 能力扩展", "8C99AE",
         ["角色参考图 + 图像一致性评分（SFace）",
          "梗概结构化输入与 AI 扩写",
          "项目版本历史与回滚",
          "PostgreSQL 迁移与团队协作"]),
    ]
    widths = [4.30, 3.45, 3.60]
    for i, (title, color, items) in enumerate(cols):
        x = M + sum(widths[:i]) + i * 0.28
        y = 2.66
        h = 3.62
        rect(s, x, y, widths[i], h, fill=CARD, line=LINE, radius=0.04)
        rect(s, x, y, widths[i], 0.045, fill=color, alpha=0.9)
        simple(s, x + 0.26, y + 0.22, widths[i] - 0.5, 0.26, title, 10.6, color, True, spc=0.6)
        tf = textbox(s, x + 0.26, y + 0.58, widths[i] - 0.48, h - 0.76)
        for j, it in enumerate(items):
            p = para(tf, j == 0, line=1.4, space_after=6)
            run(p, "· ", 9, color)
            run(p, it, 9, BODY if i == 0 else MUTED)

    tf = textbox(s, M, 6.48, CW, 0.3)
    p = para(tf, True, line=1.2)
    run(p, "黑客松期间的重点是「闭环可演示」：从一句梗概，到能导进剪映的草稿。", 9.4, DIM)

    s.notes_slide.notes_text_frame.text = (
        "左边是这次已交付的，全部可跑；中间和右边是接下来两个阶段。\n"
        "我们刻意把「可演示闭环」放在第一优先级，而不是堆功能。"
    )
    return s


# ---------------------------------------------------------------- 第 14 页 结尾
def slide_end(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s)

    simple(s, M, 0.72, 7.0, 0.26, "THANK YOU", 10, AMBER, True, spc=2.2)
    rect(s, M, 1.06, 1.55, 0.008, fill=AMBER, alpha=0.8)

    tf = textbox(s, M, 1.48, 9.4, 2.0)
    p = para(tf, True, line=1.24)
    run(p, "让每个有想法的人，", 36, TEXT, True)
    p2 = para(tf, False, line=1.24)
    run(p2, "都能拍出自己的镜头。", 36, AMBER_SOFT, True)

    tf = textbox(s, M, 3.64, 8.6, 0.9)
    p = para(tf, True, line=1.5)
    run(p, "ReCut Agent 不是一个更强的视频模型，", 12, BODY)
    p2 = para(tf, False, line=1.5)
    run(p2, "而是模型和创作者之间，那一层一直没人认真做的「镜头语言」。", 12, BODY)

    chip(s, M, 4.62, 1.66, 0.38, "三段式 Agent", CARD2, BODY, 9.2, False, LINE)
    chip(s, M + 1.76, 4.62, 1.50, 0.38, "两阶段生成", CARD2, BODY, 9.2, False, LINE)
    chip(s, M + 3.36, 4.62, 1.10, 0.38, "6 平台", CARD2, BODY, 9.2, False, LINE)
    chip(s, M + 4.56, 4.62, 1.32, 0.38, "剪映闭环", CARD2, BODY, 9.2, False, LINE)

    rect(s, M, 5.52, 8.4, 0.008, fill="FFFFFF", alpha=0.08)
    simple(s, M, 5.66, 1.2, 0.22, "仓库", 8.4, DIM, True, spc=1.0)
    simple(s, M, 5.90, 6.4, 0.26, "github.com/PhantomQAQ1/recut-agent", 10.4, TEXT, latin="Consolas")
    simple(s, M, 6.26, 1.4, 0.22, "在线 Demo", 8.4, DIM, True, spc=1.0)
    simple(s, M, 6.50, 7.0, 0.26, "魔搭创空间（Docker 空间 · 7860 端口）· 现场演示", 10, MUTED)

    qx, qy, qs = 10.44, 4.56, 1.72
    rect(s, qx, qy, qs, qs, fill="0F141D", line="3A465C", lw=0.9, radius=0.04)
    simple(s, qx, qy + qs / 2 - 0.30, qs, 0.26, "Demo 二维码", 8.4, DIM, align=PP_ALIGN.CENTER, spc=0.6)
    simple(s, qx, qy + qs / 2 - 0.02, qs, 0.26, "（占位）", 8.4, "3E495C", align=PP_ALIGN.CENTER)

    simple(s, W - M - 2.0, 6.96, 2.0, 0.24, "2026.11", 8.6, DIM, align=PP_ALIGN.RIGHT, spc=0.8)

    s.notes_slide.notes_text_frame.text = (
        "收尾：我们做的不是更强的模型，而是模型和创作者之间那层镜头语言。\n"
        "欢迎扫码试用，也欢迎直接看仓库。谢谢。"
    )
    return s


def main():
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    prs.core_properties.title = "ReCut Agent · 黑客松路演"
    prs.core_properties.author = "ReCut Agent"
    prs.core_properties.subject = "AIGC 视频分镜与提示词工作台"

    slide_cover(prs)
    slide_problem(prs)
    slide_insight(prs)
    slide_product(prs)
    slide_engine(prs)
    slide_demo(prs)
    slide_cost(prs)
    slide_consistency(prs)
    slide_delivery(prs)
    slide_arch(prs)
    slide_diff(prs)
    slide_business(prs)
    slide_roadmap(prs)
    slide_end(prs)

    out = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "ReCut-Agent-黑客松路演.pptx"))
    prs.save(out)
    print("saved", out, len(prs.slides), "slides")


if __name__ == "__main__":
    main()
