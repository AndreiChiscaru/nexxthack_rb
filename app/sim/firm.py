"""A business started by the accountant, on top of the journey engine.

The monthly cash (revenue minus operating costs, before tax) is added for one month only.
Taxes accrue and are paid when a fiscal deadline event is answered. Projections settle the
taxes up front and then count the after-tax cash, so a 12-month comparison does not ignore ANAF.
"""
import copy
from datetime import date

from ..agents import taxes
from ..schemas import Event, EventOption
from . import engine as E

LATE_DAYS = 30


def next_calendar_month(today: date | None = None) -> list[int]:
    today = today or date.today()
    return [today.year + today.month // 12, today.month % 12 + 1]


def calendar(sim: dict, month: int) -> tuple[int, int]:
    start = sim.get("calendar_start") or next_calendar_month()
    index = int(start[1]) - 1 + month
    return int(start[0]) + index // 12, index % 12 + 1


def open_business(sim: dict, business: dict) -> None:
    if sim.get("firm"):
        raise ValueError(sim["firm"]["name"])
    E.spend(sim, float(business.get("startup_cost") or 0))
    record = copy.deepcopy(business)
    record.setdefault("arrears", [])
    sim["firm"] = record


def month_cash(sim: dict) -> float:
    firm = sim.get("firm")
    if not isinstance(firm, dict):
        return 0.0
    return float(firm.get("monthly_cash") or 0)


def accrue(sim: dict) -> None:
    firm = sim.get("firm")
    if not isinstance(firm, dict) or firm.get("_projection"):
        return
    for obligation in firm.get("obligations", []):
        obligation["accrued"] = round(float(obligation["accrued"]) + float(obligation["monthly"]), 2)


def settle_projection(sim: dict) -> None:
    """On a copied state: pay what is already owed, then count only the money left after taxes."""
    firm = sim.get("firm")
    if not isinstance(firm, dict) or firm.get("_projection"):
        return
    owed = _taxes_due(firm)
    firm = copy.deepcopy(firm)
    firm["_projection"] = True
    firm["monthly_cash"] = float(firm["monthly_net"])
    for obligation in firm.get("obligations", []):
        obligation["accrued"] = 0.0
    firm["arrears"] = []
    sim["firm"] = firm
    if owed > 0.5:
        E.spend(sim, owed)


def _taxes_due(firm: dict) -> float:
    accrued = sum(float(o["accrued"]) for o in firm.get("obligations", []))
    arrears = sum(float(a["amount"]) for a in firm.get("arrears", []))
    return round(accrued + arrears, 2)


def make_fiscal_event(sim: dict, year: int, month: int) -> Event | None:
    firm = sim.get("firm")
    if not isinstance(firm, dict) or firm.get("_projection"):
        return None
    arrears = list(firm.get("arrears") or [])
    if arrears:
        total = round(sum(float(a["amount"]) for a in arrears), 2)
        extra = round(sum(float(a["extra"]) for a in arrears), 2)
        labels = "; ".join(str(a["label"]) for a in arrears)
        firm["arrears"] = []
        return Event(
            id="fiscal_arrears",
            institution="business",
            title="Restanță la ANAF",
            text=(f"Ai amânat: {labels}. Acum datorezi {E.money(total)}, din care {E.money(extra)} "
                  "dobânzi, penalități și amendă."),
            options=[EventOption(id="plateste", label=f"Plătesc restanța ({E.money(total)})",
                                 ops={"fiscal_pay": total})],
        )
    due = [o for o in firm.get("obligations", []) if month in o["months"] and float(o["accrued"]) > 0.5]
    if not due:
        return None
    total = round(sum(float(o["accrued"]) for o in due), 2)
    lines = ", ".join(f"{o['declaration']} ({E.money(o['accrued'])})" for o in due)
    form = str(due[0].get("form", "srl"))
    for obligation in due:
        obligation["accrued"] = 0.0
    late = taxes.late_cost(total, LATE_DAYS, form)
    label = " + ".join(o["declaration"] for o in due) + f" din {taxes.MONTHS_RO[month - 1]} {year}"
    return Event(
        id="fiscal_deadline",
        institution="business",
        title=f"Termen fiscal: 25 {taxes.MONTHS_RO[month - 1]} {year}",
        text=f"Trebuie depuse și plătite: {lines}. Total {E.money(total)}.",
        options=[
            EventOption(id="plateste", label="Depun și plătesc la timp", ops={"fiscal_pay": total}),
            EventOption(id="aman", label="Amân o lună", ops={"fiscal_late": {
                "amount": total, "label": label, "extra": late["total"],
            }}),
        ],
    )


def apply_fiscal_choice(sim: dict, option: EventOption) -> str:
    firm = sim.get("firm")
    if not isinstance(firm, dict):
        raise ValueError("Nu ai o firmă pornită.")
    if "fiscal_pay" in option.ops:
        amount = float(option.ops["fiscal_pay"])
        E.spend(sim, amount)
        return f"Ai plătit {E.money(amount)} către ANAF."
    late = option.ops["fiscal_late"]
    extra = float(late["extra"])
    firm.setdefault("arrears", []).append({
        "label": late["label"],
        "amount": round(float(late["amount"]) + extra, 2),
        "extra": round(extra, 2),
    })
    return (f"Restanță la ANAF: {E.money(float(late['amount']))} plus {E.money(extra)} "
            "dobânzi, penalități și amendă. Luna următoare o poți plăti de la Afacere.")


def public_view(sim: dict, month: int) -> dict | None:
    firm = sim.get("firm")
    if not isinstance(firm, dict) or firm.get("_projection"):
        return None
    return {
        "name": firm["name"],
        "form": firm["form"],
        "regime": firm["regime"],
        "regime_label": firm["regime_label"],
        "monthly_revenue": round(float(firm["monthly_revenue"]), 2),
        "monthly_expenses": round(float(firm["monthly_expenses"]), 2),
        "monthly_taxes": round(float(firm["monthly_taxes"]), 2),
        "monthly_cash": round(float(firm["monthly_cash"]), 2),
        "taxes_due": _taxes_due(firm),
        "next_due": _next_due(sim, month, firm),
    }


def _next_due(sim: dict, month: int, firm: dict) -> str:
    if not sim.get("calendar_start"):
        return ""
    for ahead in range(1, 13):
        year, calendar_month = calendar(sim, month + ahead)
        if any(calendar_month in o["months"] for o in firm.get("obligations", [])):
            return f"25 {taxes.MONTHS_RO[calendar_month - 1]} {year}"
    return ""
