"""Demo game engine: one turn = one month across the 7 institutions.
This is the single source of truth for money; agents only read it or run projections on copies."""
import copy
import random

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
        "business": None,
        "pending_event": None,
        "used_events": [],
        "log": [],
        "history": [],
    }
    state["history"].append(snapshot(state))
    return state


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
    return state["business"]["monthly_net"] if state.get("business") else 0.0


def monthly_income(state: dict) -> float:
    return sum(item_total(state, inst, 1) for inst in INSTITUTION_IDS) + max(business_net(state), 0.0)


def monthly_expenses(state: dict) -> float:
    return -sum(item_total(state, inst, -1) for inst in INSTITUTION_IDS) + debt_payments(state) + max(-business_net(state), 0.0)


def total_debt(state: dict) -> float:
    return sum(d["balance"] for d in state["debts"])


def net_worth(state: dict) -> float:
    return state["cash"] + state["savings"] + state["investments"] - total_debt(state)


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
            items.append(_item("business_net", f"{state['business']['name']} (net după taxe)", business_net(state)))
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
        "pending_event": state["pending_event"],
        "log": state["log"][-15:],
        "history": state["history"],
    }


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
    if "item_set" in ops:
        spec = ops["item_set"]
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
    if "note" in ops:
        notes.append(ops["note"])
    return notes


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
    state["month"] += 1
    after = snapshot(state)
    state["history"].append(after)
    _log(state, "bank", f"Luna {state['month']}: venituri {money(before['income'])}, cheltuieli {money(before['expenses'])}.",
         after["net_worth"] - before["net_worth"])
    if rng.random() < EVENT_CHANCE:
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

def project(state: dict, months: int, ops: dict | None = None) -> dict:
    sim = copy.deepcopy(state)
    sim["pending_event"] = None
    if ops:
        apply_ops(sim, ops)
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
    sim = copy.deepcopy(state)
    sim["pending_event"] = None
    if ops:
        apply_ops(sim, ops)
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


def _ev(event_id, inst, title, text, options):
    return {"id": event_id, "institution": inst, "title": title, "text": text,
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


EVENTS = [ev_rent, ev_subscriptions, ev_appliance, ev_vacation, ev_black_friday, ev_car_repair, ev_course,
          ev_scholarship, ev_raise, ev_bonus, ev_freelance, ev_dentist, ev_insurance, ev_loan_offer, ev_deposit]


def _pick_event(state: dict, rng: random.Random) -> dict | None:
    def candidates(exclude):
        built = [fn(state) for fn in EVENTS if fn.__name__ not in exclude]
        return [e for e in built if e]

    options = candidates(state["used_events"])
    if not options:
        state["used_events"] = []
        options = candidates([])
    if not options:
        return None
    event = rng.choice(options)
    state["used_events"].append(f"ev_{event['id']}")
    return event
