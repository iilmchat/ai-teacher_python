"""Собирает DOCX-версию отчёта docs/GITFLIC_ONBOARDING.md для шаринга.

Запуск:
    python scripts/reports/build_gitflic_onboarding_docx.py

Источник — Markdown, чтобы документ не расходился с репозиторием.
Поддерживается подмножество Markdown: заголовки #..####, абзацы, списки,
таблицы, блоки кода, цитаты, **bold**, `code`, [ссылки](url).
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs" / "GITFLIC_ONBOARDING.md"
DST = ROOT / "docs" / "GITFLIC_ONBOARDING.docx"

BODY_FONT = "Segoe UI"
MONO_FONT = "Consolas"
DARK = RGBColor(0x1F, 0x38, 0x64)
ACCENT = RGBColor(0x2E, 0x54, 0x96)
GREY = RGBColor(0x59, 0x59, 0x59)
CODE_COLOR = RGBColor(0xA3, 0x15, 0x15)

INLINE_RE = re.compile(
    r"(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|<https?://[^>]+>)",
)


# --- low-level helpers -------------------------------------------------------


def shade(element, fill: str) -> None:
    """Заливка ячейки/абзаца."""
    pr = element.get_or_add_tcPr() if element.tag.endswith("tc") else element.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    pr.append(shd)


def set_cell_margins(cell, top=60, bottom=60, left=90, right=90) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for tag, value in (("top", top), ("bottom", bottom), ("start", left), ("end", right)):
        node = OxmlElement(f"w:{tag}")
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")
        mar.append(node)
    tc_pr.append(mar)


def repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    tr_pr.append(header)


def add_hyperlink(paragraph, url: str, text: str, size: float | None = None) -> None:
    part = paragraph.part
    r_id = part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "1F4E79")
    rpr.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rpr.append(underline)
    if size:
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), str(int(size * 2)))
        rpr.append(sz)
    run.append(rpr)
    node = OxmlElement("w:t")
    node.set(qn("xml:space"), "preserve")
    node.text = text
    run.append(node)
    link.append(run)
    paragraph._p.append(link)


def add_page_field(paragraph) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instr)
    run._r.append(end)


def add_bottom_border(paragraph, color: str = "BFBFBF", size: int = 6) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color)
    borders.append(bottom)
    ppr.append(borders)


def add_runs(paragraph, text: str, size: float | None = None, bold: bool = False) -> None:
    """Разбирает **bold**, `code`, [text](url); поддерживает code внутри bold."""
    for token in INLINE_RE.split(text):
        if not token:
            continue
        if token.startswith("**") and token.endswith("**"):
            add_runs(paragraph, token[2:-2], size=size, bold=True)
        elif token.startswith("`") and token.endswith("`"):
            run = paragraph.add_run(token[1:-1])
            run.font.name = MONO_FONT
            run.font.size = Pt((size or 10.5) - 1.3)
            run.font.color.rgb = CODE_COLOR
            run.bold = bold
        elif token.startswith("<http") and token.endswith(">"):
            url = token[1:-1]
            add_hyperlink(paragraph, url, url, size)
        elif token.startswith("[") and "](" in token:
            label, url = token[1:-1].split("](", 1)
            add_hyperlink(paragraph, url, label, size)
        else:
            run = paragraph.add_run(token)
            run.bold = bold
            if size:
                run.font.size = Pt(size)


# --- document styling --------------------------------------------------------


def setup_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(10.5)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.18

    for name, size, color, before, after in (
        ("Heading 1", 16, DARK, 18, 8),
        ("Heading 2", 13, ACCENT, 14, 5),
        ("Heading 3", 11.5, RGBColor(0x33, 0x33, 0x33), 10, 4),
    ):
        style = doc.styles[name]
        style.font.name = BODY_FONT
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = color
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    title = doc.styles["Title"]
    title.font.name = BODY_FONT
    title.font.size = Pt(26)
    title.font.bold = True
    title.font.color.rgb = DARK
    title.paragraph_format.space_after = Pt(10)


def setup_page(doc: Document) -> None:
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(1.8)
    section.header_distance = Cm(1.0)
    section.footer_distance = Cm(1.0)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = footer.add_run("GitFlic onboarding · v1.0 · стр. ")
    run.font.size = Pt(8.5)
    run.font.color.rgb = GREY
    add_page_field(footer)
    for r in footer.runs:
        r.font.size = Pt(8.5)
        r.font.color.rgb = GREY


# --- block parsers -----------------------------------------------------------


def is_table_row(line: str) -> bool:
    return line.strip().startswith("|") and line.strip().endswith("|")


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_separator(line: str) -> bool:
    cells = split_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c) for c in cells)


def consume_continuation(lines: list[str], i: int, text: str) -> tuple[str, int]:
    """Склеивает перенесённые строки одного пункта списка в один абзац."""
    while i < len(lines):
        nxt = lines[i]
        if not nxt.strip() or not nxt.startswith((" ", "\t")):
            break
        stripped = nxt.strip()
        if (
            stripped.startswith(("```", "|", "#", "- ", "* ", ">"))
            or re.match(r"^\d+\.\s", stripped)
        ):
            break
        text = f"{text} {stripped}"
        i += 1
    return text, i


def render_table(doc: Document, rows: list[list[str]]) -> None:
    cols = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=cols)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True

    fractions = {
        2: [0.30, 0.70],
        3: [0.24, 0.40, 0.36],
        4: [0.16, 0.37, 0.16, 0.31],
        5: [0.14, 0.30, 0.14, 0.24, 0.18],
    }.get(cols, [1 / cols] * cols)
    usable = doc.sections[0].page_width - doc.sections[0].left_margin - doc.sections[0].right_margin
    widths = [int(usable * f) for f in fractions]

    for r_idx, row in enumerate(rows):
        for c_idx in range(cols):
            cell = table.cell(r_idx, c_idx)
            cell.width = widths[c_idx]
            set_cell_margins(cell)
            text = row[c_idx] if c_idx < len(row) else ""
            para = cell.paragraphs[0]
            para.paragraph_format.space_after = Pt(0)
            para.paragraph_format.line_spacing = 1.05
            add_runs(para, text, size=8.8)
            if r_idx == 0:
                for run in para.runs:
                    run.bold = True
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                shade(cell._tc, "1F3864")
            elif r_idx % 2 == 0:
                shade(cell._tc, "F2F5FA")

    repeat_header(table.rows[0])
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def render_code(doc: Document, lines: list[str]) -> None:
    text = "\n".join(lines).rstrip("\n")
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(4)
    para.paragraph_format.space_after = Pt(8)
    para.paragraph_format.line_spacing = 1.0
    para.paragraph_format.left_indent = Cm(0.15)
    # Короткие блоки не разрываем, длинные (листинги YAML) пусть текут по странице.
    para.paragraph_format.keep_together = len(lines) <= 30
    shade(para._p, "F4F4F4")
    run = para.add_run(text)
    run.font.name = MONO_FONT
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), MONO_FONT)


def render_quote(doc: Document, lines: list[str]) -> None:
    para = doc.add_paragraph()
    para.paragraph_format.left_indent = Cm(0.4)
    para.paragraph_format.space_before = Pt(4)
    para.paragraph_format.space_after = Pt(6)
    text = " ".join(line.lstrip("> ").strip() for line in lines)
    add_runs(para, text, size=10)
    for run in para.runs:
        run.italic = True
        run.font.color.rgb = GREY


# --- main --------------------------------------------------------------------


def parse(md: str) -> list[tuple[str, object]]:
    blocks: list[tuple[str, object]] = []
    lines = md.splitlines()
    i = 0
    paragraph: list[str] = []

    def flush() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(("p", " ".join(paragraph).strip()))
            paragraph = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush()
            fence = stripped[:3]
            code: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i].rstrip())
                i += 1
            blocks.append(("code", code))
            i += 1
            continue

        if not stripped:
            flush()
            i += 1
            continue

        if re.fullmatch(r"-{3,}", stripped):
            flush()
            blocks.append(("hr", None))
            i += 1
            continue

        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading:
            flush()
            blocks.append((f"h{len(heading.group(1))}", heading.group(2).strip()))
            i += 1
            continue

        if is_table_row(stripped):
            flush()
            rows: list[list[str]] = []
            while i < len(lines) and is_table_row(lines[i].strip()):
                if not is_separator(lines[i]):
                    rows.append(split_row(lines[i]))
                i += 1
            if rows:
                blocks.append(("table", rows))
            continue

        if stripped.startswith(">"):
            flush()
            quote: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip())
                i += 1
            blocks.append(("quote", quote))
            continue

        bullet = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if bullet:
            flush()
            indent = len(bullet.group(1))
            text = bullet.group(2).strip()
            i += 1
            text, i = consume_continuation(lines, i, text)
            blocks.append(("li", (indent, text)))
            continue

        numbered = re.match(r"^(\s*)(\d+)\.\s+(.*)$", line)
        if numbered:
            flush()
            text = numbered.group(3).strip()
            i += 1
            text, i = consume_continuation(lines, i, text)
            blocks.append(("ol", (int(numbered.group(2)), text)))
            continue

        paragraph.append(stripped)
        i += 1

    flush()
    return blocks


def build() -> None:
    blocks = parse(SRC.read_text(encoding="utf-8"))
    doc = Document()
    setup_page(doc)
    setup_styles(doc)

    # Обложка: первый h1 + подзаголовок + таблица метаданных.
    first_h1 = next(idx for idx, b in enumerate(blocks) if b[0] == "h1")
    cover_title = blocks[first_h1][1]
    subtitle = blocks[first_h1 + 1][1] if blocks[first_h1 + 1][0] == "p" else ""
    meta = next(b for b in blocks if b[0] == "table")[1]

    doc.add_paragraph().paragraph_format.space_after = Pt(60)
    title_para = doc.add_paragraph(style="Title")
    add_runs(title_para, str(cover_title), size=26)
    for run in title_para.runs:
        run.font.color.rgb = DARK
    sub = doc.add_paragraph()
    add_runs(sub, str(subtitle), size=12)
    for run in sub.runs:
        run.font.color.rgb = GREY

    doc.add_paragraph().paragraph_format.space_after = Pt(24)
    render_table(doc, meta)

    note = doc.add_paragraph()
    note.paragraph_format.space_before = Pt(16)
    add_runs(
        note,
        "Документ описывает перенос, выполненный для `ai-teacher_python` "
        "(спринт 21): конфиги, команды и тайминги взяты из его пилота.",
        size=9,
    )
    for run in note.runs:
        run.font.color.rgb = GREY
        run.italic = True

    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    skip_until = 0
    for idx, block in enumerate(blocks):
        if block[0] == "hr":
            skip_until = idx + 1
            break

    for idx, (kind, value) in enumerate(blocks[skip_until:], start=skip_until):
        if kind == "h1":
            heading = doc.add_heading(str(value), level=1)
            if str(value).startswith("Приложение"):
                heading.paragraph_format.page_break_before = True
        elif kind == "h2":
            doc.add_heading(str(value), level=2)
        elif kind == "h3":
            doc.add_heading(str(value), level=3)
        elif kind == "h4":
            para = doc.add_paragraph()
            add_runs(para, str(value), size=10.5)
            for run in para.runs:
                run.bold = True
        elif kind == "p":
            add_runs(doc.add_paragraph(), str(value))
        elif kind == "code":
            render_code(doc, value)  # type: ignore[arg-type]
        elif kind == "table":
            render_table(doc, value)  # type: ignore[arg-type]
        elif kind == "li":
            indent, text = value  # type: ignore[misc]
            if text.startswith("[ ] "):
                text = "\u2610 " + text[4:]
            elif text.startswith("[x] "):
                text = "\u2611 " + text[4:]
            para = doc.add_paragraph(style="List Bullet")
            if indent:
                para.paragraph_format.left_indent = Cm(0.63 + 0.5 * (indent // 2))
            para.paragraph_format.space_before = Pt(0)
            para.paragraph_format.space_after = Pt(3)
            para.paragraph_format.line_spacing = 1.12
            add_runs(para, text)
        elif kind == "ol":
            num, text = value  # type: ignore[misc]
            para = doc.add_paragraph()
            para.paragraph_format.left_indent = Cm(0.75)
            para.paragraph_format.first_line_indent = Cm(-0.55)
            para.paragraph_format.space_before = Pt(0)
            para.paragraph_format.space_after = Pt(3)
            para.paragraph_format.line_spacing = 1.12
            para.add_run(f"{num}. ")
            add_runs(para, text)
        elif kind == "quote":
            render_quote(doc, value)  # type: ignore[arg-type]
        elif kind == "hr":
            nxt = blocks[idx + 1][0] if idx + 1 < len(blocks) else None
            if nxt == "h1":
                continue
            spacer = doc.add_paragraph()
            spacer.paragraph_format.space_before = Pt(2)
            spacer.paragraph_format.space_after = Pt(6)
            add_bottom_border(spacer)

    doc.save(DST)
    print(f"OK: {DST}")


if __name__ == "__main__":
    build()
