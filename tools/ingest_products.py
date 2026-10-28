"""Extracts Raiffeisen products from the bank's offer PDF for MANUAL review.

    python -m tools.ingest_products oferta.pdf [--out data/products.from_pdf.json] [--dry-run]

Pipeline: PDF -> text (app/extraction.py, OCR fallback) -> Claude (structured JSON output) -> validated with
app.catalog.Product (same model the app loads at startup) -> data/products.from_pdf.json.
It never writes data/products.json: a person compares the output with the current catalog (the report printed
at the end lists added / changed / missing ids) and copies over what is correct.
--dry-run prints the validated JSON and the report without writing anything.
Needs ANTHROPIC_API_KEY (or another Anthropic credential). Model: env INGEST_MODEL (default claude-opus-5-5).
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import anthropic

from app.catalog import CATALOG_CATEGORIES, LEGACY_CAMPAIGN_CATEGORY, PRODUCTS_PATH, CatalogError, load_products, validate_entries
from app.extraction import extract_text

MODEL = os.getenv("INGEST_MODEL", "claude-opus-5-5")
DEFAULT_OUT = PRODUCTS_PATH.with_name("products.from_pdf.json")
CATEGORIES = [*CATALOG_CATEGORIES, LEGACY_CAMPAIGN_CATEGORY]

_STR = {"type": "string"}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": _STR, "category": {"type": "string", "enum": CATEGORIES}, "name": _STR,
                    "terms": _STR, "conditions": _STR, "best_for": _STR, "cautions": _STR,
                },
                "required": ["id", "category", "name", "terms", "conditions", "best_for", "cautions"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["products"],
    "additionalProperties": False,
}

SYSTEM = """Extragi produsele Raiffeisen Bank dintr-un document cu oferta băncii, pentru catalogul unui joc educațional.
Reguli:
- Folosește DOAR informații din document. Nu inventa dobânzi, comisioane, sume sau condiții.
- Un obiect per produs. Câmpuri (în română):
  id: snake_case ascii; dacă produsul există deja în lista de id-uri primită, folosește EXACT acel id.
  category: una din {categories}. Campaniile cu termen limitat au categoria „campanie”.
  name: numele comercial. terms: dobânzi, sume, perioade, comisioane, exact cum apar.
  conditions: condiții de eligibilitate ("" dacă documentul nu le dă).
  best_for: pentru cine e potrivit, pe scurt. cautions: la ce trebuie atent clientul.
- Dobânzile la credite sunt minime: scrie-le „de la X%”. Dobânzile la economii: „brută”, cum apar în document.
- Pentru campanii, păstrează în terms datele de început și de sfârșit, exact cum apar."""


class IngestError(RuntimeError):
    pass


def pdf_text(path: Path) -> str:
    text, _method = extract_text(path.name, path.read_bytes())
    if len(text.strip()) < 30:
        raise IngestError(f"{path} nu conține text lizibil (nici după OCR).")
    return text


def request_products(text: str, existing: dict, client=None) -> list[dict]:
    """One streamed Claude call with a JSON-schema output; returns the raw product dicts."""
    client = client or anthropic.Anthropic()
    known = "\n".join(f"- {p.id}: {p.name}" for p in existing.values())
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=64000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        system=SYSTEM.format(categories=", ".join(CATEGORIES)),
        messages=[{"role": "user", "content": f"Id-uri existente în catalog:\n{known}\n\n<document>\n{text}\n</document>"}],
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason == "refusal":
        raise IngestError("Modelul a refuzat cererea.")
    if message.stop_reason == "max_tokens":
        raise IngestError("Răspunsul a fost trunchiat (max_tokens); împarte documentul în bucăți.")
    raw = next((b.text for b in message.content if b.type == "text"), "")
    try:
        return json.loads(raw)["products"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise IngestError(f"JSON invalid de la model: {exc}") from exc


def validate(raw_products: list[dict], as_of: date) -> dict:
    """Same validation as data/products.json at startup; stamps every product with the document's date."""
    return validate_entries([{**p, "as_of_date": as_of.isoformat()} for p in raw_products], source="PDF output")


def review_report(new: dict, existing: dict) -> dict:
    fields = ("category", "name", "terms", "conditions", "best_for", "cautions")
    return {
        "added": sorted(set(new) - set(existing)),
        "changed": sorted(i for i in set(new) & set(existing)
                          if any(getattr(new[i], f) != getattr(existing[i], f) for f in fields)),
        "missing_from_pdf": sorted(set(existing) - set(new)),
    }


def write_output(products: dict, out: Path) -> None:
    if out.resolve() == PRODUCTS_PATH.resolve():
        raise IngestError("Refuz să suprascriu data/products.json; scrie în alt fișier și revizuiește manual.")
    out.write_text(json.dumps([p.model_dump(mode="json") for p in products.values()], ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")


def main(argv: list[str] | None = None, client=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", type=Path, help="PDF-ul cu oferta băncii")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"fișierul de revizuit (implicit {DEFAULT_OUT.name})")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today(), help="data ofertei (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="afișează rezultatul, fără să scrie fișiere")
    args = parser.parse_args(argv)

    try:
        existing = load_products()
        products = validate(request_products(pdf_text(args.pdf), existing, client), args.as_of)
        report = review_report(products, existing)
        if args.dry_run:
            print(json.dumps([p.model_dump(mode="json") for p in products.values()], ensure_ascii=False, indent=2))
        else:
            write_output(products, args.out)
            print(f"{len(products)} produse scrise în {args.out} pentru revizuire manuală.")
    except (IngestError, CatalogError, anthropic.APIError, OSError, ValueError) as exc:
        print(f"Eroare: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"review": report}, ensure_ascii=False, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
