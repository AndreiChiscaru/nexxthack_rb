"""Monthly spending averages read from a bank-statement text.

The game shows these numbers. They are sums of dated lines divided by the number of distinct months,
so they do not depend on the model's estimate.
"""
import re
from collections import defaultdict

# First match wins, so specific merchants stay above generic words like "restaurant".
RULES = [
    ("uber", "Transport (Uber / Bolt)", "market", ("uber", "bolt")),
    ("restaurante", "Restaurante și baruri", "market", ("beraria", "spoon", "mcdonald", "kfc", "pizza napoli", "terasa", "restaurant")),
    ("livrari", "Livrări de mâncare", "market", ("glovo", "tazz", "wolt", "foodpanda")),
    ("cafea", "Cafea de drum", "market", ("5 to go", "starbucks", "ted's coffee", "teds coffee")),
    ("alimente", "Cumpărături alimentare", "market", ("kaufland", "lidl", "profi", "mega image", "carrefour")),
    ("cumparaturi", "Cumpărături impulsive", "market", ("about you", "h&m", "zara", "bershka", "shein")),
    ("pariuri", "Pariuri online", "market", ("superbet", "betano", "unibet")),
    ("abonamente", "Abonamente", "home", ("netflix", "spotify", "hbo", "world class")),
    ("rate", "Rate la comercianți (PayPo)", "market", ("paypo", "klarna", "tbi pay")),
    ("numerar", "Retrageri de numerar", "bank", ("retragere numerar", "atm")),
    ("telefon", "Telefon", "home", ("orange", "vodafone", "digi mobil")),
]
INCOME_WORDS = ("incasare salariu", "salariu ")
OTHER_INCOME_WORDS = ("transfer primit",)
SCHOLARSHIP_WORDS = ("bursa facultate", "bursă facultate", "bursa de merit")
SKIP_WORDS = ("sold initial", "sold final", "comision")
LINE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})\s+(.+?)\s+([+-]?\d{1,3}(?:\.\d{3})*,\d{2})\s*$")
SOLD_FINAL = re.compile(r"Sold final\s+([+-]?\d{1,3}(?:\.\d{3})*,\d{2})")
MIN_MONTHS = 3
MIN_EXPENSES = 12


def parse_amount(raw: str) -> float:
    return float(raw.replace(".", "").replace(",", "."))


def _header(text: str, label: str) -> str | None:
    prefix = label.lower() + ":"
    for line in text.splitlines()[:20]:
        if line.lower().startswith(prefix):
            return line.split(":", 1)[1].strip() or None
    return None


def _category(description: str) -> str | None:
    text = description.lower()
    if any(word in text for word in INCOME_WORDS) or any(word in text for word in SKIP_WORDS):
        return None
    if any(word in text for word in OTHER_INCOME_WORDS) or any(word in text for word in SCHOLARSHIP_WORDS):
        return None
    for cid, _, _, words in RULES:
        if any(word in text for word in words):
            return cid
    return None


def summarize(text: str) -> dict | None:
    """Sums dated transactions by category and divides by the number of distinct months."""
    spent: dict[str, float] = defaultdict(float)
    salary: dict[str, float] = defaultdict(float)
    other: dict[str, float] = defaultdict(float)
    scholarship: dict[str, float] = defaultdict(float)
    months: set[str] = set()
    expense_count = 0
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        match = LINE.search(line)
        if not match:
            continue
        _day, month, year, description, amount_raw = match.groups()
        amount = parse_amount(amount_raw)
        key = f"{year}-{month}"
        months.add(key)
        lowered = description.lower()
        if any(word in lowered for word in SKIP_WORDS):
            continue
        if amount > 0 and any(word in lowered for word in INCOME_WORDS):
            salary[key] += amount
            continue
        if amount > 0 and any(word in lowered for word in SCHOLARSHIP_WORDS):
            scholarship[key] += amount
            continue
        if amount > 0 and any(word in lowered for word in OTHER_INCOME_WORDS):
            other[key] += amount
            continue
        if amount >= 0:
            continue
        category = _category(description)
        if not category:
            continue
        spent[category] += -amount
        expense_count += 1
    if len(months) < MIN_MONTHS or expense_count < MIN_EXPENSES or sum(spent.values()) <= 0:
        return None
    n = len(months)
    categorii = []
    for cid, label, institution, _ in RULES:
        total = spent.get(cid, 0.0)
        if total <= 0:
            continue
        categorii.append({
            "id": cid, "label": label, "institution": institution,
            "total": round(total, 2), "medie_lunara": round(total / n, 2),
        })
    categorii.sort(key=lambda c: -c["medie_lunara"])
    total_lunar = round(sum(c["medie_lunara"] for c in categorii), 2)
    for cat in categorii:
        cat["procent"] = round(100 * cat["medie_lunara"] / total_lunar, 1) if total_lunar else 0.0
    by_id = {c["id"]: c["medie_lunara"] for c in categorii}
    semnale = []
    if by_id.get("uber", 0) >= 400:
        semnale.append(f"Transport prin Uber/Bolt: {by_id['uber']:.0f} lei/lună, mult pentru un student.")
    if by_id.get("restaurante", 0) + by_id.get("livrari", 0) >= 500:
        semnale.append("Ieșirile și livrările depășesc cumpărăturile alimentare.")
    if by_id.get("pariuri", 0) >= 50:
        semnale.append(f"Pariuri online: {by_id['pariuri']:.0f} lei/lună.")
    if by_id.get("rate", 0) >= 50:
        semnale.append("Cumpărături în rate (PayPo), deși venitul e de part-time.")
    if by_id.get("numerar", 0) >= 100:
        semnale.append("Retrageri de numerar frecvente, fără să se vadă pe ce s-au dus.")
    if by_id.get("abonamente", 0) >= 150:
        semnale.append(f"Abonamente (inclusiv sală): {by_id['abonamente']:.0f} lei/lună.")
    housing = (_header(text, "Locuinta") or "").lower()
    age_raw = _header(text, "Varsta")
    sold = SOLD_FINAL.search(text)
    return {
        "luni": n,
        "venit_mediu": round(sum(salary.values()) / n, 2) if salary else None,
        "alte_intrari_medii": round(sum(other.values()) / n, 2) if other else None,
        "bursa_medie": round(sum(scholarship.values()) / n, 2) if scholarship else None,
        "cheltuieli_medii": total_lunar,
        "categorii": categorii,
        "semnale": semnale,
        "titular": _header(text, "Titular"),
        "varsta": int(age_raw) if age_raw and age_raw.isdigit() else None,
        "ocupatie": _header(text, "Ocupatie"),
        "locuinta": "parinti" if "parint" in housing else None,
        "sold_final": round(parse_amount(sold.group(1)), 2) if sold else None,
    }
