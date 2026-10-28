import json
import os

import anthropic

from .statement_spend import summarize

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
MAX_INPUT_CHARS = 180_000

SYSTEM_PROMPT = """Ești un analist financiar care evaluează extrase de cont bancare (în special din România).
Primești textul extras (posibil prin OCR, cu erori) dintr-un extras de cont.
Analizează tranzacțiile și trimite rezultatul prin unealta raport_extras (dacă unealta nu e disponibilă,
returnează EXCLUSIV un obiect JSON valid, fără text în afara lui), cu structura:

{
  "titular": string|null,
  "banca": string|null,
  "iban": string|null,
  "moneda": string,
  "perioada": {"de_la": "YYYY-MM-DD"|null, "pana_la": "YYYY-MM-DD"|null},
  "sold_initial": number|null,
  "sold_final": number|null,
  "total_intrari": number,
  "total_iesiri": number,
  "flux_net": number,
  "venituri": [{"sursa": string, "tip": "salariu|pensie|chirie|transfer|alt venit", "suma_totala": number, "frecventa": string}],
  "venit_lunar_estimat": number|null,
  "cheltuieli_lunare_estimate": number|null,
  "economii_identificate": number|null,
  "cheltuieli_pe_categorii": [{"categorie": string, "suma": number, "procent": number}],
  "obligatii_recurente": [{"descriere": string, "tip": "rata credit|leasing|chirie|utilitati|abonament|altele", "suma_lunara": number}],
  "grad_indatorare_procent": number|null,
  "cele_mai_mari_tranzactii": [{"data": string, "descriere": string, "suma": number, "directie": "intrare|iesire"}],
  "semnale_de_risc": [string],
  "puncte_forte": [string],
  "scor_stabilitate_financiara": number,
  "nivel_risc": "scazut|mediu|ridicat",
  "rezumat": string,
  "recomandari": [string],
  "observatii_calitate_date": string
}

Reguli:
- titular = numele complet al persoanei care deține contul (apare de obicei în antet, lângă adresă, „Titular”, „Client” sau „Nume”); caută-l în tot documentul înainte să pui null.
- Sumele sunt numere (fără simbol monetar), în moneda contului.
- scor_stabilitate_financiara este între 0 și 100.
- Semnale de risc relevante: sold negativ/descoperit, comisioane de neplată, popriri/executări silite, jocuri de noroc, credite rapide (IFN), retrageri mari de numerar, venit neregulat, cheltuieli > venituri.
- cheltuieli_lunare_estimate = consumul RECURENT real pe lună (chirie, mâncare, utilități, transport, cumpărături, transferuri regulate către alte persoane). Exclude tranzacțiile mari evident unice sau ocazionale (le menționezi în observatii_calitate_date și, dacă e cazul, în semnale_de_risc). FĂRĂ transferuri între conturile proprii ale titularului (ex. spre propriul Revolut), FĂRĂ alimentări de depozite/economii și FĂRĂ rate de credit. Dacă perioada nu e o lună, normalizează la o lună. Dacă banii pleacă spre un cont propriu din care probabil se plătesc cheltuielile, include sumele respective în estimare și explică în observatii_calitate_date.
- economii_identificate = economiile titularului vizibile la sfârșitul perioadei (depozite, conturi de economii active), fără soldul contului curent; null dacă nu apar.
- Nu inventa date. Dacă o informație lipsește, folosește null sau listă goală și menționează în observatii_calitate_date.
- rezumat: 3-6 propoziții în limba română despre starea financiară a persoanei.
"""


_NUM = {"type": ["number", "null"]}
_STR = {"type": ["string", "null"]}
_LIST_STR = {"type": "array", "items": {"type": "string"}}


def _objects(**props) -> dict:
    return {"type": "array", "items": {"type": "object", "properties": props}}


REPORT_TOOL = {
    "name": "raport_extras",
    "description": "Trimite analiza extrasului de cont, cu structura și regulile din instrucțiuni.",
    "input_schema": {
        "type": "object",
        "properties": {
            "titular": _STR, "banca": _STR, "iban": _STR, "moneda": _STR,
            "perioada": {"type": "object", "properties": {"de_la": _STR, "pana_la": _STR}},
            "sold_initial": _NUM, "sold_final": _NUM, "total_intrari": _NUM, "total_iesiri": _NUM, "flux_net": _NUM,
            "venituri": _objects(sursa=_STR, tip=_STR, suma_totala=_NUM, frecventa=_STR),
            "venit_lunar_estimat": _NUM, "cheltuieli_lunare_estimate": _NUM, "economii_identificate": _NUM,
            "cheltuieli_pe_categorii": _objects(categorie=_STR, suma=_NUM, procent=_NUM),
            "obligatii_recurente": _objects(descriere=_STR, tip=_STR, suma_lunara=_NUM),
            "grad_indatorare_procent": _NUM,
            "cele_mai_mari_tranzactii": _objects(data=_STR, descriere=_STR, suma=_NUM, directie=_STR),
            "semnale_de_risc": _LIST_STR, "puncte_forte": _LIST_STR,
            "scor_stabilitate_financiara": _NUM,
            "nivel_risc": {"type": "string", "enum": ["scazut", "mediu", "ridicat"]},
            "rezumat": _STR, "recomandari": _LIST_STR, "observatii_calitate_date": _STR,
        },
        "required": ["moneda", "total_intrari", "total_iesiri", "scor_stabilitate_financiara", "nivel_risc", "rezumat"],
    },
}


class AnalysisError(Exception):
    pass


def _parse_json(raw: str) -> dict:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise AnalysisError("Răspunsul modelului nu conține JSON.")
    return json.loads(raw[start : end + 1])


def _request(client, text: str, use_tool: bool) -> dict:
    # Sonnet 5.5 rejects forced tool use; accept either the report tool or JSON text.
    kwargs = {"tools": [REPORT_TOOL], "tool_choice": {"type": "auto"}} if use_tool else {}
    # Sonnet 5.5 thinks by default, using the same output budget as the report.
    # This extraction needs a direct structured response, not up-front thinking.
    if MODEL == "claude-sonnet-5-5":
        kwargs.update(thinking={"type": "between_tools"}, output_config={"effort": "medium"})
    elif MODEL == "claude-haiku-5-5":
        kwargs.update(thinking={"type": "disabled"}, output_config={"effort": "medium"})
    message = client.messages.create(
        model=MODEL,
        max_tokens=12000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"<extras_de_cont>\n{text}\n</extras_de_cont>"}],
        **kwargs,
    )
    if message.stop_reason == "max_tokens":
        raise AnalysisError("Răspunsul analizei a atins limita modelului. Conversația poate continua; extrasul nu a fost importat.")
    for block in message.content:
        if block.type == "tool_use" and isinstance(block.input, dict):
            return block.input
    raw = "".join(block.text for block in message.content if block.type == "text")
    return _parse_json(raw)


def _as_text(value):
    if isinstance(value, str) and value.lstrip().startswith("["):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return value
    if isinstance(value, list):
        return " ".join(str(v).strip() for v in value)
    return value


def _as_amount(value) -> float:
    """The model sometimes returns amounts as text. Comparisons must stay numeric."""
    if isinstance(value, bool) or value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(" ", "")
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return 0.0
    return 0.0


def _normalize(result: dict) -> dict:
    """Smaller models occasionally leave derived fields empty or inconsistent; fill them from the detail lists."""
    for key in ("rezumat", "observatii_calitate_date"):
        result[key] = _as_text(result.get(key))
    for key in ("venituri", "cheltuieli_pe_categorii", "obligatii_recurente", "cele_mai_mari_tranzactii",
                "semnale_de_risc", "puncte_forte", "recomandari"):
        if not isinstance(result.get(key), list):
            result[key] = []
    if not result.get("venit_lunar_estimat"):
        regular = [
            _as_amount(v.get("suma_totala"))
            for v in result["venituri"]
            if isinstance(v, dict) and v.get("tip") in ("salariu", "pensie")
        ]
        result["venit_lunar_estimat"] = sum(regular) or None
    by_category = sum(
        _as_amount(c.get("suma")) for c in result["cheltuieli_pe_categorii"] if isinstance(c, dict)
    )
    estimate = _as_amount(result.get("cheltuieli_lunare_estimate"))
    if isinstance(result.get("cheltuieli_lunare_estimate"), str):
        result["cheltuieli_lunare_estimate"] = estimate or None
    if estimate < 50 and by_category >= 50:
        result["cheltuieli_lunare_estimate"] = by_category
    return result


def _apply_parsed(result: dict, text: str) -> dict:
    """Replaces category totals with monthly averages counted from the statement lines."""
    stats = summarize(text)
    if not stats:
        return result
    result["medii_lunare"] = stats["categorii"]
    result["luni_analizate"] = stats["luni"]
    result["cheltuieli_pe_categorii"] = [
        {"categorie": c["label"], "suma": c["medie_lunara"], "procent": c["procent"]} for c in stats["categorii"]
    ]
    result["cheltuieli_lunare_estimate"] = stats["cheltuieli_medii"]
    if stats.get("venit_mediu"):
        result["venit_lunar_estimat"] = stats["venit_mediu"]
    if stats.get("titular"):
        result["titular"] = stats["titular"]
    if stats.get("sold_final") is not None:
        result["sold_final"] = stats["sold_final"]
    if "depozit" not in text.lower() and "cont de economii" not in text.lower():
        result["economii_identificate"] = 0
    result["profil_din_extras"] = {
        k: stats[k] for k in ("varsta", "ocupatie", "locuinta", "alte_intrari_medii", "bursa_medie") if stats.get(k) is not None
    }
    known = set(stats["semnale"])
    result["semnale_de_risc"] = stats["semnale"] + [s for s in result.get("semnale_de_risc") or [] if s not in known]
    note = (f" Mediile pe categorii sunt calculate din tranzacții, pe {stats['luni']} luni"
            " (sumă împărțită la numărul de luni), nu estimate de model.")
    result["observatii_calitate_date"] = ((result.get("observatii_calitate_date") or "") + note).strip()
    return result


def analyze_statement(text: str) -> dict:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise AnalysisError("ANTHROPIC_API_KEY nu este setat pe server.")

    truncated = len(text) > MAX_INPUT_CHARS
    client = anthropic.Anthropic()
    try:
        result = _request(client, text[:MAX_INPUT_CHARS], use_tool=True)
    except (AnalysisError, json.JSONDecodeError):
        try:
            result = _request(client, text[:MAX_INPUT_CHARS], use_tool=False)
        except json.JSONDecodeError as exc:
            raise AnalysisError(f"JSON invalid de la model: {exc}") from exc
    result = _apply_parsed(_normalize(result), text)

    if truncated:
        note = result.get("observatii_calitate_date") or ""
        result["observatii_calitate_date"] = (note + " Documentul a fost trunchiat (prea lung).").strip()
    return result
