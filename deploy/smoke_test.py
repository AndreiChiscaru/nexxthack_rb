"""Checks native PDF text extraction and the OCR fallback on a scanned (image-only) PDF."""
import io

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from app.extraction import extract_text

LINES = ["EXTRAS DE CONT - BANCA TEST", "Titular: Ion Popescu", "05.10.2026 Salariu ACME SRL +5200.00 RON",
         "07.10.2026 Kaufland -312.45 RON", "15.10.2026 Rata credit -1450.00 RON"]

doc = pymupdf.open()
page = doc.new_page()
for i, line in enumerate(LINES):
    page.insert_text((50, 80 + i * 20), line)
text, method = extract_text("text.pdf", doc.tobytes())
print("[native]", method, "| Salariu" in text or "Salariu" in text)

img = Image.new("RGB", (1700, 600), "white")
draw = ImageDraw.Draw(img)
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
for i, line in enumerate(LINES):
    draw.text((60, 60 + i * 90), line, fill="black", font=font)
buf = io.BytesIO()
img.save(buf, format="PDF", resolution=150)
text, method = extract_text("scan.pdf", buf.getvalue())
print("[scan]", method)
print(text)
