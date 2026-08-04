"""Construye una pieza para redes con la serie encadenada de la PTF total."""

from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "ptf_indices_encadenados.csv"
BACKGROUND = ROOT / "outputs" / "redes" / "assets" / "ptf_colombia_base.png"
LOGO = ROOT / "Paper" / "figures" / "logo_cjc_palatino_horizontal.png"
OUTPUT = ROOT / "outputs" / "redes" / "ptf_indice_2005_2024.png"

WIDTH, HEIGHT = 1536, 1024

NAVY = "#17365D"
BLUE = "#1F5EA8"
MID_BLUE = "#6F9ACB"
GOLD = "#D89A1D"
TEXT = "#152B3A"
MUTED = "#5E6972"
GRID = "#B9C0C5"
IVORY = "#F6F1E8"

FONT_REGULAR = Path(r"C:\Windows\Fonts\segoeui.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\segoeuib.ttf")


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def read_total_series() -> list[tuple[int, float]]:
    values: list[tuple[int, float]] = []
    with DATA.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["activity"] == "Total de la economía":
                values.append((int(row["year"]), float(row["index"])))
    if not values or values[0][0] != 2004 or values[-1][0] != 2024:
        raise ValueError("La serie total no cubre 2004–2024.")
    return values


def fit_background(image: Image.Image) -> Image.Image:
    image = image.convert("RGB")
    scale = max(WIDTH / image.width, HEIGHT / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - WIDTH) // 2
    top = (resized.height - HEIGHT) // 2
    return resized.crop((left, top, left + WIDTH, top + HEIGHT))


def soften_left(image: Image.Image) -> Image.Image:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    pixels = overlay.load()
    ivory = (246, 241, 232)
    for x in range(0, 1110):
        if x < 820:
            alpha = 228
        else:
            alpha = round(228 * (1110 - x) / 290)
        for y in range(HEIGHT):
            pixels[x, y] = (*ivory, alpha)
    return Image.alpha_composite(image.convert("RGBA"), overlay)


def rounded_label(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text_value: str,
    *,
    fill: str,
    text_fill: str,
    text_font: ImageFont.FreeTypeFont,
) -> None:
    draw.rounded_rectangle(box, radius=16, fill=fill)
    left, top, right, bottom = box
    text_box = draw.textbbox((0, 0), text_value, font=text_font)
    tw = text_box[2] - text_box[0]
    th = text_box[3] - text_box[1]
    draw.text(
        ((left + right - tw) / 2, (top + bottom - th) / 2 - 3),
        text_value,
        font=text_font,
        fill=text_fill,
    )


def make_logo_transparent() -> Image.Image:
    image = Image.open(LOGO).convert("RGBA")
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            if r > 245 and g > 245 and b > 245:
                pixels[x, y] = (r, g, b, 0)
            elif r > 225 and g > 225 and b > 225:
                pixels[x, y] = (r, g, b, round(a * (245 - max(r, g, b)) / 20))
    return image


def build() -> Path:
    series = read_total_series()
    canvas = soften_left(fit_background(Image.open(BACKGROUND)))
    draw = ImageDraw.Draw(canvas)

    # Titular
    draw.text(
        (92, 54),
        "La productividad de la economía",
        font=font(56, bold=True),
        fill=TEXT,
    )
    draw.text(
        (92, 119),
        "colombiana terminó 2024 un 1,5%",
        font=font(56, bold=True),
        fill=TEXT,
    )
    draw.text(
        (92, 184),
        "por debajo de su nivel de 2004.",
        font=font(56),
        fill=TEXT,
    )

    # Encabezado de la gráfica
    draw.text(
        (96, 290),
        "Índice de la Productividad Total de los Factores (PTF)",
        font=font(25, bold=True),
        fill=TEXT,
    )
    draw.text(
        (96, 326),
        "2004 = 100  |  variaciones observadas durante 2005–2024",
        font=font(19),
        fill=MUTED,
    )

    # Área de trazado
    x0, x1 = 102, 920
    y0, y1 = 386, 722
    y_min, y_max = 97.5, 102.7

    def px(year: int) -> float:
        return x0 + (year - 2004) / (2024 - 2004) * (x1 - x0)

    def py(value: float) -> float:
        return y1 - (value - y_min) / (y_max - y_min) * (y1 - y0)

    for tick in (98.0, 100.0, 102.0):
        y = py(tick)
        draw.line(
            (x0, y, x1, y),
            fill=NAVY if tick == 100 else GRID,
            width=3 if tick == 100 else 1,
        )
        draw.text(
            (x0 - 12, y - 12),
            f"{tick:.0f}".replace(".", ","),
            anchor="ra",
            font=font(18, bold=tick == 100),
            fill=NAVY if tick == 100 else MUTED,
        )

    for tick in (2004, 2006, 2010, 2015, 2020, 2024):
        x = px(tick)
        draw.line((x, y1 + 4, x, y1 + 13), fill=MUTED, width=2)
        draw.text(
            (x, y1 + 21),
            str(tick),
            anchor="ma",
            font=font(18),
            fill=MUTED,
        )

    points = [(px(year), py(value)) for year, value in series]
    draw.line(points, fill=NAVY, width=8, joint="curve")

    start = points[0]
    peak_row = max(enumerate(series), key=lambda item: item[1][1])
    peak = points[peak_row[0]]
    end = points[-1]
    for point in (start, peak, end):
        draw.ellipse(
            (point[0] - 7, point[1] - 7, point[0] + 7, point[1] + 7),
            fill=IVORY,
            outline=NAVY,
            width=4,
        )

    draw.text(
        (peak[0] + 9, peak[1] - 35),
        "102,3",
        font=font(18, bold=True),
        fill=NAVY,
    )
    rounded_label(
        draw,
        (834, round(end[1] - 33), 925, round(end[1] + 17)),
        "98,5",
        fill=NAVY,
        text_fill=IVORY,
        text_font=font(22, bold=True),
    )

    # Definición pedagógica
    draw.rounded_rectangle(
        (91, 804, 825, 914),
        radius=18,
        fill=(246, 241, 232, 226),
        outline=(23, 54, 93, 70),
        width=2,
    )
    draw.text(
        (116, 821),
        "¿Qué mide la PTF?",
        font=font(22, bold=True),
        fill=NAVY,
    )
    draw.text(
        (116, 855),
        "Qué tan eficientemente se combinan el trabajo y el capital",
        font=font(18),
        fill=TEXT,
    )
    draw.text(
        (116, 881),
        "para producir.",
        font=font(18),
        fill=TEXT,
    )

    # Identidad institucional y fuente
    logo = make_logo_transparent()
    logo.thumbnail((250, 80), Image.Resampling.LANCZOS)
    canvas.alpha_composite(logo, (92, 934))
    draw.text(
        (370, 961),
        "Fuente: cálculos del CJC con base en DANE.",
        font=font(16),
        fill=MUTED,
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(OUTPUT, quality=95)
    return OUTPUT


if __name__ == "__main__":
    print(build())
