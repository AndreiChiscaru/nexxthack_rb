"""The financial engine and the product catalog exposed as tools for the agents.

Plain functions over a session, each returning a JSON-safe dict with a short Romanian `summary`.
TOOL_SCHEMAS lists them for LLM tool use; run_tool() validates the arguments, runs the tool and logs the call
in the session as {name, args, summary, duration_ms} (the ToolCall shape). Server logs get only the tool name,
status and duration, never arguments or results.
Simulations run on a deep copy of the session's engine state and never change the game.
"""
import copy
import logging
import re
import time
import unicodedata
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import catalog
from .sessions import Session, find_session, game_state
from .sim import adapter
from .sim import engine as E
from .sim.events import Ops

log = logging.getLogger("extras.tools")

MAX_MONTHS = 120
DEPOSIT_TAX = 0.10
LOAN_CATEGORIES = ("credit", "locuinta")
SAVINGS_CATEGORIES = ("economii",)
OPS_HELP = ("Operații ale motorului (aceleași ca la evenimente): spend, loan{name,principal,apr,months}, salary_mult, "
            "salary_add, living_add, side_income_add, business_value, car_value, emergency_contrib, invest_contrib, "
            "insurance_level+insurance_premium, medical_cost(+finance_months), bonus{amount,mode,spend?}, mood{stress,conf}.")


class ToolError(ValueError):
    pass


# ---------------------------------------------------------------- helpers

def _r(x: float) -> float:
    return round(float(x), 2)


def _session(session_id: str) -> Session:
    session = find_session(session_id)
    if session is None:
        raise ToolError("Sesiune inexistentă.")
    if session.sim is None or session.profile is None:
        raise ToolError("Jocul nu a pornit încă.")
    return session


def _validated_ops(ops: dict) -> dict:
    try:
        return Ops.model_validate(ops).to_engine()
    except ValidationError as exc:
        raise ToolError(f"ops invalide: {exc.errors()[0]['msg']} ({'.'.join(map(str, exc.errors()[0]['loc']))})") from exc


def _sandbox(session: Session) -> SimpleNamespace:
    """Deep copy of everything a simulation could touch; the session itself is never mutated."""
    return SimpleNamespace(sim=E.clone(session.sim), rng=copy.deepcopy(session.rng),
                           year_rep=copy.deepcopy(session.year_rep), month=session.month)


def _snapshot(sim: E.SimState, profile, month: int) -> dict:
    b = adapter.balance(sim)
    return {
        "month": month, "age": int(sim["age"]),
        "cash": b.cash, "savings": b.savings, "investments": b.investments, "debt": b.debt, "net_worth": b.net_worth,
        "monthly_income": _r(E.income(sim)), "monthly_payments": _r(E.debt_payments(sim)),
        "monthly_surplus": _r(E.monthly_surplus(sim)),
        "goal_progress": adapter.goal(sim, profile, month).progress,
        "stress": _r(sim["stress"]), "confidence": _r(sim["confidence"]),
    }


def _run(session: Session, ops: dict | None, months: int) -> tuple[dict, dict]:
    """Applies `ops` (if any) to a sandbox and runs `months` months. Random events aren't simulated."""
    box = _sandbox(session)
    before = _snapshot(box.sim, session.profile, box.month)
    if ops:
        mood = E.apply_ops(box.sim, ops, [])
        box.sim["stress"] = max(0.0, min(100.0, box.sim["stress"] + mood["stress"]))
        box.sim["confidence"] = max(0.0, min(100.0, box.sim["confidence"] + mood["confidence"]))
    for _ in range(months):
        box.month = int(adapter.advance_month(box.sim, box.month, box.year_rep)["month"])
    return before, _snapshot(box.sim, session.profile, box.month)


def _diff(after: dict, before: dict) -> dict:
    return {k: _r(after[k] - before[k]) for k in ("cash", "savings", "investments", "debt", "net_worth", "goal_progress")}


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def _rate(product: catalog.Product) -> float | None:
    """First percentage in the product's terms (catalog rates are text). None if the catalog gives no rate."""
    match = re.search(r"(\d+(?:,\d+)?)\s*%", product.terms)
    return round(float(match.group(1).replace(",", ".")) / 100, 4) if match else None


def loan_cost(amount: float, apr: float, months: int) -> dict:
    payment = E.pmt(amount, apr, months)
    return {"monthly_payment": _r(payment), "total_paid": _r(payment * months), "total_interest": _r(payment * months - amount)}


def deposit_return(amount: float, rate: float, months: int) -> dict:
    gross = amount * rate * months / 12
    return {"gross_interest": _r(gross), "tax": _r(gross * DEPOSIT_TAX), "net_interest": _r(gross * (1 - DEPOSIT_TAX))}


# ---------------------------------------------------------------- tools

def get_state(session_id: str) -> dict:
    session = _session(session_id)
    state = game_state(session).model_dump(mode="json")
    b = state["balance"]
    return {**state, "summary": f"Luna {state['month']}: numerar {E.money(b['cash'])}, economii {E.money(b['savings'])}, "
                                f"datorii {E.money(b['debt'])}, progres scop {state['goal']['progress']:.0%}."}


def get_goal_progress(session_id: str) -> dict:
    session = _session(session_id)
    sim, profile = session.sim, session.profile
    goal = adapter.goal(sim, profile, session.month)
    b = adapter.balance(sim)
    saved = b.savings + b.investments
    remaining = max(goal.target_amount - saved, 0.0)
    months_left = max(profile.goal.horizon_months - session.month, 0)
    needed = remaining / months_left if months_left else remaining
    contributing = float(sim["emergency_contrib"]) + float(sim["invest_contrib"])
    return {
        "goal_type": goal.type, "target_amount": goal.target_amount, "saved": _r(saved), "remaining": _r(remaining),
        "progress": goal.progress, "on_track": goal.on_track, "months_elapsed": session.month, "months_left": months_left,
        "monthly_needed": _r(needed), "monthly_contributions": _r(contributing),
        "summary": (f"Progres {goal.progress:.0%} ({E.money(saved)} din {E.money(goal.target_amount)}); "
                    + (f"mai sunt {months_left} luni, ai nevoie de ~{E.money(needed)}/lună" if months_left
                       else "termenul a trecut") + f"; pui deoparte automat {E.money(contributing)}/lună."),
    }


def simulate_decision(session_id: str, ops: dict, months: int = 12) -> dict:
    session = _session(session_id)
    engine_ops = _validated_ops(ops)
    before, after = _run(session, engine_ops, months)
    _, baseline = _run(session, None, months)
    delta, impact = _diff(after, before), _diff(after, baseline)
    return {
        "ops": engine_ops, "months": months, "before": before, "after": after, "baseline": baseline,
        "delta": delta, "impact_vs_no_change": impact,
        "summary": (f"În {months} luni: patrimoniu {E.signed_money(impact['net_worth'])} față de fără schimbare, "
                    f"datorii {E.signed_money(impact['debt'])}, progres scop {after['goal_progress']:.0%} "
                    f"(fără schimbare {baseline['goal_progress']:.0%})."),
    }


def compare_scenarios(session_id: str, scenarios: dict[str, dict], months: int = 12) -> dict:
    session = _session(session_id)
    validated = {name: _validated_ops(ops) for name, ops in scenarios.items()}
    _, baseline = _run(session, None, months)
    rows = [{"scenario": "fără schimbări", **baseline}]
    for name, ops in validated.items():
        rows.append({"scenario": name, **_run(session, ops, months)[1]})
    best = max(rows, key=lambda r: (r["goal_progress"], r["net_worth"]))
    return {"months": months, "scenarios": rows, "best": best["scenario"],
            "summary": f"{len(rows)} scenarii pe {months} luni; cel mai bun progres spre scop: „{best['scenario']}” "
                       f"({best['goal_progress']:.0%}, patrimoniu {E.money(best['net_worth'])})."}


def search_products(category: str | None = None, query: str | None = None) -> dict:
    if category is not None and category not in catalog.CATALOG_CATEGORIES:
        raise ToolError(f"Categorie necunoscută: {category}. Alege din {', '.join(catalog.CATALOG_CATEGORIES)}.")
    found = catalog.catalog_products(category)
    if query:
        words = _fold(query).split()
        found = [p for p in found if all(w in _fold(f"{p.name} {p.terms} {p.best_for}") for w in words)]
    return {"products": [p.model_dump(mode="json") for p in found],
            "summary": f"{len(found)} produse" + (f" ({category})" if category else "") + (f" pentru „{query}”" if query else "")
                       + (": " + ", ".join(p.name for p in found) if found else "")}


def compare_products(ids: list[str], amount: float, months: int) -> dict:
    rows = []
    for product_id in ids:
        product = catalog.get_product(product_id)
        if product is None:
            raise ToolError(f"Produs necunoscut: {product_id}.")
        rate = _rate(product)
        row: dict[str, Any] = {"id": product.id, "name": product.name, "category": product.category, "rate": rate}
        notes = []
        if rate is None:
            notes.append("catalogul nu dă o dobândă pentru acest produs")
        elif product.category in LOAN_CATEGORIES:
            row.update(kind="loan", **loan_cost(amount, rate, months))
            notes.append("dobândă „de la”; costul final îl stabilește banca")
            if "IRCC" in product.terms:
                notes.append("după perioada cu dobândă fixă, rata depinde de IRCC; calculul folosește dobânda inițială")
        elif product.category in SAVINGS_CATEGORIES:
            row.update(kind="deposit", **deposit_return(amount, rate, months))
            notes.append("dobândă brută, impozit 10%; dobândă simplă pe perioada cerută, depozitul poate avea alt termen (vezi terms)")
        else:
            notes.append("produsul nu e un credit sau un depozit; nu se calculează cost/dobândă")
        if rate is not None and (len(re.findall(r"\d+(?:,\d+)?\s*%", product.terms)) > 1):
            notes.append("catalogul are mai multe procente (tranșe/variante); calculul folosește primul")
        rows.append({**row, "notes": notes, "disclaimer": product.disclaimer})
    loans = [r for r in rows if r.get("kind") == "loan"]
    deposits = [r for r in rows if r.get("kind") == "deposit"]
    parts = [f"{r['name']}: {E.money(r['monthly_payment'])}/lună, dobândă totală {E.money(r['total_interest'])}" for r in loans]
    parts += [f"{r['name']}: dobândă netă {E.money(r['net_interest'])}" for r in deposits]
    return {"amount": amount, "months": months, "products": rows,
            "summary": f"{E.money(amount)} pe {months} luni. " + ("; ".join(parts) if parts else "Niciun produs comparabil.")}


def create_action_plan(session_id: str) -> dict:
    """3-5 concrete steps, by priority: overdraft/expensive debt -> emergency fund -> protection -> goal -> investing."""
    session = _session(session_id)
    sim, profile = session.sim, session.profile
    balance_left = E.monthly_surplus(sim)
    surplus = max(balance_left, 0.0)
    em_months = E.emergency_months(sim)
    goal = get_goal_progress(session_id)
    steps: list[dict] = []

    def step(title: str, why: str, action: dict | None = None, product_id: str | None = None) -> None:
        steps.append({"title": title, "why": why, "action": action, "product_id": product_id})

    if float(sim["overdraft"]) > 0.5:
        amount = _r(min(float(sim["cash"]), float(sim["overdraft"])))
        step("Acoperă descoperitul de cont", f"Descoperitul costă {E.pct(E.OVERDRAFT_APR)} pe an.",
             {"action_id": "repay", "params": {"amount": amount}} if amount > 0 else None, "overdraft")
    if balance_left < 0:
        step("Echilibrează bugetul lunar", f"Cheltuielile și ratele depășesc venitul cu {E.money(-balance_left)}/lună; "
             "diferența se ia din economii sau din descoperit.")
    expensive = [loan for loan in sim["loans"] if float(loan["apr"]) >= 0.15]
    if expensive:
        worst = max(expensive, key=lambda loan: loan["apr"])
        step(f"Scapă întâi de „{worst['name']}”", f"Are {E.pct(worst['apr'])} pe an; o refinanțare sau rambursare anticipată reduce costul.",
             {"action_id": "repay", "params": {"amount": _r(min(float(sim['cash']) * 0.5, worst['principal']))}}
             if float(sim["cash"]) > 100 else None, "refinantare")
    if em_months < 3:
        amount = _r(max(min(surplus * 0.5, E.emergency_target(sim) - float(sim["emergency"])), 100.0))
        step("Construiește fondul de urgență", f"Acoperă {em_months:.1f} luni de cheltuieli; ținta e 3-6 luni.".replace(".", ",", 1),
             {"action_id": "set_monthly_saving", "params": {"amount": amount}}, "super_acces_plus")
    if int(sim["insurance_level"]) == 0 and profile.dependents > 0:
        step("Ia în calcul o asigurare de viață", f"Ai {profile.dependents} persoane în întreținere.", None, "asigurare_viata")
    if not goal["on_track"] and goal["months_left"]:
        amount = _r(min(goal["monthly_needed"], surplus))
        step("Pune deoparte automat pentru scop", f"Ca să atingi {E.money(goal['target_amount'])} la timp ai nevoie de "
             f"~{E.money(goal['monthly_needed'])}/lună.", {"action_id": "set_monthly_saving", "params": {"amount": amount}},
             "depozit_1_an")
    if em_months >= 6 and profile.risk_tolerance != "scazuta" and profile.goal.horizon_months - session.month > 36:
        step("Investește pe termen lung", "Ai fondul de urgență complet și un orizont de peste 3 ani.",
             {"action_id": "set_monthly_invest", "params": {"amount": _r(surplus * 0.3)}}, "fonduri_smartinvest")
    for title, why, product_id in (
        ("Verifică bugetul lunar", f"Îți rămân ~{E.money(surplus)}/lună după cheltuieli și rate.", None) if balance_left >= 0
        else ("Caută un venit suplimentar", "Un proiect pe PFA sau ore suplimentare acoperă deficitul mai repede decât tăierile.", None),
        ("Compară produsele de economisire", "Depozitele au dobânzi mai mari decât contul curent, dar banii sunt blocați pe termen.", "depozit_1_an"),
        ("Gândește-te la pensie", "Pilonul III are deducere fiscală și contribuția angajatorului, dacă există.", "pilon3"),
    ):
        if len(steps) >= 3:
            break
        step(title, why, None, product_id)
    steps = steps[:5]
    return {"steps": steps, "summary": f"{len(steps)} pași: " + "; ".join(s["title"] for s in steps)}


# ---------------------------------------------------------------- schemas + dispatcher

class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoArgs(_Args):
    pass


class SimulateArgs(_Args):
    ops: dict[str, Any] = Field(description=OPS_HELP)
    months: int = Field(12, ge=1, le=MAX_MONTHS, description="orizontul simulării, în luni")


class CompareScenariosArgs(_Args):
    scenarios: dict[str, dict[str, Any]] = Field(min_length=1, max_length=5,
                                                 description="nume scenariu -> ops. " + OPS_HELP)
    months: int = Field(12, ge=1, le=MAX_MONTHS, description="orizontul simulării, în luni")


class SearchProductsArgs(_Args):
    category: str | None = Field(None, description="una din: " + ", ".join(catalog.CATALOG_CATEGORIES))
    query: str | None = Field(None, description="cuvinte căutate în nume, condiții și „potrivit pentru”")


class CompareProductsArgs(_Args):
    ids: list[str] = Field(min_length=1, max_length=6, description="id-uri de produse din catalog")
    amount: float = Field(gt=0, description="suma creditului sau a depozitului, în lei")
    months: int = Field(gt=0, le=360, description="perioada, în luni")


# name -> (function, argument model, needs a session, description for the LLM)
TOOLS: dict[str, tuple[Callable[..., dict], type[_Args], bool, str]] = {
    "get_state": (get_state, NoArgs, True,
                  "Starea curentă din joc: solduri, venituri și cheltuieli lunare, scop, produse deținute, evenimente în așteptare."),
    "get_goal_progress": (get_goal_progress, NoArgs, True,
                          "Progresul spre scop: cât e strâns, dacă e pe drumul cel bun, câte luni au rămas și câți lei pe lună ar trebui puși deoparte."),
    "simulate_decision": (simulate_decision, SimulateArgs, True,
                          "Simulează o decizie (ops) pe N luni, pe o copie a stării, fără să schimbe jocul. Întoarce situația înainte/după și diferența față de a nu face nimic."),
    "compare_scenarios": (compare_scenarios, CompareScenariosArgs, True,
                          "Compară side-by-side mai multe scenarii (fiecare cu ops) față de „fără schimbări”, pe același orizont."),
    "search_products": (search_products, SearchProductsArgs, False,
                        "Caută în catalogul de produse Raiffeisen, după categorie și/sau cuvinte."),
    "compare_products": (compare_products, CompareProductsArgs, False,
                         "Compară produse din catalog pentru o sumă și o perioadă: la credite rata lunară, costul total și dobânda; la depozite dobânda netă după impozitul de 10%."),
    "create_action_plan": (create_action_plan, NoArgs, True,
                           "Plan de 3-5 pași concreți, pe baza stării, a scopului și a catalogului (reguli fixe, nu LLM)."),
}

TOOL_SCHEMAS: list[dict] = [
    {"name": name, "description": description, "input_schema": args_model.model_json_schema()}
    for name, (_fn, args_model, _needs_session, description) in TOOLS.items()
]


def _dispatch(name: str, args: dict, session_id: str) -> dict:
    if name not in TOOLS:
        raise ToolError(f"Unealtă necunoscută: {name}.")
    fn, args_model, needs_session, _ = TOOLS[name]
    try:
        kwargs = args_model.model_validate(args).model_dump(exclude_none=True)
    except ValidationError as exc:
        err = exc.errors()[0]
        raise ToolError(f"Argumente invalide pentru {name}: {err['msg']} ({'.'.join(map(str, err['loc'])) or 'args'})") from exc
    return fn(session_id, **kwargs) if needs_session else fn(**kwargs)


def run_tool(name: str, args: dict | None, session_id: str) -> dict:
    """Validates the arguments, runs the tool and logs the call in the session. Raises ToolError on bad input."""
    started = time.perf_counter()
    summary, status = "", "error"
    try:
        result = _dispatch(name, args or {}, session_id)
        summary, status = result.get("summary", ""), "ok"
        return result
    except ToolError as exc:
        summary = f"eroare: {exc}"
        raise
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        log.info("tool %s %s in %.1f ms", name, status, duration_ms)  # no args/results: they may hold personal data
        session = find_session(session_id) if session_id else None
        if session is not None:
            session.tool_log.append({"name": name, "args": args or {}, "summary": summary, "duration_ms": duration_ms})


def llm_tools(session_id: str) -> list:
    """TOOL_SCHEMAS bound to a session as app/agents/llm.py Tool objects, ready for chat_turn()/stream_agent()."""
    from .agents.llm import Tool

    def handler(name: str):
        return lambda **args: run_tool(name, args, session_id)

    return [Tool(s["name"], s["description"], s["input_schema"], handler(s["name"])) for s in TOOL_SCHEMAS]
