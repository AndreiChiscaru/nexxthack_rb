"""User profile built by the onboarding agent: field specs, merging, missing-field detection."""
import copy

GOAL_TYPES = ["avans_casa", "masina", "fond_urgenta", "achitare_datorii", "studii", "afacere",
              "vacanta", "pensie", "investitii", "altul"]
RISK_LEVELS = ["scazuta", "medie", "ridicata"]

# (path, label, required, format)
FIELD_SPECS = [
    ("name", "Nume", True, "text"),
    ("age", "Vârstă", True, "int"),
    ("occupation", "Ocupație", True, "text"),
    ("goal.description", "Scop", True, "text"),
    ("goal.target_amount", "Suma necesară pentru scop", True, "money"),
    ("goal.horizon_months", "Termen pentru scop", True, "months"),
    ("income.salary", "Venit net lunar din muncă", True, "money"),
    ("income.scholarship", "Bursă / lună", False, "money"),
    ("income.other", "Alte venituri / lună", False, "money"),
    ("home.housing", "Chirie sau rată locuință", True, "money"),
    ("home.utilities", "Utilități / lună", True, "money"),
    ("home.subscriptions", "Abonamente / lună", False, "money"),
    ("market.food", "Mâncare / lună", True, "money"),
    ("market.transport", "Transport / lună", False, "money"),
    ("market.leisure", "Ieșiri și vacanțe / lună", False, "money"),
    ("education.status", "Situație educațională", False, "text"),
    ("education.tuition_monthly", "Taxe școlarizare / lună", False, "money"),
    ("health.insured", "Asigurare de sănătate privată", False, "bool"),
    ("health.monthly_costs", "Costuri medicale / lună", False, "money"),
    ("bank.cash", "Bani în contul curent", True, "money"),
    ("bank.savings", "Economii", True, "money"),
    ("bank.investments", "Investiții", False, "money"),
    ("bank.debts", "Credite / rate", False, "debts"),
    ("risk_tolerance", "Toleranță la risc", True, "text"),
    ("dependents", "Persoane în întreținere", False, "int"),
    ("business.interest", "Interes pentru o afacere", False, "bool"),
    ("business.idea", "Ideea de afacere", False, "text"),
]

_money = {"type": "number", "description": "lei pe lună (convertește din sume anuale/săptămânale)"}
UPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
        "occupation": {"type": "string"},
        "goal": {"type": "object", "properties": {
            "description": {"type": "string", "description": "scopul în cuvintele utilizatorului, concret"},
            "type": {"type": "string", "enum": GOAL_TYPES},
            "target_amount": {"type": "number", "description": "lei, suma totală necesară"},
            "horizon_months": {"type": "integer", "description": "în câte luni vrea să atingă scopul"},
        }},
        "income": {"type": "object", "properties": {"salary": _money, "scholarship": _money, "other": _money}},
        "home": {"type": "object", "properties": {"housing": _money, "utilities": _money, "subscriptions": _money}},
        "market": {"type": "object", "properties": {"food": _money, "transport": _money, "leisure": _money}},
        "education": {"type": "object", "properties": {
            "status": {"type": "string", "description": "ex. elev, student, absolvent, angajat, master"},
            "tuition_monthly": _money}},
        "health": {"type": "object", "properties": {"insured": {"type": "boolean"}, "monthly_costs": _money}},
        "bank": {"type": "object", "properties": {
            "cash": {"type": "number", "description": "lei în contul curent acum"},
            "savings": {"type": "number", "description": "lei economisiți (depozite, cont de economii)"},
            "investments": {"type": "number", "description": "lei investiți (fonduri, acțiuni, Pilon III)"},
            "debts": {"type": "array", "description": "lista COMPLETĂ a creditelor (înlocuiește lista anterioară)",
                      "items": {"type": "object", "properties": {
                          "name": {"type": "string"}, "monthly_payment": {"type": "number"},
                          "remaining": {"type": "number", "description": "sold rămas, dacă se știe"},
                          "apr": {"type": "number", "description": "dobânda anuală ca fracție, ex. 0.12"}},
                          "required": ["name", "monthly_payment"]}},
        }},
        "risk_tolerance": {"type": "string", "enum": RISK_LEVELS},
        "dependents": {"type": "integer"},
        "business": {"type": "object", "properties": {"interest": {"type": "boolean"}, "idea": {"type": "string"}}},
    },
}


def empty() -> dict:
    return {"data": {}, "sources": {}}


def get(data: dict, path: str):
    node = data
    for key in path.split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _walk(patch: dict, prefix: str = ""):
    for key, value in patch.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            yield from _walk(value, path + ".")
        else:
            yield path, value


def merge(profile: dict, patch: dict, source: str) -> list[str]:
    """Deep-merges non-null values from `patch` into the profile. Returns the updated paths."""
    updated = []
    for path, value in _walk(patch or {}):
        if value is None or value == "":
            continue
        node = profile["data"]
        keys = path.split(".")
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = copy.deepcopy(value)
        profile["sources"][path] = source
        updated.append(path)
    return updated


def missing(profile: dict) -> list[str]:
    return [label for path, label, required, _ in FIELD_SPECS if required and get(profile["data"], path) is None]


def fields_view(profile: dict) -> list[dict]:
    return [{"path": path, "label": label, "required": required, "format": fmt,
             "value": get(profile["data"], path), "source": profile["sources"].get(path)}
            for path, label, required, fmt in FIELD_SPECS]
