import json
import os

import anthropic

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
MAX_INPUT_CHARS = 180_000

SYSTEM_PROMPT = """Ești un analist financiar care evaluează extrase de cont bancare (în special din România).
Primești textul extras (posibil prin OCR, cu erori) dintr-un extras de cont.
Analizează tranzacțiile și returnează EXCLUSIV un obiect JSON valid, fără text în afara lui, cu structura:

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
- Sumele sunt numere (fără simbol monetar), în moneda contului.
- scor_stabilitate_financiara este între 0 și 100.
- Semnale de risc relevante: sold negativ/descoperit, comisioane de neplată, popriri/executări silite, jocuri de noroc, credite rapide (IFN), retrageri mari de numerar, venit neregulat, cheltuieli > venituri.
- cheltuieli_lunare_estimate = consumul RECURENT real pe lună (chirie, mâncare, utilități, transport, cumpărături, transferuri regulate către alte persoane). Exclude tranzacțiile mari evident unice sau ocazionale (le menționezi în observatii_calitate_date și, dacă e cazul, în semnale_de_risc). FĂRĂ transferuri între conturile proprii ale titularului (ex. spre propriul Revolut), FĂRĂ alimentări de depozite/economii și FĂRĂ rate de credit. Dacă perioada nu e o lună, normalizează la o lună. Dacă banii pleacă spre un cont propriu din care probabil se plătesc cheltuielile, include sumele respective în estimare și explică în observatii_calitate_date.
- economii_identificate = economiile titularului vizibile la sfârșitul perioadei (depozite, conturi de economii active), fără soldul contului curent; null dacă nu apar.
- Nu inventa date. Dacă o informație lipsește, folosește null sau listă goală și menționează în observatii_calitate_date.
- rezumat: 3-6 propoziții în limba română despre starea financiară a persoanei.
"""


class AnalysisError(Exception):
    pass


def _parse_json(raw: str) -> dict:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise AnalysisError("Răspunsul modelului nu conține JSON.")
    return json.loads(raw[start : end + 1])


def analyze_statement(text: str) -> dict:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise AnalysisError("ANTHROPIC_API_KEY nu este setat pe server.")

    truncated = len(text) > MAX_INPUT_CHARS
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"<extras_de_cont>\n{text[:MAX_INPUT_CHARS]}\n</extras_de_cont>",
            }
        ],
    )
    raw = "".join(block.text for block in message.content if block.type == "text")
    try:
        result = _parse_json(raw)
    except json.JSONDecodeError as exc:
        raise AnalysisError(f"JSON invalid de la model: {exc}") from exc

    if truncated:
        note = result.get("observatii_calitate_date") or ""
        result["observatii_calitate_date"] = (note + " Documentul a fost trunchiat (prea lung).").strip()
    return result
