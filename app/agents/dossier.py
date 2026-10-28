"""ONRC registration dossier check: classifies uploaded documents and compares them with the required list."""
import re
import unicodedata

# (id, label, patterns that identify the document from its title area, patterns that only mention it)
SRL_REQUIRED = [
    ("cerere_onrc", "Cererea de înregistrare în registrul comerțului (Anexa 2a)",
     [r"cerere\W+inregistrare in registrul comertului", r"anexa nr\.? ?2a"], [r"cerere(a)? de inregistrare in registrul comertului"]),
    ("act_constitutiv", "Actul constitutiv al societății",
     [r"^.{0,300}act(ul)? constitutiv", r"statutul societatii"], [r"act(ul)? constitutiv"]),
    ("dovada_sediu", "Dovada sediului social (contract de comodat / închiriere / act de proprietate)",
     [r"^.{0,300}contract de (comodat|inchiriere|locatiune)", r"^.{0,300}extras de carte funciara"],
     [r"contract de (comodat|inchiriere|locatiune)", r"act de spatiu"]),
    ("rezervare_denumire", "Dovada verificării disponibilității și rezervării denumirii",
     [r"^.{0,300}(dovada|certificat).{0,40}(rezervar|disponibilitat)"], [r"rezervar\w* denumir"]),
    ("dovada_capital", "Dovada vărsării capitalului social",
     [r"^.{0,300}(ordin de plata|foaie de varsamant|dovada varsamant)"], [r"varsamant\w* capital", r"dovad\w* varsamant"]),
    ("declaratie_conditii", "Declarația pe propria răspundere privind îndeplinirea condițiilor de funcționare",
     [r"^.{0,300}declaratie.{0,60}conditiilor de functionare"], [r"declaratie.{0,80}conditiilor de functionare"]),
    ("declaratie_asociat", "Declarația pe propria răspundere a asociatului / administratorului",
     [r"^.{0,300}declaratie pe propria raspundere.{0,80}(asociat|administrator)"], [r"declaratie.{0,60}(asociat|administrator)"]),
    ("beneficiar_real", "Declarația privind beneficiarul real",
     [r"^.{0,300}declaratie.{0,40}beneficiar\w* real"], [r"beneficiar\w* real"]),
    ("cerere_fiscala", "Cererea de înregistrare fiscală (Anexa 1, vectorul fiscal)",
     [r"cerere de inregistrare fiscala", r"vectorul fiscal"], [r"inregistrare fiscala"]),
    ("identitate", "Copia actului de identitate al asociatului / administratorului",
     [r"^.{0,200}(carte de identitate|romania.{0,20}identity card)"], [r"act(ul)? de identitate", r"\bci seria\b"]),
]
PFA_REQUIRED = [
    ("cerere_onrc", "Cererea de înregistrare PFA în registrul comerțului",
     [r"cerere\W+inregistrare.{0,80}(persoan\w+ fizic\w+ autorizat|pfa)"], [r"cerere.{0,40}inregistrare"]),
    ("dovada_sediu", "Dovada sediului profesional", SRL_REQUIRED[2][2], SRL_REQUIRED[2][3]),
    ("declaratie_conditii", "Declarația pe propria răspundere privind îndeplinirea condițiilor de funcționare",
     SRL_REQUIRED[5][2], SRL_REQUIRED[5][3]),
    ("calificare", "Dovada calificării profesionale (diplomă, certificat), dacă activitatea o cere",
     [r"^.{0,300}(diploma|certificat de (calificare|absolvire))"], [r"calificar\w* profesional"]),
    ("cerere_fiscala", "Cererea de înregistrare fiscală", SRL_REQUIRED[8][2], SRL_REQUIRED[8][3]),
    ("identitate", "Copia actului de identitate", SRL_REQUIRED[9][2], SRL_REQUIRED[9][3]),
]
EXPENSE_INVOICE = [r"^.{0,400}factura", r"total de plata", r"cota tva"]
BANNER = re.compile(r"^document fictiv.{0,260}?valoare juridica\.?\s*", re.S)


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.split())


def _head(text: str) -> str:
    return BANNER.sub("", fold(text))[:900]


def classify(text: str) -> list[str]:
    head = _head(text)
    kinds = [rid for rid, _, title, _ in SRL_REQUIRED + PFA_REQUIRED if any(re.search(p, head) for p in title)]
    if any(re.search(p, head) for p in EXPENSE_INVOICE[:1]):
        kinds.append("factura")
    return sorted(set(kinds))


def review(form: str, documents: list[dict]) -> dict:
    required = PFA_REQUIRED if form.lower() == "pfa" else SRL_REQUIRED
    items = []
    for rid, label, _, mention in required:
        uploaded = [d["name"] for d in documents if rid in d.get("kinds", [])]
        mentioned = [d["name"] for d in documents if rid not in d.get("kinds", [])
                     and any(re.search(p, fold(d.get("text", ""))) for p in mention)]
        if uploaded:
            status = "incarcat"
        elif mentioned:
            status = "mentionat_dar_neincarcat"
        else:
            status = "lipsa"
        items.append({"document": label, "status": status, "in_fisiere": uploaded, "mentionat_in": mentioned})
    done = sum(1 for i in items if i["status"] == "incarcat")
    return {
        "forma": form.upper(), "documente_incarcate": [{"nume": d["name"], "tip_detectat": d.get("kinds", [])} for d in documents],
        "verificare": items, "complet": done == len(items),
        "nota": "Lista urmează practica ONRC conform Legii 265/2022; verifică pe onrc.ro cerințele pentru cazul tău. "
                "Citește și conținutul: date identice (denumire, sediu, asociat, CAEN) în toate documentele, act de spațiu valabil, semnături.",
        "summary": f"Dosar {form.upper()}: {done}/{len(items)} documente încărcate; lipsesc: "
                   + (", ".join(i["document"].split(" (")[0] for i in items if i["status"] != "incarcat") or "nimic"),
    }
