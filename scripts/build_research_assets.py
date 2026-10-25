#!/usr/bin/env python3
"""Generate editable, outlined, and print versions of the A0 research poster."""

from __future__ import annotations

import base64
import csv
import json
import math
import shutil
import subprocess
from pathlib import Path

import reportlab
from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.shapes import Circle, Drawing, Image, Line, Polygon, Rect, String
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assets" / "data"
FIGURES = ROOT / "assets" / "figures"
UNITN_LOGO = ROOT / "assets" / "unitn-logo.png"
W, H = 2384, 3370  # A0 portrait: 841 x 1189 mm at 72 pt/in.
WHITE, INK, MUTED, RULE = "#FFFFFF", "#142536", "#536575", "#C8D2DB"
BLUE, PALE_BLUE = "#123F67", "#EAF2F8"
GATE, LESION, READOUT, ENCODER, DAMAGE = "#138C82", "#20262B", "#B43F7A", "#D27A20", "#C64A3A"
SOFT = "#F5F8FA"
FONT_DIR = Path(reportlab.__file__).resolve().parent / "fonts"
FONT_PATH = FONT_DIR / "Vera.ttf"
BOLD_PATH = FONT_DIR / "VeraBd.ttf"
REGULAR, BOLD = "Vera", "Vera-Bold"
pdfmetrics.registerFont(TTFont(REGULAR, str(FONT_PATH)))
pdfmetrics.registerFont(TTFont(BOLD, str(BOLD_PATH)))


class Page:
    """Top-origin vector drawing helper with measured text boxes."""

    def __init__(self, drawing: Drawing, height: float) -> None:
        self.drawing = drawing
        self.height = height

    def rect(self, x: float, top: float, width: float, height: float, fill: str, stroke: str | None = None, radius: float = 0, line: float = 1) -> None:
        self.drawing.add(Rect(x, self.height - top - height, width, height, rx=radius, ry=radius, fillColor=HexColor(fill), strokeColor=HexColor(stroke) if stroke else None, strokeWidth=line))

    def line(self, x1: float, top1: float, x2: float, top2: float, color: str = RULE, width: float = 1, dash: list[int] | None = None) -> None:
        item = Line(x1, self.height - top1, x2, self.height - top2, strokeColor=HexColor(color), strokeWidth=width)
        if dash:
            item.strokeDashArray = dash
        self.drawing.add(item)

    def arrow(self, x1: float, top1: float, x2: float, top2: float, color: str, width: float = 4, head: float = 14, dash: list[int] | None = None) -> None:
        """Draw a directed line with a consistent filled arrowhead."""
        self.line(x1, top1, x2, top2, color, width, dash)
        angle = math.atan2(top2 - top1, x2 - x1)
        back_x, back_y = x2 - head * math.cos(angle), top2 - head * math.sin(angle)
        side = head * 0.55
        self.polygon(
            [
                (x2, top2),
                (back_x + side * math.sin(angle), back_y - side * math.cos(angle)),
                (back_x - side * math.sin(angle), back_y + side * math.cos(angle)),
            ],
            color,
        )

    def circle(self, x: float, top: float, radius: float, fill: str, stroke: str | None = None, width: float = 1) -> None:
        self.drawing.add(Circle(x, self.height - top, radius, fillColor=HexColor(fill), strokeColor=HexColor(stroke) if stroke else None, strokeWidth=width))

    def polygon(self, points: list[tuple[float, float]], fill: str, stroke: str | None = None, width: float = 1) -> None:
        flat = [coordinate for x, top in points for coordinate in (x, self.height - top)]
        self.drawing.add(Polygon(flat, fillColor=HexColor(fill), strokeColor=HexColor(stroke) if stroke else None, strokeWidth=width))

    def image(self, x: float, top: float, width: float, height: float, path: Path) -> None:
        """Place a raster asset with top-origin coordinates."""
        self.drawing.add(Image(x, self.height - top - height, width, height, str(path)))

    def text_box(self, x: float, top: float, width: float, height: float, value: str, size: float, color: str = INK, bold: bool = False, align: str = "left", leading: float | None = None, wrap: bool = False) -> None:
        """Draw measured text inside an explicit box or raise on overflow."""
        if x < 0 or top < 0 or x + width > W + 0.1 or top + height > self.height + 0.1:
            raise ValueError(f"Text box outside page: {(x, top, width, height, value[:30])}")
        font = BOLD if bold else REGULAR
        line_height = leading or size * 1.25
        lines = wrap_lines(value, font, size, width) if wrap else value.split("\n")
        required_height = size + max(0, len(lines) - 1) * line_height
        if required_height > height + 0.1:
            raise ValueError(f"Text box height overflow ({len(lines)} lines): {value[:80]}")
        anchor = {"left": "start", "center": "middle", "right": "end"}[align]
        text_x = {"left": x, "center": x + width / 2, "right": x + width}[align]
        for index, line_value in enumerate(lines):
            measured = pdfmetrics.stringWidth(line_value, font, size)
            if measured > width + 0.1:
                raise ValueError(f"Text box width overflow ({measured:.1f}>{width:.1f}): {line_value}")
            baseline_top = top + index * line_height + size
            self.drawing.add(String(text_x, self.height - baseline_top, line_value, fontName=font, fontSize=size, fillColor=HexColor(color), textAnchor=anchor))


def wrap_lines(value: str, font: str, size: float, width: float) -> list[str]:
    """Wrap text using the exact TrueType font used for rendering."""
    lines: list[str] = []
    for paragraph in value.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if current and pdfmetrics.stringWidth(candidate, font, size) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return lines


def section_heading(page: Page, x: float, top: float, width: float, title: str, tag: str | None = None) -> None:
    """Draw a restrained academic heading and optional aggregation tag."""
    page.text_box(x, top, width, 45, title, 36, BLUE, True)
    if tag:
        page.text_box(x, top + 7, width, 34, tag, 21, MUTED, True, "right")
    page.line(x, top + 50, x + width, top + 50, BLUE, 2.5)


def cross(page: Page, x: float, top: float, size: float = 12, color: str = LESION, width: float = 4) -> None:
    """Draw the permanent-lesion mark."""
    page.line(x - size, top - size, x + size, top + size, color, width)
    page.line(x + size, top - size, x - size, top + size, color, width)


def diamond(page: Page, x: float, top: float, size: float, fill: str, stroke: str | None = None, width: float = 1) -> None:
    """Draw a diamond marker."""
    page.polygon([(x, top - size), (x + size, top), (x, top + size), (x - size, top)], fill, stroke, width)


def load_data() -> tuple[dict, list[dict[str, str]]]:
    """Load verified endpoint/seed metrics and the shared-coordinate token sample."""
    site = json.loads((DATA / "site-data.json").read_text())
    with (DATA / "readout-empirical.csv").open(newline="") as stream:
        tokens = list(csv.DictReader(stream))
    if len(tokens) != 816:
        raise ValueError(f"Expected 816 paired tokens, found {len(tokens)}")
    return site, tokens


def draw_encoder(page: Page, x: float, top: float, width: float, height: float) -> None:
    """Draw encoder layers and projection-specific gate locations."""
    page.rect(x, top, width, height, PALE_BLUE, BLUE, 6, 2)
    page.text_box(x + 20, top + 14, width - 40, 30, "BERT-base encoder", 23, BLUE, True)
    page.text_box(x + 210, top + 17, width - 230, 26, "projection-specific input-feature gates", 18, MUTED, False, "right")
    labels = ["Q", "K", "V", "AO", "FI", "FO"]
    gate_x = x + 315
    for index, label in enumerate(labels):
        page.text_box(gate_x + index * 61, top + 53, 48, 24, label, 17, GATE, True, "center")
    for row_index, layer in enumerate(["Layer 0", "Layer 1", "...", "Layer 11"]):
        row_top = top + 82 + row_index * 40
        page.rect(x + 22, row_top, 245, 30, WHITE, RULE, 3, 1)
        page.text_box(x + 36, row_top + 2, 215, 25, layer, 17, INK, layer != "...")
        if layer == "...":
            continue
        for gate_index in range(6):
            gx = gate_x + gate_index * 61
            page.rect(gx, row_top + 5, 48, 20, WHITE, GATE, 2, 2)
            page.text_box(gx, row_top + 3, 48, 20, "g", 14, GATE, True, "center")
        if row_index < 2:
            cross(page, gate_x + (row_index + 1) * 61 + 24, row_top + 15, 8, LESION, 3)


def draw_pipeline(page: Page, top: float, note_outside: bool = False) -> None:
    """Draw the computational sequence from tokens to predicted tags."""
    page.text_box(80, top, 400, 28, "COMPUTATION", 18, BLUE, True)
    page.rect(90, top + 70, 205, 102, WHITE, RULE, 6, 2)
    page.text_box(105, top + 85, 175, 27, "Input tokens", 22, INK, True, "center")
    page.text_box(105, top + 124, 175, 28, "[The] [dog] [runs]", 18, MUTED, False, "center")
    draw_encoder(page, 350, top + 18, 730, 250)

    page.rect(1190, top + 70, 260, 118, SOFT, RULE, 5, 2)
    page.text_box(1205, top + 84, 230, 28, "Final hidden states", 21, INK, True, "center")
    for row in range(3):
        for col in range(8):
            shade = PALE_BLUE if (row + col) % 3 else BLUE
            page.rect(1240 + col * 22, top + 125 + row * 18, 13, 11, shade, BLUE if shade == PALE_BLUE else None, 1, 0.5)
    page.text_box(1190 if note_outside else 1210, top + (195 if note_outside else 172), 260 if note_outside else 220, 20, "one 768-d vector per token", 15, MUTED, False, "center")

    page.rect(1570, top + 70, 230, 118, WHITE, READOUT, 5, 3)
    page.text_box(1580, top + 87, 210, 28, "Linear POS readout", 19, READOUT, True, "center")
    page.text_box(1590, top + 132, 190, 26, "W h + b", 22, INK, True, "center")
    page.text_box(1590, top + 164, 190, 20, "17 output scores", 15, MUTED, False, "center")

    page.rect(1940, top + 52, 334, 154, WHITE, RULE, 5, 2)
    page.text_box(1960, top + 67, 294, 28, "Predicted tags", 21, INK, True, "center")
    page.text_box(1960, top + 112, 294, 56, "DET   NOUN   VERB\n... one tag per token", 18, MUTED, False, "center", 28)

    center_y = top + 129
    for start, end in [(295, 342), (1080, 1182), (1450, 1562), (1800, 1932)]:
        page.arrow(start, center_y, end, center_y, BLUE, 4, 14)


def status_cell(page: Page, x: float, top: float, width: float, value: str, color: str, editorial: bool = False) -> None:
    """Draw an explicit trainability cell without reusing gate-state symbols."""
    if editorial:
        page.text_box(x, top + 3, width, 23, value, 14, color, True, "center")
        page.line(x + 8, top + 29, x + width - 8, top + 29, color, 1.5)
        return
    fill = color if value == "TRAIN" else SOFT
    stroke = color if value in {"TRAIN", "OFF"} else RULE
    text_color = WHITE if value == "TRAIN" else color
    page.rect(x, top, width, 31, fill, stroke, 3, 1.5)
    page.text_box(x, top + 3, width, 23, value, 14, text_color, True, "center")


def draw_framework(page: Page, top: float, plain_lesion: bool = False, editorial: bool = False) -> None:
    """Draw the dominant method figure and recovery trainability table."""
    section_heading(page, 80, top, 2224, "Experimental framework")
    draw_pipeline(page, top + 72, note_outside=plain_lesion)

    band_top = top + 365
    page.text_box(80, band_top, 500, 27, "EXPERIMENTAL PROGRESSION", 18, ENCODER, True)
    a_x, a_w = 80, 575
    b_x, b_w = 710, 470
    c_x, c_w = 1235, 1069
    box_top, box_h = band_top + 42, 338
    for x, width in [(a_x, a_w), (b_x, b_w), (c_x, c_w)]:
        page.rect(x, box_top, width, box_h, WHITE, RULE, 0 if editorial else 5, 1.5)

    page.text_box(a_x + 22, box_top + 18, a_w - 44, 32, "A  Learn the task-sufficient core", 23, BLUE, True)
    page.text_box(a_x + 22, box_top + 67, a_w - 44, 88, "Train projection-specific hard-concrete gates and the linear POS readout while pretrained encoder weights remain fixed.", 19, INK, False, "left", 27, True)
    page.text_box(a_x + 22, box_top + 176, 165, 25, "Gates", 18, GATE, True)
    status_cell(page, a_x + 205, box_top + 171, 105, "TRAIN", GATE, editorial)
    page.text_box(a_x + 22, box_top + 219, 165, 25, "Readout", 18, READOUT, True)
    status_cell(page, a_x + 205, box_top + 214, 105, "TRAIN", READOUT, editorial)
    page.text_box(a_x + 22, box_top + 262, 175, 25, "Encoder weights", 18, ENCODER, True)
    status_cell(page, a_x + 205, box_top + 257, 105, "FIXED", ENCODER, editorial)
    page.text_box(a_x + 335, box_top + 174, 215, 105, "The sparse configuration reaches 94.98% primary-run POS accuracy.", 18, MUTED, False, "left", 26, True)

    page.text_box(b_x + 22, box_top + 18, b_w - 44, 32, "B  Apply a permanent lesion", 23, BLUE, True)
    cross(page, b_x + 58, box_top + 100, 19, LESION, 6)
    lesion_copy = "Gates used by the task-sufficient core are permanently disabled. Their effective values are zero and gradients are blocked." if plain_lesion else "Mask scores forced to -12; effective gates are zero and gradients are blocked."
    page.text_box(b_x + 96, box_top + 72, b_w - 120, 96 if plain_lesion else 72, lesion_copy, 18, INK, True, "left", 25, True)
    page.text_box(b_x + 22, box_top + 171, b_w - 44, 78, "74 Q/K/V 64-coordinate input groups\n5 attention-output gate tensors\n9 FFN-intermediate + 4 FFN-output tensors", 17, MUTED, False, "left", 25)
    page.text_box(b_x + 22, box_top + 274, b_w - 44, 44, "No recovery pathway can reactivate these entries.", 18, LESION, True, "left", 24, True)

    page.text_box(c_x + 22, box_top + 18, c_w - 44, 32, "C  Recovery trainability", 23, BLUE, True)
    table_x = c_x + 22
    columns = [(0, 300, "Condition"), (310, 160, "Gates"), (480, 170, "Readout"), (660, 175, "Encoder"), (845, 175, "Lesion")]
    for offset, width, label in columns:
        page.text_box(table_x + offset, box_top + 62, width, 24, label, 16, MUTED, True, "center" if offset else "left")
    rows = [
        ("Gates only", "TRAIN", "FIXED", "FIXED", "OFF"),
        ("Readout only", "FIXED", "TRAIN", "FIXED", "OFF"),
        ("Gates + readout", "TRAIN", "TRAIN", "FIXED", "OFF"),
        ("Encoder only", "FIXED", "FIXED", "TRAIN", "OFF"),
    ]
    colors = [INK, GATE, READOUT, ENCODER, LESION]
    for row_index, row in enumerate(rows):
        row_top = box_top + 96 + row_index * 55
        page.text_box(table_x, row_top + 4, 300, 28, row[0], 18, INK, True)
        for col_index, value in enumerate(row[1:], start=1):
            offset, width, _ = columns[col_index]
            status_cell(page, table_x + offset + 15, row_top, width - 30, value, colors[col_index], editorial)
        if row_index < len(rows) - 1:
            page.line(table_x, row_top + 44, c_x + c_w - 22, row_top + 44, SOFT, 1)

    page.arrow(a_x + a_w + 10, box_top + 47, b_x - 10, box_top + 47, ENCODER, 3, 12)
    page.arrow(b_x + b_w + 10, box_top + 47, c_x - 10, box_top + 47, ENCODER, 3, 12)

    strip_top = top + 765
    page.rect(80, strip_top, 2224, 80, PALE_BLUE)
    page.text_box(104, strip_top + 10, 130, 24, "SETUP", 16, BLUE, True)
    page.text_box(240, strip_top + 10, 1000, 24, "bert-base-uncased | UD English-EWT | 17 POS tags | 25,147 development tokens", 17, INK)
    page.text_box(104, strip_top + 43, 130, 24, "LESION", 16, BLUE, True)
    lesion_detail = "74 grouped Q/K/V input-coordinate masks; 5 attention-output, 9 FFN-intermediate, and 4 FFN-output projection-mask tensors; 37,248 entries clamped to -12 and gradient-blocked" if plain_lesion else "74 Q/K/V groups + 18 dense projection-mask tensors; 37,248 gate entries clamped"
    page.text_box(240, strip_top + 43, 2030 if plain_lesion else 1220, 24, lesion_detail, 15 if plain_lesion else 17, INK)
    if not plain_lesion:
        page.text_box(1520, strip_top + 9, 750, 52, "Schematic only: arrows show computation or experimental progression, not measured activation flow or traced causal paths.", 15, MUTED, False, "right", 22, True)


def draw_performance(page: Page, site: dict, x: float, top: float, width: float, height: float) -> None:
    """Draw five-seed means above capped min-max spans and individual runs."""
    keys = ["core", "encoder_only", "readout_and_mask_reg", "readout_only", "mask_only_inverse_reg", "damage"]
    colors = [BLUE, ENCODER, READOUT, READOUT, GATE, DAMAGE]
    labels = ["Core", "Encoder only", "Gates + readout", "Readout only", "Gates only, dense", "Damaged"]
    chart_x, chart_w = x + 260, width - 360
    page.rect(x + 10, top + 4, 14, 14, BLUE)
    page.text_box(x + 34, top, 150, 24, "mean", 16, MUTED)
    page.circle(x + 198, top + 11, 6, WHITE, BLUE, 2)
    page.text_box(x + 212, top, 160, 24, "individual run", 16, MUTED)
    page.line(x + 402, top + 11, x + 470, top + 11, BLUE, 5)
    page.line(x + 402, top + 3, x + 402, top + 19, BLUE, 2)
    page.line(x + 470, top + 3, x + 470, top + 19, BLUE, 2)
    page.text_box(x + 482, top, 210, 24, "observed min-max", 16, MUTED)
    axis_top, axis_bottom = top + 42, top + height - 55
    for tick in range(0, 101, 20):
        px = chart_x + chart_w * tick / 100
        page.line(px, axis_top, px, axis_bottom, SOFT, 1)
        page.text_box(px - 30, axis_bottom + 8, 60, 24, str(tick), 17, MUTED, False, "center")
    for i, (key, label, color) in enumerate(zip(keys, labels, colors)):
        values = site["seeds"][key]
        avg, lo, hi = sum(values) / len(values), min(values), max(values)
        cy = top + 70 + i * 54
        page.text_box(x, cy - 9, 235, 28, label, 18, INK, key in {"readout_only", "damage"}, "right")
        mean_x = chart_x + chart_w * avg / 100
        range_y = cy + 14
        lo_x, hi_x = chart_x + chart_w * lo / 100, chart_x + chart_w * hi / 100
        page.rect(mean_x - 7, cy - 14, 14, 14, color, color, 2)
        page.line(lo_x, range_y, hi_x, range_y, color, 5)
        page.line(lo_x, range_y - 8, lo_x, range_y + 8, color, 2)
        page.line(hi_x, range_y - 8, hi_x, range_y + 8, color, 2)
        for value_index, value in enumerate(values):
            jitter = [-5, -2.5, 0, 2.5, 5][value_index]
            page.circle(chart_x + chart_w * value / 100, range_y + jitter, 5, WHITE, color, 2)
        page.text_box(x + width - 82, cy - 9, 82, 28, f"{avg:.2f}%", 18, color, True, "right")
    page.line(chart_x, axis_bottom, chart_x + chart_w, axis_bottom, INK, 1.5)
    page.text_box(chart_x, top + height - 32, chart_w, 28, "Held-out POS accuracy (%)", 19, MUTED, False, "center")


def draw_performance_and_gates(page: Page, site: dict, x: float, top: float, width: float, height: float) -> None:
    """Pair five-run accuracy with primary-run effective gate composition."""
    keys = ["core", "encoder_only", "readout_and_mask_reg", "readout_only", "mask_only_inverse_reg", "mask_only_no_reg", "mask_only_reg", "damage"]
    labels = ["Core", "Encoder only", "Gates + readout", "Readout only", "Gates only, dense", "Gates only, no penalty", "Gates only, sparse", "Damaged"]
    colors = [BLUE, ENCODER, READOUT, READOUT, GATE, GATE, GATE, DAMAGE]
    accuracy_x, accuracy_w = x + 220, 315
    gates_x, gates_w = x + 650, 245
    page.text_box(accuracy_x, top, accuracy_w, 22, "ACCURACY · FIVE RUNS", 15, BLUE, True)
    page.rect(accuracy_x, top + 27, 10, 10, BLUE)
    page.text_box(accuracy_x + 17, top + 23, 55, 20, "mean", 13, MUTED)
    page.circle(accuracy_x + 102, top + 32, 4, WHITE, BLUE, 1.5)
    page.text_box(accuracy_x + 112, top + 23, 140, 20, "individual run", 13, MUTED)
    page.text_box(gates_x, top, width - 650, 22, "EFFECTIVE GATE STATE · PRIMARY RUN", 15, BLUE, True)
    for offset, fill, label in [(0, GATE, "active"), (82, PALE_BLUE, "mid"), (142, RULE, "inactive")]:
        page.rect(gates_x + offset, top + 27, 11, 11, fill, BLUE if label == "mid" else None, 1)
        page.text_box(gates_x + offset + 17, top + 23, 70, 20, label, 13, MUTED)
    page.text_box(gates_x + gates_w + 12, top + 23, 167, 20, "active / inactive / mid", 12, MUTED, False, "right")
    for tick in [0, 50, 100]:
        px = accuracy_x + accuracy_w * tick / 100
        page.line(px, top + 56, px, top + 373, SOFT, 1)
        page.text_box(px - 18, top + 378, 36, 20, str(tick), 13, MUTED, False, "center")
    for index, (key, label, color) in enumerate(zip(keys, labels, colors)):
        condition, values = site["conditions"][key], site["seeds"][key]
        cy = top + 66 + index * 39
        page.text_box(x, cy - 10, 200, 23, label, 15, INK, key in {"readout_only", "damage"}, "right")
        for run_index, value in enumerate(values):
            page.circle(accuracy_x + accuracy_w * value / 100, cy + [-4, -2, 0, 2, 4][run_index], 3.5, WHITE, color, 1.5)
        mean = sum(values) / len(values)
        page.rect(accuracy_x + accuracy_w * mean / 100 - 5, cy - 5, 10, 10, color)
        active, inactive, middle = (condition[name] for name in ("active_gates", "inactive_gates", "intermediate_gates"))
        page.rect(gates_x, cy - 7, gates_w * active / 100, 14, GATE)
        page.rect(gates_x + gates_w * active / 100, cy - 7, gates_w * middle / 100, 14, PALE_BLUE)
        page.rect(gates_x + gates_w * (active + middle) / 100, cy - 7, gates_w * inactive / 100, 14, RULE)
        page.text_box(gates_x + gates_w + 12, cy - 10, 167, 23, f"{active:.1f} / {inactive:.1f} / {middle:.1f}", 13, INK, False, "right")
    page.line(accuracy_x, top + 373, accuracy_x + accuracy_w, top + 373, INK, 1.5)
    page.text_box(accuracy_x, top + 402, accuracy_w, 23, "Held-out POS accuracy (%)", 15, MUTED, False, "center")
    page.text_box(gates_x, top + 402, gates_w, 23, "Fraction of all gate entries (%)", 15, MUTED, False, "center")


def draw_cka(page: Page, site: dict, x: float, top: float, width: float, height: float) -> None:
    """Draw primary-seed accuracy against linear CKA to the pre-lesion core."""
    keys = ["damage", "readout_only", "readout_and_mask_reg", "mask_only_inverse_reg", "encoder_only", "core"]
    labels = {"damage": "Damaged", "readout_only": "Readout only", "readout_and_mask_reg": "Gates + readout", "mask_only_inverse_reg": "Gates only, dense", "encoder_only": "Encoder only", "core": "Core"}
    colors = {"damage": DAMAGE, "readout_only": READOUT, "readout_and_mask_reg": READOUT, "mask_only_inverse_reg": GATE, "encoder_only": ENCODER, "core": BLUE}
    left, right, upper, lower = x + 92, x + width - 35, top + 26, top + height - 62
    sx = lambda value: left + (value - .4) / .62 * (right - left)
    sy = lambda value: lower - (value - 10) / 90 * (lower - upper)
    for tick in [.4, .5, .6, .7, .8, .9, 1.0]:
        px = sx(tick)
        page.line(px, upper, px, lower, SOFT, 1)
        page.text_box(px - 28, lower + 8, 56, 24, f"{tick:.1f}", 17, MUTED, False, "center")
    for tick in [20, 40, 60, 80, 100]:
        py = sy(tick)
        page.line(left, py, right, py, SOFT, 1)
        page.text_box(left - 58, py - 12, 45, 24, str(tick), 17, MUTED, False, "right")
    damage = site["conditions"]["damage"]
    readout = site["conditions"]["readout_only"]
    damage_x = sx(damage["cka_core"])
    page.line(damage_x, sy(damage["accuracy"]), damage_x, sy(readout["accuracy"]), READOUT, 4, [8, 7])
    page.text_box(damage_x + 16, sy(54), 250, 48, "identical encoder states", 16, READOUT, True, "left", 21, True)
    offsets = {
        "damage": (14, 9, 180, "left"),
        "readout_only": (16, 11, 210, "left"),
        "readout_and_mask_reg": (16, -42, 235, "left"),
        "mask_only_inverse_reg": (14, 9, 250, "left"),
        "encoder_only": (0, -42, 220, "center"),
        "core": (-14, 11, 150, "right"),
    }
    for key in keys:
        condition = site["conditions"][key]
        px, py = sx(condition["cka_core"]), sy(condition["accuracy"])
        page.circle(px, py, 10, colors[key], WHITE, 3)
        dx, dy, label_width, align = offsets[key]
        label_x = px + dx
        if align == "right":
            label_x -= label_width
        elif align == "center":
            label_x -= label_width / 2
        page.text_box(label_x, py + dy, label_width, 27, labels[key], 17, INK, True, align)
    page.text_box(left, top + height - 29, right - left, 27, "Linear CKA to pre-lesion core", 19, MUTED, False, "center")
    page.text_box(x + 3, top, 190, 26, "POS accuracy (%)", 17, MUTED, True)


def bounds(tokens: list[dict[str, str]]) -> tuple[float, float, float, float]:
    """Return padded full-range PCA limits shared by both readout panels."""
    xs = [float(row["pc1"]) for row in tokens]
    ys = [float(row["pc2"]) for row in tokens]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    xpad = (xmax - xmin) * .04
    ypad = (ymax - ymin) * .04
    return xmin - xpad, xmax + xpad, ymin - ypad, ymax + ypad


def draw_readout(page: Page, tokens: list[dict[str, str]], x: float, top: float, width: float, height: float) -> None:
    """Draw identical shared-PCA coordinates with original versus retrained predictions."""
    xmin, xmax, ymin, ymax = bounds(tokens)
    gap, panel_w = 120, (width - 120) / 2
    panels = [
        (x, "original_correct", "Damaged encoder + original readout", "49 / 816 subset correct", "16.82% full development"),
        (x + panel_w + gap, "remapped_correct", "Same encoder + retrained readout", "521 / 816 subset correct", "80.00% full development"),
    ]
    for x0, field, title, subset, full in panels:
        page.rect(x0, top, panel_w, height, WHITE, RULE, 5, 1.5)
        page.text_box(x0 + 22, top + 15, panel_w - 44, 30, title, 22, INK, True)
        page.text_box(x0 + 22, top + 49, panel_w - 44, 25, subset, 18, READOUT if field == "remapped_correct" else DAMAGE, True, "right")
        page.text_box(x0 + 22, top + 76, panel_w - 44, 23, full, 16, MUTED, False, "right")
        plot_left, plot_top, plot_w, plot_h = x0 + 46, top + 104, panel_w - 76, height - 157
        page.line(plot_left, plot_top + plot_h, plot_left + plot_w, plot_top + plot_h, RULE, 1)
        page.line(plot_left, plot_top, plot_left, plot_top + plot_h, RULE, 1)
        for row in tokens:
            px = plot_left + (float(row["pc1"]) - xmin) / (xmax - xmin) * plot_w
            py = plot_top + plot_h - (float(row["pc2"]) - ymin) / (ymax - ymin) * plot_h
            px, py = max(plot_left, min(plot_left + plot_w, px)), max(plot_top, min(plot_top + plot_h, py))
            if row[field] == "1":
                page.circle(px, py, 2.7, BLUE)
            else:
                page.line(px - 2.5, py - 2.5, px + 2.5, py + 2.5, DAMAGE, 1)
                page.line(px + 2.5, py - 2.5, px - 2.5, py + 2.5, DAMAGE, 1)
        page.text_box(plot_left, top + height - 34, plot_w, 24, "PC1 (14.50% of core variance)", 16, MUTED, False, "center")
        page.text_box(x0 + 8, plot_top - 3, 180, 22, "PC2 (8.82%)", 15, MUTED)
    mid = x + width / 2
    page.arrow(mid - 42, top + height / 2, mid + 42, top + height / 2, READOUT, 4, 13)


def draw_readout_stack(page: Page, tokens: list[dict[str, str]], x: float, top: float, width: float, height: float) -> None:
    """Draw the fixed-token readout comparison compactly in two stacked panels."""
    xmin, xmax, ymin, ymax = bounds(tokens)
    page.text_box(x, top, width, 30, "Readout-only recovery", 24, BLUE, True)
    page.text_box(x, top + 33, width, 24, "Same token representations; only the linear readout changes", 16, READOUT, True)
    panel_top, gap = top + 68, 34
    panel_h = (height - 68 - gap) / 2
    panels = [
        (panel_top, "original_correct", "Damaged + original readout", "49 / 816 correct | 16.82% full dev"),
        (panel_top + panel_h + gap, "remapped_correct", "Same encoder + retrained readout", "521 / 816 correct | 80.00% full dev"),
    ]
    for panel_y, field, title, result in panels:
        page.rect(x, panel_y, width, panel_h, WHITE, RULE, 4, 1.5)
        page.text_box(x + 18, panel_y + 10, width * .55, 25, title, 18, INK, True)
        page.text_box(x + width * .55, panel_y + 10, width * .42 - 18, 25, result, 15, READOUT if field == "remapped_correct" else DAMAGE, True, "right")
        plot_left, plot_top = x + 25, panel_y + 43
        plot_w, plot_h = width - 50, panel_h - 58
        page.line(plot_left, plot_top + plot_h, plot_left + plot_w, plot_top + plot_h, RULE, 1)
        page.line(plot_left, plot_top, plot_left, plot_top + plot_h, RULE, 1)
        for row in tokens:
            px = plot_left + (float(row["pc1"]) - xmin) / (xmax - xmin) * plot_w
            py = plot_top + plot_h - (float(row["pc2"]) - ymin) / (ymax - ymin) * plot_h
            px, py = max(plot_left, min(plot_left + plot_w, px)), max(plot_top, min(plot_top + plot_h, py))
            if row[field] == "1":
                page.circle(px, py, 2.0, BLUE)
            else:
                page.line(px - 1.8, py - 1.8, px + 1.8, py + 1.8, DAMAGE, .8)
                page.line(px + 1.8, py - 1.8, px - 1.8, py + 1.8, DAMAGE, .8)
    arrow_x = x + width / 2
    page.arrow(arrow_x, panel_top + panel_h + 5, arrow_x, panel_top + panel_h + gap - 5, READOUT, 3, 10)


def draw_geometry_plane(page: Page, site: dict, x: float, top: float, width: float, height: float) -> None:
    """Plot POS-centroid geometry against POS-readout geometry for recovery endpoints."""
    page.text_box(x, top, width, 30, "Encoder and readout geometry", 24, BLUE, True)
    page.text_box(x, top + 33, width, 24, "Primary-run endpoints; labels report held-out POS accuracy", 16, MUTED, True)
    left, right, upper, lower = x + 105, x + width - 28, top + 92, top + height - 68
    sx = lambda value: left + (value - .3) / .72 * (right - left)
    sy = lambda value: lower - (value - .5) / .52 * (lower - upper)
    for tick in [.3, .4, .5, .6, .7, .8, .9, 1.0]:
        px = sx(tick)
        page.line(px, upper, px, lower, SOFT, 1)
        page.text_box(px - 24, lower + 7, 48, 22, f"{tick:.1f}", 14, MUTED, False, "center")
    for tick in [.5, .6, .7, .8, .9, 1.0]:
        py = sy(tick)
        page.line(left, py, right, py, SOFT, 1)
        page.text_box(left - 52, py - 11, 40, 22, f"{tick:.1f}", 14, MUTED, False, "right")
    page.line(left, upper, left, lower, INK, 1.4)
    page.line(left, lower, right, lower, INK, 1.4)
    page.text_box(left, top + height - 31, right - left, 24, "Spearman similarity of POS-centroid RDM to core (encoder)", 16, MUTED, False, "center")
    page.text_box(x + 2, top + 59, width - 4, 23, "Spearman similarity of readout-weight RDM to core", 16, MUTED, True)

    keys = ["damage", "readout_only", "mask_only_inverse_reg", "readout_and_mask_reg", "encoder_only", "core"]
    colors = {"damage": DAMAGE, "readout_only": READOUT, "mask_only_inverse_reg": GATE, "readout_and_mask_reg": READOUT, "encoder_only": ENCODER, "core": BLUE}
    labels = {"damage": "Damaged", "readout_only": "Readout only", "mask_only_inverse_reg": "Gates only, dense", "readout_and_mask_reg": "Gates + readout", "encoder_only": "Encoder only", "core": "Core"}
    # Point positions use full-precision records; visible labels match the values reported in manuscript Table A1.
    reported_accuracy = {"damage": 16.82, "readout_only": 80.00, "mask_only_inverse_reg": 69.74, "readout_and_mask_reg": 85.87, "encoder_only": 92.31, "core": 94.98}
    damage = site["conditions"]["damage"]
    start = (sx(damage["pos_centroid"]), sy(damage["head_rdm"]))
    readout = site["conditions"]["readout_only"]
    gates = site["conditions"]["mask_only_inverse_reg"]
    joint = site["conditions"]["readout_and_mask_reg"]
    page.arrow(start[0], start[1] + 12, sx(readout["pos_centroid"]), sy(readout["head_rdm"]) - 12, READOUT, 2.8, 10)
    page.arrow(start[0] + 12, start[1], sx(gates["pos_centroid"]) - 12, sy(gates["head_rdm"]), GATE, 2.8, 10)
    page.line(start[0], start[1], sx(joint["pos_centroid"]), sy(joint["head_rdm"]), MUTED, 1.7, [6, 6])
    callout_y = (start[1] + sy(readout["head_rdm"])) / 2 - 24
    page.text_box(start[0] + 18, callout_y, 230, 48, "same encoder geometry\nnew readout", 14, READOUT, True, "left", 19)
    offsets = {
        "damage": (12, 11, "left"),
        "readout_only": (14, -25, "left"),
        "mask_only_inverse_reg": (12, -28, "left"),
        "readout_and_mask_reg": (14, 9, "left"),
        "encoder_only": (10, 11, "left"),
        "core": (-215, 11, "right"),
    }
    for key in keys:
        condition = site["conditions"][key]
        px, py = sx(condition["pos_centroid"]), sy(condition["head_rdm"])
        if key == "readout_and_mask_reg":
            page.circle(px, py, 12, GATE, WHITE, 2)
            page.circle(px, py, 7, READOUT)
        else:
            page.circle(px, py, 10, colors[key], WHITE, 2.5)
        dx, dy, align = offsets[key]
        label = f"{labels[key]} | {reported_accuracy[key]:.2f}%"
        label_w = 260
        page.text_box(px + dx - (label_w if align == "right" else 0), py + dy, label_w, 24, label, 16, INK, True, align)
    page.text_box(right - 610, lower - 42, 610, 34, "Arrows compare endpoints only; they are not training trajectories", 14, MUTED, False, "right", 19, True)


def draw_controls(page: Page, x: float, top: float, width: float) -> None:
    """Draw matched-random lesion summaries with intervention-specific axes."""
    diamond(page, x + 12, top + 12, 8, LESION)
    page.text_box(x + 28, top, 185, 24, "targeted lesion", 15, MUTED)
    page.line(x + 230, top + 12, x + 300, top + 12, GATE, 8)
    page.text_box(x + 312, top, 180, 24, "random range", 15, MUTED)
    page.circle(x + 515, top + 12, 7, WHITE, GATE, 3)
    page.text_box(x + 530, top, 180, 24, "random mean", 15, MUTED)
    rows = [
        ("QKV-only lesion", "74 input groups; n=100", 80, 92, 84.84, 86.03, 89.78, 88.02, "0/100 random as damaging"),
        ("Full QKV+dense lesion", "+18 dense tensors; n=100", 0, 40, 16.83, 8.71, 36.33, 16.33, "63/100 random as damaging"),
    ]
    for i, (label, detail, lo_axis, hi_axis, target, lo, hi, avg, result) in enumerate(rows):
        row_top = top + 52 + i * 86
        page.text_box(x, row_top, 245, 25, label, 18, INK, True)
        page.text_box(x, row_top + 27, 245, 22, detail, 15, MUTED)
        axis_x, axis_w = x + 310, width - 560
        sx = lambda value: axis_x + (value - lo_axis) / (hi_axis - lo_axis) * axis_w
        page.line(axis_x, row_top + 26, axis_x + axis_w, row_top + 26, RULE, 2)
        page.line(sx(lo), row_top + 26, sx(hi), row_top + 26, GATE, 10)
        page.circle(sx(avg), row_top + 26, 7, WHITE, GATE, 3)
        diamond(page, sx(target), row_top + 26, 9, LESION)
        page.text_box(axis_x, row_top + 52, axis_w, 22, f"axis: {lo_axis}% to {hi_axis}% POS accuracy", 14, MUTED, False, "center")
        page.text_box(x + width - 250, row_top + 8, 250, 25, result, 15, BLUE, True, "right")


def recolor_reference_style(drawing: Drawing) -> None:
    """Apply the restrained blue/teal/brick palette used by the reference-style copy."""
    replacements = [(BLUE, "#214C72"), (PALE_BLUE, "#F2F5F7"), (GATE, "#347B70"), (READOUT, "#9A4B69"), (ENCODER, "#B36B32"), (DAMAGE, "#A64E43"), (RULE, "#BEC6CC"), (SOFT, "#F7F7F5")]
    for item in drawing.getContents():
        for attribute in ("fillColor", "strokeColor"):
            current = getattr(item, attribute, None)
            for source, target in replacements:
                if current == HexColor(source):
                    setattr(item, attribute, HexColor(target))


def poster(site: dict, tokens: list[dict[str, str]], geometry_draft: bool = False, gate_state_version: bool = False, editorial_style: bool = False) -> Drawing:
    """Compose the A0 portrait poster as measured vector primitives."""
    drawing = Drawing(W, H)
    drawing.initialFontName = REGULAR
    page = Page(drawing, H)
    page.rect(0, 0, W, H, WHITE)
    if gate_state_version:
        page.image(85, 72, 136, 136, UNITN_LOGO)
    page.text_box(240 if gate_state_version else 80, 38, 2064 if gate_state_version else 2224, 90, "Multiple Recovery Paths in a Lesioned Transformer", 70 if gate_state_version else 73, INK, True, "center")
    page.text_box(80, 132, 2224, 68, "Internal Rerouting and Readout Remapping", 51, BLUE, True, "center")
    page.text_box(80, 219, 2224, 40, "Lorenzo Cannata   |   Uri Hasson", 29, INK, True, "center")
    venue = "BlackboxNLP 2026   |   Poster #192" if gate_state_version else "BlackboxNLP 2026   |   Main Track   |   Poster #192"
    page.text_box(80, 269, 2224, 32, venue, 20, BLUE, True, "center")
    page.line(80, 322, 2304, 322, BLUE, 3)

    section_heading(page, 80, 350, 2224, "Motivation")
    motivation = (
        "Using BERT as a frozen encoder and a linear part-of-speech (POS) readout as a task classifier, we first use gate masking to learn a sparse core subnetwork sufficient for POS classification. "
        "We then ablate this subnetwork to produce a large drop in performance. "
        "Our main question is whether performance can recover by adapting the surviving projection-specific gates, retraining the linear POS readout, or both."
    )
    page.text_box(80, 419, 1450, 158, motivation, 24, INK, False, "left", 33, True)
    if editorial_style:
        page.line(1585, 420, 1585, 576, BLUE, 6)
    else:
        page.rect(1585, 415, 719, 166, PALE_BLUE)
    page.text_box(1616, 433, 657, 26, "CENTRAL FINDING", 17, BLUE, True)
    finding = "Recovery can use internal rerouting or readout retraining; among fixed-weight routes, combining both recovers most without necessarily restoring the original representation." if gate_state_version else "Recovery of performance does not require recovery of the original representation."
    page.text_box(1616, 472, 657, 100, finding, 20 if gate_state_version else 27, INK, True, "left", 26 if gate_state_version else 35, True)

    draw_framework(page, 620, plain_lesion=gate_state_version, editorial=editorial_style)

    left_x, right_x, col_w = 80, 1230, 1074
    section_heading(page, left_x, 1515, col_w, "Performance and gate state" if gate_state_version else "Recovery performance", "Five-run accuracy · primary-run gates" if gate_state_version else "Mean across five seeds")
    if gate_state_version:
        draw_performance_and_gates(page, site, left_x, 1586, col_w, 440)
        gate_note = "Circles are individual runs; squares are means. Gate state at the primary-run endpoint: active p > 0.99, inactive p < 0.01, otherwise intermediate. Lesioned entries are held at -12 and cannot change during recovery."
        page.text_box(left_x, 2040, col_w, 116, gate_note, 17, MUTED, False, "left", 24, True)
    else:
        draw_performance(page, site, left_x, 1586, col_w, 440)
        page.text_box(left_x, 2040, col_w, 116, "All recovery conditions produced marked improvement over the damaged baseline. Filled squares show arithmetic means across five full-pipeline runs. Open circles are individual runs; capped spans show observed min-max ranges, not confidence intervals. The gate-only result is the density-promoting variant.", 18, MUTED, False, "left", 25, True)

    section_heading(page, right_x, 1515, col_w, "Accuracy versus representation", "Primary run")
    draw_cka(page, site, right_x, 1586, col_w, 440)
    cka_note = "Linear CKA compares each condition's final hidden states with the pre-lesion core. Readout-only preserves the damaged hidden states (CKA 0.43) while primary-run accuracy rises from 16.82% to 80.00%."
    page.text_box(right_x, 2040, col_w, 116, cka_note if gate_state_version else "Representational analysis showed that behavioral recovery was not necessarily accompanied by restoration of the original hidden-state geometry. CKA measures hidden-state similarity, not recovered circuitry. Readout-only leaves encoder states unchanged yet raises primary-run accuracy from 16.82% to 80.00%.", 18, MUTED, False, "left", 25, True)

    if geometry_draft or gate_state_version:
        section_heading(page, 80, 2200, 2224, "Encoder and readout geometry change differently across recovery paths" if gate_state_version else "Different recovery constraints produce different representational geometries")
        draw_readout_stack(page, tokens, 80, 2272, 760, 470)
        draw_geometry_plane(page, site, 890, 2272, 1414, 470)
        page.circle(96, 2780, 5, BLUE)
        page.text_box(110, 2769, 175, 22, "correct", 15, MUTED)
        cross(page, 300, 2780, 4, DAMAGE, 1.6)
        page.text_box(314, 2769, 180, 22, "incorrect", 15, MUTED)
        page.text_box(80, 2798, 760, 58, "Coordinates are fixed across panels; only correctness under the original versus retrained readout changes. The shared core-fitted PC1-PC2 view explains 23.32% of core variance, while classification uses all 768 dimensions.", 15, MUTED, False, "left", 21, True)
        page.text_box(890, 2798, 1414, 58, "Readout-only holds encoder POS-centroid similarity at 0.33 while readout-weight similarity changes from 1.00 to 0.54 and accuracy reaches 80.0%. Gate-only and joint recovery also move the encoder geometry.", 15, MUTED, False, "left", 21, True)
    else:
        section_heading(page, 80, 2200, 2224, "Readout remapping recovers performance without changing encoder geometry")
        page.text_box(80, 2262, 2224, 31, "SAME TOKEN REPRESENTATIONS; ONLY THE LINEAR READOUT CHANGES", 20, READOUT, True, "center")
        draw_readout(page, tokens, 80, 2305, 2224, 445)
        page.circle(100, 2782, 6, BLUE)
        page.text_box(115, 2770, 240, 24, "correct under shown readout", 16, MUTED)
        cross(page, 390, 2782, 5, DAMAGE, 2)
        page.text_box(405, 2770, 250, 24, "incorrect under shown readout", 16, MUTED)
        page.text_box(710, 2766, 1594, 73, "The damaged configuration contained task-relevant information that was poorly aligned with the original readout. Both panels show the same 816 POS-balanced token coordinates in one core-fitted PCA basis and shared scale; markers report correctness under each 768-dimensional readout. PC1-PC2 explain 23.32% of core variance and are not the classifier decision space.", 17, MUTED, False, "left", 24, True)

    section_heading(page, 80, 2895, 1450, "Robustness and controls")
    draw_controls(page, 80, 2965, 1450)
    controls_note = "Matched controls give different answers. The targeted Q/K/V-only lesion is more damaging than all 100 random 74-group lesions. For the full Q/K/V+dense lesion, 63/100 random matches are equally or more damaging; its severe endpoint is common under matched random targets."
    page.text_box(80, 3177, 1450, 64, controls_note if gate_state_version else "The QKV-only control supports enrichment relative to globally random QKV groups. The full random QKV+dense control does not establish unique specificity of the exact dense target set; it qualifies the causal interpretation of the severe lesion.", 16, MUTED, False, "left", 22, True)

    section_heading(page, 1580, 2895, 724, "Conclusions")
    page.text_box(1580, 2965, 724, 76, "Performance can recover without relearning the underlying transformations.", 22, INK, True, "left", 30, True)
    page.text_box(1580, 3050, 724, 68, "The extent to which the original geometry is recovered depends on the degrees of freedom of the recovery protocol.", 18, INK, False, "left", 25, True)
    page.text_box(1580, 3125, 724, 92, "Circuit necessity is conditional on the permitted rerouting strategy. A component may be necessary under the original fixed routing and readout, but cease to be so when the readout can be retrained or surviving transformations can be reselected.", 16, INK, False, "left", 22, True)
    limitations = "LIMITATIONS\nOur evaluations were based on a single task and a single backbone model." if gate_state_version else "Our evaluations were based on a single task and a single backbone model. The biological relevance of these findings remains unclear."
    page.text_box(1580, 3222, 724, 48, limitations, 14, MUTED, gate_state_version, "left", 19, True)

    page.line(80, 3290, 2304, 3290, RULE, 2)
    page.text_box(80, 3303, 1500, 28, "Methods: Louizos et al. (2018); Cao et al. (2021). Data: Universal Dependencies English-EWT.", 15, MUTED)
    page.text_box(1600, 3303, 704, 28, "BlackboxNLP 2026   |   Poster #192", 15, MUTED, False, "right")
    if editorial_style:
        recolor_reference_style(drawing)
    return drawing


def reusable_figure(width: int, height: int, draw) -> Drawing:
    """Create a white standalone vector canvas for one poster figure."""
    drawing = Drawing(width, height)
    drawing.initialFontName = REGULAR
    page = Page(drawing, height)
    page.rect(0, 0, width, height, WHITE)
    draw(page)
    return drawing


def write_pdf(drawing: Drawing, path: Path) -> None:
    """Write one vector PDF page with embedded Bitstream Vera fonts."""
    pdf = canvas.Canvas(
        str(path),
        pagesize=(drawing.width, drawing.height),
        pageCompression=1,
        initialFontName=REGULAR,
        invariant=1,
    )
    pdf.setTitle("Multiple Recovery Paths in a Lesioned Transformer")
    pdf.setAuthor("Lorenzo Cannata and Uri Hasson")
    pdf.setSubject("BlackboxNLP 2026 conference poster")
    renderPDF.draw(drawing, pdf, 0, 0)
    pdf.showPage()
    pdf.save()


def write_editable_svg(drawing: Drawing, path: Path, title: str, description: str) -> None:
    """Write live-text SVG with embedded redistributable fonts and weights."""
    renderSVG.drawToFile(drawing, str(path))
    regular_data = base64.b64encode(FONT_PATH.read_bytes()).decode("ascii")
    bold_data = base64.b64encode(BOLD_PATH.read_bytes()).decode("ascii")
    font_style = (
        "<style type=\"text/css\"><![CDATA["
        "@font-face{font-family:'Bitstream Vera Sans';font-style:normal;font-weight:400;src:url(data:font/ttf;base64,"
        + regular_data
        + ") format('truetype');}"
        "@font-face{font-family:'Bitstream Vera Sans';font-style:normal;font-weight:700;src:url(data:font/ttf;base64,"
        + bold_data
        + ") format('truetype');}"
        "]]></style>"
    )
    svg = path.read_text()
    svg = svg.replace(f"font-family: {BOLD};", "font-family: 'Bitstream Vera Sans'; font-weight: 700;")
    svg = svg.replace(f"font-family: {REGULAR};", "font-family: 'Bitstream Vera Sans'; font-weight: 400;")
    svg = svg.replace('<svg width="2384" height="3370"', '<svg width="841mm" height="1189mm"')
    svg = svg.replace("<title>...</title>", f"<title>{title}</title>")
    svg = svg.replace("<desc>...</desc>", f"<desc>{description}</desc>{font_style}")
    path.write_text(svg)


def find_binary(name: str) -> str:
    """Find Poppler in PATH or the bundled Codex runtime."""
    located = shutil.which(name)
    if located:
        return located
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/poppler/bin" / name
    if bundled.exists():
        return str(bundled)
    raise RuntimeError(f"{name} is required; install Poppler and rerun the generator")


def write_outlined_svg(pdf_path: Path, svg_path: Path) -> None:
    """Convert the embedded-font PDF to portable SVG glyph outlines."""
    subprocess.run([find_binary("pdftocairo"), "-svg", str(pdf_path), str(svg_path)], check=True)
    svg = svg_path.read_text().replace('width="2384pt" height="3370pt"', 'width="841mm" height="1189mm"')
    svg_start = svg.find("<svg")
    first_close = svg.find(">", svg_start) + 1
    metadata = "\n<title>Multiple Recovery Paths in a Lesioned Transformer</title>\n<desc>A0 portrait poster with all text converted to vector outlines.</desc>"
    svg_path.write_text(svg[:first_close] + metadata + svg[first_close:])
    if "<text" in svg_path.read_text():
        raise RuntimeError("Outlined SVG unexpectedly contains live text")


def write_png(pdf_path: Path, png_path: Path) -> None:
    """Render the print PDF to a 150 dpi PNG preview."""
    subprocess.run([find_binary("pdftoppm"), "-f", "1", "-singlefile", "-r", "150", "-png", str(pdf_path), str(png_path.with_suffix(""))], check=True)


def main() -> None:
    """Generate editable, outlined, print, preview, and reusable vector artifacts."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    site, tokens = load_data()
    drawing = poster(site, tokens)
    editable_svg = FIGURES / "recovery-paths-poster.svg"
    pdf_path = FIGURES / "recovery-paths-poster.pdf"
    outlined_svg = FIGURES / "recovery-paths-poster-outlined.svg"
    png_path = FIGURES / "recovery-paths-poster.png"

    write_editable_svg(drawing, editable_svg, "Multiple Recovery Paths in a Lesioned Transformer", "Editable A0 portrait BlackboxNLP 2026 poster with embedded live-text fonts.")
    write_pdf(drawing, pdf_path)
    write_outlined_svg(pdf_path, outlined_svg)
    write_png(pdf_path, png_path)

    geometry_draft = poster(site, tokens, geometry_draft=True)
    draft_svg = FIGURES / "recovery-paths-poster-geometry-draft.svg"
    draft_pdf = FIGURES / "recovery-paths-poster-geometry-draft.pdf"
    draft_png = FIGURES / "recovery-paths-poster-geometry-draft.png"
    write_editable_svg(geometry_draft, draft_svg, "Recovery paths geometry draft", "Alternate A0 poster draft emphasizing encoder and readout geometry.")
    write_pdf(geometry_draft, draft_pdf)
    write_png(draft_pdf, draft_png)

    gate_state = poster(site, tokens, gate_state_version=True)
    gate_svg = FIGURES / "recovery-paths-poster-gate-state.svg"
    gate_pdf = FIGURES / "recovery-paths-poster-gate-state.pdf"
    gate_outline = FIGURES / "recovery-paths-poster-gate-state-outlined.svg"
    gate_png = FIGURES / "recovery-paths-poster-gate-state.png"
    write_editable_svg(gate_state, gate_svg, "Recovery paths poster with gate state", "A0 poster combining five-run recovery accuracy with primary-run effective gate composition.")
    write_pdf(gate_state, gate_pdf)
    write_outlined_svg(gate_pdf, gate_outline)
    write_png(gate_pdf, gate_png)

    reference_style = poster(site, tokens, gate_state_version=True, editorial_style=True)
    reference_svg = FIGURES / "recovery-paths-poster-reference-style.svg"
    reference_pdf = FIGURES / "recovery-paths-poster-reference-style.pdf"
    reference_outline = FIGURES / "recovery-paths-poster-reference-style-outlined.svg"
    reference_png = FIGURES / "recovery-paths-poster-reference-style.png"
    write_editable_svg(reference_style, reference_svg, "Recovery paths poster - reference style", "A0 poster with restrained academic colors and flat trainability tables.")
    write_pdf(reference_style, reference_pdf)
    write_outlined_svg(reference_pdf, reference_outline)
    write_png(reference_pdf, reference_png)

    figures = {
        "poster-recovery-performance.svg": reusable_figure(1074, 440, lambda page: draw_performance(page, site, 0, 0, 1074, 440)),
        "poster-accuracy-cka.svg": reusable_figure(1074, 440, lambda page: draw_cka(page, site, 0, 0, 1074, 440)),
        "poster-readout-remapping.svg": reusable_figure(2224, 445, lambda page: draw_readout(page, tokens, 0, 0, 2224, 445)),
        "poster-recovery-geometry.svg": reusable_figure(1414, 470, lambda page: draw_geometry_plane(page, site, 0, 0, 1414, 470)),
    }
    for filename, figure in figures.items():
        write_editable_svg(figure, FIGURES / filename, filename.removesuffix(".svg"), "Reusable vector figure from the BlackboxNLP 2026 poster.")
    print("Generated A0 PDF, live-text SVG, outlined SVG, PNG preview, and reusable SVG figures")


if __name__ == "__main__":
    main()
