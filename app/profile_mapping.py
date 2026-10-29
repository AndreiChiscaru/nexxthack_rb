"""Maps the onboarding agent's profile (app/agents/profile.py) onto the §4.1 Profile contract.

Pure functions, no I/O. The agent keeps its own field names; this module is the only place that knows both.
"""
from typing import Any

from .agents import profile as prof
from .schemas import INSTITUTIONS

# Agent path -> §4.1 path, for fields that are copied as-is (only renamed or moved).
FIELD_MAP: dict[str, str] = {
    "name": "name",
    "age": "age",
    "goal.description": "goal.description",
    "goal.type": "goal.type",
    "goal.target_amount": "goal.target_amount",
    "goal.horizon_months": "goal.horizon_months",
    "income.salary": "income.salary",
    "income.other": "income.other",
    "income.scholarship": "education.scholarship",  # the adapter counts it as engine side_income
    "home.housing": "recurring.rent",                # "rent OR mortgage payment" in the agent
    "home.utilities": "recurring.utilities",
    "home.subscriptions": "recurring.subscriptions",
    "market.transport": "recurring.transport",
    "market.food": "spending.food",
    "market.leisure": "spending.leisure",
    "education.status": "education.status",
    "education.tuition_monthly": "education.tuition_monthly",
    "health.insured": "health.insured",
    "health.monthly_costs": "health.monthly_costs",
    "bank.cash": "cash",
    "bank.savings": "savings",
    "bank.investments": "investments",
    "risk_tolerance": "risk_tolerance",
    "dependents": "dependents",
    "business.interest": "business_interest",
}
# Agent-only fields with no §4.1 equivalent; dropped on purpose.
DROPPED = ("occupation", "business.idea")
DEFAULT_GOAL_TYPE = "altul"


def _set(target: dict, path: str, value: Any) -> None:
    keys = path.split(".")
    for key in keys[:-1]:
        target = target.setdefault(key, {})
    target[keys[-1]] = value


def _debt(item: dict) -> dict:
    """Agent debt {name, monthly_payment, remaining?, apr?} -> §4.1 {name, monthly, remaining, apr}.

    Missing APR/principal stay null until explicitly supplied by the user or statement.
    """
    name = str(item.get("name") or "Credit existent")
    monthly = float(item.get("monthly_payment") or 0)
    # Unknown balances/rates remain unknown; onboarding must ask, never amortize a guessed term.
    apr = float(item['apr']) if item.get('apr') is not None else None
    remaining = float(item['remaining']) if item.get('remaining') is not None else None
    return {"name": name, "monthly": monthly, "remaining": remaining, "apr": apr}


def agent_profile_to_profile(data: dict, statement: dict | None = None) -> dict:
    """The single mapping from the agent's profile data (`profile["data"]`) to a §4.1 Profile dict.

    Differences handled here (everything else in FIELD_MAP is only renamed or moved):
    - home.* / market.*      -> recurring.* (rent, utilities, subscriptions, transport) and spending.* (food, leisure)
    - bank.cash/savings/...  -> root fields cash / savings / investments
    - bank.debts[]           -> debts[] with monthly_payment -> monthly; apr/remaining remain null if missing;
                                no debts reported -> [] (optional for the agent, required in §4.1)
    - income.scholarship     -> education.scholarship
    - business.interest      -> business_interest
    - goal.type              -> optional in the agent; defaults to "altul" when the agent set a goal
    - occupation, business.idea -> no §4.1 field, dropped
    - statement (score, risk_signals) -> source
    Only fields present in `data` are emitted, so the result can be partial; validate it with Profile.
    """
    out: dict = {}
    for agent_path, profile_path in FIELD_MAP.items():
        value = prof.get(data, agent_path)
        if value is not None:
            _set(out, profile_path, value)
    if "goal" in out:
        out["goal"].setdefault("type", DEFAULT_GOAL_TYPE)
    # The onboarding quiz no longer asks the 10% drop question, so a missing answer stays neutral.
    out.setdefault("risk_tolerance", "medie")
    # Debts are optional for the agent: none reported means none.
    out["debts"] = [_debt(item) for item in prof.get(data, "bank.debts") or []]
    categories = []
    for item in prof.get(data, "categories") or []:
        if not isinstance(item, dict) or item.get("institution") not in INSTITUTIONS:
            continue
        if not item.get("id") or not item.get("label"):
            continue
        categories.append({"id": str(item["id"]), "label": str(item["label"]), "institution": item["institution"],
                           "monthly": round(float(item.get("monthly") or 0), 2)})
    if categories:
        out["categories"] = [c for c in categories if c["monthly"] > 0]
    if statement:
        out["source"] = {"statement_uploaded": True, "statement_score": statement.get("score"),
                         "risk_signals": list(statement.get("risk_signals") or [])}
    return out


def missing_fields(agent_profile: dict) -> list[str]:
    """Required fields the agent still needs, as §4.1 paths (agent-only fields keep the agent's name)."""
    result = [FIELD_MAP.get(path, path) for path, _, required, _ in prof.FIELD_SPECS
              if required and prof.get(agent_profile["data"], path) is None]
    for index, debt in enumerate(prof.get(agent_profile['data'], 'bank.debts') or []):
        for field in ('remaining', 'apr'):
            if debt.get(field) is None: result.append(f'debts.{index}.{field}')
    return result
