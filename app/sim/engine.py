"""Financial engine of Raiff Quest: a 1:1 port of raiffquest/scripts/raiff/finance_sim.gd.

Pure functions, no I/O. State is a plain dict with exactly the same keys as the .gd version,
so it maps 1:1 to the Godot data and is JSON-serializable. Amounts are in lei (RON).
One period = 36 months (3 years). Randomness only comes from the injected `random.Random`.
"""
import copy
import math
import random
from typing import Any, TypedDict

MONTHS_PER_PERIOD = 36
PERIODS = 10
START_AGE = 22
OVERDRAFT_APR = 0.30
OVERDRAFT_LIMIT = 15000.0
EMERGENCY_APR = 0.03
DEPOSIT_APR = 0.045
FUND_APR = 0.07
SALARY_GROWTH = 0.04
LIVING_INFLATION = 0.04
LIFESTYLE_CREEP = 0.6
CAR_DEPRECIATION = 0.12
INSURANCE_COVERAGE = [0.0, 0.35, 0.85]


class Loan(TypedDict):
    name: str
    principal: float
    apr: float
    months_left: int
    payment: float
    original: float


class SimState(TypedDict):
    name: str
    age: int
    period: int
    salary: float
    side_income: float
    living: float
    cash: float
    emergency: float
    deposit: float
    fund: float
    overdraft: float
    loans: list[Loan]
    emergency_contrib: float
    invest_contrib: float
    insurance_level: int
    insurance_premium: float
    car_value: float
    business_value: float
    home_value: float
    stress: float
    confidence: float
    shocks: list[float]
    history: list[dict[str, Any]]
    decisions: list[Any]
    interest_paid_total: float
    from_statement: bool


# ---------------------------------------------------------------- GDScript built-ins

def round_half_away(x: float) -> float:
    """GDScript round(): halves go away from zero (Python's round() goes to even)."""
    return math.copysign(math.floor(abs(x) + 0.5), x)


def snapped(x: float, step: float) -> float:
    """GDScript snappedf()."""
    return math.floor(x / step + 0.5) * step


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# ---------------------------------------------------------------- state

def new_state(rng: random.Random, profile: dict[str, Any] | None = None) -> SimState:
    """`profile` (optional): the player's real situation, computed from the bank statement."""
    shocks = [snapped(rng.uniform(-0.06, 0.04), 0.005) for _ in range(PERIODS)]
    s: SimState = {
        "name": "Ana Ionescu",
        "age": START_AGE,
        "period": 0,
        "salary": 4300.0,
        "side_income": 0.0,
        "living": 3900.0,
        "cash": 4000.0,
        "emergency": 1200.0,
        "deposit": 0.0,
        "fund": 0.0,
        "overdraft": 0.0,
        "loans": [],
        "emergency_contrib": 0.0,
        "invest_contrib": 0.0,
        "insurance_level": 0,
        "insurance_premium": 0.0,
        "car_value": 0.0,
        "business_value": 0.0,
        "home_value": 0.0,
        "stress": 35.0,
        "confidence": 45.0,
        "shocks": shocks,
        "history": [],
        "decisions": [],
        "interest_paid_total": 0.0,
        "from_statement": False,
    }
    if profile:
        apply_profile(s, profile)
    s["history"].append(snapshot(s))
    return s


def apply_profile(s: SimState, p: dict[str, Any]) -> None:
    if p.get("name") is not None:
        s["name"] = str(p["name"])
    for key in ("salary", "living", "cash", "emergency", "home_value", "stress", "confidence"):
        if p.get(key) is not None:
            s[key] = max(float(p[key]), 0.0)
    s["overdraft"] = _clamp(float(p.get("overdraft", 0.0)), 0.0, OVERDRAFT_LIMIT)
    for loan in p.get("loans", []):
        if float(loan.get("principal", 0.0)) > 0.5 and int(loan.get("months", 0)) > 0:
            add_loan(s, str(loan.get("name", "Credit existent")), float(loan["principal"]),
                     float(loan.get("apr", 0.1)), int(loan["months"]))
    s["from_statement"] = True


def clone(s: SimState) -> SimState:
    return copy.deepcopy(s)


# ---------------------------------------------------------------- formatting

def money(x: float) -> str:
    digits = str(int(round_half_away(abs(x))))
    groups = []
    while len(digits) > 3:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    groups.insert(0, digits)
    sign = "-" if x < -0.5 else ""
    return f"{sign}{'.'.join(groups)} lei"


def signed_money(x: float) -> str:
    if abs(x) < 0.5:
        return "0 lei"
    return ("+" if x > 0.0 else "") + money(x)


def pct(x: float) -> str:
    return f"{x * 100.0:.1f}".replace(".", ",") + "%"


# ---------------------------------------------------------------- derived values

def pmt(principal: float, apr: float, months: int) -> float:
    """Annuity payment."""
    if months <= 0:
        return principal
    if apr <= 0.00001:
        return principal / float(months)
    r = apr / 12.0
    return principal * r / (1.0 - (1.0 + r) ** -float(months))


def months_left_for(principal: float, apr: float, payment: float) -> int:
    if principal <= 0.5:
        return 0
    if apr <= 0.00001:
        return int(math.ceil(principal / max(payment, 1.0)))
    r = apr / 12.0
    if payment <= principal * r:
        return 999
    return int(math.ceil(-math.log(1.0 - principal * r / payment) / math.log(1.0 + r)))


def income(s: SimState) -> float:
    return float(s["salary"]) + float(s["side_income"])


def debt_payments(s: SimState) -> float:
    total = 0.0
    for loan in s["loans"]:
        if int(loan["months_left"]) > 0:
            total += min(float(loan["payment"]), float(loan["principal"]) * (1.0 + float(loan["apr"]) / 12.0))
    return total


def total_debt(s: SimState) -> float:
    return float(s["overdraft"]) + sum(float(loan["principal"]) for loan in s["loans"])


def investments(s: SimState) -> float:
    return float(s["deposit"]) + float(s["fund"])


def net_worth(s: SimState) -> float:
    return (float(s["cash"]) + float(s["emergency"]) + investments(s) + float(s["car_value"])
            + float(s["business_value"]) + float(s.get("home_value", 0.0)) - total_debt(s))


def emergency_target(s: SimState) -> float:
    return float(s["living"]) * 6.0


def emergency_months(s: SimState) -> float:
    return float(s["emergency"]) / max(float(s["living"]), 1.0)


def dsr(s: SimState) -> float:
    return debt_payments(s) / max(income(s), 1.0)


def monthly_surplus(s: SimState) -> float:
    return income(s) - float(s["living"]) - debt_payments(s) - float(s["insurance_premium"])


def snapshot(s: SimState) -> dict[str, Any]:
    return {
        "age": int(s["age"]),
        "net_worth": net_worth(s),
        "cash": float(s["cash"]),
        "emergency": float(s["emergency"]),
        "investments": investments(s),
        "debt": total_debt(s),
        "stress": float(s["stress"]),
        "confidence": float(s["confidence"]),
    }


# ---------------------------------------------------------------- operations

def spend(s: SimState, amount: float) -> None:
    """Pays an amount: cash, then emergency fund, then deposit; the rest goes into overdraft."""
    rest = amount
    for key in ("cash", "emergency", "deposit"):
        take = min(float(s[key]), rest)
        s[key] = float(s[key]) - take
        rest -= take
    if rest > 0.0:
        s["overdraft"] = float(s["overdraft"]) + rest


def add_loan(s: SimState, name: str, principal: float, apr: float, months: int) -> None:
    s["loans"].append({
        "name": name,
        "principal": principal,
        "apr": apr,
        "months_left": months,
        "payment": pmt(principal, apr, months),
        "original": principal,
    })


def prepay(s: SimState, amount: float) -> float:
    """Early repayment: overdraft first, then highest-APR loans. Payment stays, term shrinks. Returns the leftover."""
    rest = amount
    od = min(float(s["overdraft"]), rest)
    s["overdraft"] = float(s["overdraft"]) - od
    rest -= od
    for loan in sorted(s["loans"], key=lambda loan: float(loan["apr"]), reverse=True):
        if rest <= 0.0:
            break
        pay = min(float(loan["principal"]), rest)
        loan["principal"] = float(loan["principal"]) - pay
        rest -= pay
        loan["months_left"] = months_left_for(float(loan["principal"]), float(loan["apr"]), float(loan["payment"]))
    _remove_paid_loans(s)
    return rest


def fill_safe(s: SimState, amount: float) -> None:
    room = max(emergency_target(s) - float(s["emergency"]), 0.0)
    to_em = min(room, amount)
    s["emergency"] = float(s["emergency"]) + to_em
    s["deposit"] = float(s["deposit"]) + (amount - to_em)


def _remove_paid_loans(s: SimState) -> None:
    s["loans"] = [loan for loan in s["loans"] if float(loan["principal"]) > 0.5 and int(loan["months_left"]) > 0]


def apply_ops(s: SimState, ops: dict[str, Any], notes: list[str]) -> dict[str, float]:
    """Applies an option's immediate effects. Returns the mood change (stress/confidence); appends to `notes`."""
    if "spend" in ops:
        spend(s, float(ops["spend"]))
    if "loan" in ops:
        loan = ops["loan"]
        # .gd reads loan.name unconditionally; §4.4's example omits it, so default instead of crashing.
        add_loan(s, str(loan.get("name", "Credit")), float(loan["principal"]), float(loan["apr"]), int(loan["months"]))
    if "salary_mult" in ops:
        raise_amount = float(s["salary"]) * (float(ops["salary_mult"]) - 1.0)
        s["salary"] = float(s["salary"]) + raise_amount
        s["living"] = float(s["living"]) + raise_amount * LIFESTYLE_CREEP
    if "salary_add" in ops:
        s["salary"] = float(s["salary"]) + float(ops["salary_add"])
        s["living"] = float(s["living"]) + float(ops["salary_add"]) * LIFESTYLE_CREEP
    if "living_add" in ops:
        s["living"] = float(s["living"]) + float(ops["living_add"])
    if "side_income_add" in ops:
        s["side_income"] = float(s["side_income"]) + float(ops["side_income_add"])
        s["living"] = float(s["living"]) + float(ops["side_income_add"]) * 0.3
    if "business_value" in ops:
        s["business_value"] = float(s["business_value"]) + float(ops["business_value"])
    if "car_value" in ops:
        s["car_value"] = float(s["car_value"]) + float(ops["car_value"])
    if "emergency_contrib" in ops:
        s["emergency_contrib"] = float(ops["emergency_contrib"])
    if "invest_contrib" in ops:
        s["invest_contrib"] = float(ops["invest_contrib"])
    if "insurance_level" in ops:
        s["insurance_level"] = int(ops["insurance_level"])
        s["insurance_premium"] = float(ops.get("insurance_premium", 0.0))
    if "medical_cost" in ops:
        coverage = INSURANCE_COVERAGE[int(_clamp(int(s["insurance_level"]), 0, 2))]
        gross = float(ops["medical_cost"])
        net = gross * (1.0 - coverage)
        notes.append(f"Asigurarea a acoperit {money(gross - net)} din {money(gross)}.")
        fin = int(ops.get("finance_months", 0))
        if fin > 0:
            add_loan(s, "Plată în rate clinică", net, 0.0, fin)
        else:
            spend(s, net)
    if "bonus" in ops:
        b = ops["bonus"]
        amount = float(b["amount"])
        mode = str(b["mode"])
        if mode == "prepay":
            left = prepay(s, amount)
            if left > 0.0:
                fill_safe(s, left)
                notes.append(f"După rambursare au rămas {money(left)}, mutați în fondul de urgență/depozit.")
        elif mode == "fund":
            s["fund"] = float(s["fund"]) + amount
        elif mode == "safe":
            fill_safe(s, amount)
        elif mode == "spend":
            fill_safe(s, amount - float(b["spend"]))
    mood = ops.get("mood", {})
    return {"stress": float(mood.get("stress", 0.0)), "confidence": float(mood.get("conf", 0.0))}


# ---------------------------------------------------------------- simulation

def simulate_period(s: SimState, shock: float) -> dict[str, Any]:
    rep: dict[str, Any] = {
        "interest_paid": 0.0,
        "overdraft_months": 0,
        "austerity_months": 0,
        "invest_gain": 0.0,
        "loans_closed": 0,
        "start": snapshot(s),
        "shock": shock,
    }
    loans_before = len(s["loans"])
    for m in range(MONTHS_PER_PERIOD):
        _month(s, shock, rep)
        if (m + 1) % 12 == 0:
            s["salary"] = float(s["salary"]) * (1.0 + SALARY_GROWTH)
            s["living"] = float(s["living"]) * (1.0 + LIVING_INFLATION)
            s["side_income"] = float(s["side_income"]) * 1.03
            s["car_value"] = float(s["car_value"]) * (1.0 - CAR_DEPRECIATION)
    rep["loans_closed"] = max(loans_before - len(s["loans"]), 0)
    s["age"] = int(s["age"]) + 3
    s["period"] = int(s["period"]) + 1
    s["interest_paid_total"] = float(s["interest_paid_total"]) + float(rep["interest_paid"])
    _update_wellbeing(s, rep)
    return rep


def _month(s: SimState, shock: float, rep: dict[str, Any]) -> None:
    inc = income(s)
    paid = 0.0
    for loan in s["loans"]:
        if int(loan["months_left"]) <= 0:
            continue
        interest = float(loan["principal"]) * float(loan["apr"]) / 12.0
        pay = min(float(loan["payment"]), float(loan["principal"]) + interest)
        if int(loan["months_left"]) == 1:
            pay = float(loan["principal"]) + interest
        loan["principal"] = float(loan["principal"]) + interest - pay
        loan["months_left"] = int(loan["months_left"]) - 1
        rep["interest_paid"] = float(rep["interest_paid"]) + interest
        paid += pay
        if int(loan["months_left"]) <= 0:
            loan["principal"] = 0.0
    _remove_paid_loans(s)
    if float(s["overdraft"]) > 0.0:
        od_interest = float(s["overdraft"]) * OVERDRAFT_APR / 12.0
        s["overdraft"] = float(s["overdraft"]) + od_interest
        rep["interest_paid"] = float(rep["interest_paid"]) + od_interest
    s["cash"] = float(s["cash"]) + inc - float(s["living"]) - paid - float(s["insurance_premium"])
    # Automatic contributions (only from available cash)
    if float(s["emergency_contrib"]) > 0.0 and float(s["emergency"]) < emergency_target(s):
        ec = min(float(s["emergency_contrib"]), emergency_target(s) - float(s["emergency"]), max(float(s["cash"]), 0.0))
        s["emergency"] = float(s["emergency"]) + ec
        s["cash"] = float(s["cash"]) - ec
    if float(s["invest_contrib"]) > 0.0:
        ic = min(float(s["invest_contrib"]), max(float(s["cash"]), 0.0))
        s["fund"] = float(s["fund"]) + ic
        s["cash"] = float(s["cash"]) - ic
    if float(s["cash"]) < 0.0:
        deficit = -float(s["cash"])
        s["cash"] = 0.0
        for key in ("emergency", "deposit"):
            take = min(float(s[key]), deficit)
            s[key] = float(s[key]) - take
            deficit -= take
        s["overdraft"] = float(s["overdraft"]) + deficit
    elif float(s["overdraft"]) > 0.0 and float(s["cash"]) > 0.0:
        repay = min(float(s["cash"]), float(s["overdraft"]))
        s["cash"] = float(s["cash"]) - repay
        s["overdraft"] = float(s["overdraft"]) - repay
    if float(s["overdraft"]) > 0.5:
        rep["overdraft_months"] = int(rep["overdraft_months"]) + 1
    if float(s["overdraft"]) > OVERDRAFT_LIMIT:
        # The bank stops extending the overdraft: spending is cut by force (austerity).
        s["overdraft"] = OVERDRAFT_LIMIT
        rep["austerity_months"] = int(rep["austerity_months"]) + 1
    s["emergency"] = float(s["emergency"]) * (1.0 + EMERGENCY_APR / 12.0)
    s["deposit"] = float(s["deposit"]) * (1.0 + DEPOSIT_APR / 12.0)
    gain = float(s["fund"]) * (FUND_APR + shock) / 12.0
    s["fund"] = float(s["fund"]) + gain
    rep["invest_gain"] = float(rep["invest_gain"]) + gain


def _update_wellbeing(s: SimState, rep: dict[str, Any]) -> None:
    em = emergency_months(s)
    ratio = dsr(s)
    stress_target = 30.0
    if em < 1.0:
        stress_target += 28.0
    elif em < 3.0:
        stress_target += 14.0
    elif em >= 6.0:
        stress_target -= 8.0
    if ratio > 0.4:
        stress_target += 18.0
    elif ratio > 0.3:
        stress_target += 10.0
    elif ratio > 0.2:
        stress_target += 4.0
    if float(s["overdraft"]) > 0.5:
        stress_target += 14.0
    if int(rep["austerity_months"]) > 0:
        stress_target += 14.0
    conf_target = 40.0
    if em >= 3.0:
        conf_target += 12.0
    if em >= 6.0:
        conf_target += 8.0
    if net_worth(s) > float(rep["start"]["net_worth"]):
        conf_target += 8.0
    if investments(s) > income(s) * 6.0:
        conf_target += 8.0
    if float(s["overdraft"]) > 0.5:
        conf_target -= 15.0
    if int(rep["austerity_months"]) > 0:
        conf_target -= 12.0
    if ratio > 0.35:
        conf_target -= 10.0
    s["stress"] = _clamp(0.4 * float(s["stress"]) + 0.6 * stress_target, 0.0, 100.0)
    s["confidence"] = _clamp(0.4 * float(s["confidence"]) + 0.6 * conf_target, 0.0, 100.0)


def resolve(s: SimState, option: dict[str, Any], shock: float) -> dict[str, Any]:
    """Applies the option, runs 36 months, then applies the decision's mood effect.

    `s` is mutated; for "what if" scenarios pass a clone().
    """
    notes: list[str] = []
    before = snapshot(s)
    mood = apply_ops(s, option.get("ops", {}), notes)
    after_ops = snapshot(s)
    rep = simulate_period(s, shock)
    s["stress"] = _clamp(float(s["stress"]) + float(mood["stress"]), 0.0, 100.0)
    s["confidence"] = _clamp(float(s["confidence"]) + float(mood["confidence"]), 0.0, 100.0)
    rep["notes"] = notes
    rep["before"] = before
    rep["after_ops"] = after_ops
    rep["after"] = snapshot(s)
    rep["net_worth"] = net_worth(s)
    rep["monthly_payments"] = debt_payments(s)
    rep["emergency_months"] = emergency_months(s)
    rep["overdraft"] = float(s["overdraft"])
    rep["value"] = decision_value(rep)
    return rep


def decision_value(rep: dict[str, Any]) -> float:
    """Score used to compare options: net worth adjusted by stress and confidence."""
    after = rep["after"]
    return float(after["net_worth"]) - 120.0 * float(after["stress"]) + 60.0 * float(after["confidence"])


# ---------------------------------------------------------------- final score

def resilience_score(s: SimState) -> int:
    score = 0.0
    score += _clamp(emergency_months(s) / 6.0, 0.0, 1.0) * 30.0
    score += (1.0 - _clamp(dsr(s) / 0.4, 0.0, 1.0)) * 20.0
    score += _clamp(net_worth(s) / (income(s) * 12.0 * 3.0), 0.0, 1.0) * 30.0
    score += (1.0 - float(s["stress"]) / 100.0) * 10.0
    score += float(s["confidence"]) / 100.0 * 10.0
    if float(s["overdraft"]) > 0.5:
        score -= 10.0
    return int(_clamp(round_half_away(score), 0.0, 100.0))


def archetype(score: int) -> str:
    if score >= 80:
        return "Arhitectul stabilității"
    if score >= 60:
        return "Constructor prudent"
    if score >= 40:
        return "Echilibrist în progres"
    return "Supraviețuitor de la lună la lună"


def retirement_projection(s: SimState) -> float:
    """Estimated capital at 67 (15 years after the end), 6%/year average. An estimate, not a promise."""
    years = 67 - int(s["age"])
    r = 0.06
    base = investments(s) + float(s["emergency"]) * 0.5
    fv = base * (1.0 + r) ** years
    fv += float(s["invest_contrib"]) * 12.0 * (((1.0 + r) ** years - 1.0) / r)
    return fv
