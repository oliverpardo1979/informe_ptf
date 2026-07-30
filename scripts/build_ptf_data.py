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
VALUE_ADDED_TOTAL_CSV = (
    ROOT / "data" / "processed" / "ptf_valor_agregado_total_anual.csv"
)
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
COUNTERFACTUAL_ANNUAL_CSV = (
    ROOT / "data" / "processed" / "ptf_contrafactual_cuatro_actividades_anual.csv"
)
COUNTERFACTUAL_SUMMARY_CSV = (
    ROOT / "data" / "processed" / "ptf_contrafactual_cuatro_actividades_resumen.csv"
)
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

VALUE_ADDED_FIELDS = [
    "gross_value_added",
    "labor",
    "capital",
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
    "Agricultura": "Agropecuario",
    "Minería": "Minería",
    "Manufactura": "Manufactura",
    "Electricidad, gas y agua": "Servicios públicos",
    "Construcción": "Construcción",
    "Comercio, hoteles y restaurantes": "Comercio y hotelería",
    "Transporte y comunicaciones": "Transporte y comunicaciones",
    "Finanzas e inmobiliarias": "Financieras",
    "Servicios sociales": "Servicios sociales y personales",
}

FIGURE_NAMES = {
    "Total de la economía": "Total de la economía",
    "Agricultura": "Agropecuario",
    "Minería": "Minería",
    "Manufactura": "Manufactura",
    "Electricidad, gas y agua": "Servicios públicos",
    "Construcción": "Construcción",
    "Comercio, hoteles y restaurantes": "Comercio y hotelería",
    "Transporte y comunicaciones": "Transporte y comunicaciones",
    "Finanzas e inmobiliarias": "Financieras",
    "Servicios sociales": "Servicios sociales y personales",
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


def load_value_added_total() -> list[dict[str, float | int | str]]:
    observations = load_numeric_csv(
        VALUE_ADDED_TOTAL_CSV,
        set(),
        {"year"},
    )
    if len(observations) != 21:
        raise RuntimeError(
            "Se esperaban 21 observaciones del enfoque de valor agregado y "
            f"se obtuvieron {len(observations)}"
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


def build_counterfactual(
    total_observations: list[dict[str, float | int | str]],
    contribution_annual: list[dict[str, float | int | str]],
    contribution_long: list[dict[str, float | int | str]],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    sector_rows = [
        row
        for row in contribution_long
        if str(row["activity"]) != "Total de la economía"
    ]
    selected = sorted(
        sector_rows,
        key=lambda row: float(row["average_sector_ptf"]),
    )[:4]
    selected_names = {str(row["activity"]) for row in selected}
    expected_names = {
        "Minería",
        "Construcción",
        "Finanzas e inmobiliarias",
        "Electricidad, gas y agua",
    }
    if selected_names != expected_names:
        raise RuntimeError(
            "Las cuatro actividades con menor PTF cambiaron: "
            f"{sorted(selected_names)}"
        )

    total_by_year = {
        int(row["year"]): row
        for row in total_observations
        if 2005 <= int(row["year"]) <= 2024
    }
    contributions_by_year: dict[int, list[dict[str, float | int | str]]] = (
        defaultdict(list)
    )
    for row in contribution_annual:
        contributions_by_year[int(row["year"])].append(row)

    annual_rows: list[dict[str, object]] = []
    for year in range(2005, 2025):
        selected_contribution = sum(
            float(row["contribution"])
            for row in contributions_by_year[year]
            if str(row["activity"]) in selected_names
        )
        all_contributions = sum(
            float(row["contribution"]) for row in contributions_by_year[year]
        )
        observed_ptf = float(total_by_year[year]["ptf"])
        observed_production = float(total_by_year[year]["production"])
        if abs(all_contributions - observed_ptf) > 1e-9:
            raise RuntimeError(
                f"Las contribuciones no reproducen la PTF total en {year}"
            )
        annual_rows.append(
            {
                "year": year,
                "selected_contribution": selected_contribution,
                "observed_ptf": observed_ptf,
                "counterfactual_ptf": observed_ptf - selected_contribution,
                "observed_production": observed_production,
                "counterfactual_production": (
                    observed_production - selected_contribution
                ),
            }
        )

    n = len(annual_rows)
    observed_ptf_average = sum(
        float(row["observed_ptf"]) for row in annual_rows
    ) / n
    counterfactual_ptf_average = sum(
        float(row["counterfactual_ptf"]) for row in annual_rows
    ) / n
    observed_production_average = sum(
        float(row["observed_production"]) for row in annual_rows
    ) / n
    counterfactual_production_average = sum(
        float(row["counterfactual_production"]) for row in annual_rows
    ) / n
    observed_output_index = 100 * math.exp(
        sum(float(row["observed_production"]) for row in annual_rows) / 100
    )
    counterfactual_output_index = 100 * math.exp(
        sum(float(row["counterfactual_production"]) for row in annual_rows)
        / 100
    )
    summary_rows: list[dict[str, object]] = [
        {
            "scenario": "Observado",
            "average_ptf": observed_ptf_average,
            "average_production_growth": observed_production_average,
            "output_index_2024": observed_output_index,
            "cumulative_production_growth": observed_output_index - 100,
            "level_difference_vs_observed": 0.0,
        },
        {
            "scenario": (
                "Tasa anual de crecimiento de la PTF igual a cero "
                "en las cuatro actividades"
            ),
            "average_ptf": counterfactual_ptf_average,
            "average_production_growth": counterfactual_production_average,
            "output_index_2024": counterfactual_output_index,
            "cumulative_production_growth": counterfactual_output_index - 100,
            "level_difference_vs_observed": (
                100 * (counterfactual_output_index / observed_output_index - 1)
            ),
        },
    ]
    driver_rows: list[dict[str, object]] = [
        {
            "activity": str(row["activity"]),
            "average_sector_ptf": float(row["average_sector_ptf"]),
            "average_contribution": float(row["average_contribution"]),
            "change_in_aggregate_growth": -float(row["average_contribution"]),
        }
        for row in selected
    ]
    driver_rows.sort(
        key=lambda row: float(row["change_in_aggregate_growth"]),
        reverse=True,
    )
    expected_change = sum(
        float(row["change_in_aggregate_growth"]) for row in driver_rows
    )
    observed_change = (
        counterfactual_production_average - observed_production_average
    )
    if abs(expected_change - observed_change) > 1e-12:
        raise RuntimeError(
            "El contrafactual no coincide con la suma de las contribuciones"
        )
    return annual_rows, summary_rows, driver_rows


def build_value_added_counterfactual(
    observations: list[dict[str, float | int | str]],
) -> list[dict[str, object]]:
    rows = [
        row
        for row in observations
        if 2005 <= int(row["year"]) <= 2025
    ]
    if len(rows) != 21:
        raise RuntimeError(
            "El contrafactual de valor agregado requiere 21 observaciones"
        )
    max_identity_error = max(
        abs(
            float(row["gross_value_added"])
            - float(row["labor"])
            - float(row["capital"])
            - float(row["ptf"])
        )
        for row in rows
    )
    if max_identity_error > 1e-9:
        raise RuntimeError(
            "No reconcilia la identidad de valor agregado: "
            f"{max_identity_error}"
        )

    averages = {
        field: sum(float(row[field]) for row in rows) / len(rows)
        for field in VALUE_ADDED_FIELDS
    }
    observed_index = 100 * math.exp(
        sum(float(row["gross_value_added"]) for row in rows) / 100
    )
    counterfactual_index = observed_index * math.exp(len(rows) / 100)
    return [
        {
            "scenario": "Observado",
            **averages,
            "value_added_index_2025": observed_index,
            "level_difference_vs_observed": 0.0,
            "annual_tfp_increment": 0.0,
        },
        {
            "scenario": (
                "Tasa anual de crecimiento de la PTF un punto "
                "porcentual mayor"
            ),
            **{
                **averages,
                "gross_value_added": averages["gross_value_added"] + 1,
                "factors": averages["factors"],
                "ptf": averages["ptf"] + 1,
            },
            "value_added_index_2025": counterfactual_index,
            "level_difference_vs_observed": (
                100 * (counterfactual_index / observed_index - 1)
            ),
            "annual_tfp_increment": 1.0,
        },
    ]


def fmt(value: float) -> str:
    if abs(value) < 0.005:
        value = 0.0
    return f"{value:.2f}".replace("-", "−")


def tex_fmt(value: float) -> str:
    if abs(value) < 0.005:
        value = 0.0
    return f"{value:.2f}".replace(".", ",")


def tex_escape(text: str) -> str:
    return text.replace("&", r"\&").replace("%", r"\%")


def write_tex_tables(long_run: list[dict[str, float | int | str]]) -> None:
    lines = [
        r"\begingroup",
        r"\small",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{longtable}{p{4.45cm}rrrrrrr}",
        r"\caption{Descomposición promedio anual del crecimiento de la producción por actividad, 2005--2024}",
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
            r"\multicolumn{8}{p{15.9cm}}{\footnotesize \textit{Nota:} la producción y la PTF se expresan como tasas de crecimiento logarítmicas anualizadas (\%). Trabajo, capital, energía, materiales y servicios son contribuciones al crecimiento, en puntos porcentuales por año. Como la PTF entra con coeficiente uno en la identidad contable, su tasa también equivale numéricamente a su contribución. El periodo usa las 20 tasas anuales de 2005 a 2024, que enlazan los niveles de 2004 y 2024. El total de la economía corresponde a la serie agregada publicada por el DANE y no a la suma ni al promedio simple de las actividades. Por redondeo, los componentes pueden no sumar exactamente la producción.}\\",
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
        r"\caption{Descomposición de los servicios de trabajo y capital, promedio anual 2005--2024}",
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
        r"Actividad & 2005--10 & 2011--15 & 2016--19 & 2020--24 & 2005--24 & Años positivos \\",
        r"\midrule",
    ]
    for row in long_run:
        activity = str(row["activity"])
        values = [
            float(by_period[label][activity]["ptf"])
            for label, _ in period_summaries
        ]
        lines.append(
            "{} & {} & {} & {} & {} & {} & {}/20 \\\\".format(
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
            r"\footnotesize \textit{Nota:} tasas de crecimiento logarítmicas anualizadas de la PTF (\%). Como la PTF entra con coeficiente uno en la identidad contable de cada actividad, la tasa también equivale numéricamente a su contribución al crecimiento de la producción. El total de la economía corresponde a la serie agregada publicada por el DANE y no a un promedio simple de las actividades. Los subperiodos tienen distinta duración; se usan para describir cambios en la trayectoria, no para atribuirlos a un evento específico.",
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
        r"Actividad & Peso promedio & Crecimiento acumulado & Tasa anualizada de la PTF & Contribución al total \\",
        r" & (\%) & 2005--2024 (\%) & (\%) & (pp por año) \\",
        r"\midrule",
    ]
    for row in sectors:
        lines.append(
            "{} & {} & {} & {} & {} \\\\".format(
                tex_escape(TEX_NAMES[str(row["activity"])]),
                tex_fmt(float(row["average_weight"]) * 100),
                tex_fmt(float(row["ptf_index_2024"]) - 100),
                tex_fmt(float(row["average_sector_ptf"])),
                tex_fmt(float(row["average_contribution"])),
            )
        )
    lines.extend(
        [
            r"\midrule",
            r"\textbf{Total de la economía} & \textbf{100,00} & "
            + rf"\textbf{{{tex_fmt(float(total['ptf_index_2024']) - 100)}}} & "
            + rf"\textbf{{{tex_fmt(float(total['average_sector_ptf']))}}} & "
            + rf"\textbf{{{tex_fmt(float(total['average_contribution']))}}} \\",
            r"\bottomrule",
            r"\end{tabular}",
            r"\vspace{0.15cm}",
            r"\begin{minipage}{0.96\textwidth}",
            r"\footnotesize \textit{Nota:} el crecimiento acumulado de 2005 a 2024 compara el índice al final de 2024 con el índice al final de 2004; la tasa anualizada es el promedio de las 20 tasas de crecimiento logarítmicas anuales de 2005 a 2024. Ambas medidas describen la PTF dentro de cada actividad y los crecimientos acumulados sectoriales no se suman. La contribución multiplica la tasa de crecimiento anual de la PTF de cada actividad por su peso anual antes de promediar; las nueve contribuciones suman la tasa de crecimiento de la PTF del total de la economía. Las cifras pueden no sumar por redondeo.",
            r"\par\textit{Fuente:} cálculos del CJC con base en DANE, anexo PTF 2025.",
            r"\end{minipage}",
            r"\end{table}",
        ]
    )
    (SECTIONS / "tabla_contribucion_ptf_total.tex").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    periods = ["2005-2010", "2011-2015", "2016-2019", "2020-2024"]
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
        r"Actividad & 2005--2010 & 2011--2015 & 2016--2019 & 2020--2024 & 2005--2024 \\",
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
                *[tex_fmt(by_key[(activity, period)]) for period in periods],
                tex_fmt(long_lookup[activity]),
            )
        )
    lines.extend(
        [
            r"\midrule",
            r"\textbf{Total de la economía} & "
            + " & ".join(
                rf"\textbf{{{tex_fmt(total_by_period[period])}}}"
                for period in periods
            )
            + rf" & \textbf{{{tex_fmt(long_lookup['Total de la economía'])}}} \\",
            r"\bottomrule",
            r"\end{tabular}",
            r"\vspace{0.15cm}",
            r"\begin{minipage}{0.96\textwidth}",
            r"\footnotesize \textit{Nota:} promedio anual en puntos porcentuales. Cada celda es el promedio del producto entre el peso anual de la actividad y la tasa anual de crecimiento de su PTF. Los subperiodos tienen distinta duración.",
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


def draw_activity_label(
    draw: ImageDraw.ImageDraw,
    f: dict[str, ImageFont.FreeTypeFont],
    activity: str,
    x: float,
    y: float,
    *,
    bold: bool = False,
) -> None:
    label = FIGURE_NAMES[activity]
    font = f["small_bold"] if bold else f["small"]
    box = draw.multiline_textbbox(
        (0, 0),
        label,
        font=font,
        spacing=1,
    )
    height = box[3] - box[1]
    draw.multiline_text(
        (x, y - height / 2),
        label,
        fill="#222222",
        font=font,
        spacing=1,
    )


def draw_value_added_tfp_bars(
    observations: list[dict[str, float | int | str]],
) -> None:
    rows = [
        row
        for row in observations
        if 2005 <= int(row["year"]) <= 2025
    ]
    rows.sort(key=lambda row: int(row["year"]))
    img, draw, f = canvas(
        "Crecimiento de la PTF",
        "Enfoque de valor agregado, 2005–2025; tasa logarítmica (%)",
        1800,
        1000,
    )
    left, right, top, bottom = 125, 1710, 220, 790
    ymin, ymax = -3.0, 5.0

    def y_position(value: float) -> float:
        return bottom - (value - ymin) / (ymax - ymin) * (bottom - top)

    for tick in range(-3, 6):
        y = y_position(float(tick))
        draw.line(
            (left, y, right, y),
            fill=BLUE if tick == 0 else GRID,
            width=3 if tick == 0 else 1,
        )
        draw.text((72, y - 13), str(tick), fill=GRAY, font=f["small"])

    step = (right - left) / len(rows)
    bar_width = step * 0.62
    zero_y = y_position(0.0)
    for index, row in enumerate(rows):
        year = int(row["year"])
        value = float(row["ptf"])
        x_center = left + step * (index + 0.5)
        value_y = y_position(value)
        fill = MID_BLUE if value >= 0 else RED
        draw.rectangle(
            (
                x_center - bar_width / 2,
                min(zero_y, value_y),
                x_center + bar_width / 2,
                max(zero_y, value_y),
            ),
            fill=fill,
        )
        value_label = f"{value:.1f}".replace("-", "−")
        label_box = draw.textbbox((0, 0), value_label, font=f["small_bold"])
        label_width = label_box[2] - label_box[0]
        label_y = value_y - 30 if value >= 0 else value_y + 6
        draw.text(
            (x_center - label_width / 2, label_y),
            value_label,
            fill=BLUE if value >= 0 else RED,
            font=f["small_bold"],
        )
        year_label = str(year)[2:]
        year_box = draw.textbbox((0, 0), year_label, font=f["small"])
        year_width = year_box[2] - year_box[0]
        draw.text(
            (x_center - year_width / 2, bottom + 19),
            year_label,
            fill=GRAY,
            font=f["small"],
        )

    draw.text(
        (80, 886),
        "Fuente: cálculos del CJC con base en DANE, anexo PTF 2025, Cuadro 1.",
        fill=GRAY,
        font=f["small"],
    )
    img.save(FIGURES / "fig_ptf_total_anual_valor_agregado.png", quality=95)


def draw_value_added_waterfall(summary: list[dict[str, object]]) -> None:
    observed = summary[0]
    labor = float(observed["labor"])
    capital = float(observed["capital"])
    ptf = float(observed["ptf"])
    value_added = float(observed["gross_value_added"])
    factors = labor + capital
    if abs(factors + ptf - value_added) > 1e-9:
        raise RuntimeError(
            "No reconcilia la cascada del crecimiento del valor agregado"
        )

    img, draw, f = canvas(
        "Descomposición del crecimiento del valor agregado bruto",
        "Puntos porcentuales por año",
        1800,
        1000,
    )
    left, right, top, bottom = 150, 1650, 245, 765
    ymin, ymax = 0.0, 4.2

    def y_position(value: float) -> float:
        return bottom - (value - ymin) / (ymax - ymin) * (bottom - top)

    for tick in range(0, 5):
        y = y_position(float(tick))
        draw.line(
            (left, y, right, y),
            fill=BLUE if tick == 0 else GRID,
            width=3 if tick == 0 else 1,
        )
        draw.text(
            (98, y - 13),
            str(tick),
            fill=GRAY,
            font=f["small"],
        )

    labels = ["Trabajo", "Capital", "PTF", "Valor agregado"]
    positions = [
        left + (index + 0.5) * (right - left) / len(labels)
        for index in range(len(labels))
    ]
    bar_width = 220
    positive_color = MID_BLUE
    negative_color = "#E0A12B"
    total_color = "#4A4A4A"

    components = [
        (labor, 0.0, labor, positive_color),
        (capital, labor, factors, positive_color),
        (ptf, factors, value_added, negative_color),
    ]
    previous_right = None
    for index, (change, start, end, color) in enumerate(components):
        x = positions[index]
        if previous_right is not None:
            draw.line(
                (
                    previous_right,
                    y_position(start),
                    x - bar_width / 2,
                    y_position(start),
                ),
                fill=GRAY,
                width=2,
            )
        draw.rectangle(
            (
                x - bar_width / 2,
                min(y_position(start), y_position(end)),
                x + bar_width / 2,
                max(y_position(start), y_position(end)),
            ),
            fill=color,
            outline=BLUE if change >= 0 else "#9A6A12",
            width=2,
        )
        label = f"{change:+.2f} pp".replace(".", ",").replace("-", "−")
        label_y = (
            min(y_position(start), y_position(end)) - 36
            if change >= 0
            else max(y_position(start), y_position(end)) + 36
        )
        draw.text(
            (x, label_y),
            label,
            fill=BLUE if change >= 0 else "#8A5A08",
            font=f["axis_bold"],
            anchor="ms",
        )
        previous_right = x + bar_width / 2

    total_x = positions[-1]
    draw.line(
        (
            previous_right,
            y_position(value_added),
            total_x - bar_width / 2,
            y_position(value_added),
        ),
        fill=GRAY,
        width=2,
    )
    draw.rectangle(
        (
            total_x - bar_width / 2,
            y_position(value_added),
            total_x + bar_width / 2,
            y_position(0.0),
        ),
        fill=total_color,
    )
    draw.text(
        (total_x, y_position(value_added) - 36),
        f"{value_added:.2f}%".replace(".", ","),
        fill=total_color,
        font=f["axis_bold"],
        anchor="ms",
    )

    for x, label in zip(positions, labels):
        draw.text(
            (x, bottom + 28),
            label,
            fill="#222222",
            font=f["axis"],
            anchor="ma",
        )

    draw.text(
        (80, 865),
        "Fuente: cálculos del CJC con base en DANE, Cuadro 1.",
        fill=GRAY,
        font=f["small"],
    )
    img.save(
        FIGURES / "fig_descomposicion_valor_agregado.png",
        quality=95,
    )


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
        "Enfoque de producción, 2004=100",
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
        x = left + (year - 2004) / (2024 - 2004) * (right - left)
        y = bottom - (value - ymin) / (ymax - ymin) * (bottom - top)
        points.append((x, y))
    draw.line(points, fill=MID_BLUE, width=6)
    for x, y in points:
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=MID_BLUE)
    for year in [2004, 2005, 2010, 2015, 2020, 2024]:
        x = left + (year - 2004) / (2024 - 2004) * (right - left)
        draw.text((x - 26, bottom + 22), str(year), fill=GRAY, font=f["small"])
    label_rows = {
        2004: (14, -55),
        2005: (14, -55),
        2020: (-45, 18),
        2024: (-80, -55),
    }
    for row in rows:
        year = int(row["year"])
        if year not in label_rows:
            continue
        value = float(row["index"])
        x = left + (year - 2004) / (2024 - 2004) * (right - left)
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
        "Nota: las tasas logarítmicas anuales se encadenan de forma multiplicativa. La escala vertical se concentra entre 97 y 103.",
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
    total_log_contribution = float(total["cumulative_log_contribution"])
    total_cumulative_change = 100 * math.expm1(total_log_contribution / 100)
    cumulative_scale = (
        total_cumulative_change / total_log_contribution
        if abs(total_log_contribution) > 1e-12
        else 1.0
    )
    cumulative_sector_sum = sum(
        float(row["cumulative_log_contribution"]) * cumulative_scale
        for row in sector_rows
    )
    if abs(cumulative_sector_sum - total_cumulative_change) > 1e-9:
        raise RuntimeError(
            "Las contribuciones acumuladas en puntos porcentuales no suman "
            "el cambio acumulado de la PTF total"
        )

    img, draw, f = canvas(
        "Contribuciones de las actividades a la PTF total",
        "Acumuladas y anualizadas, 2005–2024",
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
        "Contribución acumulada (puntos porcentuales)",
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
        accumulated = (
            float(row["cumulative_log_contribution"]) * cumulative_scale
        )
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
        draw_activity_label(
            draw,
            f,
            str(row["activity"]),
            left_label,
            y,
            bold=is_total,
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
        annualized_label = f"{annualized:.2f}".replace("-", "−")
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

    cumulative_total_label = f"{total_cumulative_change:.2f}".replace("-", "−")
    annual_total_label = f"{float(total['average_contribution']):.2f}".replace(
        "-", "−"
    )
    draw.text(
        (70, 992),
        "Nota: las contribuciones acumuladas distribuyen el cambio exacto de la PTF total en proporción a las",
        fill=GRAY,
        font=f["small"],
    )
    draw.text(
        (70, 1029),
        f"contribuciones logarítmicas. Las barras suman {cumulative_total_label} pp en el panel izquierdo y "
        f"{annual_total_label} pp por año en el derecho; las cifras pueden no sumar por redondeo.",
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


def draw_counterfactual(
    summary_rows: list[dict[str, object]],
    long_rows: list[dict[str, float | int | str]],
) -> None:
    observed = next(
        row for row in summary_rows if str(row["scenario"]) == "Observado"
    )
    total = next(
        row for row in long_rows if str(row["activity"]) == "Total de la economía"
    )
    sector_rows = [
        row for row in long_rows if str(row["activity"]) != "Total de la economía"
    ]
    positive_rows = sorted(
        [
            row
            for row in sector_rows
            if float(row["average_sector_ptf"]) > 0
        ],
        key=lambda row: float(row["average_contribution"]),
    )
    negative_rows = sorted(
        [
            row
            for row in sector_rows
            if float(row["average_sector_ptf"]) < 0
        ],
        key=lambda row: float(row["average_contribution"]),
    )
    if len(positive_rows) != 4 or len(negative_rows) != 5:
        raise RuntimeError(
            "La cascada requiere cuatro actividades con PTF positiva y cinco "
            "con PTF negativa"
        )
    if any(
        float(row["average_sector_ptf"])
        * float(row["average_contribution"])
        <= 0
        for row in sector_rows
    ):
        raise RuntimeError(
            "El signo de una contribución sectorial no coincide con el signo "
            "de su tasa de crecimiento de la PTF"
        )

    observed_growth = float(observed["average_production_growth"])
    total_ptf_contribution = float(total["average_contribution"])
    growth_without_ptf = observed_growth - total_ptf_contribution
    positive_contribution = sum(
        float(row["average_contribution"]) for row in positive_rows
    )
    negative_contribution = sum(
        float(row["average_contribution"]) for row in negative_rows
    )
    counterfactual_growth = growth_without_ptf + positive_contribution
    rebuilt_observed_growth = counterfactual_growth + negative_contribution
    if abs(rebuilt_observed_growth - observed_growth) > 1e-9:
        raise RuntimeError(
            "La cascada no reproduce el crecimiento observado de la producción"
        )

    img, draw, f = canvas(
        "De las contribuciones sectoriales al crecimiento observado",
        "Promedio anual, 2005–2024; tasa y contribuciones en puntos porcentuales",
        1800,
        1120,
    )
    left, right, top, bottom = 105, 1735, 245, 740
    ymin, ymax = 3.20, 3.70

    def y_position(value: float) -> float:
        return bottom - (value - ymin) / (ymax - ymin) * (bottom - top)

    for tick in [3.2, 3.3, 3.4, 3.5, 3.6, 3.7]:
        y = y_position(tick)
        draw.line((left, y, right, y), fill=GRID, width=1)
        draw.text(
            (45, y - 13),
            f"{tick:.1f}".replace(".", ","),
            fill=GRAY,
            font=f["small"],
        )

    short_labels = {
        "Agricultura": "Agropecuario",
        "Minería": "Minería",
        "Manufactura": "Manufactura",
        "Electricidad, gas y agua": "Servicios\npúblicos",
        "Construcción": "Construcción",
        "Comercio, hoteles y restaurantes": "Comercio y\nhotelería",
        "Transporte y comunicaciones": "Transporte y\ncomunic.",
        "Finanzas e inmobiliarias": "Financieras",
        "Servicios sociales": "Servicios\nsociales",
    }
    labels = [
        "Sin PTF",
        *[short_labels[str(row["activity"])] for row in positive_rows],
        "Contrafactual",
        *[short_labels[str(row["activity"])] for row in negative_rows],
        "Observado",
    ]
    positions = [
        left + (index + 0.5) * (right - left) / len(labels)
        for index in range(len(labels))
    ]
    bar_width = 88
    anchor_color = "#3A3A3A"

    base_y = y_position(growth_without_ptf)
    draw.rectangle(
        (
            positions[0] - bar_width / 2,
            base_y,
            positions[0] + bar_width / 2,
            y_position(ymin),
        ),
        fill=anchor_color,
    )
    draw.text(
        (positions[0], base_y - 18),
        f"{growth_without_ptf:.2f}%".replace(".", ","),
        fill=anchor_color,
        font=f["axis_bold"],
        anchor="ms",
    )

    current = growth_without_ptf
    previous_right = positions[0] + bar_width / 2
    for index, row in enumerate(positive_rows, start=1):
        change = float(row["average_contribution"])
        updated = current + change
        x = positions[index]
        draw.line(
            (
                previous_right,
                y_position(current),
                x - bar_width / 2,
                y_position(current),
            ),
            fill=GRAY,
            width=2,
        )
        draw.rectangle(
            (
                x - bar_width / 2,
                y_position(updated),
                x + bar_width / 2,
                y_position(current),
            ),
            fill=MID_BLUE,
            outline=MID_BLUE,
            width=2,
        )
        draw.text(
            (x, min(y_position(current), y_position(updated)) - 16),
            f"+{change:.2f} pp".replace(".", ","),
            fill=BLUE,
            font=f["small_bold"],
            anchor="ms",
        )
        current = updated
        previous_right = x + bar_width / 2

    counterfactual_index = 1 + len(positive_rows)
    counterfactual_x = positions[counterfactual_index]
    draw.line(
        (
            previous_right,
            y_position(current),
            counterfactual_x - bar_width / 2,
            y_position(current),
        ),
        fill=GRAY,
        width=2,
    )
    draw.rectangle(
        (
            counterfactual_x - bar_width / 2,
            y_position(counterfactual_growth),
            counterfactual_x + bar_width / 2,
            y_position(ymin),
        ),
        fill=anchor_color,
    )
    draw.text(
        (counterfactual_x, y_position(counterfactual_growth) - 18),
        f"{counterfactual_growth:.2f}%".replace(".", ","),
        fill=anchor_color,
        font=f["axis_bold"],
        anchor="ms",
    )

    current = counterfactual_growth
    previous_right = counterfactual_x + bar_width / 2
    negative_start = counterfactual_index + 1
    for offset, row in enumerate(negative_rows):
        index = negative_start + offset
        change = float(row["average_contribution"])
        updated = current + change
        x = positions[index]
        draw.line(
            (
                previous_right,
                y_position(current),
                x - bar_width / 2,
                y_position(current),
            ),
            fill=GRAY,
            width=2,
        )
        draw.rectangle(
            (
                x - bar_width / 2,
                y_position(current),
                x + bar_width / 2,
                y_position(updated),
            ),
            fill=RED,
            outline=RED,
            width=2,
        )
        draw.text(
            (x, min(y_position(current), y_position(updated)) - 16),
            f"{change:.2f} pp".replace("-", "−").replace(".", ","),
            fill=RED,
            font=f["small_bold"],
            anchor="ms",
        )
        current = updated
        previous_right = x + bar_width / 2

    observed_x = positions[-1]
    draw.line(
        (
            previous_right,
            y_position(current),
            observed_x - bar_width / 2,
            y_position(current),
        ),
        fill=GRAY,
        width=2,
    )
    draw.rectangle(
        (
            observed_x - bar_width / 2,
            y_position(observed_growth),
            observed_x + bar_width / 2,
            y_position(ymin),
        ),
        fill=anchor_color,
    )
    draw.text(
        (observed_x, y_position(observed_growth) - 18),
        f"{observed_growth:.2f}%".replace(".", ","),
        fill=anchor_color,
        font=f["axis_bold"],
        anchor="ms",
    )

    for x, label in zip(positions, labels):
        box = draw.multiline_textbbox(
            (0, 0),
            label,
            font=f["small"],
            spacing=3,
            align="center",
        )
        label_width = box[2] - box[0]
        draw.multiline_text(
            (x - label_width / 2, bottom + 28),
            label,
            fill="#222222",
            font=f["small"],
            spacing=3,
            align="center",
        )

    draw.text(
        (80, 895),
        "Nota: por espacio, la cascada abrevia las denominaciones de las actividades. El apéndice reproduce los nombres del DANE.",
        fill=GRAY,
        font=f["small"],
    )
    draw.text(
        (80, 930),
        "“Sin PTF” suma las contribuciones del trabajo, el capital y los insumos intermedios. El contrafactual mantiene",
        fill=GRAY,
        font=f["small"],
    )
    draw.text(
        (80, 965),
        "las contribuciones positivas y fija en cero las negativas. Es una identidad contable y no un efecto causal.",
        fill=GRAY,
        font=f["small"],
    )
    draw.text(
        (80, 1000),
        "La producción corresponde al enfoque KLEMS y no al PIB. La escala vertical comienza en 3,20%.",
        fill=GRAY,
        font=f["small"],
    )
    draw.text(
        (80, 1035),
        "Fuente: cálculos del CJC con base en DANE, anexo PTF 2025.",
        fill=GRAY,
        font=f["small"],
    )
    img.save(FIGURES / "fig_ptf_cascada_contribuciones_actividad.png", quality=95)


def draw_aggregate_contributions_by_period(
    period_rows: list[dict[str, float | int | str]],
) -> None:
    periods = ["2005-2010", "2011-2015", "2016-2019", "2020-2024"]
    period_labels = ["2005–2010", "2011–2015", "2016–2019", "2020–2024"]
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
        draw_activity_label(draw, f, activity, 65, y)
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
        "Crecimiento acumulado y tasa anualizada de la PTF 2005-2024",
        "",
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
        "Tasa anualizada de la PTF (%)",
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
        draw_activity_label(
            draw,
            f,
            str(row["activity"]),
            left_label,
            y,
            bold=is_total,
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
        "Fuente: cálculos del CJC con base en DANE, anexo PTF 2025.",
        fill=GRAY,
        font=f["small"],
    )
    img.save(FIGURES / "fig_ptf_promedio_actividad.png", quality=95)


def draw_decomposition(long_run: list[dict[str, float | int | str]]) -> None:
    img, draw, f = canvas(
        "Más producción no significó necesariamente más productividad",
        "Descomposición promedio anual del crecimiento de la producción, 2005–2024 (puntos porcentuales)",
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
        draw_activity_label(draw, f, str(row["activity"]), 65, y)
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
        if int(d["year"]) >= 2005:
            by_activity[str(d["activity"])].append(d)
    img, draw, f = canvas(
        "La PTF sectorial fue volátil, pero los patrones no fueron aleatorios",
        "Contribución anual de la PTF al crecimiento de la producción, 2005–2024 (puntos porcentuales)",
        1800,
        1400,
    )
    plot_left, plot_top = 90, 255
    panel_w, panel_h = 535, 275
    gap_x, gap_y = 55, 95
    ymin, ymax = -12.0, 12.0
    for idx, activity in enumerate(SHORT.values()):
        col, row = idx % 3, idx // 3
        x1 = plot_left + col * (panel_w + gap_x)
        y1 = plot_top + row * (panel_h + gap_y)
        x2, y2 = x1 + panel_w, y1 + panel_h
        panel_label = FIGURE_NAMES[activity]
        label_box = draw.multiline_textbbox(
            (0, 0),
            panel_label,
            font=f["small_bold"],
            spacing=1,
        )
        label_height = label_box[3] - label_box[1]
        draw.multiline_text(
            (x1, y1 - label_height - 8),
            panel_label,
            fill=BLUE,
            font=f["small_bold"],
            spacing=1,
        )
        y0 = y2 - (0 - ymin) / (ymax - ymin) * panel_h
        draw.line((x1, y0, x2, y0), fill=GRID, width=2)
        x2020 = x1 + (2020 - 2005) / (2024 - 2005) * panel_w
        draw.rectangle((x2020, y1, x2, y2), fill="#F3F3F3")
        draw.line((x1, y0, x2, y0), fill=GRID, width=2)
        points = []
        for d in sorted(by_activity[activity], key=lambda z: int(z["year"])):
            x = x1 + (int(d["year"]) - 2005) / (2024 - 2005) * panel_w
            value = max(ymin, min(ymax, float(d["ptf"])))
            y = y2 - (value - ymin) / (ymax - ymin) * panel_h
            points.append((x, y))
        draw.line(points, fill=MID_BLUE, width=4)
        for x, y in points:
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=MID_BLUE)
        draw.rectangle((x1, y1, x2, y2), outline=GRID, width=1)
        draw.text((x1, y2 + 6), "2005", fill=GRAY, font=f["small"])
        draw.text((x2 - 52, y2 + 6), "2024", fill=GRAY, font=f["small"])
    draw.text((90, 1340), "Nota: el área gris corresponde a 2020–2024. La escala se limita a ±12 pp para facilitar la comparación.", fill=GRAY, font=f["small"])
    draw.text((90, 1370), "Fuente: cálculos del CJC con base en DANE, anexo PTF 2025.", fill=GRAY, font=f["small"])
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
    rows = [d for d in observations if int(d["year"]) >= 2005]
    lookup = {(str(d["activity"]), int(d["year"])): float(d["ptf"]) for d in rows}
    years = list(range(2005, 2025))
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
        "Crecimiento de la PTF por actividad económica 2005-2024",
        "",
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
        draw_activity_label(draw, f, activity, 60, y + cell_h / 2)
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
    draw.text((525, legend_y - 2), "Tasa negativa", fill=GRAY, font=f["small"])
    for idx, value in enumerate([-6, -4, -2, 0, 2, 4, 6]):
        x = 705 + idx * 90
        draw.rectangle((x, legend_y, x + 87, legend_y + 28), fill=interpolate_color(value))
        draw.text((x + 28, legend_y + 34), str(value).replace("-", "−"), fill=GRAY, font=f["small"])
    draw.text((1355, legend_y - 2), "Tasa positiva", fill=GRAY, font=f["small"])
    draw.text(
        (70, 1120),
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
        draw_activity_label(draw, f, activity, 65, y)
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
    value_added_observations = load_value_added_total()
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
    (
        counterfactual_annual,
        counterfactual_summary,
        counterfactual_drivers,
    ) = build_counterfactual(
        total_observations,
        contribution_annual,
        contribution_long,
    )
    value_added_summary = build_value_added_counterfactual(
        value_added_observations
    )
    identity_error, detail_error = validate(observations)
    total_identity_error, total_detail_error = validate(total_observations)
    long_run = summarize(observations, 2005, 2024)
    total_long_run = summarize(
        total_observations, 2005, 2024, ["Total de la economía"]
    )
    comparison_long_run = [*total_long_run, *long_run]
    pre = summarize(observations, 2005, 2019)
    post = summarize(observations, 2020, 2024)
    period_summaries = [
        ("2005–2010", summarize(observations, 2005, 2010)),
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
            ("2005–2010", 2005, 2010),
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
    write_csv(PROCESSED / "ptf_actividad_promedio_2005_2024.csv", long_run)
    write_csv(PROCESSED / "ptf_actividad_promedio_2005_2019.csv", pre)
    write_csv(PROCESSED / "ptf_actividad_promedio_2020_2024.csv", post)
    write_csv(PROCESSED / "ptf_total_economia_promedio_2005_2024.csv", total_long_run)
    write_csv(COUNTERFACTUAL_ANNUAL_CSV, counterfactual_annual)
    write_csv(COUNTERFACTUAL_SUMMARY_CSV, counterfactual_summary)
    write_csv(
        PROCESSED / "ptf_valor_agregado_resumen_2005_2025.csv",
        value_added_summary,
    )
    write_tex_tables(comparison_long_run)
    write_evolution_table(comparison_long_run, comparison_period_summaries)
    write_aggregate_contribution_tables(contribution_long, contribution_periods)
    draw_value_added_tfp_bars(value_added_observations)
    draw_value_added_waterfall(value_added_summary)
    draw_total_index(index_rows)
    draw_aggregate_contributions(contribution_long)
    draw_counterfactual(counterfactual_summary, contribution_long)
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
        if 2005 <= int(row["year"]) <= 2024
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
    observed = counterfactual_summary[0]
    total_contribution = next(
        row
        for row in contribution_long
        if str(row["activity"]) == "Total de la economía"
    )
    sector_contributions = [
        row
        for row in contribution_long
        if str(row["activity"]) != "Total de la economía"
    ]
    positive_contribution = sum(
        float(row["average_contribution"])
        for row in sector_contributions
        if float(row["average_sector_ptf"]) > 0
    )
    negative_contribution = sum(
        float(row["average_contribution"])
        for row in sector_contributions
        if float(row["average_sector_ptf"]) < 0
    )
    observed_growth = float(observed["average_production_growth"])
    growth_without_ptf = observed_growth - float(
        total_contribution["average_contribution"]
    )
    waterfall_counterfactual = growth_without_ptf + positive_contribution
    print(
        "Cascada crecimiento sin PTF, contrafactual y observado: "
        f"{growth_without_ptf:.6f}; "
        f"{waterfall_counterfactual:.6f}; "
        f"{observed_growth:.6f}"
    )
    print(
        "Contribuciones positivas y negativas a la cascada: "
        f"{positive_contribution:.6f}; {negative_contribution:.6f}"
    )
    value_added_observed = value_added_summary[0]
    value_added_counterfactual = value_added_summary[1]
    print(
        "Valor agregado anual observado y con PTF +1 pp: "
        f"{float(value_added_observed['gross_value_added']):.6f}; "
        f"{float(value_added_counterfactual['gross_value_added']):.6f}"
    )
    print(
        "Diferencia de nivel del valor agregado en 2025: "
        f"{float(value_added_counterfactual['level_difference_vs_observed']):.6f}%"
    )


if __name__ == "__main__":
    main()
