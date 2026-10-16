"""Independent vector/raster proof, before integration with document flow.

Run: uv run --locked --extra dev python examples/figure_proof.py
This is display-only sample content; no engineering calculation is performed.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from PIL import Image as PILImage, ImageDraw

from gridlayoutpdf.bounds import command_bounds
from gridlayoutpdf.figures import Arrow, Figure, Image, Label
from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.layout import LayoutContext, measure_block
from gridlayoutpdf.profiles import A4_PORTRAIT_REFERENCE
from gridlayoutpdf.renderers.reportlab import render_pdf
from gridlayoutpdf.scene import Line, RasterImage, Rectangle, ScenePage, Text
from gridlayoutpdf.styles import ReportStyle, TextStyle


ROOT = Path(__file__).resolve().parents[1]


def _sample_image(path: Path) -> None:
    """An original deterministic alpha test pattern, not a reference PDF crop."""
    with PILImage.new("RGBA", (240, 120), (255, 255, 255, 0)) as picture:
        draw = ImageDraw.Draw(picture)
        draw.rounded_rectangle((8, 12, 232, 108), radius=16, fill=(36, 119, 153, 70))
        for x, color in ((18, (38, 108, 176, 220)), (94, (24, 150, 127, 180)),
                         (170, (222, 139, 44, 220))):
            draw.rounded_rectangle((x, 24, x + 52, 96), radius=8, fill=color)
            draw.ellipse((x + 12, 46, x + 40, 74), fill=(255, 255, 255, 230))
        picture.save(path)


def build_pages(fonts: FontRegistry, image_path: Path) -> tuple[ScenePage, ...]:
    profile = A4_PORTRAIT_REFERENCE
    grid = profile.grid
    context = LayoutContext(fonts, profile, ReportStyle())
    load_color = (.12, .35, .56)
    items = [
        Label(210, 14, "等分布荷重 q = 10 kN/m", align="center"),
        Rectangle(80, 70, 250, 22, stroke_width=1.1),
        Rectangle(190, 92, 30, 128, stroke_width=1.1),
        Label(210, 85, "梁", align="center"),
        Label(205, 160, "柱", align="center"),
        Line(175, 220, 235, 220, width=1.1),
    ]
    items.extend(Arrow(x, 24, x, 64, head_length=8, head_width=6, width=.9,
                       color=load_color) for x in (100, 155, 210, 265, 320))
    items.extend(Line(x, 220, x - 6, 227, width=.6) for x in range(180, 236, 10))
    items.extend((
        Line(80, 238, 80, 258), Line(330, 238, 330, 258),
        Arrow(80, 250, 330, 250, width=.5), Arrow(330, 250, 80, 250, width=.5),
        Label(205, 270, "梁幅 5.00 m", align="center"),
        Line(350, 92, 372, 92), Line(350, 220, 372, 220),
        Arrow(362, 92, 362, 220, width=.5), Arrow(362, 220, 362, 92, width=.5),
        Label(375, 150, "柱高"), Label(375, 166, "3.00 m"),
    ))
    figure = measure_block(Figure(26, 18, *items, block_id="load-figure"), context, grid.pitch_x * 26)
    picture = measure_block(Image(image_path, col_span=14, rows=8, block_id="alpha-image"),
                            context, grid.pitch_x * 14)
    commands = (
        Text(grid.x(0), grid.y(0) + 11, "図と画像の最小実証", TextStyle(size=12)),
        Text(grid.x(0), grid.y(2) + 11, "図の内部をptで指定し、外枠をグリッドで配置。", TextStyle()),
        *figure.translated(grid.x(2), grid.y(5)),
        Text(grid.x(0), grid.y(24) + 11, "画像：透過PNG、2:1の縦横比を維持", TextStyle()),
        *picture.translated(grid.x(8), grid.y(27)),
        Text(grid.x(0), grid.y(37) + 11, "線・矢印・ラベルはベクター。画像データは計測時に固定。", TextStyle()),
        Text(grid.x(0), grid.y(39) + 11, "表示用原稿。工学計算は実行しない。", TextStyle()),
    )
    return (ScenePage(profile, commands),)


def write_proof(output_dir: str | Path, font_path: str | Path) -> tuple[Path, Path, Path]:
    """Write normal/grid PDFs, a trace and independent 144dpi previews."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / "figure-proof-source.png"
    _sample_image(image_path)
    fonts = FontRegistry()
    face = fonts.register("body", font_path)
    pages = build_pages(fonts, image_path)
    plain, grid = output_dir / "figure-proof.pdf", output_dir / "figure-proof-grid.pdf"
    render_pdf(pages, plain, fonts)
    render_pdf(pages, grid, fonts, debug_grid=True)
    trace = {"font_sha256": face.sha256, "commands": []}
    for command in pages[0].commands:
        bounds = command_bounds(command, fonts)
        entry = {"kind": type(command).__name__, "bounds": [bounds.x, bounds.y, bounds.width, bounds.height]}
        if isinstance(command, Text):
            entry["text"] = command.text
        if isinstance(command, RasterImage):
            entry["image_sha256"] = sha256(command.data).hexdigest()
        trace["commands"].append(entry)
    trace_path = output_dir / "figure-proof.json"
    trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Existing development dependency; never used by product measurement/rendering.
    import pymupdf
    previews = output_dir / "previews"
    previews.mkdir(exist_ok=True)
    for path in (plain, grid):
        with pymupdf.open(path) as document:
            document[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).save(
                previews / f"{path.stem}-page-1.png")
    return plain, grid, trace_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=ROOT / "tests/fixtures/fonts/ipaexm.ttf")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build/reports")
    arguments = parser.parse_args()
    for path in write_proof(arguments.output_dir, arguments.font):
        print(path)


if __name__ == "__main__":
    main()
