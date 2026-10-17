"""Recreate only the 16 reviewed source figure panels (never text or tables).

Run explicitly from the repository root with the locked development environment.
The fixture renderer consumes the committed PNGs; it never runs this extractor.
"""

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

from PIL import Image
import pymupdf


ROOT = Path(__file__).resolve().parents[4]
DESTINATION = Path(__file__).resolve().parent
SOURCE = ROOT / "tests/output/13_片持ち梁照査.pdf"
SOURCE_HASH = "e56bf3ddbe3314ed95517099bedb0e68005df1567b0b3e8f52a2a4066d03393e"
SCALE = 4  # 288 dpi; rendered back at exactly the crop's original pt dimensions.

# All boxes were selected by viewing the source pages. Coordinates are source
# top-origin pt and surround figure panels only, excluding headings/equations.
CROPS = (
    (1, "p01-load-b", (122, 441, 504, 555)),
    (2, "p02-load-c", (122, 100, 504, 214)),
    (2, "p02-load-bc", (122, 414, 504, 528)),
    (9, "p09-load-b", (122, 128, 504, 242)),
    (9, "p09-torque-origin", (122, 360, 534, 523)),
    (10, "p10-load-c", (122, 102, 504, 216)),
    (10, "p10-torque-end", (122, 335, 534, 498)),
    (11, "p11-load-bc", (122, 96, 480, 226)),
    (13, "p13-inertia-origin", (122, 210, 534, 348)),
    (13, "p13-inertia-end", (122, 546, 534, 702)),
    (14, "p14-train-origin", (155, 194, 432, 350)),
    (14, "p14-train-end", (155, 546, 432, 704)),
    (23, "p23-weight-section", (93, 109, 273, 300)),
    (23, "p23-weight-front", (310, 95, 491, 286)),
    (24, "p24-load-section", (93, 99, 273, 384)),
    (24, "p24-load-front", (310, 141, 491, 384)),
)

# p11 is already a raster in the source; these labels were read in the image.
P11_LABELS = (
    "14.425", "2.200", "2.200", "7.425", "2.800", "0.575",
    "18.850", "0.575", "0.375", "9.250", "0.375", "20.000", "10.000",
)


def extract():
    if sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_HASH:
        raise ValueError("Source PDF differs from the reviewed original")
    figures = []
    with pymupdf.open(SOURCE) as document:
        for page_number, identifier, bbox in CROPS:
            page = document[page_number - 1]
            clip = pymupdf.Rect(bbox)
            characters = [character for block in page.get_text("rawdict")["blocks"]
                          if block["type"] == 0 for line in block["lines"]
                          for span in line["spans"] for character in span["chars"]]
            if any(clip.intersects(c["bbox"]) and not clip.contains(c["bbox"])
                   for c in characters):
                raise ValueError(f"{identifier}: crop cuts through a source glyph")
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(SCALE, SCALE),
                                     clip=clip, colorspace=pymupdf.csRGB, alpha=False)
            png = pixmap.tobytes("png")
            normalized = BytesIO()
            with Image.open(BytesIO(png)) as decoded:
                rgb = decoded.convert("RGB")
                rgb.save(normalized, format="PNG")
                pixel_hash = sha256(rgb.tobytes()).hexdigest()
            filename = f"{identifier}.png"
            (DESTINATION / filename).write_bytes(png)
            labels = (list(P11_LABELS) if page_number == 11
                      else page.get_text(clip=clip).strip().splitlines())
            figures.append({
                "id": identifier, "file": f"assets/{filename}",
                "source_page": page_number, "source_bbox": list(bbox),
                "source_sha256": SOURCE_HASH, "sha256": sha256(png).hexdigest(),
                "normalized_byte_sha256": sha256(normalized.getvalue()).hexdigest(),
                "decoded_pixel_sha256": pixel_hash,
                "pixel_width": pixmap.width, "pixel_height": pixmap.height,
                "physical_width_pt": clip.width, "physical_height_pt": clip.height,
                "occurrence_count": 1,
                "method": "reviewed figure-only PDF crop, RGB PNG at 288 dpi; no rescaling in layout",
                "labels": labels,
                "label_method": "source image visual transcription" if page_number == 11 else "source text extraction checked against source image",
                "source_review": {"reviewer": "root", "date": "2026-10-17", "result": "pass"},
            })
    result = {"schema_version": 1, "source_sha256": SOURCE_HASH,
              "render_scale": SCALE, "pymupdf_version": pymupdf.VersionBind,
              "figures": figures}
    (DESTINATION / "metadata.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {len(figures)} figure-only panels")


if __name__ == "__main__":
    extract()
