"""Maps the Claude statement analysis onto the starting state of the Raiff Quest simulation."""
from datetime import date

DEBT_TYPES = {"rata credit", "leasing"}
DEFAULT_LOAN = {"apr": 0.10, "months": 48}
MORTGAGE_LOAN = {"apr": 0.065, "months": 240}
IFN_LOAN = {"apr": 0.35, "months": 24}
IFN_MARKERS = ("ifn", "credius", "provident", "viva credit", "ferratum", "cetelem", "tbi", "mogo", "credit rapid")
MIN_LIVING = 300.0
# Typical Romanian mortgages finance ~80% of the property, so value ≈ principal / 0.8.
HOME_VALUE_TO_MORTGAGE = 1.25


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _period_months(period: dict | None) -> float:
    try:
        start = date.fromisoformat(period["de_la"])
        end = date.fromisoformat(period["pana_la"])
    except (TypeError, KeyError, ValueError):
        return 1.0
    return max(1.0, round(((end - start).days + 1) / 30.4, 1))


def _principal(payment: float, apr: float, months: int) -> float:
    r = apr / 12.0
    return payment * (1 - (1 + r) ** -months) / r


def _loan_terms(description: str) -> dict:
    text = description.lower()
    if "ipotec" in text or "imobiliar" in text or "casa" in text:
        return MORTGAGE_LOAN
    if any(marker in text for marker in IFN_MARKERS):
        return IFN_LOAN
    return DEFAULT_LOAN


def _display_name(holder: str | None) -> str:
    if not holder:
        return "Jucătorul"
    return " ".join(part.capitalize() for part in holder.split())


def to_game_profile(analysis: dict) -> dict:
    months = _period_months(analysis.get("perioada"))

    loans = []
    for item in analysis.get("obligatii_recurente") or []:
        if str(item.get("tip", "")).lower() not in DEBT_TYPES:
            continue
        payment = _num(item.get("suma_lunara"))
        if payment <= 0:
            continue
        terms = _loan_terms(str(item.get("descriere", "")))
        loans.append({
            "name": str(item.get("descriere") or "Credit existent")[:40],
            "principal": round(_principal(payment, terms["apr"], terms["months"]), 2),
            "apr": terms["apr"],
            "months": terms["months"],
            "payment": payment,
        })
    debt_payments = sum(loan["payment"] for loan in loans)
    mortgage_principal = sum(loan["principal"] for loan in loans if loan["months"] == MORTGAGE_LOAN["months"])

    income = _num(analysis.get("venit_lunar_estimat")) or _num(analysis.get("total_intrari")) / months
    if analysis.get("cheltuieli_lunare_estimate") is not None:
        living = _num(analysis.get("cheltuieli_lunare_estimate"))
    else:
        living = _num(analysis.get("total_iesiri")) / months - debt_payments
    living = max(living, MIN_LIVING)

    balance = _num(analysis.get("sold_final"))
    score = max(0.0, min(100.0, _num(analysis.get("scor_stabilitate_financiara"), 50.0)))

    return {
        "name": _display_name(analysis.get("titular")),
        "salary": round(max(income, 0.0), 2),
        "living": round(living, 2),
        "cash": round(max(balance, 0.0), 2),
        "overdraft": round(max(-balance, 0.0), 2),
        "emergency": round(max(_num(analysis.get("economii_identificate")), 0.0), 2),
        "home_value": round(mortgage_principal * HOME_VALUE_TO_MORTGAGE, 2),
        "loans": loans,
        "stress": round(max(10.0, min(90.0, 80.0 - 0.6 * score)), 1),
        "confidence": round(max(10.0, min(90.0, 20.0 + 0.6 * score)), 1),
        "insights": {
            "score": round(score),
            "risk": analysis.get("nivel_risc") or "mediu",
            "summary": analysis.get("rezumat") or "",
            "risk_signals": (analysis.get("semnale_de_risc") or [])[:4],
            "strengths": (analysis.get("puncte_forte") or [])[:3],
            "period_months": months,
        },
    }
