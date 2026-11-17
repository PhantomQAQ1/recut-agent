"""把 docs/PRD.md 转成排版好的 Word 文档。

用法（用 DSH 自带的 Python，它带有 python-docx）：
    python docs/build_prd_docx.py

只处理 PRD 里实际用到的 Markdown 子集：标题、表格、代码块、引用、列表、分隔线。
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "PRD.md"
TARGET = ROOT / "docs" / "ReCut-Agent-PRD-v1.0.docx"

LATIN = "Segoe UI"
CJK = "Microsoft YaHei"
MONO = "Consolas"
ACCENT = RGBColor(0xB4, 0x53, 0x09)
MUTED = RGBColor(0x6B, 0x72, 0x80)

# Word 里彩色 emoji 字体不稳定，统一换成能在中文字体里正常显示的字形
SYMBOLS = {
    "✅": "√",
    "⚠️": "▲",
    "⚠": "▲",
    "⬜": "□",
    "❌": "×",
    "⌘": "Cmd+",
}

TOKEN = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def set_font(run, *, latin: str = LATIN, cjk: str = CJK, size: float | None = None,
             bold: bool | None = None, color: RGBColor | None = None) -> None:
    run.font.name = latin
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    fonts.set(qn("w:ascii"), latin)
    fonts.set(qn("w:hAnsi"), latin)
    fonts.set(qn("w:eastAsia"), cjk)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color is not None:
        run.font.color.rgb = color


def add_inline(paragraph, text: str, *, size: float = 10.5, bold: bool = False) -> None:
    """把 **粗体** 和 `等宽` 渲染成对应样式的 run。"""
    for piece in TOKEN.split(text):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**"):
            run = paragraph.add_run(piece[2:-2])
            set_font(run, size=size, bold=True)
        elif piece.startswith("`") and piece.endswith("`"):
            run = paragraph.add_run(piece[1:-1])
            set_font(run, latin=MONO, cjk=CJK, size=size - 0.5, bold=bold, color=RGBColor(0x1F, 0x3A, 0x5F))
        else:
            run = paragraph.add_run(piece)
            set_font(run, size=size, bold=bold)


def shade(element_pr, color: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    element_pr.append(shd)


def cell_shade(cell, color: str) -> None:
    shade(cell._tc.get_or_add_tcPr(), color)


def table_borders(table, color: str = "D5DCE6") -> None:
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        borders.append(el)
    tbl_pr.append(borders)


def cell_margins(table, top: int = 50, left: int = 90) -> None:
    mar = OxmlElement("w:tblCellMar")
    for side, value in (("top", top), ("left", left), ("bottom", top), ("right", left)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(value))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    table._tbl.tblPr.append(mar)


def repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    tr_pr.append(header)


def paragraph_shading(paragraph, color: str) -> None:
    shade(paragraph._p.get_or_add_pPr(), color)


def split_row(line: str) -> list[str]:
    # 表格里可能出现转义的 \| （例如命令的多个子命令），先保护再切分
    text = line.strip().strip("|").replace("\\|", "\x00")
    return [cell.strip().replace("\x00", "|") for cell in text.split("|")]


def is_separator_row(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells if cell) and bool(cells)


def add_table(document, rows: list[list[str]]) -> None:
    # Markdown 的 |---|---| 分隔行不是数据，先剔掉
    rows = [row for row in rows if not is_separator_row(row)]
    if not rows:
        return
    columns = max(len(row) for row in rows)
    table = document.add_table(rows=len(rows), cols=columns)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    table_borders(table)
    cell_margins(table)
    for r_index, row in enumerate(rows):
        for c_index in range(columns):
            cell = table.cell(r_index, c_index)
            text = row[c_index] if c_index < len(row) else ""
            cell.text = ""
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_before = Pt(1)
            paragraph.paragraph_format.space_after = Pt(1)
            paragraph.paragraph_format.line_spacing = 1.15
            add_inline(paragraph, text, size=9, bold=(r_index == 0))
            if r_index == 0:
                cell_shade(cell, "F3F5F8")
    repeat_header(table.rows[0])
    document.add_paragraph().paragraph_format.space_after = Pt(2)


def add_code_block(document, lines: list[str]) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(8)
    paragraph.paragraph_format.left_indent = Cm(0.3)
    paragraph.paragraph_format.line_spacing = 1.1
    paragraph_shading(paragraph, "F6F8FA")
    for index, raw in enumerate(lines):
        run = paragraph.add_run(raw)
        set_font(run, latin=MONO, cjk=CJK, size=9, color=RGBColor(0x24, 0x29, 0x2E))
        if index < len(lines) - 1:
            run.add_break()


def build() -> Path:
    markdown = SOURCE.read_text(encoding="utf-8")
    for symbol, replacement in SYMBOLS.items():
        markdown = markdown.replace(symbol, replacement)

    document = Document()

    section = document.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(2.0)

    normal = document.styles["Normal"]
    normal.font.name = LATIN
    normal.font.size = Pt(10.5)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), CJK)
    normal.paragraph_format.line_spacing = 1.45
    normal.paragraph_format.space_after = Pt(4)

    # 页脚页码
    footer_paragraph = section.footer.paragraphs[0]
    footer_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer_paragraph.add_run("")
    set_font(run, size=8.5, color=MUTED)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer_paragraph._p.append(field)

    table_buffer: list[list[str]] = []
    code_buffer: list[str] = []
    in_code = False
    first_rule = True
    title_done = False

    def flush_table() -> None:
        nonlocal table_buffer
        if table_buffer:
            add_table(document, table_buffer)
            table_buffer = []

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()

        if line.startswith("```"):
            if in_code:
                add_code_block(document, code_buffer)
                code_buffer = []
                in_code = False
            else:
                flush_table()
                in_code = True
            continue
        if in_code:
            code_buffer.append(raw_line)
            continue

        if line.startswith("|"):
            table_buffer.append(split_row(line))
            continue
        if table_buffer and not line.startswith("|"):
            flush_table()

        if not line.strip():
            continue

        if line.startswith("# "):
            flush_table()
            paragraph = document.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.space_before = Pt(28)
            paragraph.paragraph_format.space_after = Pt(4)
            run = paragraph.add_run(line[2:].strip())
            set_font(run, size=22, bold=True, color=RGBColor(0x0F, 0x17, 0x2A))
            subtitle = document.add_paragraph()
            subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
            subtitle.paragraph_format.space_after = Pt(18)
            sub_run = subtitle.add_run("AIGC 分镜与提示词工作台 · 内部文档")
            set_font(sub_run, size=10, color=MUTED)
            title_done = True
            continue

        if line.startswith("### "):
            flush_table()
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.space_before = Pt(10)
            paragraph.paragraph_format.space_after = Pt(3)
            paragraph.paragraph_format.keep_with_next = True
            run = paragraph.add_run(line[4:].strip())
            set_font(run, size=11.5, bold=True, color=RGBColor(0x1F, 0x29, 0x37))
            continue

        if line.startswith("## "):
            flush_table()
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.space_before = Pt(16)
            paragraph.paragraph_format.space_after = Pt(6)
            paragraph.paragraph_format.keep_with_next = True
            run = paragraph.add_run(line[3:].strip())
            set_font(run, size=15, bold=True, color=RGBColor(0x0F, 0x17, 0x2A))
            # 章节标题下画一条细线
            p_pr = paragraph._p.get_or_add_pPr()
            borders = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single")
            bottom.set(qn("w:sz"), "6")
            bottom.set(qn("w:space"), "3")
            bottom.set(qn("w:color"), "E4B33C")
            borders.append(bottom)
            p_pr.append(borders)
            continue

        if re.fullmatch(r"-{3,}", line.strip()):
            flush_table()
            if first_rule and title_done:
                first_rule = False
                document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            continue

        if line.startswith("> "):
            flush_table()
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.left_indent = Cm(0.5)
            paragraph.paragraph_format.space_before = Pt(2)
            paragraph.paragraph_format.space_after = Pt(8)
            p_pr = paragraph._p.get_or_add_pPr()
            borders = OxmlElement("w:pBdr")
            left = OxmlElement("w:left")
            left.set(qn("w:val"), "single")
            left.set(qn("w:sz"), "18")
            left.set(qn("w:space"), "8")
            left.set(qn("w:color"), "E4B33C")
            borders.append(left)
            p_pr.append(borders)
            add_inline(paragraph, line[2:].strip(), size=11.5, bold=True)
            continue

        if line.startswith("- "):
            flush_table()
            paragraph = document.add_paragraph(style="List Bullet")
            paragraph.paragraph_format.space_after = Pt(2)
            paragraph.paragraph_format.line_spacing = 1.35
            add_inline(paragraph, line[2:].strip())
            continue

        match = re.match(r"^(\d+)\.\s+(.*)$", line)
        if match:
            flush_table()
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.left_indent = Cm(0.6)
            paragraph.paragraph_format.first_line_indent = Cm(-0.6)
            paragraph.paragraph_format.space_after = Pt(2)
            run = paragraph.add_run(f"{match.group(1)}. ")
            set_font(run, size=10.5, bold=True, color=ACCENT)
            add_inline(paragraph, match.group(2).strip())
            continue

        flush_table()
        paragraph = document.add_paragraph()
        add_inline(paragraph, line.strip())

    flush_table()
    document.save(TARGET)
    return TARGET


if __name__ == "__main__":
    path = build()
    print(f"written: {path}")
