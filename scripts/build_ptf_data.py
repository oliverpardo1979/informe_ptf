"""Reconstruye la historia sectorial KLEMS 2005-2024 a partir del anexo DANE."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SECTOR_CSV = ROOT / "data" / "processed" / "ptf_actividad_anual.csv"
TOTAL_CSV = ROOT / "data" / "processed" / "ptf_total_economia_anual.csv"
CONTRIBUTION_ANNUAL_CSV = (
    ROOT / "data" / "processed" / "ptf_pesos_contribuciones_anual.csv"
)
CONTRIBUTION_LONG_CSV = (
    ROOT / "data" / "processed" / "ptf_contribucion_largo_plazo.csv"
)
CONTRIBUTION_PERIOD_CSV = (
    ROOT / "data" / "processed" / "ptf_contribucion_subperiodos.csv"
)
INDEX_CSV = ROOT / "data" / "processed" / "ptf_indices_encadenados.csv"
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
    if not SECTOR_CSV.exists():
        raise RuntimeError(
            "Falta ptf_actividad_anual.csv. Ejecute primero "
            "`node scripts/extract_ptf_workbook.mjs`."
        )
    observations: list[dict[str, float | int | str]] = []
    with SECTOR_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            obs: dict[str, float | int | str] = {
                "year": int(row["year"]),
                "activity_full": row["activity_full"],
                "activity": row["activity"],
            }
            for field in FIELDS:
                obs[field] = float(row[field])
            observations.append(obs)
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


def load_numeric_csv(
    path: Path,
    text_fields: set[str],
    integer_fields: set[str] | None = None,
) -> list[dict[str, float | int | str]]:
    integer_fields = integer_fields or set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows: list[dict[str, float | int | str]] = []
        for source in csv.DictReader(handle):
            row: dict[str, float | int | str] = {}
            for key, value in source.items():
                if value == "":
                    row[key] = ""
                elif key in text_fields:
                    row[key] = value
                elif key in integer_fields:
                    row[key] = int(value)
                else:
                    row[key] = float(value)
            rows.append(row)
    return rows


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
    return f"{value:.2f}".replace(".", ",")


def tex_fmt3(value: float) -> str:
    if abs(value) < 0.0005:
        value = 0.0
    return f"{value:.3f}".replace(".", ",")


def tex_escape(text: str) -> str:
    return text.replace("&", r"\&").replace("%", r"\%")


def write_tex_tables(long_run: list[dict[str, float | int | str]]) -> None:
    lines = [
        r"\begingroup",
        r"\small",
        r"\setlength{\tabcolsep}{4pt}",
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
        activity = str(row["activity"])
        name = tex_escape(TEX_NAMES[activity])
        values = [
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
        ]
        if activity == "Total de la economía":
            name = rf"\textbf{{{name}}}"
            values = [rf"\textbf{{{value}}}" for value in values]
        lines.append(
            "{} & {} & {} & {} & {} & {} & {} & {} \\\\".format(
                name,
                *values,
            )
        )
        if activity == "Total de la economía":
            lines.append(r"\midrule")
    lines.extend(
        [
            r"\bottomrule",
            r"\multicolumn{8}{p{15.9cm}}{\footnotesize \textit{Nota:} cifras en puntos porcentuales promedio por año, salvo la producción, expresada como tasa logarítmica anual. El periodo usa las 19 variaciones de 2006 a 2024, que enlazan los niveles de 2005 y 2024. El total de la economía corresponde a la serie agregada publicada por el DANE y no a la suma ni al promedio simple de las actividades. Por redondeo, los componentes pueden no sumar exactamente la producción.}\\",
            r"\multicolumn{8}{l}{\footnotesize Fuente: cálculos del CJC con base en DANE, anexo PTF 2025.}\\",
            r"\end{longtable}",
            r"\endgroup",
        ]
    )
    (SECTIONS / "tabla_descomposicion_largo_plazo.tex").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    detail = [
        r"\begingroup",
        r"\small",
        r"\setlength{\tabcolsep}{4pt}",
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
        activity = str(row["activity"])
        name = tex_escape(TEX_NAMES[activity])
        values = [
            tex_fmt(float(row[key]))
            for key in (
                "labor_composition",
                "hours",
                "labor",
                "capital_tic",
                "capital_non_tic",
                "capital",
            )
        ]
        if activity == "Total de la economía":
            name = rf"\textbf{{{name}}}"
            values = [rf"\textbf{{{value}}}" for value in values]
        detail.append(
            "{} & {} & {} & {} & {} & {} & {} \\\\".format(
                name,
                *values,
            )
        )
        if activity == "Total de la economía":
            detail.append(r"\midrule")
    detail.extend(
        [
            r"\bottomrule",
            r"\multicolumn{7}{p{15.9cm}}{\footnotesize \textit{Nota:} aportes en puntos porcentuales promedio por año. Trabajo es la suma de composición laboral y horas; capital es la suma de capital TIC y no TIC. El total de la economía corresponde a la serie agregada publicada por el DANE y no a la suma ni al promedio simple de las actividades.}\\",
            r"\multicolumn{7}{l}{\footnotesize Fuente: cálculos del CJC con base en DANE, anexo PTF 2025.}\\",
            r"\end{longtable}",
            r"\endgroup",
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


def write_aggregate_contribution_tables(
    long_rows: list[dict[str, float | int | str]],
    period_rows: list[dict[str, float | int | str]],
) -> None:
    sectors = [
        row for row in long_rows if str(row["activity"]) != "Total de la economía"
    ]
    sectors.sort(key=lambda row: float(row["average_contribution"]), reverse=True)
    total = next(
        row for row in long_rows if str(row["activity"]) == "Total de la economía"
    )
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Evolución de la PTF por actividad y contribución al total, 2005--2024}",
        r"\label{tab:contribucion_ptf_total}",
        r"\footnotesize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular}{p{4.3cm}>{\raggedleft\arraybackslash}p{1.7cm}>{\raggedleft\arraybackslash}p{2.25cm}>{\raggedleft\arraybackslash}p{2.2cm}>{\raggedleft\arraybackslash}p{2.35cm}}",
        r"\toprule",
        r"Actividad & Peso promedio & Crecimiento acumulado & PTF anualizada & Contribución al total \\",
        r" & (\%) & 2005--2024 (\%) & (pp por año) & (pp por año) \\",
        r"\midrule",
    ]
    for row in sectors:
        lines.append(
            "{} & {} & {} & {} & {} \\\\".format(
                tex_escape(TEX_NAMES[str(row["activity"])]),
                tex_fmt(float(row["average_weight"]) * 100),
                tex_fmt(float(row["ptf_index_2024"]) - 100),
                tex_fmt(float(row["average_sector_ptf"])),
                tex_fmt3(float(row["average_contribution"])),
            )
        )
    lines.extend(
        [
            r"\midrule",
            r"\textbf{Total de la economía} & \textbf{100,00} & "
            + rf"\textbf{{{tex_fmt(float(total['ptf_index_2024']) - 100)}}} & "
            + rf"\textbf{{{tex_fmt(float(total['average_sector_ptf']))}}} & "
            + rf"\textbf{{{tex_fmt3(float(total['average_contribution']))}}} \\",
            r"\bottomrule",
            r"\end{tabular}",
            r"\vspace{0.15cm}",
            r"\begin{minipage}{0.96\textwidth}",
            r"\footnotesize \textit{Nota:} el crecimiento acumulado compara el índice de 2024 con el de 2005; la PTF anualizada es la variación logarítmica promedio. Ambas medidas describen la PTF dentro de cada actividad y los acumulados sectoriales no se suman. La contribución multiplica cada PTF anual por su peso anual antes de promediar; las nueve contribuciones suman la PTF del total de la economía. Las cifras pueden no sumar por redondeo.",
            r"\par\textit{Fuente:} cálculos del CJC con base en DANE, anexo PTF 2025.",
            r"\end{minipage}",
            r"\end{table}",
        ]
    )
    (SECTIONS / "tabla_contribucion_ptf_total.tex").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    periods = ["2006-2010", "2011-2015", "2016-2019", "2020-2024"]
    by_key = {
        (str(row["activity"]), str(row["period"])): float(
            row["average_contribution"]
        )
        for row in period_rows
    }
    total_by_period = {
        period: sum(by_key[(activity, period)] for activity in SHORT.values())
        for period in periods
    }
    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Contribución de cada actividad a la PTF total por subperiodo}",
        r"\label{tab:contribucion_ptf_subperiodos}",
        r"\footnotesize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular}{p{5.3cm}*{5}{>{\raggedleft\arraybackslash}p{1.45cm}}}",
        r"\toprule",
        r"Actividad & 2006--2010 & 2011--2015 & 2016--2019 & 2020--2024 & 2006--2024 \\",
        r"\midrule",
    ]
    long_lookup = {
        str(row["activity"]): float(row["average_contribution"])
        for row in long_rows
    }
    for activity in SHORT.values():
        lines.append(
            "{} & {} & {} & {} & {} & {} \\\\".format(
                tex_escape(TEX_NAMES[activity]),
                *[tex_fmt3(by_key[(activity, period)]) for period in periods],
                tex_fmt3(long_lookup[activity]),
            )
        )
    lines.extend(
        [
            r"\midrule",
            r"\textbf{Total de la economía} & "
            + " & ".join(
                rf"\textbf{{{tex_fmt3(total_by_period[period])}}}"
                for period in periods
            )
            + rf" & \textbf{{{tex_fmt3(long_lookup['Total de la economía'])}}} \\",
            r"\bottomrule",
            r"\end{tabular}",
            r"\vspace{0.15cm}",
            r"\begin{minipage}{0.96\textwidth}",
            r"\footnotesize \textit{Nota:} promedio anual en puntos porcentuales. Cada celda es el promedio del producto entre el peso anual de la actividad y su PTF anual. Los subperiodos tienen distinta duración.",
            r"\par\textit{Fuente:} cálculos del CJC con base en DANE, anexo PTF 2025.",
            r"\end{minipage}",
            r"\end{table}",
        ]
    )
    (SECTIONS / "tabla_contribucion_ptf_subperiodos.tex").write_text(
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


def draw_total_index(
    index_rows: list[dict[str, float | int | str]],
) -> None:
    rows = [
        row
        for row in index_rows
        if str(row["activity"]) == "Total de la economía"
    ]
    rows.sort(key=lambda row: int(row["year"]))
    img, draw, f = canvas(
        "Índice encadenado de la PTF del total de la economía",
        "Enfoque de producción, 2005=100",
        1800,
        1000,
    )
    left, right, top, bottom = 140, 1690, 225, 815
    ymin, ymax = 97.0, 103.0
    for tick in [97, 98, 99, 100, 101, 102, 103]:
        y = bottom - (tick - ymin) / (ymax - ymin) * (bottom - top)
        draw.line(
            (left, y, right, y),
            fill=BLUE if tick == 100 else GRID,
            width=3 if tick == 100 else 1,
        )
        draw.text((75, y - 13), str(tick), fill=GRAY, font=f["small"])
    points = []
    for row in rows:
        year = int(row["year"])
        value = float(row["index"])
        x = left + (year - 2005) / (2024 - 2005) * (right - left)
        y = bottom - (value - ymin) / (ymax - ymin) * (bottom - top)
        points.append((x, y))
    draw.line(points, fill=MID_BLUE, width=6)
    for x, y in points:
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=MID_BLUE)
    for year in [2005, 2006, 2010, 2015, 2020, 2024]:
        x = left + (year - 2005) / (2024 - 2005) * (right - left)
        draw.text((x - 26, bottom + 22), str(year), fill=GRAY, font=f["small"])
    label_rows = {
        2005: (14, -55),
        2006: (10, -55),
        2020: (-45, 18),
        2024: (-80, -55),
    }
    for row in rows:
        year = int(row["year"])
        if year not in label_rows:
            continue
        value = float(row["index"])
        x = left + (year - 2005) / (2024 - 2005) * (right - left)
        y = bottom - (value - ymin) / (ymax - ymin) * (bottom - top)
        dx, dy = label_rows[year]
        draw.text(
            (x + dx, y + dy),
            f"{value:.1f}".replace("-", "−"),
            fill=BLUE,
            font=f["axis_bold"],
        )
    draw.text(
        (80, 900),
        "Nota: cada variación anual se encadena de forma multiplicativa. La escala vertical se concentra entre 97 y 103.",
        fill=GRAY,
        font=f["small"],
    )
    draw.text(
        (80, 935),
        "Fuente: cálculos del CJC con base en DANE, anexo PTF 2025.",
        fill=GRAY,
        font=f["small"],
    )
    img.save(FIGURES / "fig_ptf_total_encadenada.png", quality=95)


def draw_aggregate_contributions(
    long_rows: list[dict[str, float | int | str]],
) -> None:
    sector_rows = [
        row for row in long_rows if str(row["activity"]) != "Total de la economía"
    ]
    sector_rows.sort(key=lambda row: float(row["average_contribution"]))
    total = next(
        row for row in long_rows if str(row["activity"]) == "Total de la economía"
    )
    rows = [*sector_rows, total]
    img, draw, f = canvas(
        "Contribuciones de las actividades a la PTF total",
        "Acumuladas y anualizadas, 2006–2024",
        1800,
        1120,
    )
    left_label = 55
    top, bottom = 275, 910
    cumulative_left, cumulative_right = 610, 1090
    annualized_left, annualized_right = 1240, 1720
    cumulative_min, cumulative_max = -3.0, 3.3
    annualized_min, annualized_max = -0.17, 0.17

    draw.text(
        (645, 185),
        "Contribución acumulada (puntos logarítmicos)",
        fill=BLUE,
        font=f["small_bold"],
    )
    draw.text(
        (1290, 185),
        "Contribución anualizada (pp por año)",
        fill=BLUE,
        font=f["small_bold"],
    )
    def x_position(
        value: float,
        left: float,
        right: float,
        minimum: float,
        maximum: float,
    ) -> float:
        return left + (value - minimum) / (maximum - minimum) * (right - left)

    for tick in [-3, -2, -1, 0, 1, 2, 3]:
        x = x_position(
            tick,
            cumulative_left,
            cumulative_right,
            cumulative_min,
            cumulative_max,
        )
        draw.line(
            (x, top, x, bottom),
            fill=BLUE if tick == 0 else GRID,
            width=3 if tick == 0 else 1,
        )
        draw.text(
            (x - 12, bottom + 18),
            str(tick).replace("-", "−"),
            fill=GRAY,
            font=f["small"],
        )

    for tick in [-0.15, -0.10, -0.05, 0, 0.05, 0.10, 0.15]:
        x = x_position(
            tick,
            annualized_left,
            annualized_right,
            annualized_min,
            annualized_max,
        )
        draw.line(
            (x, top, x, bottom),
            fill=BLUE if tick == 0 else GRID,
            width=3 if tick == 0 else 1,
        )
        draw.text(
            (x - 24, bottom + 18),
            f"{tick:.2f}".replace("-", "−"),
            fill=GRAY,
            font=f["small"],
        )

    cumulative_zero = x_position(
        0,
        cumulative_left,
        cumulative_right,
        cumulative_min,
        cumulative_max,
    )
    annualized_zero = x_position(
        0,
        annualized_left,
        annualized_right,
        annualized_min,
        annualized_max,
    )
    row_h = (bottom - top) / len(rows)
    for index, row in enumerate(rows):
        y = top + (index + 0.5) * row_h
        is_total = str(row["activity"]) == "Total de la economía"
        accumulated = float(row["cumulative_log_contribution"])
        annualized = float(row["average_contribution"])
        accumulated_x = x_position(
            accumulated,
            cumulative_left,
            cumulative_right,
            cumulative_min,
            cumulative_max,
        )
        annualized_x = x_position(
            annualized,
            annualized_left,
            annualized_right,
            annualized_min,
            annualized_max,
        )
        color = "#333333" if is_total else (MID_BLUE if annualized >= 0 else RED)
        if is_total:
            separator_y = y - row_h / 2
            draw.line(
                (left_label, separator_y, annualized_right, separator_y),
                fill=BLUE,
                width=3,
            )
        draw.text(
            (left_label, y - 15),
            str(row["activity"]),
            fill="#222222",
            font=f["axis_bold"] if is_total else f["axis"],
        )
        draw.rectangle(
            (
                min(accumulated_x, cumulative_zero),
                y - 20,
                max(accumulated_x, cumulative_zero),
                y + 20,
            ),
            fill=color,
        )
        draw.rectangle(
            (
                min(annualized_x, annualized_zero),
                y - 20,
                max(annualized_x, annualized_zero),
                y + 20,
            ),
            fill=color,
        )

        accumulated_label = f"{accumulated:.2f}".replace("-", "−")
        annualized_label = f"{annualized:.3f}".replace("-", "−")
        accumulated_box = draw.textbbox(
            (0, 0),
            accumulated_label,
            font=f["small_bold"],
        )
        annualized_box = draw.textbbox(
            (0, 0),
            annualized_label,
            font=f["small_bold"],
        )
        accumulated_width = accumulated_box[2] - accumulated_box[0]
        annualized_width = annualized_box[2] - annualized_box[0]
        draw.text(
            (
                accumulated_x + 10
                if accumulated >= 0
                else accumulated_x - accumulated_width - 10,
                y - 13,
            ),
            accumulated_label,
            fill=color,
            font=f["small_bold"],
        )
        draw.text(
            (
                annualized_x + 10
                if annualized >= 0
                else annualized_x - annualized_width - 10,
                y - 13,
            ),
            annualized_label,
            fill=color,
            font=f["small_bold"],
        )

    draw.text(
        (70, 992),
        "Nota: el acumulado suma las 19 contribuciones anuales en puntos logarítmicos; la anualizada divide esa suma por 19.",
        fill=GRAY,
        font=f["small"],
    )
    draw.text(
        (70, 1029),
        "El acumulado no se interpreta como puntos porcentuales del cambio acumulado de −1,52%.",
        fill=GRAY,
        font=f["small"],
    )
    draw.text(
        (70, 1066),
        "Fuente: cálculos del CJC con base en DANE, anexo PTF 2025.",
        fill=GRAY,
        font=f["small"],
    )
    img.save(FIGURES / "fig_ptf_contribucion_total_actividad.png", quality=95)


def draw_aggregate_contributions_by_period(
    period_rows: list[dict[str, float | int | str]],
) -> None:
    periods = ["2006-2010", "2011-2015", "2016-2019", "2020-2024"]
    period_labels = ["2006–2010", "2011–2015", "2016–2019", "2020–2024"]
    colors = ["#9FBAD9", "#4F81BD", "#244A7C", "#E0A12B"]
    lookup = {
        (str(row["activity"]), str(row["period"])): float(
            row["average_contribution"]
        )
        for row in period_rows
    }
    activities = ["Total de la economía", *SHORT.values()]
    for period in periods:
        lookup[("Total de la economía", period)] = sum(
            lookup[(activity, period)] for activity in SHORT.values()
        )
    img, draw, f = canvas(
        "Contribución de las actividades a la PTF total por subperiodo",
        "Promedio anual (puntos porcentuales)",
        1800,
        1120,
    )
    left, right, top, bottom = 620, 1690, 255, 970
    xmin, xmax = -0.32, 0.30
    xscale = (right - left) / (xmax - xmin)
    for tick in [-0.3, -0.2, -0.1, 0, 0.1, 0.2, 0.3]:
        x = left + (tick - xmin) * xscale
        draw.line(
            (x, top, x, bottom),
            fill=BLUE if tick == 0 else GRID,
            width=3 if tick == 0 else 1,
        )
        draw.text(
            (x - 20, bottom + 18),
            f"{tick:.1f}".replace("-", "−"),
            fill=GRAY,
            font=f["small"],
        )
    legend_x = 600
    for label, color in zip(period_labels, colors):
        draw.ellipse((legend_x, 190, legend_x + 24, 214), fill=color)
        draw.text((legend_x + 34, 188), label, fill="#333333", font=f["small"])
        legend_x += 240
    row_h = (bottom - top) / len(activities)
    for index, activity in enumerate(activities):
        y = top + (index + 0.5) * row_h
        draw.text((65, y - 14), activity, fill="#222222", font=f["axis"])
        points = []
        for period_index, period in enumerate(periods):
            value = lookup[(activity, period)]
            x = left + (value - xmin) * xscale
            yy = y + (period_index - 1.5) * 9
            points.append((x, yy))
        draw.line(points, fill="#A7A7A7", width=3)
        for period_index, (x, yy) in enumerate(points):
            draw.ellipse(
                (x - 9, yy - 9, x + 9, yy + 9),
                fill=colors[period_index],
            )
        if activity == "Total de la economía":
            draw.line(
                (55, y + row_h / 2, right, y + row_h / 2),
                fill=BLUE,
                width=3,
            )
    draw.text(
        (70, 1065),
        "Fuente: cálculos del CJC con base en DANE, anexo PTF 2025.",
        fill=GRAY,
        font=f["small"],
    )
    img.save(FIGURES / "fig_ptf_contribucion_subperiodos.png", quality=95)


def draw_ptf_bars(long_run: list[dict[str, float | int | str]]) -> None:
    sector_rows = sorted(
        [
            row
            for row in long_run
            if str(row["activity"]) != "Total de la economía"
        ],
        key=lambda d: float(d["average_sector_ptf"]),
        reverse=True,
    )
    total = next(
        row for row in long_run if str(row["activity"]) == "Total de la economía"
    )
    rows = [*sector_rows, total]
    img, draw, f = canvas(
        "Crecimiento acumulado y anualizado de la PTF",
        "Total y actividades, 2005–2024",
        1800,
        1180,
    )
    left_label = 55
    top, bottom = 260, 955
    accumulated_left, accumulated_right = 600, 1080
    annualized_left, annualized_right = 1245, 1725
    accumulated_min, accumulated_max = -40.0, 30.0
    annualized_min, annualized_max = -2.6, 1.6

    draw.text(
        (665, 190),
        "Crecimiento acumulado (%)",
        fill=BLUE,
        font=f["small_bold"],
    )
    draw.text(
        (1300, 190),
        "PTF anualizada (pp por año)",
        fill=BLUE,
        font=f["small_bold"],
    )

    def x_position(
        value: float,
        left: float,
        right: float,
        minimum: float,
        maximum: float,
    ) -> float:
        return left + (value - minimum) / (maximum - minimum) * (right - left)

    for tick in [-40, -20, 0, 20]:
        x = x_position(
            tick,
            accumulated_left,
            accumulated_right,
            accumulated_min,
            accumulated_max,
        )
        draw.line(
            (x, top, x, bottom),
            fill=BLUE if tick == 0 else GRID,
            width=3 if tick == 0 else 1,
        )
        draw.text(
            (x - 17, bottom + 18),
            str(tick).replace("-", "−"),
            fill=GRAY,
            font=f["small"],
        )

    for tick in [-2, -1, 0, 1]:
        x = x_position(
            tick,
            annualized_left,
            annualized_right,
            annualized_min,
            annualized_max,
        )
        draw.line(
            (x, top, x, bottom),
            fill=BLUE if tick == 0 else GRID,
            width=3 if tick == 0 else 1,
        )
        draw.text(
            (x - 10, bottom + 18),
            str(tick).replace("-", "−"),
            fill=GRAY,
            font=f["small"],
        )

    accumulated_zero = x_position(
        0,
        accumulated_left,
        accumulated_right,
        accumulated_min,
        accumulated_max,
    )
    annualized_zero = x_position(
        0,
        annualized_left,
        annualized_right,
        annualized_min,
        annualized_max,
    )
    row_h = (bottom - top) / len(rows)
    for i, row in enumerate(rows):
        y = top + (i + 0.5) * row_h
        is_total = str(row["activity"]) == "Total de la economía"
        annualized = float(row["average_sector_ptf"])
        accumulated = float(row["ptf_index_2024"]) - 100
        accumulated_x = x_position(
            accumulated,
            accumulated_left,
            accumulated_right,
            accumulated_min,
            accumulated_max,
        )
        annualized_x = x_position(
            annualized,
            annualized_left,
            annualized_right,
            annualized_min,
            annualized_max,
        )
        color = GRAY if is_total else (MID_BLUE if annualized >= 0 else RED)
        if is_total:
            separator_y = y - row_h / 2
            draw.line(
                (left_label, separator_y, annualized_right, separator_y),
                fill=BLUE,
                width=3,
            )
        draw.text(
            (left_label, y - 16),
            str(row["activity"]),
            fill="#222222",
            font=f["axis_bold"] if is_total else f["axis"],
        )
        draw.rectangle(
            (
                min(accumulated_x, accumulated_zero),
                y - 18,
                max(accumulated_x, accumulated_zero),
                y + 18,
            ),
            fill=color,
        )
        draw.rectangle(
            (
                min(annualized_x, annualized_zero),
                y - 18,
                max(annualized_x, annualized_zero),
                y + 18,
            ),
            fill=color,
        )

        accumulated_label = f"{accumulated:.1f}".replace("-", "−")
        annualized_label = fmt(annualized)
        accumulated_box = draw.textbbox(
            (0, 0),
            accumulated_label,
            font=f["small_bold"],
        )
        annualized_box = draw.textbbox(
            (0, 0),
            annualized_label,
            font=f["small_bold"],
        )
        accumulated_label_width = accumulated_box[2] - accumulated_box[0]
        annualized_label_width = annualized_box[2] - annualized_box[0]
        draw.text(
            (
                accumulated_x + 9
                if accumulated >= 0
                else accumulated_x - accumulated_label_width - 9,
                y - 13,
            ),
            accumulated_label,
            fill=color,
            font=f["small_bold"],
        )
        draw.text(
            (
                annualized_x + 9
                if annualized >= 0
                else annualized_x - annualized_label_width - 9,
                y - 13,
            ),
            annualized_label,
            fill=color,
            font=f["small_bold"],
        )
    draw.text(
        (70, 1035),
        "Nota: el acumulado compara 2024 con 2005. La medida anualizada es la variación logarítmica promedio.",
        fill=GRAY,
        font=f["small"],
    )
    draw.text(
        (70, 1080),
        "Fuente: cálculos del CJC con base en DANE, anexo PTF 2025.",
        fill=GRAY,
        font=f["small"],
    )
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
    years = list(range(2006, 2025))
    sector_activities = [
        activity for activity in ACTIVITY_ORDER if activity != "Total de la economía"
    ]
    cumulative_ptf = {
        activity: 100
        * (
            math.exp(
                sum(lookup[(activity, year)] for year in years) / 100
            )
            - 1
        )
        for activity in sector_activities
    }
    activities = [
        *sorted(sector_activities, key=cumulative_ptf.get),
        "Total de la economía",
    ]
    img, draw, f = canvas(
        "Variación anual de la PTF: total y actividades",
        "2006–2024, puntos porcentuales; actividades ordenadas por PTF acumulada, de menor a mayor",
        1900,
        1200,
    )
    left, top = 520, 235
    cell_w, cell_h = 68, 70
    for j, year in enumerate(years):
        x = left + j * cell_w
        draw.text((x + 7, top - 38), str(year)[2:], fill=GRAY, font=f["small"])
    for i, activity in enumerate(activities):
        y = top + i * cell_h
        if activity == "Total de la economía":
            draw.line(
                (55, y - 3, left + len(years) * cell_w, y - 3),
                fill=BLUE,
                width=4,
            )
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
    contribution_annual = load_numeric_csv(
        CONTRIBUTION_ANNUAL_CSV,
        {"activity"},
        {"year"},
    )
    contribution_long = load_numeric_csv(
        CONTRIBUTION_LONG_CSV,
        {"activity"},
    )
    contribution_periods = load_numeric_csv(
        CONTRIBUTION_PERIOD_CSV,
        {"period", "activity"},
        {"start", "end"},
    )
    index_rows = load_numeric_csv(
        INDEX_CSV,
        {"activity"},
        {"year"},
    )
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
    write_csv(PROCESSED / "ptf_actividad_promedio_2006_2024.csv", long_run)
    write_csv(PROCESSED / "ptf_actividad_promedio_2006_2019.csv", pre)
    write_csv(PROCESSED / "ptf_actividad_promedio_2020_2024.csv", post)
    write_csv(PROCESSED / "ptf_total_economia_promedio_2006_2024.csv", total_long_run)
    write_tex_tables(comparison_long_run)
    write_evolution_table(comparison_long_run, comparison_period_summaries)
    write_aggregate_contribution_tables(contribution_long, contribution_periods)
    draw_total_index(index_rows)
    draw_aggregate_contributions(contribution_long)
    draw_aggregate_contributions_by_period(contribution_periods)
    draw_ptf_bars(contribution_long)
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
    annual_lookup = {
        int(row["year"]): float(row["ptf"])
        for row in total_observations
        if 2006 <= int(row["year"]) <= 2024
    }
    max_aggregate_error = max(
        abs(
            sum(
                float(row["contribution"])
                for row in contribution_annual
                if int(row["year"]) == year
            )
            - annual_lookup[year]
        )
        for year in annual_lookup
    )
    print(
        "Error máximo suma de contribuciones sectoriales = PTF total: "
        f"{max_aggregate_error:.3e}"
    )


if __name__ == "__main__":
    main()
