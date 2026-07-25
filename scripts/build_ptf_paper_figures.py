"""Build the English-language paper figures with the repository's PIL stack."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
FIGURES = ROOT / "Paper" / "figures"

BLUE = "#17365D"
MID_BLUE = "#4F81BD"
LIGHT_BLUE = "#DCE6F1"
RED = "#B54A4A"
LIGHT_RED = "#F1DCDC"
GRAY = "#666666"
LIGHT_GRAY = "#D9DDE3"
DARK = "#2F2F2F"
WHITE = "#FFFFFF"

ENGLISH = {
    "Agricultura": "Agriculture",
    "Minería": "Mining",
    "Manufactura": "Manufacturing",
    "Electricidad, gas y agua": "Electricity, gas, and water",
    "Construcción": "Construction",
    "Comercio, hoteles y restaurantes": "Trade, hotels, and restaurants",
    "Transporte y comunicaciones": "Transport and communications",
    "Finanzas e inmobiliarias": "Finance and real estate",
    "Servicios sociales": "Social services",
    "Total de la economía": "Total economy",
}


def fonts() -> dict[str, ImageFont.FreeTypeFont]:
    regular = Path("C:/Windows/Fonts/arial.ttf")
    bold = Path("C:/Windows/Fonts/arialbd.ttf")
    return {
        "title": ImageFont.truetype(str(bold), 48),
        "subtitle": ImageFont.truetype(str(regular), 26),
        "axis": ImageFont.truetype(str(regular), 24),
        "axis_bold": ImageFont.truetype(str(bold), 24),
        "small": ImageFont.truetype(str(regular), 19),
        "small_bold": ImageFont.truetype(str(bold), 19),
        "tiny": ImageFont.truetype(str(regular), 15),
    }


def load_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def canvas(
    title: str,
    subtitle: str,
    width: int = 2000,
    height: int = 1200,
) -> tuple[Image.Image, ImageDraw.ImageDraw, dict[str, ImageFont.FreeTypeFont]]:
    image = Image.new("RGB", (width, height), WHITE)
    draw = ImageDraw.Draw(image)
    f = fonts()
    draw.text((70, 48), title, font=f["title"], fill=BLUE)
    draw.text((70, 112), subtitle, font=f["subtitle"], fill=GRAY)
    return image, draw, f


def finish(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    f: dict[str, ImageFont.FreeTypeFont],
    filename: str,
    note: str | None = None,
) -> None:
    if note:
        draw.text((70, image.height - 84), note, font=f["tiny"], fill=GRAY)
    draw.text(
        (70, image.height - 48),
        "Source: authors' calculations based on DANE, 2025 TFP annex.",
        font=f["tiny"],
        fill=GRAY,
    )
    FIGURES.mkdir(parents=True, exist_ok=True)
    image.save(FIGURES / filename, quality=95)


def text_width(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont
) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def draw_total_index() -> None:
    rows = [
        row
        for row in load_csv("ptf_indices_encadenados.csv")
        if row["activity"] == "Total de la economía"
    ]
    years = [int(row["year"]) for row in rows]
    values = [float(row["index"]) for row in rows]
    image, draw, f = canvas(
        "Chained TFP index for the total economy",
        "2004 = 100; annual log growth rates from the DANE production approach",
        1800,
        1050,
    )
    left, right, top, bottom = 160, 1700, 245, 875
    ymin, ymax = 96.5, 103.0

    def x(year: int) -> float:
        return left + (year - 2004) / (2024 - 2004) * (right - left)

    def y(value: float) -> float:
        return bottom - (value - ymin) / (ymax - ymin) * (bottom - top)

    for tick in [97, 98, 99, 100, 101, 102, 103]:
        yy = y(tick)
        draw.line((left, yy, right, yy), fill=BLUE if tick == 100 else LIGHT_GRAY, width=3 if tick == 100 else 1)
        draw.text((95, yy - 13), str(tick), font=f["small"], fill=GRAY)
    for year in [2004, 2008, 2012, 2016, 2020, 2024]:
        xx = x(year)
        label = str(year)
        draw.text((xx - text_width(draw, label, f["small"]) / 2, bottom + 26), label, font=f["small"], fill=GRAY)

    points = [(x(year), y(value)) for year, value in zip(years, values)]
    draw.line(points, fill=BLUE, width=6)
    for xx, yy in points:
        draw.ellipse((xx - 6, yy - 6, xx + 6, yy + 6), fill=MID_BLUE, outline=BLUE, width=2)
    final_label = f"{values[-1]:.1f}"
    draw.text((points[-1][0] - 54, points[-1][1] - 48), final_label, font=f["small_bold"], fill=BLUE)
    finish(image, draw, f, "paper_fig_ptf_total_index.png")


def interpolate(value: float, limit: float = 6.0) -> str:
    clipped = max(-limit, min(limit, value))
    if clipped < 0:
        ratio = abs(clipped) / limit
        start, end = (255, 255, 255), (181, 74, 74)
    else:
        ratio = clipped / limit
        start, end = (255, 255, 255), (79, 129, 189)
    rgb = tuple(
        round(start[channel] + ratio * (end[channel] - start[channel]))
        for channel in range(3)
    )
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def draw_heatmap() -> None:
    sectors = [
        row
        for row in load_csv("ptf_actividad_anual.csv")
        if 2005 <= int(row["year"]) <= 2024
    ]
    totals = [
        row
        for row in load_csv("ptf_total_economia_anual.csv")
        if 2005 <= int(row["year"]) <= 2024
    ]
    long_run = load_csv("ptf_contribucion_largo_plazo.csv")
    ranking = sorted(
        (
            row
            for row in long_run
            if row["activity"] != "Total de la economía"
        ),
        key=lambda row: float(row["average_sector_ptf"]),
    )
    activities = [*[row["activity"] for row in ranking], "Total de la economía"]
    years = list(range(2005, 2025))
    lookup = {
        (row["activity"], int(row["year"])): float(row["ptf"])
        for row in [*sectors, *totals]
    }
    image, draw, f = canvas(
        "Annual TFP growth by activity",
        "2005-2024, annual log growth rates (%); activities ranked by cumulative TFP growth",
        2200,
        1280,
    )
    left, top = 650, 250
    cell_w, cell_h = 77, 72
    for column, year in enumerate(years):
        xx = left + column * cell_w
        draw.text((xx + 20, top - 38), str(year)[2:], font=f["small"], fill=GRAY)
    for row_index, activity in enumerate(activities):
        yy = top + row_index * cell_h
        if activity == "Total de la economía":
            draw.line((65, yy - 5, left + len(years) * cell_w, yy - 5), fill=BLUE, width=4)
        draw.text((65, yy + 20), ENGLISH[activity], font=f["axis_bold"] if activity == "Total de la economía" else f["axis"], fill=DARK)
        for column, year in enumerate(years):
            value = lookup[(activity, year)]
            xx = left + column * cell_w
            draw.rectangle((xx, yy, xx + cell_w - 3, yy + cell_h - 3), fill=interpolate(value))
            label = f"{value:.1f}"
            color = WHITE if abs(max(-6, min(6, value))) >= 4.2 else DARK
            label_width = text_width(draw, label, f["tiny"])
            draw.text((xx + (cell_w - 3 - label_width) / 2, yy + 24), label, font=f["tiny"], fill=color)
    legend_y = 1060
    draw.text((650, legend_y), "Negative TFP", font=f["small"], fill=GRAY)
    for index, value in enumerate([-6, -4, -2, 0, 2, 4, 6]):
        xx = 835 + index * 100
        draw.rectangle((xx, legend_y, xx + 96, legend_y + 30), fill=interpolate(value))
        label = str(value)
        draw.text((xx + 40 - text_width(draw, label, f["tiny"]) / 2, legend_y + 38), label, font=f["tiny"], fill=GRAY)
    draw.text((1555, legend_y), "Positive TFP", font=f["small"], fill=GRAY)
    finish(
        image,
        draw,
        f,
        "paper_fig_ptf_heatmap.png",
        "Note: the color scale is capped at +/-6 points; cell labels retain observed values.",
    )


def bar_label(
    draw: ImageDraw.ImageDraw,
    f: dict[str, ImageFont.FreeTypeFont],
    value: float,
    xx: float,
    yy: float,
    digits: int,
    positive: bool,
) -> None:
    label = f"{value:.{digits}f}"
    width = text_width(draw, label, f["small_bold"])
    draw.text(
        (xx + 10 if positive else xx - width - 10, yy - 12),
        label,
        font=f["small_bold"],
        fill=DARK,
    )


def draw_two_panel_bars(
    rows: list[dict[str, str]],
    order_field: str,
    left_field: str,
    right_field: str,
    left_range: tuple[float, float],
    right_range: tuple[float, float],
    left_title: str,
    right_title: str,
    main_title: str,
    main_subtitle: str,
    filename: str,
    left_digits: int,
    right_digits: int,
) -> None:
    sector_rows = [row for row in rows if row["activity"] != "Total de la economía"]
    sector_rows.sort(key=lambda row: float(row[order_field]))
    total = next(row for row in rows if row["activity"] == "Total de la economía")
    ordered = [*sector_rows, total]
    image, draw, f = canvas(
        main_title,
        main_subtitle,
        2100,
        1320,
    )
    label_left = 60
    panels = [
        (690, 1330, left_field, left_range, left_title, left_digits),
        (1440, 2030, right_field, right_range, right_title, right_digits),
    ]
    top, bottom = 300, 1120
    row_h = (bottom - top) / len(ordered)

    for panel_left, panel_right, field, value_range, title, digits in panels:
        xmin, xmax = value_range
        zero = panel_left + (0 - xmin) / (xmax - xmin) * (panel_right - panel_left)
        draw.text((panel_left, 220), title, font=f["axis_bold"], fill=BLUE)
        span = xmax - xmin
        step = 10 if span > 20 else 1 if span > 3 else 0.5 if span > 1 else 0.1
        first_tick = math.ceil(xmin / step) * step
        tick_count = int(math.floor((xmax - first_tick) / step)) + 1
        for tick_index in range(tick_count):
            tick = first_tick + tick_index * step
            xx = panel_left + (tick - xmin) / (xmax - xmin) * (panel_right - panel_left)
            draw.line((xx, top, xx, bottom), fill=GRAY if tick == 0 else LIGHT_GRAY, width=3 if tick == 0 else 1)
            label = f"{tick:.1f}".rstrip("0").rstrip(".")
            draw.text((xx - text_width(draw, label, f["tiny"]) / 2, bottom + 18), label, font=f["tiny"], fill=GRAY)
        for index, row in enumerate(ordered):
            yy = top + (index + 0.5) * row_h
            value = float(row[field])
            endpoint = panel_left + (value - xmin) / (xmax - xmin) * (panel_right - panel_left)
            is_total = row["activity"] == "Total de la economía"
            color = DARK if is_total else (MID_BLUE if value >= 0 else RED)
            draw.rectangle((min(zero, endpoint), yy - 20, max(zero, endpoint), yy + 20), fill=color)
            bar_label(draw, f, value, endpoint, yy, digits, value >= 0)
    for index, row in enumerate(ordered):
        yy = top + (index + 0.5) * row_h
        is_total = row["activity"] == "Total de la economía"
        if is_total:
            draw.line((label_left, yy - row_h / 2, 2030, yy - row_h / 2), fill=BLUE, width=3)
        draw.text((label_left, yy - 15), ENGLISH[row["activity"]], font=f["axis_bold"] if is_total else f["axis"], fill=DARK)
    finish(image, draw, f, filename)


def draw_sector_performance() -> None:
    rows = load_csv("ptf_contribucion_largo_plazo.csv")
    for row in rows:
        row["cumulative_growth"] = str(float(row["ptf_index_2024"]) - 100)
    draw_two_panel_bars(
        rows,
        "average_sector_ptf",
        "cumulative_growth",
        "average_sector_ptf",
        (-40, 32),
        (-2.7, 1.7),
        "Cumulative TFP growth (%)",
        "Annualized TFP growth (%)",
        "Long-run sectoral TFP performance",
        "20 annual rates, 2005-2024; the total economy is shown in dark gray",
        "paper_fig_ptf_sector_performance.png",
        1,
        2,
    )


def draw_contributions() -> None:
    rows = load_csv("ptf_contribucion_largo_plazo.csv")
    draw_two_panel_bars(
        rows,
        "average_contribution",
        "cumulative_log_contribution",
        "average_contribution",
        (-3.0, 3.2),
        (-0.18, 0.19),
        "Cumulative contribution (log points)",
        "Average annual contribution (pp)",
        "Activity contributions to aggregate TFP",
        "2005-2024; the total economy is shown in dark gray",
        "paper_fig_ptf_contributions.png",
        2,
        3,
    )


def draw_counterfactual() -> None:
    summary = load_csv("ptf_contrafactual_cuatro_actividades_resumen.csv")
    long_run = load_csv("ptf_contribucion_largo_plazo.csv")
    observed = float(summary[0]["average_production_growth"])
    counterfactual = float(summary[1]["average_production_growth"])
    selected = {
        "Finanzas e inmobiliarias",
        "Minería",
        "Construcción",
        "Electricidad, gas y agua",
    }
    drivers = [
        (ENGLISH[row["activity"]], -float(row["average_contribution"]))
        for row in long_run
        if row["activity"] in selected
    ]
    drivers.sort(key=lambda item: item[1], reverse=True)
    image, draw, f = canvas(
        "Observed and counterfactual production-account output growth",
        "2005-2024; counterfactual sets annual TFP growth to zero in four activities",
        1900,
        1100,
    )
    left, right, top, bottom = 180, 1800, 280, 850
    ymin, ymax = 3.0, 3.66

    def y(value: float) -> float:
        return bottom - (value - ymin) / (ymax - ymin) * (bottom - top)

    labels = ["Observed", *[name for name, _ in drivers], "Counterfactual"]
    positions = [
        left + index * (right - left) / (len(labels) - 1)
        for index in range(len(labels))
    ]
    for tick in [3.0, 3.2, 3.4, 3.6]:
        yy = y(tick)
        draw.line((left, yy, right, yy), fill=LIGHT_GRAY, width=1)
        draw.text((100, yy - 12), f"{tick:.1f}", font=f["small"], fill=GRAY)
    width = 100
    draw.rectangle((positions[0] - width / 2, y(observed), positions[0] + width / 2, bottom), fill=DARK)
    draw.text((positions[0] - 34, y(observed) - 36), f"{observed:.2f}%", font=f["small_bold"], fill=DARK)
    running = observed
    for index, (_, change) in enumerate(drivers, start=1):
        before, after = running, running + change
        draw.line((positions[index - 1] + width / 2, y(before), positions[index] - width / 2, y(before)), fill=GRAY, width=2)
        draw.rectangle((positions[index] - width / 2, y(after), positions[index] + width / 2, y(before)), fill=MID_BLUE)
        label = f"+{change:.3f} pp"
        draw.text((positions[index] - text_width(draw, label, f["small_bold"]) / 2, y(after) - 34), label, font=f["small_bold"], fill=BLUE)
        running = after
    draw.line((positions[-2] + width / 2, y(running), positions[-1] - width / 2, y(running)), fill=GRAY, width=2)
    draw.rectangle((positions[-1] - width / 2, y(counterfactual), positions[-1] + width / 2, bottom), fill=DARK)
    final_label = f"{counterfactual:.2f}%"
    draw.text((positions[-1] - text_width(draw, final_label, f["small_bold"]) / 2, y(counterfactual) - 36), final_label, font=f["small_bold"], fill=DARK)
    for xx, label in zip(positions, labels):
        parts = label.split(" and ") if len(label) > 16 else [label]
        for line_index, part in enumerate(parts):
            draw.text((xx - text_width(draw, part, f["tiny"]) / 2, bottom + 25 + line_index * 20), part, font=f["tiny"], fill=DARK)
    finish(
        image,
        draw,
        f,
        "paper_fig_ptf_counterfactual.png",
        "Note: the vertical scale starts at 3.0%. All other input contributions and annual weights remain fixed.",
    )


def main() -> None:
    draw_total_index()
    draw_heatmap()
    draw_sector_performance()
    draw_contributions()
    draw_counterfactual()
    print("English paper figures created.")


if __name__ == "__main__":
    main()
