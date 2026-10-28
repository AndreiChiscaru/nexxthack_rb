"""Offline checks for the demo: tax calculator, game engine and tool handlers (no Claude calls)."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DEMO_DB", str(Path(tempfile.mkdtemp()) / "demo.sqlite3"))

from app.agents import business, consultant, onboarding, store, taxes  # noqa: E402
from app.agents import profile as prof  # noqa: E402
from app.demo import engine  # noqa: E402


def check(cond, msg):
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        check.failed = True


check.failed = False

# taxes
p = taxes.calculate("pfa", 120_000, 20_000)
check(p["taxe"]["cas_pensie"] == 24_300, f"PFA CAS la 100k net = 24.300 ({p['taxe']['cas_pensie']})")
check(p["taxe"]["cass_sanatate"] == 10_000, f"PFA CASS 10% din 100k ({p['taxe']['cass_sanatate']})")
check(abs(p["taxe"]["impozit_venit_10"] - 6_570) < 1, f"PFA impozit 10% din 65.700 ({p['taxe']['impozit_venit_10']})")
p2 = taxes.calculate("pfa", 20_000, 0)
check(p2["taxe"]["cas_pensie"] == 0 and p2["taxe"]["cass_sanatate"] == 2_430, "PFA sub 12 salarii: CAS 0, CASS minim 6 salarii")
m = taxes.calculate("micro", 300_000, 50_000)
check(m["taxe"]["impozit_micro_1"] == 3_000, "micro 1% din cifra de afaceri")
check(m["eligibil"], "micro eligibil sub 100k euro")
check(not taxes.calculate("micro", 600_000, 0)["eligibil"], "micro neeligibil peste plafon")
c = taxes.compare(60_000, 10_000)
print("     ", c["summary"])
check(len(c["variante"]) == 3, "compare întoarce 3 variante")

# profile + engine
profile = prof.empty()
prof.merge(profile, {"name": "Ana", "age": 27, "occupation": "programatoare",
                     "goal": {"description": "Avans apartament", "target_amount": 60000, "horizon_months": 36},
                     "income": {"salary": 7000}, "home": {"housing": 2000, "utilities": 450, "subscriptions": 80},
                     "market": {"food": 1300, "transport": 250, "leisure": 600},
                     "bank": {"cash": 3000, "savings": 8000, "debts": [{"name": "Card", "monthly_payment": 300, "remaining": 3000, "apr": 0.24}]},
                     "risk_tolerance": "medie"}, "conversație")
check(prof.missing(profile) == [], f"profil complet ({prof.missing(profile)})")
game = engine.new_game(profile["data"], 42)
for _ in range(12):
    if game["pending_event"]:
        engine.choose(game, game["pending_event"]["options"][0]["id"])
    engine.advance(game)
view = engine.public_view(game)
check(game["month"] == 12, f"12 luni jucate, patrimoniu {engine.money(view['balance']['net_worth'])}, progres {view['goal']['progress']:.0%}")
json.dumps(view)

# tool handlers through the store
sid = store.new_session()
store.save(sid, "profile", profile)
store.save(sid, "game", game)
ctools = {t.name: t for t in consultant._tools(sid)}
check("remember" in ctools, "consultant are unealta de memorie comună")
state = ctools["get_financial_state"].handler()
check(state["joc_pornit"], "consultant: " + state["summary"])
plan = ctools["simulate_plan"].handler(savings_per_month=800, months=12)
check("cu_planul" in plan, "consultant: " + plan["summary"])
if game["pending_event"]:
    sim = ctools["simulate_event_options"].handler()
    check("rezultate" in sim, "consultant: " + sim["summary"])
check(ctools["search_products"].handler(category="economii")["produse"], "consultant: produse economii")
btools = {t.name: t for t in business._tools(sid)}
check(btools["startup_checklist"].handler(form="SRL")["pasi"], "contabil: checklist SRL")
res = btools["apply_business_to_game"].handler(name="Studio web", form="PFA", regime="pfa", startup_cost=1500,
                                                monthly_revenue=4000, monthly_expenses=500)
check(res.get("ok"), "contabil: " + res.get("summary", str(res)))
check(store.load(sid, "game")["business"]["name"] == "Studio web", "afacerea salvată în joc")

# onboarding tools + statement patch
convo = onboarding.new_conversation()
p3 = prof.empty()
otools = {t.name: t for t in onboarding._tools(p3, convo)}
check(otools["finish_onboarding"].handler(summary="x", scenario_title="y").get("error"), "onboarding: nu finalizează profil incomplet")
patch = onboarding.statement_patch({"titular": "POPESCU ION", "venit_lunar_estimat": 5200, "sold_final": -20, "economii_identificate": 1000},
                                   {"name": "Ion Popescu", "loans": [{"name": "Credit", "payment": 600, "principal": 15000, "apr": 0.1}]})
saved = prof.merge(p3, patch, "extras")
check(set(saved) >= {"name", "income.salary", "bank.cash", "bank.savings", "bank.debts"}, f"patch din extras: {saved}")

print("\nREZULTAT:", "EȘEC" if check.failed else "toate verificările au trecut")
sys.exit(1 if check.failed else 0)
