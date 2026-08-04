"""Genera GIF para el hilo sobre PTF a partir de las figuras definitivas."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "Paper" / "figures"
OUTPUT = ROOT / "outputs" / "redes" / "gifs"

FONT_REGULAR = Path(r"C:\Windows\Fonts\segoeui.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\segoeuib.ttf")

NAVY = "#17365D"
GRAY = "#666666"
WHITE = "#FFFFFF"


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def resize_width(image: Image.Image, width: int = 1200) -> Image.Image:
    height = round(image.height * width / image.width)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def reveal_frames(
    image: Image.Image,
    rect: tuple[int, int, int, int],
    *,
    direction: str,
    steps: int,
) -> list[Image.Image]:
    """Crea cuadros acumulativos que terminan en la figura original."""
    source = image.convert("RGB")
    x0, y0, x1, y1 = rect
    frames: list[Image.Image] = []

    for step in range(steps + 1):
        progress = step / steps
        frame = source.copy()
        draw = ImageDraw.Draw(frame)
        draw.rectangle(rect, fill=WHITE)

        if direction == "horizontal":
            edge = round(x0 + (x1 - x0) * progress)
            if edge > x0:
                frame.paste(source.crop((x0, y0, edge, y1)), (x0, y0))
        elif direction == "vertical":
            edge = round(y0 + (y1 - y0) * progress)
            if edge > y0:
                frame.paste(source.crop((x0, y0, x1, edge)), (x0, y0))
        else:
            raise ValueError(f"Dirección no reconocida: {direction}")

        frames.append(resize_width(frame))

    # Garantiza que el cuadro final sea exactamente la figura completa.
    frames[-1] = resize_width(source)
    return frames


def save_gif(
    frames: list[Image.Image],
    output: Path,
    *,
    step_duration: int = 105,
    first_duration: int = 650,
    final_duration: int = 2200,
    colors: int = 64,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    playback = [frames[-1]] + frames
    palette = frames[-1].quantize(
        colors=colors,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    quantized = [
        frame.quantize(palette=palette, dither=Image.Dither.NONE)
        for frame in playback
    ]
    durations = (
        [first_duration, 500]
        + [step_duration] * (len(frames) - 2)
        + [final_duration]
    )
    quantized[0].save(
        output,
        save_all=True,
        append_images=quantized[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )


def panel_a_figure_4() -> Image.Image:
    """Construye una pieza autónoma con el panel acumulado de la Figura 4."""
    source = Image.open(FIGURES / "fig_ptf_promedio_actividad.png").convert("RGB")
    crop = source.crop((35, 170, 1080, 1015))

    canvas = Image.new("RGB", (1080, 1080), WHITE)
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (45, 30),
        "Crecimiento acumulado de la PTF",
        font=font(46, bold=True),
        fill=NAVY,
    )
    draw.text(
        (45, 88),
        "por actividad económica, 2005–2024",
        font=font(32),
        fill=GRAY,
    )

    available_width = 1010
    available_height = 840
    scale = min(available_width / crop.width, available_height / crop.height)
    crop = crop.resize(
        (round(crop.width * scale), round(crop.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = 35
    top = 145
    canvas.paste(crop, (left, top))
    draw.text(
        (45, 1034),
        "Fuente: cálculos del CJC con base en DANE.",
        font=font(22),
        fill=GRAY,
    )
    return canvas


def build() -> list[Path]:
    jobs = [
        (
            FIGURES / "fig_descomposicion_valor_agregado.png",
            OUTPUT / "figura_2_descomposicion_crecimiento.gif",
            (140, 245, 1655, 835),
            "horizontal",
            16,
        ),
        (
            FIGURES / "fig_ptf_mapa_anual.png",
            OUTPUT / "figura_3_ptf_actividad.gif",
            (515, 185, 1885, 945),
            "horizontal",
            20,
        ),
        (
            FIGURES / "fig_ptf_cascada_contribuciones_actividad.png",
            OUTPUT / "figura_6_contribuciones_sectoriales.gif",
            (100, 220, 1740, 825),
            "horizontal",
            18,
        ),
        (
            FIGURES / "fig_descomposicion_actividad.png",
            OUTPUT / "figura_7_descomposicion_ramas.gif",
            (45, 235, 1740, 995),
            "vertical",
            18,
        ),
    ]

    outputs: list[Path] = []
    for source_path, output_path, rect, direction, steps in jobs:
        source = Image.open(source_path)
        frames = reveal_frames(source, rect, direction=direction, steps=steps)
        save_gif(frames, output_path)
        outputs.append(output_path)

    panel = panel_a_figure_4()
    panel_frames = reveal_frames(
        panel,
        (25, 145, 1055, 1018),
        direction="vertical",
        steps=18,
    )
    panel_output = OUTPUT / "figura_4_panel_a_crecimiento_acumulado.gif"
    save_gif(panel_frames, panel_output)
    outputs.insert(2, panel_output)
    return outputs


if __name__ == "__main__":
    for path in build():
        print(path)
