"""Maps between the §4 API contracts (app/schemas.py) and the engine state (app/sim/engine.py).

Pure functions, no I/O, no FastAPI. The engine dict is the source of truth; GameState is rebuilt from it.
Mapping:
  savings     = emergency + deposit      investments = fund
  debt        = engine.total_debt        net_worth   = engine.net_worth (includes car/home/business)
  goal.progress = (savings + investments) / target, clamped 0..1
"""
import random
from typing import Any

from ..schemas import (
    INSTITUTIONS,
    Balance,
    Event,
    GameState,
    GoalProgress,
    InstitutionStatus,
    LogEntry,
    Monthly,
    MonthlyExpenses,
    ProductHolding,
    Profile,
    Wellbeing,
)
from . import engine as E

MONTHS_PER_YEAR = 12
DELTA_KEYS = ("cash", "savings", "investments", "debt", "net_worth")


def _r2(x: float) -> float:
    return round(x, 2)


# ---------------------------------------------------------------- profile -> engine

def _base_categories(profile: Profile) -> dict[str, float]:
    """Profile spending grouped by institution; their sum is the engine's `living`."""
    if profile.categories:
        # Statement lines already include transport, food, leisure and subscriptions.
        # Rent, utilities, tuition and medical costs stay beside them.
        base = {
            "home": profile.recurring.rent + profile.recurring.utilities,
            "market": 0.0,
            "education": profile.education.tuition_monthly,
            "health": profile.health.monthly_costs,
        }
        for cat in profile.categories:
            bucket = cat.institution if cat.institution in ("home", "market", "education") else "market"
            base[bucket] += cat.monthly
        return base
    r, s = profile.recurring, profile.spending
    return {
        "home": r.rent + r.utilities + r.subscriptions,
        "market": s.food + s.leisure + r.transport,
        "education": profile.education.tuition_monthly,
        "health": profile.health.monthly_costs,
    }


def profile_to_state(profile: Profile, seed: str) -> tuple[E.SimState, random.Random]:
    """Builds the engine state from a §4.1 profile. The returned rng is the session's only randomness source."""
    rng = random.Random(seed)
    sim = E.new_state(rng, {
        "name": profile.name or "Jucător",
        "salary": profile.income.salary,
        "living": sum(_base_categories(profile).values()),
        "cash": profile.cash,
        "emergency": profile.savings,
    })
    sim["age"] = profile.age
    # The engine has one extra-income field: other income plus the scholarship.
    sim["side_income"] = float(profile.income.other) + float(profile.education.scholarship)
    sim["fund"] = float(profile.investments)
    for debt in profile.debts:
        months = E.months_left_for(debt.remaining, debt.apr, debt.monthly)
        if debt.remaining <= 0.5 or months <= 0:
            continue
        E.add_loan(sim, debt.name, debt.remaining, debt.apr, months)
        # Keep the real bank payment from the statement instead of the recomputed annuity.
        sim["loans"][-1]["payment"] = float(debt.monthly)
    sim["history"] = [E.snapshot(sim)]
    return sim, rng


# ---------------------------------------------------------------- monthly turn

def new_year_report(sim: E.SimState) -> dict[str, Any]:
    """Accumulator that _month fills during a year; closed by advance_month every 12 months."""
    return {"interest_paid": 0.0, "overdraft_months": 0, "austerity_months": 0, "invest_gain": 0.0,
            "start": E.snapshot(sim)}


def advance_month(sim: E.SimState, month: int, year_rep: dict[str, Any]) -> dict[str, float]:
    """Runs one month. `month` = months already elapsed. Mutates `sim` and `year_rep`.

    Every 12 months applies the same yearly updates as engine.simulate_period (salary growth,
    inflation, car depreciation), age +1 and wellbeing; then restarts `year_rep`.
    """
    shock = sim["shocks"][min(month // E.MONTHS_PER_PERIOD, E.PERIODS - 1)]
    inc = E.income(sim)
    out = float(sim["living"]) + float(sim["insurance_premium"]) + E.debt_payments(sim)
    E._month(sim, shock, year_rep)
    month += 1
    if month % MONTHS_PER_YEAR == 0:
        sim["salary"] = float(sim["salary"]) * (1.0 + E.SALARY_GROWTH)
        sim["living"] = float(sim["living"]) * (1.0 + E.LIVING_INFLATION)
        sim["side_income"] = float(sim["side_income"]) * 1.03
        sim["car_value"] = float(sim["car_value"]) * (1.0 - E.CAR_DEPRECIATION)
        sim["age"] = int(sim["age"]) + 1
        sim["interest_paid_total"] = float(sim["interest_paid_total"]) + float(year_rep["interest_paid"])
        E._update_wellbeing(sim, year_rep)
        sim["history"].append(E.snapshot(sim))
        year_rep.clear()
        year_rep.update(new_year_report(sim))
    sim["period"] = month // E.MONTHS_PER_PERIOD
    return {"month": month, "income": inc, "expenses": out, "cash": float(sim["cash"])}


# ---------------------------------------------------------------- engine -> GameState

def expenses(sim: E.SimState, profile: Profile) -> MonthlyExpenses:
    """The single mapping of engine outflows onto §4.2 expense keys.

    `living` is split across home/market/education/health by the profile's starting proportions, so the
    keys always sum to living + insurance_premium + debt_payments (what _month subtracts).
    health = its share of living (profile health.monthly_costs) + the insurance premium.
    """
    base = _base_categories(profile)
    total = sum(base.values())
    shares = ({k: v / total for k, v in base.items()} if total > 0
              else {"home": 0.0, "market": 1.0, "education": 0.0, "health": 0.0})
    living = float(sim["living"])
    return MonthlyExpenses(
        home=_r2(living * shares["home"]),
        market=_r2(living * shares["market"]),
        education=_r2(living * shares["education"]),
        health=_r2(living * shares["health"] + float(sim["insurance_premium"])),
        business=0.0,  # TODO(real): business running costs once the engine models them.
        bank=_r2(E.debt_payments(sim)),
    )


def balance(sim: E.SimState) -> Balance:
    return Balance(
        cash=_r2(float(sim["cash"])),
        savings=_r2(float(sim["emergency"]) + float(sim["deposit"])),
        investments=_r2(float(sim["fund"])),
        debt=_r2(E.total_debt(sim)),
        net_worth=_r2(E.net_worth(sim)),
    )


def delta(before: Balance, after: Balance) -> dict[str, float]:
    return {k: _r2(getattr(after, k) - getattr(before, k)) for k in DELTA_KEYS}


def goal(sim: E.SimState, profile: Profile, month: int) -> GoalProgress:
    b = balance(sim)
    target = profile.goal.target_amount
    progress = min(1.0, max(0.0, (b.savings + b.investments) / target)) if target > 0 else 1.0
    return GoalProgress(
        type=profile.goal.type,
        target_amount=target,
        progress=round(progress, 3),
        on_track=progress >= month / max(1, profile.goal.horizon_months),
    )


# Engine balance -> the catalog product (data/products.json) it represents in GameState.products.
HOLDING_PRODUCTS = {"emergency": "super_acces_plus", "deposit": "depozit_1_an", "fund": "fonduri_smartinvest"}


def products(sim: E.SimState) -> list[ProductHolding]:
    return [ProductHolding(id=pid, balance=_r2(float(sim[key])))
            for key, pid in HOLDING_PRODUCTS.items() if float(sim[key]) > 0.5]


def to_game_state(session_id: str, sim: E.SimState, profile: Profile, month: int,
                  pending_events: list[Event], log: list[LogEntry]) -> GameState:
    return GameState(
        session_id=session_id,
        month=month,
        age=int(sim["age"]),
        goal=goal(sim, profile, month),
        balance=balance(sim),
        monthly=Monthly(income=_r2(E.income(sim)), expenses=expenses(sim, profile)),
        wellbeing=Wellbeing(stress=_r2(float(sim["stress"])), confidence=_r2(float(sim["confidence"]))),
        institutions=[InstitutionStatus(id=i, pending_events=sum(1 for e in pending_events if e.institution == i))
                      for i in INSTITUTIONS],
        products=products(sim),
        log=list(log),
        categories=list(profile.categories),
    )
