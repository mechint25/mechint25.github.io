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
from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assets" / "data"
FIGURES = ROOT / "assets" / "figures"
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


def draw_pipeline(page: Page, top: float) -> None:
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
    page.text_box(1210, top + 172, 220, 20, "one 768-d vector per token", 15, MUTED, False, "center")

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


def status_cell(page: Page, x: float, top: float, width: float, value: str, color: str) -> None:
    """Draw an explicit trainability cell without reusing gate-state symbols."""
    fill = color if value == "TRAIN" else SOFT
    stroke = color if value in {"TRAIN", "OFF"} else RULE
    text_color = WHITE if value == "TRAIN" else color
    page.rect(x, top, width, 31, fill, stroke, 3, 1.5)
    page.text_box(x, top + 3, width, 23, value, 14, text_color, True, "center")


def draw_framework(page: Page, top: float) -> None:
    """Draw the dominant method figure and recovery trainability table."""
    section_heading(page, 80, top, 2224, "Experimental framework")
    draw_pipeline(page, top + 72)

    band_top = top + 365
    page.text_box(80, band_top, 500, 27, "EXPERIMENTAL PROGRESSION", 18, ENCODER, True)
    a_x, a_w = 80, 575
    b_x, b_w = 710, 470
    c_x, c_w = 1235, 1069
    box_top, box_h = band_top + 42, 338
    for x, width in [(a_x, a_w), (b_x, b_w), (c_x, c_w)]:
        page.rect(x, box_top, width, box_h, WHITE, RULE, 5, 1.5)

    page.text_box(a_x + 22, box_top + 18, a_w - 44, 32, "A  Learn the task-sufficient core", 23, BLUE, True)
    page.text_box(a_x + 22, box_top + 67, a_w - 44, 88, "Train projection-specific hard-concrete gates and the linear POS readout while pretrained encoder weights remain fixed.", 19, INK, False, "left", 27, True)
    page.text_box(a_x + 22, box_top + 176, 165, 25, "Gates", 18, GATE, True)
    status_cell(page, a_x + 205, box_top + 171, 105, "TRAIN", GATE)
    page.text_box(a_x + 22, box_top + 219, 165, 25, "Readout", 18, READOUT, True)
    status_cell(page, a_x + 205, box_top + 214, 105, "TRAIN", READOUT)
    page.text_box(a_x + 22, box_top + 262, 175, 25, "Encoder weights", 18, ENCODER, True)
    status_cell(page, a_x + 205, box_top + 257, 105, "FIXED", ENCODER)
    page.text_box(a_x + 335, box_top + 174, 215, 105, "The sparse configuration reaches 94.98% primary-run POS accuracy.", 18, MUTED, False, "left", 26, True)

    page.text_box(b_x + 22, box_top + 18, b_w - 44, 32, "B  Apply a permanent lesion", 23, BLUE, True)
    cross(page, b_x + 58, box_top + 100, 19, LESION, 6)
    page.text_box(b_x + 96, box_top + 72, b_w - 120, 72, "Mask scores forced to -12; effective gates are zero and gradients are blocked.", 18, INK, True, "left", 26, True)
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
            status_cell(page, table_x + offset + 15, row_top, width - 30, value, colors[col_index])
        if row_index < len(rows) - 1:
            page.line(table_x, row_top + 44, c_x + c_w - 22, row_top + 44, SOFT, 1)

    page.arrow(a_x + a_w + 10, box_top + 47, b_x - 10, box_top + 47, ENCODER, 3, 12)
    page.arrow(b_x + b_w + 10, box_top + 47, c_x - 10, box_top + 47, ENCODER, 3, 12)

    strip_top = top + 765
    page.rect(80, strip_top, 2224, 80, PALE_BLUE)
    page.text_box(104, strip_top + 10, 130, 24, "SETUP", 16, BLUE, True)
    page.text_box(240, strip_top + 10, 1000, 24, "bert-base-uncased | UD English-EWT | 17 POS tags | 25,147 development tokens", 17, INK)
    page.text_box(104, strip_top + 43, 130, 24, "LESION", 16, BLUE, True)
    page.text_box(240, strip_top + 43, 1220, 24, "74 Q/K/V groups + 18 dense projection-mask tensors; 37,248 gate entries clamped", 17, INK)
    page.text_box(1520, strip_top + 9, 750, 52, "Schematic only: arrows show computation or experimental progression, not measured activation flow or traced causal paths.", 15, MUTED, False, "right", 22, True)


def draw_performance(page: Page, site: dict, x: float, top: float, width: float, height: float) -> None:
    """Draw five-seed endpoint means, observed ranges, and individual runs."""
    keys = ["core", "encoder_only", "readout_and_mask_reg", "readout_only", "mask_only_inverse_reg", "damage"]
    colors = [BLUE, ENCODER, READOUT, READOUT, GATE, DAMAGE]
    labels = ["Core", "Encoder only", "Gates + readout", "Readout only", "Gates only, dense", "Damaged"]
    chart_x, chart_w = x + 260, width - 360
    page.rect(x + 8, top + 4, 18, 13, BLUE)
    page.text_box(x + 34, top, 150, 24, "mean", 16, MUTED)
    page.circle(x + 198, top + 11, 6, WHITE, BLUE, 2)
    page.text_box(x + 212, top, 160, 24, "individual run", 16, MUTED)
    page.line(x + 402, top + 11, x + 470, top + 11, BLUE, 3)
    page.text_box(x + 482, top, 190, 24, "observed range", 16, MUTED)
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
        page.rect(chart_x, cy - 5, chart_w * avg / 100, 18, color, radius=3)
        page.line(chart_x + chart_w * lo / 100, cy + 20, chart_x + chart_w * hi / 100, cy + 20, color, 3)
        for value_index, value in enumerate(values):
            jitter = [-4, -2, 0, 2, 4][value_index]
            page.circle(chart_x + chart_w * value / 100, cy + 20 + jitter, 5, WHITE, color, 2)
        page.text_box(x + width - 82, cy - 9, 82, 28, f"{avg:.2f}%", 18, color, True, "right")
    page.line(chart_x, axis_bottom, chart_x + chart_w, axis_bottom, INK, 1.5)
    page.text_box(chart_x, top + height - 32, chart_w, 28, "Held-out POS accuracy (%)", 19, MUTED, False, "center")


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
    damage_x = sx(site["conditions"]["damage"]["cka_core"])
    page.line(damage_x, sy(16.82), damage_x, sy(80.00), READOUT, 4, [8, 7])
    page.text_box(damage_x + 16, sy(54), 250, 48, "identical encoder states", 16, READOUT, True, "left", 21, True)
    offsets = {
        "damage": (14, 9, "left"),
        "readout_only": (14, -29, "left"),
        "readout_and_mask_reg": (14, -29, "left"),
        "mask_only_inverse_reg": (14, 9, "left"),
        "encoder_only": (-220, -29, "right"),
        "core": (-150, -29, "right"),
    }
    for key in keys:
        condition = site["conditions"][key]
        px, py = sx(condition["cka_core"]), sy(condition["accuracy"])
        page.circle(px, py, 10, colors[key], WHITE, 3)
        dx, dy, align = offsets[key]
        label_width = 210 if align == "right" else 250
        page.text_box(px + dx - (label_width if align == "right" else 0), py + dy, label_width, 27, labels[key], 17, INK, True, align)
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


def poster(site: dict, tokens: list[dict[str, str]]) -> Drawing:
    """Compose the A0 portrait poster as measured vector primitives."""
    drawing = Drawing(W, H)
    drawing.initialFontName = REGULAR
    page = Page(drawing, H)
    page.rect(0, 0, W, H, WHITE)
    page.text_box(80, 38, 2224, 90, "Multiple Recovery Paths in a Lesioned Transformer", 73, INK, True, "center")
    page.text_box(80, 132, 2224, 68, "Internal Rerouting and Readout Remapping", 51, BLUE, True, "center")
    page.text_box(80, 219, 2224, 40, "Lorenzo Cannata   |   Uri Hasson", 29, INK, True, "center")
    page.text_box(80, 269, 2224, 32, "BlackboxNLP 2026   |   Main Track   |   Poster #192", 20, BLUE, True, "center")
    page.line(80, 322, 2304, 322, BLUE, 3)

    section_heading(page, 80, 350, 2224, "Motivation")
    motivation = (
        "Using BERT as a frozen encoder and a linear part-of-speech (POS) readout as a task classifier, we first use gate masking to learn a sparse core subnetwork sufficient for POS classification. "
        "We then ablate this subnetwork to produce a large drop in performance. "
        "Our main question is whether recovery can be achieved by reselecting surviving projection-specific gates, remapping a learned readout, or both."
    )
    page.text_box(80, 419, 1450, 158, motivation, 24, INK, False, "left", 33, True)
    page.rect(1585, 415, 719, 166, PALE_BLUE)
    page.text_box(1616, 433, 657, 26, "CENTRAL FINDING", 17, BLUE, True)
    page.text_box(1616, 472, 657, 92, "Recovery of performance does not require recovery of the original representation.", 27, INK, True, "left", 35, True)

    draw_framework(page, 620)

    left_x, right_x, col_w = 80, 1230, 1074
    section_heading(page, left_x, 1515, col_w, "Recovery performance", "Mean across five seeds")
    draw_performance(page, site, left_x, 1586, col_w, 440)
    page.text_box(left_x, 2040, col_w, 116, "All recovery conditions produced marked improvement over the damaged baseline. Bars show arithmetic means across five full-pipeline runs. Open circles are individual runs; lines show observed ranges, not confidence intervals. The gate-only result is the density-promoting variant.", 18, MUTED, False, "left", 25, True)

    section_heading(page, right_x, 1515, col_w, "Accuracy versus representation", "Primary run")
    draw_cka(page, site, right_x, 1586, col_w, 440)
    page.text_box(right_x, 2040, col_w, 116, "Representational analysis showed that behavioral recovery was not necessarily accompanied by restoration of the original hidden-state geometry. CKA measures hidden-state similarity, not recovered circuitry. Readout-only leaves encoder states unchanged yet raises primary-run accuracy from 16.82% to 80.00%.", 18, MUTED, False, "left", 25, True)

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
    page.text_box(80, 3177, 1450, 64, "The QKV-only control supports enrichment relative to globally random QKV groups. The full random QKV+dense control does not establish unique specificity of the exact dense target set; it qualifies the causal interpretation of the severe lesion.", 16, MUTED, False, "left", 22, True)

    section_heading(page, 1580, 2895, 724, "Conclusions")
    page.text_box(1580, 2965, 724, 76, "Performance can recover without relearning the underlying transformations.", 22, INK, True, "left", 30, True)
    page.text_box(1580, 3050, 724, 68, "The extent to which the original geometry is recovered depends on the degrees of freedom of the recovery protocol.", 18, INK, False, "left", 25, True)
    page.text_box(1580, 3125, 724, 92, "Circuit necessity is conditional on the permitted rerouting strategy. A component may be necessary under the original fixed routing and readout, but cease to be so when the readout can be retrained or surviving transformations can be reselected.", 16, INK, False, "left", 22, True)
    page.text_box(1580, 3222, 724, 48, "Our evaluations were based on a single task and a single backbone model. The biological relevance of these findings remains unclear.", 14, MUTED, False, "left", 19, True)

    page.line(80, 3290, 2304, 3290, RULE, 2)
    page.text_box(80, 3303, 1500, 28, "Methods: Louizos et al. (2018); Cao et al. (2021). Data: Universal Dependencies English-EWT.", 15, MUTED)
    page.text_box(1600, 3303, 704, 28, "BlackboxNLP 2026   |   Poster #192", 15, MUTED, False, "right")
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

    figures = {
        "poster-recovery-performance.svg": reusable_figure(1074, 440, lambda page: draw_performance(page, site, 0, 0, 1074, 440)),
        "poster-accuracy-cka.svg": reusable_figure(1074, 440, lambda page: draw_cka(page, site, 0, 0, 1074, 440)),
        "poster-readout-remapping.svg": reusable_figure(2224, 445, lambda page: draw_readout(page, tokens, 0, 0, 2224, 445)),
    }
    for filename, figure in figures.items():
        write_editable_svg(figure, FIGURES / filename, filename.removesuffix(".svg"), "Reusable vector figure from the BlackboxNLP 2026 poster.")
    print("Generated A0 PDF, live-text SVG, outlined SVG, PNG preview, and reusable SVG figures")


if __name__ == "__main__":
    main()
