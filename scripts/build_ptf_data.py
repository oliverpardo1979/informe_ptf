"""Reconstruye la historia sectorial KLEMS 2005-2024 a partir del anexo DANE."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

import openpyxl
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "anex-PTF-Productividad-2025.xlsx"
TOTAL_CSV = ROOT / "data" / "processed" / "ptf_total_economia_anual.csv"
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "Paper" / "figures"
SECTIONS = ROOT / "Paper" / "sections"

FIELDS = [
    "production",
    "labor_composition",
    "hours",
    "labor",
    "capital_tic",
    "capital_non_tic",
    "capital",
    "energy",
    "materials",
    "services",
    "intermediate",
    "factors",
    "ptf",
]

SHORT = {
    "Agricultura, ganadería, caza, silvicultura y pesca": "Agricultura",
    "Minería y extracción": "Minería",
    "Industrias manufactureras": "Manufactura",
    "Electricidad, gas y agua": "Electricidad, gas y agua",
    "Construcción": "Construcción",
    "Comercio, hoteles y restaurantes": "Comercio, hoteles y restaurantes",
    "Transporte, almacenamiento y comunicaciones": "Transporte y comunicaciones",
    "Intermediación financiera, actividades inmobiliarias, empresariales y de alquiler": "Finanzas e inmobiliarias",
    "Actividades de servicios sociales, comunales y personales": "Servicios sociales",
}

TEX_NAMES = {
    "Total de la economía": "Total de la economía",
    "Agricultura": "Agricultura, ganadería, caza, silvicultura y pesca",
    "Minería": "Minería y extracción",
    "Manufactura": "Industrias manufactureras",
    "Electricidad, gas y agua": "Electricidad, gas y agua",
    "Construcción": "Construcción",
    "Comercio, hoteles y restaurantes": "Comercio, hoteles y restaurantes",
    "Transporte y comunicaciones": "Transporte, almacenamiento y comunicaciones",
    "Finanzas e inmobiliarias": "Intermediación financiera, inmobiliarias, empresariales y de alquiler",
    "Servicios sociales": "Servicios sociales, comunales y personales",
}

ACTIVITY_ORDER = ["Total de la economía", *SHORT.values()]

BLUE = "#17365D"
MID_BLUE = "#4F81BD"
LIGHT_BLUE = "#DCE6F1"
RED = "#B54A4A"
GRAY = "#666666"
GRID = "#D7D7D7"
WHITE = "#FFFFFF"


def clean_activity(value: object) -> str:
    return str(value or "").strip().replace("\xa0", "")


def load_observations() -> list[dict[str, float | int | str]]:
    wb = openpyxl.load_workbook(RAW, data_only=True, read_only=True)
    observations: list[dict[str, float | int | str]] = []
    for year in range(2005, 2025):
        ws = wb[f"Cuadro {year - 2001}"]
        for row in ws.iter_rows(min_row=1, max_col=15, values_only=True):
            activity = clean_activity(row[1])
            if activity not in SHORT:
                continue
            if not isinstance(row[2], (int, float)):
                continue
            obs: dict[str, float | int | str] = {
                "year": year,
                "activity_full": activity,
                "activity": SHORT[activity],
            }
            for field, value in zip(FIELDS, row[2:15]):
                obs[field] = float(value)
            observations.append(obs)
    wb.close()
    if len(observations) != 180:
        raise RuntimeError(f"Se esperaban 180 observaciones y se obtuvieron {len(observations)}")
    return observations


def load_total_observations() -> list[dict[str, float | int | str]]:
    if not TOTAL_CSV.exists():
        raise RuntimeError(
            "Falta ptf_total_economia_anual.csv. Ejecute primero "
            "`node scripts/extract_ptf_workbook.mjs`."
        )
    observations: list[dict[str, float | int | str]] = []
    with TOTAL_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            obs: dict[str, float | int | str] = {
                "year": int(row["year"]),
                "activity_full": "Total de la economía",
                "activity": "Total de la economía",
            }
            for field in FIELDS:
                obs[field] = float(row[field])
            observations.append(obs)
    if len(observations) != 20:
        raise RuntimeError(
            f"Se esperaban 20 observaciones del total y se obtuvieron {len(observations)}"
        )
    return observations


def validate(observations: list[dict[str, float | int | str]]) -> tuple[float, float]:
    identity_error = 0.0
    detail_error = 0.0
    for d in observations:
        v = {k: float(d[k]) for k in FIELDS}
        identity_error = max(identity_error, abs(v["production"] - v["factors"] - v["ptf"]))
        detail_error = max(
            detail_error,
            abs(v["labor"] - v["labor_composition"] - v["hours"]),
            abs(v["capital"] - v["capital_tic"] - v["capital_non_tic"]),
            abs(v["intermediate"] - v["energy"] - v["materials"] - v["services"]),
            abs(v["factors"] - v["labor"] - v["capital"] - v["intermediate"]),
        )
    if identity_error > 1e-9 or detail_error > 1e-9:
        raise RuntimeError(
            f"Falló la conciliación: identidad={identity_error}; detalle={detail_error}"
        )
    return identity_error, detail_error


def summarize(
    observations: list[dict[str, float | int | str]],
    start: int,
    end: int,
    activity_order: list[str] | None = None,
) -> list[dict[str, float | int | str]]:
    groups: dict[str, list[dict[str, float | int | str]]] = defaultdict(list)
    for d in observations:
        if start <= int(d["year"]) <= end:
            groups[str(d["activity"])].append(d)
    result = []
    for activity in activity_order or list(SHORT.values()):
        rows = groups[activity]
        out: dict[str, float | int | str] = {
            "activity": activity,
            "start": start,
            "end": end,
            "n": len(rows),
            "ptf_positive_years": sum(float(d["ptf"]) > 0 for d in rows),
        }
        for field in FIELDS:
            out[field] = sum(float(d[field]) for d in rows) / len(rows)
        result.append(out)
    return result


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: float) -> str:
    if abs(value) < 0.005:
        value = 0.0
    return f"{value:.2f}".replace("-", "−")


def tex_fmt(value: float) -> str:
    if abs(value) < 0.005:
        value = 0.0
    return f"{value:.2f}"


def tex_escape(text: str) -> str:
    return text.replace("&", r"\&").replace("%", r"\%")


def write_tex_tables(long_run: list[dict[str, float | int | str]]) -> None:
    lines = [
        r"\begin{longtable}{p{4.45cm}rrrrrrr}",
        r"\caption{Descomposición promedio anual del crecimiento de la producción por actividad, 2006--2024}",
        r"\label{tab:descomposicion_largo_plazo}\\",
        r"\toprule",
        r"Actividad & Producción & Trabajo & Capital & Energía & Materiales & Servicios & PTF \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        r"Actividad & Producción & Trabajo & Capital & Energía & Materiales & Servicios & PTF \\",
        r"\midrule",
        r"\endhead",
    ]
    for row in long_run:
        lines.append(
            "{} & {} & {} & {} & {} & {} & {} & {} \\\\".format(
                tex_escape(TEX_NAMES[str(row["activity"])]),
                *[
                    tex_fmt(float(row[key]))
                    for key in (
                        "production",
                        "labor",
                        "capital",
                        "energy",
                        "materials",
                        "services",
                        "ptf",
                    )
                ],
            )
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\multicolumn{8}{p{15.9cm}}{\footnotesize \textit{Nota:} cifras en puntos porcentuales promedio por año, salvo la producción, expresada como tasa logarítmica anual. El periodo usa las 19 variaciones de 2006 a 2024, que enlazan los niveles de 2005 y 2024. Por redondeo, los componentes pueden no sumar exactamente la producción.}\\",
            r"\multicolumn{8}{l}{\footnotesize Fuente: cálculos del CJC con base en DANE, anexo PTF 2025.}\\",
            r"\end{longtable}",
        ]
    )
    (SECTIONS / "tabla_descomposicion_largo_plazo.tex").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    detail = [
        r"\begin{longtable}{p{4.65cm}rrrrrr}",
        r"\caption{Descomposición de los servicios de trabajo y capital, promedio anual 2006--2024}",
        r"\label{tab:detalle_factores}\\",
        r"\toprule",
        r"Actividad & Composición laboral & Horas & Trabajo & Capital TIC & Capital no TIC & Capital \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        r"Actividad & Composición laboral & Horas & Trabajo & Capital TIC & Capital no TIC & Capital \\",
        r"\midrule",
        r"\endhead",
    ]
    for row in long_run:
        detail.append(
            "{} & {} & {} & {} & {} & {} & {} \\\\".format(
                tex_escape(TEX_NAMES[str(row["activity"])]),
                *[
                    tex_fmt(float(row[key]))
                    for key in (
                        "labor_composition",
                        "hours",
                        "labor",
                        "capital_tic",
                        "capital_non_tic",
                        "capital",
                    )
                ],
            )
        )
    detail.extend(
        [
            r"\bottomrule",
            r"\multicolumn{7}{p{15.9cm}}{\footnotesize \textit{Nota:} aportes en puntos porcentuales promedio por año. Trabajo es la suma de composición laboral y horas; capital es la suma de capital TIC y no TIC.}\\",
            r"\multicolumn{7}{l}{\footnotesize Fuente: cálculos del CJC con base en DANE, anexo PTF 2025.}\\",
            r"\end{longtable}",
        ]
    )
    (SECTIONS / "tabla_detalle_factores.tex").write_text(
        "\n".join(detail) + "\n", encoding="utf-8"
    )


def write_evolution_table(
    long_run: list[dict[str, float | int | str]],
    period_summaries: list[tuple[str, list[dict[str, float | int | str]]]],
) -> None:
    by_period = {
        label: {str(row["activity"]): row for row in rows}
        for label, rows in period_summaries
    }
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Evolución de la PTF por actividad y subperiodo}",
        r"\label{tab:evolucion_ptf}",
        r"\footnotesize",
        r"\begin{tabular}{p{3.8cm}rrrrr>{\centering\arraybackslash}p{1.3cm}}",
        r"\toprule",
        r"Actividad & 2006--10 & 2011--15 & 2016--19 & 2020--24 & 2006--24 & Años positivos \\",
        r"\midrule",
    ]
    for row in long_run:
        activity = str(row["activity"])
        values = [
            float(by_period[label][activity]["ptf"])
            for label, _ in period_summaries
        ]
        lines.append(
            "{} & {} & {} & {} & {} & {} & {}/19 \\\\".format(
                tex_escape(TEX_NAMES[activity]),
                *[tex_fmt(value) for value in values],
                tex_fmt(float(row["ptf"])),
                int(row["ptf_positive_years"]),
            )
        )
        if str(row["activity"]) == "Total de la economía":
            lines.append(r"\midrule")
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\vspace{0.15cm}",
            r"\begin{minipage}{0.96\textwidth}",
            r"\footnotesize \textit{Nota:} contribución promedio anual de la PTF al crecimiento de la producción, en puntos porcentuales. El total de la economía corresponde a la serie agregada publicada por el DANE y no a un promedio simple de las actividades. Los subperiodos tienen distinta duración; se usan para describir cambios en la trayectoria, no para atribuirlos a un evento específico.",
            r"\par\textit{Fuente:} cálculos del CJC con base en DANE, anexo PTF 2025.",
            r"\end{minipage}",
            r"\end{table}",
        ]
    )
    (SECTIONS / "tabla_evolucion_ptf.tex").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def fonts() -> dict[str, ImageFont.FreeTypeFont]:
    regular = Path(r"C:\Windows\Fonts\arial.ttf")
    bold = Path(r"C:\Windows\Fonts\arialbd.ttf")
    return {
        "title": ImageFont.truetype(str(bold), 52),
        "subtitle": ImageFont.truetype(str(regular), 29),
        "axis": ImageFont.truetype(str(regular), 25),
        "axis_bold": ImageFont.truetype(str(bold), 25),
        "small": ImageFont.truetype(str(regular), 21),
        "small_bold": ImageFont.truetype(str(bold), 21),
    }


def canvas(title: str, subtitle: str, width: int = 1800, height: int = 1120):
    img = Image.new("RGB", (width, height), WHITE)
    draw = ImageDraw.Draw(img)
    f = fonts()
    draw.text((85, 62), title, fill=BLUE, font=f["title"])
    draw.text((87, 128), subtitle, fill=GRAY, font=f["subtitle"])
    return img, draw, f


def draw_ptf_bars(long_run: list[dict[str, float | int | str]]) -> None:
    rows = sorted(long_run, key=lambda d: float(d["ptf"]))
    img, draw, f = canvas(
        "Contribución promedio de la PTF: total y actividades",
        "Contribución promedio anual de la PTF al crecimiento de la producción, 2006–2024 (puntos porcentuales)",
    )
    left, right, top, bottom = 590, 1690, 215, 1000
    xmin, xmax = -2.6, 1.6
    xscale = (right - left) / (xmax - xmin)
    x0 = left + (0 - xmin) * xscale
    for tick in [-2, -1, 0, 1]:
        x = left + (tick - xmin) * xscale
        draw.line((x, top, x, bottom), fill=BLUE if tick == 0 else GRID, width=3 if tick == 0 else 1)
        label = str(tick).replace("-", "−")
        draw.text((x - 10, bottom + 18), label, fill=GRAY, font=f["small"])
    row_h = (bottom - top) / len(rows)
    for i, row in enumerate(rows):
        y = top + (i + 0.5) * row_h
        value = float(row["ptf"])
        x = left + (value - xmin) * xscale
        color = GRAY if str(row["activity"]) == "Total de la economía" else (MID_BLUE if value >= 0 else RED)
        draw.text((70, y - 16), str(row["activity"]), fill="#222222", font=f["axis"])
        draw.rectangle((min(x, x0), y - 22, max(x, x0), y + 22), fill=color)
        anchor_x = x + 12 if value >= 0 else x - 78
        draw.text((anchor_x, y - 16), fmt(value), fill=color, font=f["axis_bold"])
    draw.text((85, 1060), "Fuente: cálculos del CJC con base en DANE, anexo PTF 2025.", fill=GRAY, font=f["small"])
    img.save(FIGURES / "fig_ptf_promedio_actividad.png", quality=95)


def draw_decomposition(long_run: list[dict[str, float | int | str]]) -> None:
    img, draw, f = canvas(
        "Más producción no significó necesariamente más productividad",
        "Descomposición promedio anual del crecimiento de la producción, 2006–2024 (puntos porcentuales)",
    )
    left, right, top, bottom = 520, 1710, 245, 975
    xmin, xmax = -2.8, 5.0
    xscale = (right - left) / (xmax - xmin)
    x0 = left + (0 - xmin) * xscale
    colors = {
        "labor": "#7EA6D8",
        "capital": "#244A7C",
        "intermediate": "#B9C4D0",
        "ptf": "#E0A12B",
    }
    labels = [("labor", "Trabajo"), ("capital", "Capital"), ("intermediate", "Insumos"), ("ptf", "PTF")]
    lx = 610
    for key, label in labels:
        draw.rectangle((lx, 190, lx + 28, 218), fill=colors[key])
        draw.text((lx + 38, 188), label, fill="#333333", font=f["small"])
        lx += 210
    for tick in [-2, 0, 2, 4]:
        x = left + (tick - xmin) * xscale
        draw.line((x, top, x, bottom), fill=BLUE if tick == 0 else GRID, width=3 if tick == 0 else 1)
        draw.text((x - 10, bottom + 18), str(tick).replace("-", "−"), fill=GRAY, font=f["small"])
    row_h = (bottom - top) / len(long_run)
    for i, row in enumerate(long_run):
        y = top + (i + 0.5) * row_h
        draw.text((65, y - 14), str(row["activity"]), fill="#222222", font=f["axis"])
        positive = 0.0
        negative = 0.0
        for key, _ in labels:
            value = float(row[key])
            if value >= 0:
                a, b = positive, positive + value
                positive = b
            else:
                a, b = negative + value, negative
                negative = a
            xa = left + (a - xmin) * xscale
            xb = left + (b - xmin) * xscale
            draw.rectangle((xa, y - 20, xb, y + 20), fill=colors[key], outline=WHITE)
        production = float(row["production"])
        xp = left + (production - xmin) * xscale
        draw.line((xp, y - 28, xp, y + 28), fill="#111111", width=3)
    draw.text((85, 1055), "Nota: la marca negra indica el crecimiento de la producción. Insumos = energía, materiales y servicios.", fill=GRAY, font=f["small"])
    draw.text((85, 1083), "Fuente: cálculos del CJC con base en DANE, anexo PTF 2025.", fill=GRAY, font=f["small"])
    img.save(FIGURES / "fig_descomposicion_actividad.png", quality=95)


def draw_series(observations: list[dict[str, float | int | str]]) -> None:
    by_activity: dict[str, list[dict[str, float | int | str]]] = defaultdict(list)
    for d in observations:
        if int(d["year"]) >= 2006:
            by_activity[str(d["activity"])].append(d)
    img, draw, f = canvas(
        "La PTF sectorial fue volátil, pero los patrones no fueron aleatorios",
        "Contribución anual de la PTF al crecimiento de la producción, 2006–2024 (puntos porcentuales)",
        1800,
        1280,
    )
    plot_left, plot_top = 90, 225
    panel_w, panel_h = 535, 285
    gap_x, gap_y = 55, 65
    ymin, ymax = -12.0, 12.0
    for idx, activity in enumerate(SHORT.values()):
        col, row = idx % 3, idx // 3
        x1 = plot_left + col * (panel_w + gap_x)
        y1 = plot_top + row * (panel_h + gap_y)
        x2, y2 = x1 + panel_w, y1 + panel_h
        draw.text((x1, y1 - 34), activity, fill=BLUE, font=f["small_bold"])
        y0 = y2 - (0 - ymin) / (ymax - ymin) * panel_h
        draw.line((x1, y0, x2, y0), fill=GRID, width=2)
        x2020 = x1 + (2020 - 2006) / (2024 - 2006) * panel_w
        draw.rectangle((x2020, y1, x2, y2), fill="#F3F3F3")
        draw.line((x1, y0, x2, y0), fill=GRID, width=2)
        points = []
        for d in sorted(by_activity[activity], key=lambda z: int(z["year"])):
            x = x1 + (int(d["year"]) - 2006) / (2024 - 2006) * panel_w
            value = max(ymin, min(ymax, float(d["ptf"])))
            y = y2 - (value - ymin) / (ymax - ymin) * panel_h
            points.append((x, y))
        draw.line(points, fill=MID_BLUE, width=4)
        for x, y in points:
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=MID_BLUE)
        draw.rectangle((x1, y1, x2, y2), outline=GRID, width=1)
        draw.text((x1, y2 + 6), "2006", fill=GRAY, font=f["small"])
        draw.text((x2 - 52, y2 + 6), "2024", fill=GRAY, font=f["small"])
    draw.text((90, 1230), "Nota: el área gris corresponde a 2020–2024. La escala se limita a ±12 pp para facilitar la comparación.", fill=GRAY, font=f["small"])
    draw.text((90, 1256), "Fuente: cálculos del CJC con base en DANE, anexo PTF 2025.", fill=GRAY, font=f["small"])
    img.save(FIGURES / "fig_ptf_series_actividad.png", quality=95)


def interpolate_color(value: float, limit: float = 6.0) -> str:
    value = max(-limit, min(limit, value))
    if value < 0:
        ratio = abs(value) / limit
        start, end = (255, 255, 255), (181, 74, 74)
    else:
        ratio = value / limit
        start, end = (255, 255, 255), (79, 129, 189)
    rgb = tuple(round(start[i] + ratio * (end[i] - start[i])) for i in range(3))
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def draw_heatmap(observations: list[dict[str, float | int | str]]) -> None:
    rows = [d for d in observations if int(d["year"]) >= 2006]
    lookup = {(str(d["activity"]), int(d["year"])): float(d["ptf"]) for d in rows}
    img, draw, f = canvas(
        "Contribución anual de la PTF: total y actividades",
        "2006–2024, puntos porcentuales; azul = aporte positivo, rojo = aporte negativo",
        1900,
        1200,
    )
    left, top = 520, 235
    cell_w, cell_h = 68, 70
    years = list(range(2006, 2025))
    activities = ACTIVITY_ORDER
    for j, year in enumerate(years):
        x = left + j * cell_w
        draw.text((x + 7, top - 38), str(year)[2:], fill=GRAY, font=f["small"])
    for i, activity in enumerate(activities):
        y = top + i * cell_h
        draw.text((60, y + 19), activity, fill="#222222", font=f["axis"])
        for j, year in enumerate(years):
            value = lookup[(activity, year)]
            x = left + j * cell_w
            color = interpolate_color(value)
            draw.rectangle((x, y, x + cell_w - 3, y + cell_h - 3), fill=color)
            text_color = WHITE if abs(value) >= 4.2 else "#222222"
            label = f"{value:.1f}".replace("-", "−")
            box = draw.textbbox((0, 0), label, font=f["small"])
            tw = box[2] - box[0]
            draw.text(
                (x + (cell_w - 3 - tw) / 2, y + 20),
                label,
                fill=text_color,
                font=f["small"],
            )
        if activity == "Total de la economía":
            draw.line(
                (55, y + cell_h - 1, left + len(years) * cell_w, y + cell_h - 1),
                fill=BLUE,
                width=4,
            )
    legend_y = 1010
    draw.text((525, legend_y - 2), "PTF negativa", fill=GRAY, font=f["small"])
    for idx, value in enumerate([-6, -4, -2, 0, 2, 4, 6]):
        x = 705 + idx * 90
        draw.rectangle((x, legend_y, x + 87, legend_y + 28), fill=interpolate_color(value))
        draw.text((x + 28, legend_y + 34), str(value).replace("-", "−"), fill=GRAY, font=f["small"])
    draw.text((1355, legend_y - 2), "PTF positiva", fill=GRAY, font=f["small"])
    draw.text(
        (70, 1120),
        "Nota: la escala de color se limita a ±6 puntos; las cifras dentro de cada celda conservan el valor observado.",
        fill=GRAY,
        font=f["small"],
    )
    draw.text(
        (70, 1155),
        "Fuente: cálculos del CJC con base en DANE, anexo PTF 2025.",
        fill=GRAY,
        font=f["small"],
    )
    img.save(FIGURES / "fig_ptf_mapa_anual.png", quality=95)


def draw_periods(
    period_summaries: list[tuple[str, list[dict[str, float | int | str]]]]
) -> None:
    img, draw, f = canvas(
        "Contribución promedio de la PTF: total y actividades",
        "Promedio anual, puntos porcentuales",
        1800,
        1120,
    )
    left, right, top, bottom = 560, 1690, 255, 990
    xmin, xmax = -3.6, 2.8
    xscale = (right - left) / (xmax - xmin)
    colors = ["#9FBAD9", "#4F81BD", "#244A7C", "#E0A12B"]
    for tick in [-3, -2, -1, 0, 1, 2]:
        x = left + (tick - xmin) * xscale
        draw.line((x, top, x, bottom), fill=BLUE if tick == 0 else GRID, width=3 if tick == 0 else 1)
        draw.text((x - 9, bottom + 18), str(tick).replace("-", "−"), fill=GRAY, font=f["small"])
    lx = 585
    for (label, _), color in zip(period_summaries, colors):
        draw.ellipse((lx, 190, lx + 24, 214), fill=color)
        draw.text((lx + 34, 188), label, fill="#333333", font=f["small"])
        lx += 235
    by_period = [
        {str(row["activity"]): float(row["ptf"]) for row in rows}
        for _, rows in period_summaries
    ]
    row_h = (bottom - top) / len(ACTIVITY_ORDER)
    for i, activity in enumerate(ACTIVITY_ORDER):
        y = top + (i + 0.5) * row_h
        draw.text((65, y - 15), activity, fill="#222222", font=f["axis"])
        points = []
        for period_idx, period in enumerate(by_period):
            value = period[activity]
            x = left + (value - xmin) * xscale
            yy = y + (period_idx - 1.5) * 10
            points.append((x, yy))
        draw.line(points, fill="#A7A7A7", width=3)
        for period_idx, (x, yy) in enumerate(points):
            draw.ellipse((x - 9, yy - 9, x + 9, yy + 9), fill=colors[period_idx])
        if activity == "Total de la economía":
            draw.line((55, y + row_h / 2, right, y + row_h / 2), fill=BLUE, width=3)
    draw.text(
        (70, 1065),
        "Fuente: cálculos del CJC con base en DANE, anexo PTF 2025.",
        fill=GRAY,
        font=f["small"],
    )
    img.save(FIGURES / "fig_ptf_periodos_actividad.png", quality=95)


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    SECTIONS.mkdir(parents=True, exist_ok=True)
    observations = load_observations()
    total_observations = load_total_observations()
    identity_error, detail_error = validate(observations)
    total_identity_error, total_detail_error = validate(total_observations)
    long_run = summarize(observations, 2006, 2024)
    total_long_run = summarize(
        total_observations, 2006, 2024, ["Total de la economía"]
    )
    comparison_long_run = [*total_long_run, *long_run]
    pre = summarize(observations, 2006, 2019)
    post = summarize(observations, 2020, 2024)
    period_summaries = [
        ("2006–2010", summarize(observations, 2006, 2010)),
        ("2011–2015", summarize(observations, 2011, 2015)),
        ("2016–2019", summarize(observations, 2016, 2019)),
        ("2020–2024", summarize(observations, 2020, 2024)),
    ]
    total_period_summaries = [
        (
            label,
            summarize(total_observations, start, end, ["Total de la economía"]),
        )
        for label, start, end in [
            ("2006–2010", 2006, 2010),
            ("2011–2015", 2011, 2015),
            ("2016–2019", 2016, 2019),
            ("2020–2024", 2020, 2024),
        ]
    ]
    comparison_period_summaries = [
        (
            label,
            [
                *total_rows,
                *dict(period_summaries)[label],
            ],
        )
        for label, total_rows in total_period_summaries
    ]
    write_csv(PROCESSED / "ptf_actividad_anual.csv", observations)
    write_csv(PROCESSED / "ptf_actividad_promedio_2006_2024.csv", long_run)
    write_csv(PROCESSED / "ptf_actividad_promedio_2006_2019.csv", pre)
    write_csv(PROCESSED / "ptf_actividad_promedio_2020_2024.csv", post)
    write_csv(PROCESSED / "ptf_total_economia_promedio_2006_2024.csv", total_long_run)
    write_tex_tables(long_run)
    write_evolution_table(comparison_long_run, comparison_period_summaries)
    draw_ptf_bars(comparison_long_run)
    draw_decomposition(long_run)
    draw_series(observations)
    draw_heatmap([*total_observations, *observations])
    draw_periods(comparison_period_summaries)
    print(f"Observaciones: {len(observations)}")
    print(f"Error máximo identidad producción = factores + PTF: {identity_error:.3e}")
    print(f"Error máximo identidades internas: {detail_error:.3e}")
    print(
        "Error máximo total economía: "
        f"identidad={total_identity_error:.3e}; detalle={total_detail_error:.3e}"
    )


if __name__ == "__main__":
    main()
