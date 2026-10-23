#!/usr/bin/env python3
"""Generate the empirical readout asset and the A0 portrait conference poster."""

from __future__ import annotations

import csv
import json
from pathlib import Path

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
LIGHT, SOFT = "#F5F8FA", "#E8EDF1"
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial.ttf"
BOLD_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
pdfmetrics.registerFont(TTFont("PosterSans", FONT_PATH))
pdfmetrics.registerFont(TTFont("PosterSans-Bold", BOLD_PATH))


class Page:
    """Small top-origin drawing helper used by the poster and reusable figures."""

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

    def text(self, x: float, top: float, value: str, size: float, color: str = INK, bold: bool = False, anchor: str = "start") -> None:
        self.drawing.add(String(x, self.height - top - size, value, fontName="PosterSans-Bold" if bold else "PosterSans", fontSize=size, fillColor=HexColor(color), textAnchor=anchor))

    def circle(self, x: float, top: float, radius: float, fill: str, stroke: str | None = None, width: float = 1) -> None:
        self.drawing.add(Circle(x, self.height - top, radius, fillColor=HexColor(fill), strokeColor=HexColor(stroke) if stroke else None, strokeWidth=width))

    def polygon(self, points: list[tuple[float, float]], fill: str, stroke: str | None = None, width: float = 1) -> None:
        flat = [coordinate for x, top in points for coordinate in (x, self.height - top)]
        self.drawing.add(Polygon(flat, fillColor=HexColor(fill), strokeColor=HexColor(stroke) if stroke else None, strokeWidth=width))


def wrap(page: Page, text: str, x: float, top: float, width: float, size: float = 27, leading: float = 36, color: str = INK, bold: bool = False) -> float:
    """Draw plain wrapped text and return the next top coordinate."""
    font = "PosterSans-Bold" if bold else "PosterSans"
    line = ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and pdfmetrics.stringWidth(candidate, font, size) > width:
            page.text(x, top, line, size, color, bold)
            top += leading
            line = word
        else:
            line = candidate
    if line:
        page.text(x, top, line, size, color, bold)
        top += leading
    return top


def section(page: Page, x: float, top: float, width: float, name: str, subtitle: str | None = None) -> float:
    """Draw a navy section heading and optional descriptive figure title."""
    page.text(x, top, name, 39, BLUE, True)
    page.line(x, top + 52, x + width, top + 52, BLUE, 3)
    if subtitle:
        page.text(x, top + 68, subtitle, 29, INK, True)
        return top + 112
    return top + 70


def symbol(page: Page, x: float, top: float, kind: str, color: str, size: float = 18, active: bool = True) -> None:
    """Draw the redundant shape-and-colour parameter-status symbols."""
    fill = color if active else WHITE
    if kind == "gate":
        page.circle(x, top, size, fill, color, 4)
    elif kind == "readout":
        page.polygon([(x, top - size), (x + size, top), (x, top + size), (x - size, top)], fill, color, 4)
    elif kind == "encoder":
        page.polygon([(x, top - size), (x + size, top + size), (x - size, top + size)], fill, color, 4)
    else:
        page.line(x - size, top - size, x + size, top + size, color, 5)
        page.line(x + size, top - size, x - size, top + size, color, 5)


def load_data() -> tuple[dict, list[dict[str, str]]]:
    """Load verified endpoint/seed metrics and the shared-coordinate token sample."""
    site = json.loads((DATA / "site-data.json").read_text())
    with (DATA / "readout-empirical.csv").open(newline="") as stream:
        tokens = list(csv.DictReader(stream))
    if len(tokens) != 816:
        raise ValueError(f"Expected 816 paired tokens, found {len(tokens)}")
    return site, tokens


def draw_framework(page: Page, top: float) -> None:
    """Draw the large learn-lesion-recover schematic at implementation granularity."""
    y = section(page, 80, top, 2224, "Experimental framework", "Learn a sparse task-sufficient route, hold the lesion fixed, then vary what can adapt")
    cols = [(80, 690, "A", "Learn the sparse core"), (820, 520, "B", "Apply a permanent lesion"), (1390, 914, "C", "Compare recovery pathways")]
    for x, width, letter, title in cols:
        page.text(x, y, letter, 33, BLUE, True)
        page.text(x + 48, y + 2, title, 30, INK, True)
        page.line(x, y + 47, x + width, y + 47, RULE, 2)

    for i in range(5):
        layer_top = y + 92 + i * 55
        page.rect(118, layer_top, 330, 38, PALE_BLUE, BLUE, 6, 1.5)
        page.text(135, layer_top + 5, f"BERT layer {i if i < 4 else '... 11'}", 19, BLUE, True)
        for j in range(5):
            symbol(page, 485 + j * 38, layer_top + 19, "gate", GATE, 8, active=(i + j) % 3 != 0)
    page.line(448, y + 218, 650, y + 218, BLUE, 4)
    page.polygon([(650, y + 218), (630, y + 206), (630, y + 230)], BLUE)
    symbol(page, 688, y + 218, "readout", READOUT, 20)
    page.text(688, y + 255, "17-way POS readout", 19, READOUT, True, "middle")
    wrap(page, "Projection-specific hard-concrete gates and a linear readout train jointly; pretrained BERT weights remain fixed.", 118, y + 382, 610, 23, 31, MUTED)

    page.rect(860, y + 90, 430, 180, LIGHT, RULE, 8, 1.5)
    for i, label in enumerate(["Q / K / V", "Attn out", "FFN in", "FFN out"]):
        page.text(890, y + 112 + i * 37, label, 21, INK, i == 0)
        symbol(page, 1225, y + 124 + i * 37, "lesion", LESION, 11)
    page.text(1075, y + 300, "mask score = -12", 23, LESION, True, "middle")
    page.text(1075, y + 334, "gradient blocked", 22, LESION, False, "middle")
    wrap(page, "The selected mask entries are forced to zero and frozen. No recovery condition can reactivate a lesioned component.", 860, y + 382, 430, 23, 31, MUTED)

    pathways = [
        ("Gates only", True, False, False, "surviving gates change"),
        ("Readout only", False, True, False, "same damaged representation"),
        ("Gates + readout", True, True, False, "routing and interface adapt"),
        ("Encoder only", False, False, True, "surviving BERT weights change"),
    ]
    for i, (name, gates, readout, encoder, note) in enumerate(pathways):
        row = y + 82 + i * 86
        page.text(1420, row, name, 24, INK, True)
        symbol(page, 1745, row + 13, "gate", GATE, 13, gates)
        symbol(page, 1825, row + 13, "readout", READOUT, 13, readout)
        symbol(page, 1905, row + 13, "encoder", ENCODER, 13, encoder)
        symbol(page, 1985, row + 13, "lesion", LESION, 11)
        page.text(2040, row + 1, note, 20, MUTED)
        page.line(1420, row + 57, 2275, row + 57, SOFT, 1)
    for x, label, color in [(1745, "gates", GATE), (1825, "readout", READOUT), (1905, "encoder", ENCODER), (1985, "lesion", LESION)]:
        page.text(x, y + 438, label, 17, color, True, "middle")

    page.rect(80, y + 492, 2224, 100, PALE_BLUE)
    page.text(110, y + 515, "SETUP", 21, BLUE, True)
    page.text(245, y + 515, "bert-base-uncased  |  UD English-EWT  |  17 POS tags  |  25,147 held-out development tokens", 22, INK)
    page.text(110, y + 554, "LESION", 21, BLUE, True)
    page.text(245, y + 554, "74 Q/K/V 64-wide input groups + 5 attention-output + 9 FFN-intermediate + 4 FFN-output gate tensors", 22, INK)
    page.text(2304, y + 612, "Schematic: connections illustrate parameter status, not measured activation flow.", 19, MUTED, False, "end")


def draw_performance(page: Page, site: dict, x: float, top: float, width: float, height: float) -> None:
    """Draw five-seed endpoint means, observed ranges, and individual runs."""
    keys = ["core", "encoder_only", "readout_and_mask_reg", "readout_only", "mask_only_inverse_reg", "damage"]
    colors = [BLUE, ENCODER, READOUT, READOUT, GATE, DAMAGE]
    labels = ["Core", "Encoder only", "Gates + readout", "Readout only", "Gates only, dense", "Damaged"]
    chart_x, chart_w = x + 260, width - 340
    page.line(chart_x, top + height - 48, chart_x + chart_w, top + height - 48, INK, 2)
    for tick in range(0, 101, 20):
        px = chart_x + chart_w * tick / 100
        page.line(px, top + 28, px, top + height - 48, SOFT, 1)
        page.text(px, top + height - 37, str(tick), 18, MUTED, False, "middle")
    for i, (key, label, color) in enumerate(zip(keys, labels, colors)):
        values = site["seeds"][key]
        avg, lo, hi = sum(values) / len(values), min(values), max(values)
        cy = top + 53 + i * 59
        page.text(x + 230, cy - 9, label, 21, INK, key in {"readout_only", "damage"}, "end")
        page.rect(chart_x, cy - 4, chart_w * avg / 100, 20, color, radius=4)
        page.line(chart_x + chart_w * lo / 100, cy + 25, chart_x + chart_w * hi / 100, cy + 25, color, 4)
        for value in values:
            page.circle(chart_x + chart_w * value / 100, cy + 25, 6, WHITE, color, 3)
        page.text(x + width - 5, cy - 10, f"{avg:.2f}%", 21, color, True, "end")
    page.text(chart_x + chart_w / 2, top + height - 7, "Held-out POS accuracy (%)", 20, MUTED, False, "middle")


def draw_cka(page: Page, site: dict, x: float, top: float, width: float, height: float) -> None:
    """Draw primary-seed accuracy against linear CKA to the pre-lesion core."""
    keys = ["damage", "readout_only", "readout_and_mask_reg", "mask_only_inverse_reg", "encoder_only", "core"]
    labels = {"damage": "Damaged", "readout_only": "Readout only", "readout_and_mask_reg": "Gates + readout", "mask_only_inverse_reg": "Gates only, dense", "encoder_only": "Encoder only", "core": "Core"}
    colors = {"damage": DAMAGE, "readout_only": READOUT, "readout_and_mask_reg": READOUT, "mask_only_inverse_reg": GATE, "encoder_only": ENCODER, "core": BLUE}
    left, right, upper, lower = x + 92, x + width - 40, top + 30, top + height - 72
    sx = lambda value: left + (value - .4) / .62 * (right - left)
    sy = lambda value: lower - (value - 10) / 90 * (lower - upper)
    for tick in [.4, .5, .6, .7, .8, .9, 1.0]:
        px = sx(tick)
        page.line(px, upper, px, lower, SOFT, 1)
        page.text(px, lower + 12, f"{tick:.1f}", 17, MUTED, False, "middle")
    for tick in [20, 40, 60, 80, 100]:
        py = sy(tick)
        page.line(left, py, right, py, SOFT, 1)
        page.text(left - 16, py - 10, str(tick), 17, MUTED, False, "end")
    damage_x = sx(site["conditions"]["damage"]["cka_core"])
    page.line(damage_x, sy(16.82), damage_x, sy(80.00), READOUT, 4, [8, 7])
    page.text(damage_x + 18, sy(50), "same encoder states", 18, READOUT, True)
    offsets = {"damage": (14, 12), "readout_only": (14, -28), "readout_and_mask_reg": (14, -28), "mask_only_inverse_reg": (14, 12), "encoder_only": (-10, -30), "core": (-10, -30)}
    for key in keys:
        condition = site["conditions"][key]
        px, py = sx(condition["cka_core"]), sy(condition["accuracy"])
        page.circle(px, py, 10, colors[key], WHITE, 3)
        dx, dy = offsets[key]
        page.text(px + dx, py + dy, labels[key], 18, INK, True, "end" if dx < 0 else "start")
    page.text((left + right) / 2, top + height - 22, "Linear CKA to pre-lesion core", 20, MUTED, False, "middle")
    page.text(x + 15, top + 6, "POS accuracy (%)", 18, MUTED, True)


def bounds(tokens: list[dict[str, str]]) -> tuple[float, float, float, float]:
    """Return shared 1st-99th percentile PCA limits for the balanced token sample."""
    xs = sorted(float(row["pc1"]) for row in tokens)
    ys = sorted(float(row["pc2"]) for row in tokens)
    lo, hi = int(len(tokens) * .01), int(len(tokens) * .99)
    return xs[lo], xs[hi], ys[lo], ys[hi]


def draw_readout(page: Page, tokens: list[dict[str, str]], x: float, top: float, width: float, height: float) -> None:
    """Draw identical shared-PCA coordinates with original versus retrained predictions."""
    xmin, xmax, ymin, ymax = bounds(tokens)
    gap, panel_w = 100, (width - 100) / 2
    panels = [(x, "original_correct", "Original core readout", "49 / 816 subset correct", "16.82% full dev"), (x + panel_w + gap, "remapped_correct", "Retrained readout", "521 / 816 subset correct", "80.00% full dev")]
    for x0, field, title, subset, full in panels:
        page.rect(x0, top, panel_w, height, LIGHT, RULE, 8, 1.5)
        page.text(x0 + 24, top + 20, title, 25, INK, True)
        page.text(x0 + panel_w - 24, top + 20, subset, 21, READOUT if field.startswith("remapped") else DAMAGE, True, "end")
        page.text(x0 + panel_w - 24, top + 52, full, 18, MUTED, False, "end")
        plot_left, plot_top, plot_w, plot_h = x0 + 50, top + 92, panel_w - 82, height - 145
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
        page.text(x0 + panel_w / 2, top + height - 31, "PC1 (14.50%)", 18, MUTED, False, "middle")
        page.text(x0 + 12, top + 92, "PC2 (8.82%)", 17, MUTED)
    mid = x + width / 2
    page.line(mid - 35, top + height / 2, mid + 35, top + height / 2, READOUT, 5)
    page.polygon([(mid + 35, top + height / 2), (mid + 16, top + height / 2 - 11), (mid + 16, top + height / 2 + 11)], READOUT)
    page.text(mid, top + height / 2 - 42, "same points", 18, READOUT, True, "middle")


def draw_controls(page: Page, x: float, top: float, width: float) -> None:
    """Draw matched-random lesion summaries with intervention-specific axes."""
    rows = [
        ("QKV-only lesion", "74 input groups; n=100", 80, 92, 84.84, 86.03, 89.78, 88.02, "0/100 random as damaging"),
        ("Full QKV+dense lesion", "+18 dense tensors; n=100", 0, 40, 16.83, 8.71, 36.33, 16.33, "63/100 random as damaging"),
    ]
    for i, (label, detail, lo_axis, hi_axis, target, lo, hi, avg, result) in enumerate(rows):
        row_top = top + i * 94
        page.text(x, row_top, label, 22, INK, True)
        page.text(x, row_top + 31, detail, 18, MUTED)
        sx = lambda value: x + 390 + (value - lo_axis) / (hi_axis - lo_axis) * (width - 620)
        page.line(x + 390, row_top + 34, x + width - 230, row_top + 34, RULE, 3)
        page.line(sx(lo), row_top + 34, sx(hi), row_top + 34, GATE, 12)
        page.circle(sx(avg), row_top + 34, 8, WHITE, GATE, 4)
        symbol(page, sx(target), row_top + 34, "readout", LESION, 11)
        page.text(x + width, row_top + 4, result, 19, BLUE, True, "end")
        page.text(x + 390, row_top + 56, f"{lo_axis}%", 16, MUTED)
        page.text(x + width - 230, row_top + 56, f"{hi_axis}%", 16, MUTED, False, "end")


def poster(site: dict, tokens: list[dict[str, str]]) -> Drawing:
    """Compose the complete A0 portrait poster as vector primitives."""
    drawing = Drawing(W, H)
    drawing.initialFontName = "PosterSans"
    page = Page(drawing, H)
    page.rect(0, 0, W, H, WHITE)
    page.text(W / 2, 52, "Multiple Recovery Paths in a Lesioned Transformer", 82, INK, True, "middle")
    page.text(W / 2, 145, "Internal Rerouting and Readout Remapping", 64, BLUE, True, "middle")
    page.text(W / 2, 238, "Lorenzo Cannata  |  Uri Hasson", 34, INK, True, "middle")
    page.text(W / 2, 298, "BlackboxNLP 2026  |  Main Track  |  Poster #192", 23, BLUE, True, "middle")
    page.line(80, 360, 2304, 360, BLUE, 4)

    y = section(page, 80, 405, 2224, "Motivation")
    motivation = ("A pretrained BERT encoder and a learned linear readout classify each word into one of 17 part-of-speech categories. "
                  "A large immediate accuracy drop after removing a learned sparse, task-sufficient configuration establishes necessity only for that fixed routing and readout. "
                  "Allowing the residual model to adapt asks a second question: can performance return through another route, and must that recovery restore the original hidden-state representation?")
    wrap(page, motivation, 80, y, 1500, 28, 38)
    page.rect(1640, y - 14, 664, 178, PALE_BLUE)
    page.text(1680, y + 10, "CENTRAL FINDING", 21, BLUE, True)
    wrap(page, "High POS accuracy can return without restoring the pre-lesion encoder geometry.", 1680, y + 50, 570, 31, 40, INK, True)

    draw_framework(page, 680)

    left_x, right_x, col_w = 80, 1230, 1074
    y_left = section(page, left_x, 1510, col_w, "Recovery results", "Five-seed recovery preserves the same ordering")
    draw_performance(page, site, left_x, y_left, col_w, 430)
    wrap(page, "Bars are means across five independent full-pipeline seeds; circles are individual runs and short lines show the observed range, not confidence intervals. The displayed gate-only result is the density-promoting variant. Mask-only recovery is visibly more seed-sensitive than readout, joint, or encoder recovery.", left_x, y_left + 450, col_w, 23, 31, MUTED)

    y_right = section(page, right_x, 1510, col_w, "Representational analysis", "Performance and return to the core representation diverge")
    draw_cka(page, site, right_x, y_right, col_w, 430)
    wrap(page, "Linear centered kernel alignment (CKA) measures hidden-state similarity, not recovered circuitry. Primary-seed endpoints are shown because matching representations are available for that run. Readout-only stays at the damaged model's CKA by construction while accuracy rises from 16.82% to 80.00%.", right_x, y_right + 450, col_w, 23, 31, MUTED)

    readout_y = section(page, 80, 2280, 2224, "Representational analysis", "A new readout extracts useful POS information from the same damaged representation")
    draw_readout(page, tokens, 80, readout_y, 2224, 400)
    page.circle(112, readout_y + 433, 7, BLUE)
    page.text(132, readout_y + 420, "correct prediction", 19, MUTED)
    symbol(page, 360, readout_y + 433, "lesion", DAMAGE, 7)
    page.text(380, readout_y + 420, "incorrect prediction", 19, MUTED)
    wrap(page, "Both panels contain the same POS-balanced sample of 816 token identities in one PCA basis fitted on the pre-lesion core. Coordinates remain identical; only the 17-way linear readout changes. Subset counts illustrate prediction changes; 16.82% and 80.00% are full-development accuracies over 25,147 tokens. PC1-PC2 show 23.32% of variance, not the full 768-dimensional classifier space.", 730, readout_y + 412, 1574, 20, 27, MUTED)

    controls_y = section(page, 80, 2945, 1450, "Robustness and controls", "Random lesions qualify what the structural intervention establishes")
    draw_controls(page, 80, controls_y, 1450)
    wrap(page, "QKV-only controls support enrichment relative to global random groups. Full QKV+dense controls do not establish unique specificity of the exact dense target set; they validate recovery from a severe structured lesion.", 80, controls_y + 202, 1450, 17, 23, MUTED)

    conclusions_y = section(page, 1580, 2945, 724, "Conclusions")
    wrap(page, "A sparse route can be necessary in the original fixed model yet cease to be necessary once surviving parameters adapt. Readout remapping, internal rerouting, and encoder-weight retraining recover different amounts of behavior and geometry.", 1580, conclusions_y, 724, 22, 29, INK, True)
    wrap(page, "Scope: one BERT backbone, one supervised POS task, and a learned task readout. Recovery depends on which components may adapt; these experiments do not establish biological recovery mechanisms.", 1580, conclusions_y + 126, 724, 18, 25, MUTED)

    page.line(80, 3295, 2304, 3295, RULE, 2)
    page.text(80, 3310, "Methods: Louizos et al. (2018); Cao et al. (2021). Data: Universal Dependencies English-EWT.", 18, MUTED)
    page.text(2304, 3310, "BlackboxNLP 2026  |  Poster #192", 18, MUTED, False, "end")
    return drawing


def reusable_figure(width: int, height: int, draw) -> Drawing:
    """Create a white standalone vector canvas for one poster figure."""
    drawing = Drawing(width, height)
    drawing.initialFontName = "PosterSans"
    page = Page(drawing, height)
    page.rect(0, 0, width, height, WHITE)
    draw(page)
    return drawing


def write_pdf(drawing: Drawing, path: Path) -> None:
    """Write a one-page vector PDF with embedded TrueType fonts and metadata."""
    pdf = canvas.Canvas(str(path), pagesize=(drawing.width, drawing.height), pageCompression=1, initialFontName="PosterSans")
    pdf.setTitle("Multiple Recovery Paths in a Lesioned Transformer")
    pdf.setAuthor("Lorenzo Cannata and Uri Hasson")
    pdf.setSubject("BlackboxNLP 2026 conference poster")
    renderPDF.draw(drawing, pdf, 0, 0)
    pdf.showPage()
    pdf.save()


def main() -> None:
    """Generate the editable poster, print PDF, and three reusable vector figures."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    site, tokens = load_data()
    main_drawing = poster(site, tokens)
    poster_svg = FIGURES / "recovery-paths-poster.svg"
    renderSVG.drawToFile(main_drawing, str(poster_svg))
    svg_text = poster_svg.read_text()
    svg_text = svg_text.replace('<svg width="2384" height="3370"', '<svg width="841mm" height="1189mm"')
    svg_text = svg_text.replace("<title>...</title>", "<title>Multiple Recovery Paths in a Lesioned Transformer</title>")
    svg_text = svg_text.replace("<desc>...</desc>", "<desc>A0 portrait BlackboxNLP 2026 scientific conference poster.</desc>")
    poster_svg.write_text(svg_text)
    write_pdf(main_drawing, FIGURES / "recovery-paths-poster.pdf")

    perf = reusable_figure(1074, 430, lambda p: draw_performance(p, site, 0, 0, 1074, 430))
    cka = reusable_figure(1074, 430, lambda p: draw_cka(p, site, 0, 0, 1074, 430))
    readout = reusable_figure(2224, 470, lambda p: draw_readout(p, tokens, 0, 0, 2224, 470))
    renderSVG.drawToFile(perf, str(FIGURES / "poster-recovery-performance.svg"))
    renderSVG.drawToFile(cka, str(FIGURES / "poster-accuracy-cka.svg"))
    renderSVG.drawToFile(readout, str(FIGURES / "poster-readout-remapping.svg"))
    print("Generated A0 portrait poster SVG/PDF and three reusable vector figures")


if __name__ == "__main__":
    main()
