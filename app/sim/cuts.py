"""Cut suggestions built from statement category averages.

When a profile has these lines, the game offers to remove them instead of generic surprise events.
Accepting a cut subtracts the monthly amount from living and drops the line.
"""
from ..schemas import Event, EventOption, Profile, SpendingCategory
from . import engine as E

IRRESPONSIBLE = ("uber", "restaurante", "abonamente", "pariuri", "livrari", "numerar", "cumparaturi", "cafea", "rate")
MIN_MONTHLY = 40.0
# After every current suggestion was shown, wait before the same ones can return.
REPEAT_GAP = 3

WHY = {
    "uber": "Uber și Bolt, mai ales noaptea, îți mănâncă salariul de part-time. Transportul în comun acoperă aceleași drumuri.",
    "restaurante": "Ieșirile depășesc mâncarea de acasă. Gătitul acasă scoate categoria.",
    "abonamente": "Sala la care nu mergi și streamingul nefolosit se plătesc în fiecare lună.",
    "pariuri": "Pariurile online nu se întorc în cont. Ștergerea aplicației oprește depunerile.",
    "livrari": "Livrările de noapte sunt o masă scumpă peste ieșirile de la restaurant.",
    "numerar": "Banii scoși de la bancomat pleacă fără o categorie. Plata cu cardul oprește retragerile.",
    "cumparaturi": "Hainele cumpărate din impuls nu sunt o cheltuială lunară necesară.",
    "cafea": "Cafeaua de drum, de câteva ori pe zi, se adună. Cafeaua de acasă o înlocuiește.",
    "rate": "Cumpărăturile în rate PayPo continuă după ce produsul e deja la tine.",
}


def eligible(profile: Profile) -> list[SpendingCategory]:
    rows = [c for c in profile.categories if c.id in IRRESPONSIBLE and c.monthly >= MIN_MONTHLY]
    rows.sort(key=lambda c: -c.monthly)
    return rows


def suggestion(cat: SpendingCategory, offered: list[str]) -> Event | None:
    if cat.id in offered or cat.id not in IRRESPONSIBLE or cat.monthly < MIN_MONTHLY:
        return None
    options = [
        EventOption(id="taie", label="Taie cheltuiala",
                    ops={"living_add": -round(cat.monthly, 2)}),
        EventOption(id="lasa", label="O las așa", ops={"mood": {"stress": 0}}),
    ]
    text = f"{WHY.get(cat.id, 'Cheltuiala asta nu e necesară.')} Din extras, media este {E.money(cat.monthly)} pe lună. Dacă accepți, dispare din cheltuielile lunare."
    if cat.id == "abonamente":
        gym = min(149.0, round(cat.monthly * 0.55))
        options.insert(1, EventOption(
            id="sala", label="Anulează doar sala",
            ops={"living_add": -gym},
        ))
        text += f" Sala e cam {E.money(gym)} din sumă."
    return Event(id=f"taie_{cat.id}", institution=cat.institution, title=f"Taie {cat.label}", text=text, options=options)


def next_suggestion(profile: Profile, offered: list[str]) -> Event | None:
    for cat in eligible(profile):
        event = suggestion(cat, offered)
        if event:
            return event
    return None


def _bucket(profile: Profile, cat_id: str):
    leisure = {"restaurante", "livrari", "cafea", "cumparaturi", "pariuri", "rate", "numerar"}
    if cat_id == "uber":
        return profile.recurring, "transport"
    if cat_id == "alimente":
        return profile.spending, "food"
    if cat_id in ("abonamente", "telefon"):
        return profile.recurring, "subscriptions"
    if cat_id in leisure:
        return profile.spending, "leisure"
    return None


def apply_cut(profile: Profile, sim: dict, cat_id: str, option_id: str) -> str:
    cat = next((c for c in profile.categories if c.id == cat_id), None)
    if cat is None:
        raise ValueError(cat_id)
    if option_id == "lasa":
        return f"{cat.label} rămâne în cheltuielile lunare."
    if option_id == "sala" and cat.id == "abonamente":
        gym = min(149.0, round(cat.monthly * 0.55, 2))
        cat.monthly = round(cat.monthly - gym, 2)
        sim["living"] = max(0.0, float(sim["living"]) - gym)
        holder = _bucket(profile, cat.id)
        if holder:
            obj, attr = holder
            setattr(obj, attr, max(0.0, float(getattr(obj, attr)) - gym))
        if cat.monthly < MIN_MONTHLY:
            profile.categories.remove(cat)
        return f"Abonamentul la sală a dispărut. Cheltuielile lunare scad cu {E.money(gym)}."
    if option_id != "taie":
        raise ValueError(option_id)
    amount = float(cat.monthly)
    sim["living"] = max(0.0, float(sim["living"]) - amount)
    holder = _bucket(profile, cat.id)
    if holder:
        obj, attr = holder
        setattr(obj, attr, max(0.0, round(float(getattr(obj, attr)) - amount, 2)))
    profile.categories.remove(cat)
    return f"{cat.label} a dispărut din cheltuielile lunare (−{E.money(amount)}/lună)."
