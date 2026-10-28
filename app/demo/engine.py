"""Demo game engine: one turn = one month across the 7 institutions.
This is the single source of truth for money; agents only read it or run projections on copies."""
import copy
import random
from datetime import date

SAVINGS_APR = 0.04
INVEST_APR = 0.06
INVEST_VOLATILITY = 0.08
OVERDRAFT_APR = 0.22
OVERDRAFT_NAME = "Descoperit de cont"
INSURANCE_COVERAGE = 0.7
EVENT_CHANCE = 0.75
MAX_PROJECTION_MONTHS = 360

INSTITUTIONS = [
    {"id": "home", "name": "Acasă", "icon": "🏠", "desc": "Facturi, abonamente, costuri recurente"},
    {"id": "market", "name": "Piață", "icon": "🛒", "desc": "Mâncare, ieșiri, transport, vacanțe, neprevăzute"},
    {"id": "education", "name": "Educație", "icon": "🎓", "desc": "Școală, facultate, cursuri, burse"},
    {"id": "work", "name": "Loc de muncă", "icon": "💼", "desc": "Venitul curent și avansarea în carieră"},
    {"id": "business", "name": "Afacere", "icon": "🏢", "desc": "Deschidere firmă, contabil AI, taxe"},
    {"id": "hospital", "name": "Spital", "icon": "🏥", "desc": "Sănătate, asigurări, urgențe medicale"},
    {"id": "bank", "name": "Bancă", "icon": "🏦", "desc": "Conturi, economii, investiții, credite"},
]
INSTITUTION_IDS = [i["id"] for i in INSTITUTIONS]
MONTHS_RO = ["Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie", "Iulie", "August", "Septembrie",
             "Octombrie", "Noiembrie", "Decembrie"]
LATE_DAYS = 30
LATE_DAY_RATE = 0.0003       # dobândă 0,02%/zi + penalitate 0,01%/zi (Codul de procedură fiscală art. 174, 176)
LATE_FINE = {"pfa": 50.0, "srl": 500.0}  # minimul amenzii pentru nedepunere (CPF art. 336)


class GameError(Exception):
    pass


def money(x: float) -> str:
    sign = "-" if x < -0.5 else ""
    return f"{sign}{abs(x):,.0f}".replace(",", ".") + " lei"


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _get(data: dict, path: str):
    node = data
    for key in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _item(item_id: str, label: str, amount: float) -> dict:
    return {"id": item_id, "label": label, "amount": round(float(amount), 2)}


# ---------------------------------------------------------------- setup

def new_game(profile: dict, seed: int) -> dict:
    def g(path, default=0.0):
        return _num(_get(profile, path), default)

    items = {inst: [] for inst in INSTITUTION_IDS}
    if g("income.salary"):
        items["work"].append(_item("salary", "Salariu net", g("income.salary")))
    if g("income.other"):
        items["work"].append(_item("other_income", "Alte venituri", g("income.other")))
    if g("income.scholarship"):
        items["education"].append(_item("scholarship", "Bursă", g("income.scholarship")))
    if g("education.tuition_monthly"):
        items["education"].append(_item("tuition", "Taxă de școlarizare", -g("education.tuition_monthly")))
    categories = [c for c in (_get(profile, "categories") or []) if isinstance(c, dict)]
    if categories:
        for cat in categories:
            monthly = _num(cat.get("monthly"))
            if monthly <= 0:
                continue
            inst = cat.get("institution") if cat.get("institution") in INSTITUTION_IDS else "market"
            items[inst].append(_item(str(cat["id"]), f"{cat['label']} · medie/lună", -monthly))
    else:
        for key, label in (("housing", "Chirie / rată locuință"), ("utilities", "Utilități"), ("subscriptions", "Abonamente")):
            if g(f"home.{key}"):
                items["home"].append(_item(key, label, -g(f"home.{key}")))
        for key, label in (("food", "Mâncare"), ("transport", "Transport"), ("leisure", "Ieșiri și vacanțe")):
            if g(f"market.{key}"):
                items["market"].append(_item(key, label, -g(f"market.{key}")))
    if g("health.monthly_costs"):
        items["hospital"].append(_item("health", "Costuri medicale", -g("health.monthly_costs")))

    debts = []
    for debt in _get(profile, "bank.debts") or []:
        payment = _num(debt.get("monthly_payment"))
        if payment <= 0:
            continue
        debts.append({
            "name": str(debt.get("name") or "Credit"),
            "balance": _num(debt.get("remaining")) or payment * 24,
            "apr": _num(debt.get("apr")) or 0.12,
            "payment": payment,
        })

    state = {
        "month": 0,
        "seed": seed,
        "name": _get(profile, "name") or "Jucător",
        "age": int(g("age", 25)),
        "goal": {
            "description": _get(profile, "goal.description") or "Stabilitate financiară",
            "target_amount": g("goal.target_amount") or 10000.0,
            "horizon_months": int(g("goal.horizon_months") or 24),
        },
        "cash": g("bank.cash"),
        "savings": g("bank.savings"),
        "investments": g("bank.investments"),
        "debts": debts,
        "items": items,
        "auto": {"savings": 0.0, "investments": 0.0},
        "insured": bool(_get(profile, "health.insured")),
        "student": str(_get(profile, "education.status") or "").lower().startswith(("elev", "student", "master")),
        "lives_with_parents": _get(profile, "home.housing") == 0,
        "statement_months": int(g("statement_months")) or None,
        "from_statement": bool(categories),
        "business": None,
        "calendar_start": _next_month(date.today()),
        "fiscal_arrears": [],
        "pending_event": None,
        "used_events": [],
        "log": [],
        "history": [],
    }
    state["history"].append(snapshot(state))
    return state


def _next_month(today: date) -> list[int]:
    return [today.year + today.month // 12, today.month % 12 + 1]


def calendar(state: dict, month: int | None = None) -> tuple[int, int]:
    """Calendar (year, month) of a game month; game month 0 is the month after the game was created."""
    start_year, start_month = state.get("calendar_start") or _next_month(date.today())
    index = start_month - 1 + (state["month"] if month is None else month)
    return start_year + index // 12, index % 12 + 1


def calendar_label(state: dict, month: int | None = None) -> str:
    year, m = calendar(state, month)
    return f"{MONTHS_RO[m - 1]} {year}"


# ---------------------------------------------------------------- derived values

def item_total(state: dict, inst: str, sign: int = 0) -> float:
    values = [i["amount"] for i in state["items"].get(inst, [])]
    if sign > 0:
        values = [v for v in values if v > 0]
    elif sign < 0:
        values = [v for v in values if v < 0]
    return sum(values)


def debt_payments(state: dict) -> float:
    return sum(min(d["payment"], d["balance"] * (1 + d["apr"] / 12)) for d in state["debts"])


def business_net(state: dict) -> float:
    """Cash the business brings each month. Taxes are not deducted here: they accrue and are paid at the deadlines."""
    business = state.get("business")
    if not business:
        return 0.0
    return business.get("monthly_cash", business["monthly_net"])


def taxes_due(state: dict) -> float:
    business = state.get("business") or {}
    accrued = sum(o["accrued"] for o in business.get("obligations", []))
    return accrued + sum(a["amount"] for a in state.get("fiscal_arrears", []))


def monthly_income(state: dict) -> float:
    return sum(item_total(state, inst, 1) for inst in INSTITUTION_IDS) + max(business_net(state), 0.0)


def monthly_expenses(state: dict) -> float:
    return -sum(item_total(state, inst, -1) for inst in INSTITUTION_IDS) + debt_payments(state) + max(-business_net(state), 0.0)


def total_debt(state: dict) -> float:
    return sum(d["balance"] for d in state["debts"])


def net_worth(state: dict) -> float:
    return state["cash"] + state["savings"] + state["investments"] - total_debt(state) - taxes_due(state)


def goal_progress(state: dict) -> float:
    return (state["savings"] + state["investments"]) / max(state["goal"]["target_amount"], 1.0)


def essential_expenses(state: dict) -> float:
    return -(item_total(state, "home", -1) + sum(i["amount"] for i in state["items"]["market"] if i["id"] == "food")) + debt_payments(state)


def emergency_months(state: dict) -> float:
    return state["savings"] / max(essential_expenses(state), 1.0)


def snapshot(state: dict) -> dict:
    return {
        "month": state["month"],
        "cash": round(state["cash"], 2),
        "savings": round(state["savings"], 2),
        "investments": round(state["investments"], 2),
        "debt": round(total_debt(state), 2),
        "taxes_due": round(taxes_due(state), 2),
        "net_worth": round(net_worth(state), 2),
        "goal_progress": round(goal_progress(state), 4),
        "income": round(monthly_income(state), 2),
        "expenses": round(monthly_expenses(state), 2),
    }


def institutions_view(state: dict) -> list[dict]:
    out = []
    pending = state.get("pending_event") or {}
    for inst in INSTITUTIONS:
        items = list(state["items"][inst["id"]])
        if inst["id"] == "bank":
            items += [_item(f"debt_{i}", f"Rată: {d['name']}", -min(d["payment"], d["balance"] * (1 + d["apr"] / 12)))
                      for i, d in enumerate(state["debts"])]
        if inst["id"] == "business" and state.get("business"):
            business = state["business"]
            label = f"{business['name']} (înainte de taxe)" if business.get("obligations") else f"{business['name']} (net după taxe)"
            items.append(_item("business_net", label, business_net(state)))
        out.append({
            **inst,
            "items": items,
            "in": round(sum(i["amount"] for i in items if i["amount"] > 0), 2),
            "out": round(-sum(i["amount"] for i in items if i["amount"] < 0), 2),
            "has_event": pending.get("institution") == inst["id"],
        })
    return out


def public_view(state: dict) -> dict:
    goal = state["goal"]
    months_left = max(goal["horizon_months"] - state["month"], 0)
    expected = min(state["month"] / max(goal["horizon_months"], 1), 1.0)
    return {
        "month": state["month"],
        "calendar": calendar_label(state),
        "fiscal": fiscal_view(state),
        "name": state["name"],
        "goal": {**goal, "progress": round(goal_progress(state), 4), "months_left": months_left,
                 "on_track": goal_progress(state) >= expected * 0.9},
        "balance": snapshot(state),
        "monthly": {"income": round(monthly_income(state), 2), "expenses": round(monthly_expenses(state), 2),
                    "surplus": round(monthly_income(state) - monthly_expenses(state), 2)},
        "emergency_months": round(emergency_months(state), 1),
        "auto": state["auto"],
        "insured": state["insured"],
        "debts": state["debts"],
        "business": state["business"],
        "institutions": institutions_view(state),
        "averages": _averages(state),
        "statement_months": state.get("statement_months"),
        "pending_event": state["pending_event"],
        "log": state["log"][-15:],
        "history": state["history"],
    }


def _averages(state: dict) -> list[dict]:
    rows = []
    for inst in INSTITUTION_IDS:
        for item in state["items"].get(inst, []):
            if item["amount"] < 0 and "medie/lună" in item["label"]:
                rows.append({"id": item["id"], "label": item["label"].replace(" · medie/lună", ""),
                             "monthly": round(-item["amount"], 2), "institution": inst})
    rows.sort(key=lambda row: -row["monthly"])
    return rows


def _next_due(state: dict, months: list[int]) -> str | None:
    for ahead in range(1, 13):
        year, m = calendar(state, state["month"] + ahead)
        if m in months:
            return f"25 {MONTHS_RO[m - 1].lower()} {year}"
    return None


def fiscal_view(state: dict) -> dict:
    business = state.get("business") or {}
    obligations = [{"name": o["name"], "declaration": o["declaration"], "accrued": round(o["accrued"], 2),
                    "monthly": o["monthly"], "next_due": _next_due(state, o["months"]), "when": o["when"]}
                   for o in business.get("obligations", [])]
    return {"obligations": obligations, "arrears": state.get("fiscal_arrears", []), "taxes_due": round(taxes_due(state), 2)}


# ---------------------------------------------------------------- operations

def _add_overdraft(state: dict, amount: float) -> None:
    for debt in state["debts"]:
        if debt["name"] == OVERDRAFT_NAME:
            debt["balance"] += amount
            debt["payment"] = max(150.0, debt["balance"] * 0.1)
            return
    state["debts"].append({"name": OVERDRAFT_NAME, "balance": amount, "apr": OVERDRAFT_APR,
                           "payment": max(150.0, amount * 0.1)})


def _spend(state: dict, amount: float) -> None:
    rest = amount
    for key in ("cash", "savings", "investments"):
        take = min(max(state[key], 0.0), rest)
        state[key] -= take
        rest -= take
    if rest > 0.5:
        _add_overdraft(state, rest)


def _find_item(state: dict, inst: str, item_id: str):
    return next((i for i in state["items"][inst] if i["id"] == item_id), None)


def apply_ops(state: dict, ops: dict) -> list[str]:
    notes = []
    if "spend" in ops:
        _spend(state, float(ops["spend"]))
    if "medical" in ops:
        gross = float(ops["medical"])
        covered = gross * INSURANCE_COVERAGE if state["insured"] else 0.0
        if covered:
            notes.append(f"Asigurarea a acoperit {money(covered)} din {money(gross)}.")
        _spend(state, gross - covered)
    if "cash_add" in ops:
        state["cash"] += float(ops["cash_add"])
    for key in ("to_savings", "to_investments"):
        if key in ops:
            amount = min(float(ops[key]), max(state["cash"], 0.0))
            state["cash"] -= amount
            state[key.removeprefix("to_")] += amount
    specs = list(ops.get("item_sets") or [])
    if "item_set" in ops:
        specs.append(ops["item_set"])
    for spec in specs:
        items = state["items"][spec["inst"]]
        existing = _find_item(state, spec["inst"], spec["id"])
        if existing:
            items.remove(existing)
        if abs(float(spec["amount"])) > 0.5:
            items.append(_item(spec["id"], spec["label"], spec["amount"]))
    if "item_scale" in ops:
        spec = ops["item_scale"]
        item = _find_item(state, spec["inst"], spec["id"])
        if item:
            item["amount"] = round(item["amount"] * float(spec["factor"]), 2)
    if "loan" in ops:
        loan = ops["loan"]
        principal, apr, months = float(loan["principal"]), float(loan["apr"]), int(loan["months"])
        r = apr / 12
        payment = principal / months if r == 0 else principal * r / (1 - (1 + r) ** -months)
        state["debts"].append({"name": loan["name"], "balance": principal, "apr": apr, "payment": round(payment, 2)})
        if loan.get("to_cash"):
            state["cash"] += principal
        notes.append(f"{loan['name']}: {money(payment)}/lună timp de {months} luni.")
    if "insured" in ops:
        state["insured"] = bool(ops["insured"])
    if "auto" in ops:
        for key in ("savings", "investments"):
            if key in ops["auto"]:
                state["auto"][key] = max(float(ops["auto"][key]), 0.0)
    if "fiscal_pay" in ops:
        _spend(state, float(ops["fiscal_pay"]))
    if "fiscal_late" in ops:
        late = ops["fiscal_late"]
        extra = late["amount"] * LATE_DAY_RATE * LATE_DAYS + late["fine"]
        state["fiscal_arrears"].append({"label": late["label"], "amount": round(late["amount"] + extra, 2),
                                        "principal": late["amount"], "extra": round(extra, 2)})
        notes.append(f"Restanță la ANAF: {money(late['amount'])} + {money(extra)} dobânzi, penalități și amendă.")
    if "note" in ops:
        notes.append(ops["note"])
    return notes


def _accrue_taxes(state: dict) -> None:
    for obligation in (state.get("business") or {}).get("obligations", []):
        obligation["accrued"] = round(obligation["accrued"] + obligation["monthly"], 2)


def _fiscal_event(state: dict) -> dict | None:
    """Deadline event for the calendar month that just started: arrears first, then the obligations due now."""
    if state.get("fiscal_arrears"):
        total = sum(a["amount"] for a in state["fiscal_arrears"])
        labels = "; ".join(a["label"] for a in state["fiscal_arrears"])
        extra = sum(a["extra"] for a in state["fiscal_arrears"])
        state["fiscal_arrears"] = []
        return _ev("fiscal_arrears", "business", "Restanță la ANAF",
                   f"Ai amânat: {labels}. Acum datorezi {money(total)}, din care {money(extra)} dobânzi (0,02%/zi), "
                   "penalități (0,01%/zi) și amendă pentru depunerea cu întârziere.", [
                       ("Plătesc restanța", f"Plătești {money(total)} acum.", {"fiscal_pay": total}),
                   ])
    business = state.get("business") or {}
    _, month = calendar(state)
    due = [o for o in business.get("obligations", []) if month in o["months"] and o["accrued"] > 0.5]
    if not due:
        return None
    total = round(sum(o["accrued"] for o in due), 2)
    lines = ", ".join(f"{o['declaration']} ({money(o['accrued'])})" for o in due)
    label = " + ".join(o["declaration"] for o in due) + f" din {calendar_label(state).lower()}"
    form = due[0].get("form", "srl")
    fine = LATE_FINE.get(form, 500.0)
    for o in due:
        o["accrued"] = 0.0
    late_extra = total * LATE_DAY_RATE * LATE_DAYS + fine
    return _ev("fiscal_deadline", "business", f"Termen fiscal: 25 {calendar_label(state).lower()}",
               f"Trebuie depuse și plătite: {lines}. Total {money(total)}.", [
                   ("Depun și plătesc la timp", f"Plătești {money(total)}.", {"fiscal_pay": total}),
                   ("Amân o lună", f"Luna viitoare plătești în plus ~{money(late_extra)} (dobânzi, penalități, amendă minimă).",
                    {"fiscal_late": {"amount": total, "label": label, "fine": fine}}),
               ])


def _run_month(state: dict, invest_return: float) -> None:
    state["cash"] += sum(item_total(state, inst) for inst in INSTITUTION_IDS) + business_net(state)
    for debt in state["debts"]:
        interest = debt["balance"] * debt["apr"] / 12
        pay = min(debt["payment"], debt["balance"] + interest)
        debt["balance"] = debt["balance"] + interest - pay
        state["cash"] -= pay
        if debt["name"] == OVERDRAFT_NAME:
            debt["payment"] = max(150.0, debt["balance"] * 0.1)
    state["debts"] = [d for d in state["debts"] if d["balance"] > 0.5]
    for key in ("savings", "investments"):
        amount = min(state["auto"][key], max(state["cash"], 0.0))
        state["cash"] -= amount
        state[key] += amount
    state["savings"] *= 1 + SAVINGS_APR / 12
    state["investments"] *= 1 + invest_return / 12
    if state["cash"] < 0:
        deficit = -state["cash"]
        state["cash"] = 0.0
        take = min(state["savings"], deficit)
        state["savings"] -= take
        deficit -= take
        if deficit > 0.5:
            _add_overdraft(state, deficit)


def _log(state: dict, inst: str, text: str, delta: float | None = None) -> None:
    state["log"].append({"month": state["month"], "institution": inst, "text": text,
                         "delta": round(delta, 2) if delta is not None else None})


def advance(state: dict) -> dict:
    if state.get("pending_event"):
        raise GameError("Rezolvă întâi evenimentul curent.")
    rng = random.Random(state["seed"] * 7919 + state["month"])
    before = snapshot(state)
    _run_month(state, INVEST_APR + rng.uniform(-INVEST_VOLATILITY, INVEST_VOLATILITY))
    _accrue_taxes(state)
    state["month"] += 1
    after = snapshot(state)
    state["history"].append(after)
    _log(state, "bank", f"Luna {state['month']} ({calendar_label(state)}): venituri {money(before['income'])}, "
                        f"cheltuieli {money(before['expenses'])}.", after["net_worth"] - before["net_worth"])
    fiscal = _fiscal_event(state)
    if fiscal:
        state["pending_event"] = fiscal
    elif state.get("from_statement"):
        state["pending_event"] = _pick_event(state, rng)
    elif rng.random() < EVENT_CHANCE:
        state["pending_event"] = _pick_event(state, rng)
    return {"before": before, "after": after}


def choose(state: dict, option_id: str) -> dict:
    event = state.get("pending_event")
    if not event:
        raise GameError("Nu există niciun eveniment activ.")
    option = next((o for o in event["options"] if o["id"] == option_id), None)
    if not option:
        raise GameError("Opțiune inexistentă.")
    before = net_worth(state)
    notes = apply_ops(state, option.get("ops", {}))
    state["pending_event"] = None
    state["history"][-1] = snapshot(state)
    _log(state, event["institution"], f"{event['title']}: {option['label']}. " + " ".join(notes), net_worth(state) - before)
    return {"notes": notes}


def bank_action(state: dict, action: str, amount: float) -> str:
    amount = max(float(amount), 0.0)
    if action == "auto_savings":
        state["auto"]["savings"] = amount
        text = f"Transfer automat spre economii: {money(amount)}/lună."
    elif action == "auto_investments":
        state["auto"]["investments"] = amount
        text = f"Investiție lunară automată: {money(amount)}/lună."
    elif action == "to_savings":
        amount = min(amount, max(state["cash"], 0.0))
        state["cash"] -= amount
        state["savings"] += amount
        text = f"Ai mutat {money(amount)} în economii."
    elif action == "prepay":
        if not state["debts"]:
            raise GameError("Nu ai credite de rambursat.")
        debt = max(state["debts"], key=lambda d: d["apr"])
        amount = min(amount, max(state["cash"], 0.0), debt["balance"])
        state["cash"] -= amount
        debt["balance"] -= amount
        state["debts"] = [d for d in state["debts"] if d["balance"] > 0.5]
        text = f"Ai rambursat anticipat {money(amount)} din „{debt['name']}”."
    else:
        raise GameError("Acțiune necunoscută.")
    state["history"][-1] = snapshot(state)
    _log(state, "bank", text)
    return text


def set_business(state: dict, business: dict) -> None:
    _spend(state, float(business.get("startup_cost", 0.0)))
    state["business"] = business
    state["history"][-1] = snapshot(state)
    _log(state, "business", f"Ai pornit „{business['name']}” ({business['form']}, {business['regime_label']}): "
                            f"cost inițial {money(business['startup_cost'])}, net estimat {money(business['monthly_net'])}/lună.")


# ---------------------------------------------------------------- projections (for the consultant)

def _sim_copy(state: dict) -> dict:
    """Projection copy: the business counts after taxes and taxes already owed are paid upfront."""
    sim = copy.deepcopy(state)
    sim["pending_event"] = None
    if sim.get("business"):
        sim["business"]["monthly_cash"] = sim["business"]["monthly_net"]
        owed = taxes_due(sim)
        for o in sim["business"].get("obligations", []):
            o["accrued"] = 0.0
        sim["fiscal_arrears"] = []
        if owed:
            _spend(sim, owed)
    return sim


def _settle_arrears(sim: dict) -> None:
    owed = sum(a["amount"] for a in sim.get("fiscal_arrears", []))
    sim["fiscal_arrears"] = []
    if owed:
        _spend(sim, owed)


def project(state: dict, months: int, ops: dict | None = None) -> dict:
    sim = _sim_copy(state)
    if ops:
        apply_ops(sim, ops)
    _settle_arrears(sim)
    min_cash = sim["cash"]
    for _ in range(months):
        _run_month(sim, INVEST_APR)
        sim["month"] += 1
        min_cash = min(min_cash, sim["cash"])
    result = {
        "months": months,
        "net_worth": round(net_worth(sim), 2),
        "savings_plus_investments": round(sim["savings"] + sim["investments"], 2),
        "debt": round(total_debt(sim), 2),
        "goal_progress": round(goal_progress(sim), 4),
        "min_cash": round(min_cash, 2),
        "overdraft": any(d["name"] == OVERDRAFT_NAME for d in sim["debts"]),
        "monthly_surplus": round(monthly_income(sim) - monthly_expenses(sim), 2),
    }
    result["months_to_goal"] = months_to_goal(state, ops)
    return result


def months_to_goal(state: dict, ops: dict | None = None) -> int | None:
    sim = _sim_copy(state)
    if ops:
        apply_ops(sim, ops)
    _settle_arrears(sim)
    for month in range(MAX_PROJECTION_MONTHS + 1):
        if goal_progress(sim) >= 1.0:
            return month
        _run_month(sim, INVEST_APR)
    return None


# ---------------------------------------------------------------- events

def _salary(state: dict) -> float:
    item = _find_item(state, "work", "salary")
    return item["amount"] if item else 0.0


def _expense(state: dict, inst: str, item_id: str) -> float:
    item = _find_item(state, inst, item_id)
    return -item["amount"] if item else 0.0


def _ev(event_id, inst, title, text, options, kind="event", saves=0):
    return {"id": event_id, "institution": inst, "title": title, "text": text, "kind": kind, "saves": saves,
            "options": [{"id": f"{event_id}_{i}", "label": label, "desc": desc, "ops": ops}
                        for i, (label, desc, ops) in enumerate(options)]}


def ev_rent(s):
    rent = _expense(s, "home", "housing")
    if rent <= 0:
        return None
    up, half, down = round(rent * 1.08), round(rent * 1.04), round(rent * 0.85)
    return _ev("rent", "home", "Chiria crește", f"Proprietarul vrea să mărească chiria de la {money(rent)} la {money(up)} pe lună.", [
        ("Accept", f"Chiria devine {money(up)}/lună.", {"item_set": {"inst": "home", "id": "housing", "label": "Chirie / rată locuință", "amount": -up}}),
        ("Negociez", f"Rămâne la {money(half)}/lună.", {"item_set": {"inst": "home", "id": "housing", "label": "Chirie / rată locuință", "amount": -half}}),
        ("Mă mut mai ieftin", f"Mutarea costă 2.000 lei, chiria scade la {money(down)}/lună.",
         {"spend": 2000, "item_set": {"inst": "home", "id": "housing", "label": "Chirie / rată locuință", "amount": -down}}),
    ])


def ev_subscriptions(s):
    return _ev("subscriptions", "home", "Abonamente uitate",
               "Ai descoperit în extras 3 abonamente de streaming și o aplicație de fitness pe care nu le mai folosești: 140 lei/lună.", [
        ("Le anulez pe toate", "Economisești 140 lei/lună.", {"note": "Abonamentele au fost anulate."}),
        ("Păstrez unul", "Rămâi cu 45 lei/lună.", {"item_set": {"inst": "home", "id": "extra_subs", "label": "Abonamente streaming", "amount": -45}}),
        ("Le păstrez", "Continui să plătești 140 lei/lună.", {"item_set": {"inst": "home", "id": "extra_subs", "label": "Abonamente streaming", "amount": -140}}),
    ])


def ev_appliance(s):
    return _ev("appliance", "home", "Mașina de spălat s-a stricat", "Reparația costă 650 lei, una nouă 2.100 lei.", [
        ("Repar", "Plătești 650 lei acum.", {"spend": 650}),
        ("Cumpăr nouă, cash", "Plătești 2.100 lei acum.", {"spend": 2100}),
        ("Cumpăr nouă în 6 rate fără dobândă", "350 lei/lună, 6 luni.", {"loan": {"name": "Rate mașină de spălat", "principal": 2100, "apr": 0.0, "months": 6}}),
    ])


def ev_vacation(s):
    return _ev("vacation", "market", "Vacanță cu prietenii", "Prietenii pleacă o săptămână în Grecia: 3.200 lei de persoană.", [
        ("Merg, plătesc din cont", "Cheltuiești 3.200 lei acum.", {"spend": 3200}),
        ("Merg, cu cardul de credit în 12 rate", "Dobândă 24%/an: ~302 lei/lună.", {"loan": {"name": "Card de credit (vacanță)", "principal": 3200, "apr": 0.24, "months": 12}}),
        ("Aleg un city-break mai ieftin", "Cheltuiești 900 lei.", {"spend": 900}),
        ("Nu merg", "Fără cheltuială.", {}),
    ])


def ev_black_friday(s):
    return _ev("black_friday", "market", "Black Friday", "Reduceri mari la electronice: un laptop nou de 4.500 lei și alte „oferte”.", [
        ("Iau laptopul", "Cheltuiești 4.500 lei.", {"spend": 4500}),
        ("Doar ce îmi trebuie", "Cheltuiești 400 lei.", {"spend": 400}),
        ("Nu cumpăr nimic", "Fără cheltuială.", {}),
    ])


def ev_car_repair(s):
    if _expense(s, "market", "transport") <= 0:
        return None
    return _ev("car_repair", "market", "Reparație neprevăzută", "Mașina (sau abonamentul de transport anual) îți cere brusc 2.300 lei.", [
        ("Plătesc acum", "Cheltuiești 2.300 lei.", {"spend": 2300}),
        ("Plătesc în 4 rate fără dobândă", "575 lei/lună, 4 luni.", {"loan": {"name": "Rate service auto", "principal": 2300, "apr": 0.0, "months": 4}}),
    ])


def ev_course(s):
    salary = _salary(s)
    if salary <= 0:
        return None
    return _ev("course", "education", "Curs de specializare", f"Un curs de 3 luni (2.400 lei) ți-ar putea crește salariul cu ~10% ({money(salary * 0.1)}/lună).", [
        ("Mă înscriu, plătesc integral", "Cheltuiești 2.400 lei, salariul crește cu 10%.", {"spend": 2400, "item_scale": {"inst": "work", "id": "salary", "factor": 1.10}}),
        ("Mă înscriu, plătesc în 6 rate", "400 lei/lună, salariul crește cu 10%.",
         {"loan": {"name": "Rate curs", "principal": 2400, "apr": 0.0, "months": 6}, "item_scale": {"inst": "work", "id": "salary", "factor": 1.10}}),
        ("Nu acum", "Nicio schimbare.", {}),
    ])


def ev_scholarship(s):
    if not s.get("student"):
        return None
    return _ev("scholarship", "education", "Bursă de merit", "Ai medii bune: poți aplica la o bursă de 600 lei/lună. Dosarul costă 150 lei (traduceri, adeverințe).", [
        ("Aplic la bursă", "Plătești 150 lei, primești +600 lei/lună.",
         {"spend": 150, "item_set": {"inst": "education", "id": "merit", "label": "Bursă de merit", "amount": 600}}),
        ("Nu aplic", "Nicio schimbare.", {}),
    ])


def ev_raise(s):
    salary = _salary(s)
    if salary <= 0:
        return None
    return _ev("raise", "work", "Evaluarea anuală", "Ai rezultate bune. Poți negocia o mărire sau poți accepta o ofertă de la altă firmă.", [
        ("Negociez +8%", f"Salariul crește la {money(salary * 1.08)}.", {"item_scale": {"inst": "work", "id": "salary", "factor": 1.08}}),
        ("Schimb jobul (+20%)", f"Salariul crește la {money(salary * 1.2)}, dar naveta costă +250 lei/lună.",
         {"item_scale": {"inst": "work", "id": "salary", "factor": 1.2},
          "item_set": {"inst": "market", "id": "commute", "label": "Navetă job nou", "amount": -250}}),
        ("Rămân așa", "Nicio schimbare.", {}),
    ])


def ev_bonus(s):
    salary = _salary(s)
    if salary <= 0:
        return None
    bonus = round(salary * 0.6)
    return _ev("bonus", "work", "Bonus de performanță", f"Ai primit un bonus de {money(bonus)}. Ce faci cu el?", [
        ("Totul la economii", "Crește fondul pentru scop.", {"cash_add": bonus, "to_savings": bonus}),
        ("Totul în investiții", "Randament mai mare pe termen lung, cu risc.", {"cash_add": bonus, "to_investments": bonus}),
        ("Jumătate economii, jumătate mă răsfăț", f"{money(bonus / 2)} la economii.", {"cash_add": bonus, "to_savings": bonus / 2, "spend": bonus / 2}),
    ])


def ev_freelance(s):
    if s.get("business"):
        return None
    return _ev("freelance", "business", "Proiect pe cont propriu", "Un client îți oferă un proiect recurent: ~2.000 lei/lună brut, 10 ore pe săptămână. Pentru a factura ai nevoie de PFA sau SRL — întreabă contabilul AI din clădirea Afacere.", [
        ("Accept (fără firmă încă)", "Estimare simplă: +1.400 lei/lună net. Discută cu contabilul pentru calculul exact.",
         {"item_set": {"inst": "business", "id": "freelance", "label": "Proiect freelance (estimare)", "amount": 1400}}),
        ("Refuz", "Nicio schimbare.", {}),
    ])


def ev_dentist(s):
    return _ev("dentist", "hospital", "Urgență stomatologică", "Ai nevoie de un tratament de canal și o coroană: 1.900 lei.", [
        ("Plătesc acum", "Asigurarea privată (dacă ai) acoperă 70%.", {"medical": 1900}),
        ("Plătesc în 6 rate la clinică", "~317 lei/lună, fără dobândă.", {"loan": {"name": "Rate stomatolog", "principal": 1900, "apr": 0.0, "months": 6}}),
    ])


def ev_insurance(s):
    if s.get("insured"):
        return None
    return _ev("insurance", "hospital", "Asigurare de sănătate", "Banca îți propune o asigurare privată de sănătate: 110 lei/lună, acoperă 70% din urgențele medicale.", [
        ("Accept", "+110 lei/lună cheltuieli, protecție la urgențe.",
         {"insured": True, "item_set": {"inst": "hospital", "id": "insurance", "label": "Asigurare de sănătate", "amount": -110}}),
        ("Refuz", "Rămâi neprotejat la urgențe.", {}),
    ])


def ev_loan_offer(s):
    return _ev("loan_offer", "bank", "Credit preaprobat", "Banca îți oferă un credit de nevoi personale preaprobat: 20.000 lei pe 48 de luni, dobândă 13%/an.", [
        ("Accept", "Primești 20.000 lei acum, rata ~537 lei/lună.", {"loan": {"name": "Credit nevoi personale", "principal": 20000, "apr": 0.13, "months": 48, "to_cash": True}}),
        ("Refuz", "Nicio schimbare.", {}),
    ])


def ev_deposit(s):
    amount = round(min(max(s["cash"] * 0.5, 0), 10000) / 100) * 100
    if amount < 500:
        return None
    return _ev("deposit", "bank", "Ai bani care stau degeaba", f"În contul curent ai {money(s['cash'])} care nu aduc dobândă. Poți muta o parte la economii (4%/an).", [
        (f"Mut {money(amount)} la economii", "Câștigi dobândă și crește progresul spre scop.", {"to_savings": amount}),
        ("Îi las în cont", "Rămân disponibili, fără dobândă.", {}),
    ])


def _keep(inst: str, item_id: str, label: str, monthly: float) -> dict:
    return {"inst": inst, "id": item_id, "label": f"{label} · medie/lună", "amount": -round(monthly)}


def _drop(inst: str, item_id: str, label: str, amount: float, why: str):
    """Suggestion to remove one irresponsible monthly expense. Amount 0 deletes the line."""
    if amount < 40:
        return None
    return _ev(f"taie_{item_id}", inst, f"Taie {label.lower()}",
               f"{why} Din extras, media e {money(amount)} pe lună. Dacă accepți, dispare din cheltuielile lunare.",
               [
                   ("Taie cheltuiala", f"{label} dispare. Cheltuielile lunare scad cu {money(amount)}.",
                    {"item_set": _keep(inst, item_id, label, 0)}),
                   ("O las așa", "Rămâne în cheltuielile lunare.", {}),
               ],
               kind="suggestion", saves=round(amount))


def ev_taie_uber(s):
    amount = _expense(s, "market", "uber")
    return _drop("market", "uber", "Transport (Uber / Bolt)", amount,
                 "Uber și Bolt, mai ales noaptea, îți mănâncă salariul de part-time. Un abonament de transport sau mersul pe jos acoperă aceleași drumuri.")


def ev_taie_restaurante(s):
    amount = _expense(s, "market", "restaurante")
    return _drop("market", "restaurante", "Restaurante și baruri", amount,
                 "Stai cu părinții, iar ieșirile depășesc mâncarea de acasă. Gătitul acasă și o ieșire pe săptămână, nu în fiecare seară, scoate categoria.")


def ev_taie_pariuri(s):
    amount = _expense(s, "market", "pariuri")
    return _drop("market", "pariuri", "Pariuri online", amount,
                 "Superbet nu îți aduce bani înapoi. Ștergerea aplicației oprește depunerile.")


def ev_taie_livrari(s):
    amount = _expense(s, "market", "livrari")
    return _drop("market", "livrari", "Livrări de mâncare", amount,
                 "Glovo la ore târzii e o masă scumpă peste ieșirile de la restaurant.")


def ev_taie_cumparaturi(s):
    amount = _expense(s, "market", "cumparaturi")
    return _drop("market", "cumparaturi", "Cumpărături impulsive", amount,
                 "About You, H&M și Bershka apar când nu ai nevoie de haine noi. O pauză de cumpărături scoate linia.")


def ev_taie_numerar(s):
    amount = _expense(s, "bank", "numerar")
    return _drop("bank", "numerar", "Retrageri de numerar", amount,
                 "Banii scoși de la bancomat pleacă fără să știi pe ce. Dacă plătești cu cardul, retragerea dispare.")


def ev_taie_cafea(s):
    amount = _expense(s, "market", "cafea")
    return _drop("market", "cafea", "Cafea de drum", amount,
                 "5 to go de câteva ori pe zi se adună. Cafeaua de acasă acoperă același obicei.")


def ev_taie_rate(s):
    amount = _expense(s, "market", "rate")
    return _drop("market", "rate", "Rate la comercianți (PayPo)", amount,
                 "Hanorace și comenzi în rate PayPo, deși venitul e de part-time. Fără cumpărături noi în rate, linia dispare.")


def ev_taie_abonamente(s):
    amount = _expense(s, "home", "abonamente")
    if amount < 80:
        return None
    gym = min(149, round(amount * 0.55))
    left = round(max(amount - gym, 0))
    return _ev("taie_abonamente", "home", "Taie abonamentele nefolosite",
               f"Plătești {money(amount)}/lună pe Netflix, Spotify, HBO și sala la care nu mergi. Sala e cam {money(gym)} din sumă.",
               [
                   ("Anulează tot", f"Abonamentele dispar. Cheltuielile lunare scad cu {money(amount)}.",
                    {"item_set": _keep("home", "abonamente", "Abonamente", 0)}),
                   ("Anulează doar sala", f"Rămâi cu streamingul, {money(left)}/lună. Sala dispare.",
                    {"item_set": _keep("home", "abonamente", "Abonamente", left)}),
                   ("Le păstrez", "Abonamentele rămân.", {}),
               ],
               kind="suggestion", saves=round(amount))


HABIT_EVENTS = [ev_taie_uber, ev_taie_restaurante, ev_taie_pariuri, ev_taie_livrari, ev_taie_cumparaturi,
                ev_taie_numerar, ev_taie_cafea, ev_taie_rate, ev_taie_abonamente]

EVENTS = [ev_rent, ev_subscriptions, ev_appliance, ev_vacation, ev_black_friday, ev_car_repair, ev_course,
          ev_scholarship, ev_raise, ev_bonus, ev_freelance, ev_dentist, ev_insurance, ev_loan_offer, ev_deposit]


def _event_pool(state: dict) -> list:
    if state.get("from_statement"):
        return HABIT_EVENTS
    return EVENTS


def _pick_event(state: dict, rng: random.Random) -> dict | None:
    pool = _event_pool(state)

    def candidates(exclude):
        built = [fn(state) for fn in pool if fn.__name__ not in exclude]
        return [e for e in built if e]

    options = candidates(state["used_events"])
    if not options:
        state["used_events"] = []
        options = candidates([])
    if not options:
        return None
    if state.get("from_statement"):
        event = max(options, key=lambda item: item.get("saves") or 0)
    else:
        event = rng.choice(options)
    state["used_events"].append(f"ev_{event['id']}")
    return event
