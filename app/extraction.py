import io
import logging

import pymupdf as fitz
import pytesseract
from PIL import Image

log = logging.getLogger(__name__)

OCR_LANG = "ron+eng"
MIN_CHARS_PER_PAGE = 50
OCR_DPI = 300

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def _ocr_image(image: Image.Image) -> str:
    return pytesseract.image_to_string(image, lang=OCR_LANG)


def _extract_pdf(data: bytes) -> tuple[str, str]:
    doc = fitz.open(stream=data, filetype="pdf")
    pages = []
    used_ocr = False
    for page in doc:
        text = page.get_text("text").strip()
        if len(text) < MIN_CHARS_PER_PAGE:
            pix = page.get_pixmap(dpi=OCR_DPI)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
            ocr_text = _ocr_image(image).strip()
            if len(ocr_text) > len(text):
                text = ocr_text
                used_ocr = True
        pages.append(f"--- Pagina {page.number + 1} ---\n{text}")
    doc.close()
    method = "pdf-text + ocr (tesseract)" if used_ocr else "pdf-text"
    return "\n\n".join(pages), method


def extract_text(filename: str, data: bytes) -> tuple[str, str]:
    """Returns (text, method). Native text extraction first, Tesseract OCR as fallback."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == ".pdf":
        return _extract_pdf(data)

    if ext in IMAGE_EXTENSIONS:
        image = Image.open(io.BytesIO(data))
        frames = []
        for i in range(getattr(image, "n_frames", 1)):
            image.seek(i)
            frames.append(_ocr_image(image.convert("RGB")))
        return "\n\n".join(frames), "ocr (tesseract)"

    if ext in {".txt", ".csv"}:
        return data.decode("utf-8", errors="replace"), "text"

    raise ValueError(f"Tip de fișier nesuportat: {ext or 'necunoscut'}")
