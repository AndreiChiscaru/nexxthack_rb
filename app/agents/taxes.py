"""Romanian tax calculator for 2026 (PFA real system, SRL micro 1%, SRL profit tax 16%).
Deterministic: the accountant agent must call these functions instead of computing taxes itself."""

YEAR = 2026
MIN_WAGE_FOR_CAPS = 4050.0   # salariul minim la 1 ian. 2026: bază pentru plafoanele CAS/CASS ale veniturilor din 2026
MIN_WAGE_CURRENT = 4325.0    # salariul minim din 1 iul. 2026 (HG 146/2026)
EUR_RON = 5.1                # curs orientativ pentru plafonul micro
MICRO_RATE = 0.01            # Codul fiscal art. 51 (cota de 3% abrogată)
MICRO_CAP_EUR = 100_000      # plafon micro 2026
PROFIT_TAX = 0.16
DIVIDEND_TAX = 0.16          # Legea 141/2025, dividende distribuite din 1 ian. 2026
CAS_RATE = 0.25
CASS_RATE = 0.10
INCOME_TAX = 0.10
CAM_RATE = 0.0225            # contribuția asiguratorie pentru muncă (angajator)
VAT_RATE = 0.21              # din 1 aug. 2025 (Legea 141/2025); cota redusă 11%
VAT_THRESHOLD = 395_000.0    # plafon scutire TVA din 1 sep. 2025 (OG 22/2025)

SOURCES = [
    "Legea 227/2015 (Codul fiscal), modificată prin Legea 141/2025, OG 22/2025 și OUG 8/2026",
    "HG 146/2026 (salariul minim 4.325 lei din 1 iulie 2026)",
    "ANAF: plafoane CAS/CASS 2026 calculate la salariul minim de 4.050 lei",
]
DISCLAIMER = ("Calcul orientativ pentru anul fiscal 2026, simplificat (fără deducere personală, pierderi reportate, "
              "rezervă legală sau cazuri speciale). Pentru decizii reale verifică cu un expert contabil CECCAR.")


def _r(x: float) -> float:
    return round(x, 2)


def _cas_pfa(net: float) -> float:
    mw = MIN_WAGE_FOR_CAPS
    if net < 12 * mw:
        return 0.0
    return CAS_RATE * (12 * mw if net < 24 * mw else 24 * mw)


def _cass_pfa(net: float) -> float:
    if net <= 0:
        return 0.0
    mw = MIN_WAGE_FOR_CAPS
    return CASS_RATE * min(max(net, 6 * mw), 72 * mw)


def _cass_dividends(dividends: float) -> float:
    mw = MIN_WAGE_FOR_CAPS
    if dividends < 6 * mw:
        return 0.0
    if dividends < 12 * mw:
        return CASS_RATE * 6 * mw
    if dividends < 24 * mw:
        return CASS_RATE * 12 * mw
    return CASS_RATE * 24 * mw


def _salary(gross_monthly: float) -> dict:
    gross = gross_monthly * 12
    cas, cass = gross * CAS_RATE, gross * CASS_RATE
    tax = (gross - cas - cass) * INCOME_TAX
    cam = gross * CAM_RATE
    return {"brut_anual": _r(gross), "cas": _r(cas), "cass": _r(cass), "impozit": _r(tax), "cam_angajator": _r(cam),
            "net_anual": _r(gross - cas - cass - tax), "cost_total_angajator": _r(gross + cam)}


def _vat_notes(revenue: float) -> list[str]:
    if revenue > VAT_THRESHOLD:
        return [f"Cifra de afaceri depășește plafonul de scutire TVA ({VAT_THRESHOLD:,.0f} lei): înregistrare obligatorie în scopuri de TVA, cota standard {VAT_RATE:.0%}.".replace(",", ".")]
    return [f"Sub plafonul de scutire TVA ({VAT_THRESHOLD:,.0f} lei/an): nu e obligatorie înregistrarea în scopuri de TVA.".replace(",", ".")]


def pfa(revenue: float, expenses: float) -> dict:
    net = revenue - expenses
    cas, cass = _cas_pfa(net), _cass_pfa(net)
    tax = max(net - cas - cass, 0.0) * INCOME_TAX
    pocket = net - cas - cass - tax
    notes = ["Declarația unică se depune până la 25 mai a anului următor."]
    if net < 12 * MIN_WAGE_FOR_CAPS:
        notes.append(f"Venit net sub 12 salarii minime ({12 * MIN_WAGE_FOR_CAPS:,.0f} lei): CAS nu e obligatoriu (poți opta pentru el, contează la pensie).".replace(",", "."))
    if 0 < net < 6 * MIN_WAGE_FOR_CAPS:
        notes.append("CASS se plătește la minimul de 6 salarii minime, chiar dacă venitul net e mai mic.")
    return {
        "regim": "pfa", "denumire": "PFA – sistem real", "eligibil": True,
        "venit_brut": _r(revenue), "cheltuieli_deductibile": _r(expenses), "venit_net": _r(net),
        "taxe": {"cas_pensie": _r(cas), "cass_sanatate": _r(cass), "impozit_venit_10": _r(tax)},
        "total_taxe": _r(cas + cass + tax), "bani_in_mana_anual": _r(pocket), "bani_in_mana_lunar": _r(pocket / 12),
        "rata_efectiva_din_net": _r((cas + cass + tax) / net) if net > 0 else 0.0,
        "note": notes + _vat_notes(revenue),
    }


def srl(revenue: float, expenses: float, regime: str = "micro", owner_is_employee: bool = True) -> dict:
    micro = regime == "micro"
    cap = MICRO_CAP_EUR * EUR_RON
    eligible = not micro or revenue <= cap
    salary = _salary(MIN_WAGE_CURRENT) if (micro or owner_is_employee) else None
    labor_cost = salary["cost_total_angajator"] if salary else 0.0
    profit = revenue - expenses - labor_cost
    corp_tax = revenue * MICRO_RATE if micro else max(profit, 0.0) * PROFIT_TAX
    dividends = max(profit - corp_tax, 0.0)
    div_tax = dividends * DIVIDEND_TAX
    cass_div = _cass_dividends(dividends)
    pocket = dividends - div_tax - cass_div
    taxes = {("impozit_micro_1" if micro else "impozit_profit_16"): _r(corp_tax),
             "impozit_dividende_16": _r(div_tax), "cass_dividende": _r(cass_div)}
    if salary and owner_is_employee:
        pocket += salary["net_anual"]
        taxes.update({"salariu_cas": salary["cas"], "salariu_cass": salary["cass"],
                      "salariu_impozit": salary["impozit"], "cam_angajator": salary["cam_angajator"]})
    notes = ["Presupune distribuirea integrală a profitului ca dividende (fără rezervă legală)."]
    if micro:
        notes.append(f"Micro cere cel puțin un salariat cu normă întreagă: inclus salariu minim {MIN_WAGE_CURRENT:,.0f} lei brut/lună "
                     f"(cost angajator {labor_cost:,.0f} lei/an){' plătit chiar ție' if owner_is_employee else ' plătit unui angajat'}.".replace(",", "."))
        notes.append("Impozitul micro se plătește trimestrial, până la data de 25 a lunii următoare trimestrului.")
        if not eligible:
            notes.append(f"Cifra de afaceri depășește plafonul micro de {MICRO_CAP_EUR:,} euro (~{cap:,.0f} lei): se aplică impozit pe profit 16%.".replace(",", "."))
    if profit < 0:
        notes.append("Firma ar fi pe pierdere: cheltuielile și salariul depășesc veniturile.")
    total = corp_tax + div_tax + cass_div
    if salary and owner_is_employee:
        total += salary["cas"] + salary["cass"] + salary["impozit"] + salary["cam_angajator"]
    return {
        "regim": regime, "denumire": "SRL – microîntreprindere 1%" if micro else "SRL – impozit pe profit 16%",
        "eligibil": eligible, "venit_brut": _r(revenue), "cheltuieli_deductibile": _r(expenses),
        "profit_contabil": _r(profit), "dividende_brute": _r(dividends), "taxe": taxes,
        "total_taxe": _r(total), "bani_in_mana_anual": _r(pocket), "bani_in_mana_lunar": _r(pocket / 12),
        "rata_efectiva_din_net": _r(total / (revenue - expenses)) if revenue - expenses > 0 else 0.0,
        "note": notes + _vat_notes(revenue),
    }


def calculate(regime: str, annual_revenue: float, annual_expenses: float, owner_is_employee: bool = True) -> dict:
    if regime == "pfa":
        result = pfa(annual_revenue, annual_expenses)
    elif regime in ("micro", "profit"):
        result = srl(annual_revenue, annual_expenses, regime, owner_is_employee)
    else:
        raise ValueError("regim trebuie să fie pfa, micro sau profit")
    result["an_fiscal"] = YEAR
    result["avertisment"] = DISCLAIMER
    result["summary"] = f"{result['denumire']}: taxe {result['total_taxe']:,.0f} lei/an, rămân {result['bani_in_mana_lunar']:,.0f} lei/lună".replace(",", ".")
    return result


def compare(annual_revenue: float, annual_expenses: float, owner_is_employee: bool = True) -> dict:
    options = [pfa(annual_revenue, annual_expenses),
               srl(annual_revenue, annual_expenses, "micro", owner_is_employee),
               srl(annual_revenue, annual_expenses, "profit", owner_is_employee)]
    eligible = [o for o in options if o["eligibil"]]
    best = max(eligible, key=lambda o: o["bani_in_mana_anual"])
    return {
        "an_fiscal": YEAR, "variante": options, "cea_mai_avantajoasa": best["denumire"],
        "parametri": {"salariu_minim_plafoane": MIN_WAGE_FOR_CAPS, "salariu_minim_curent": MIN_WAGE_CURRENT,
                      "cota_micro": MICRO_RATE, "plafon_micro_eur": MICRO_CAP_EUR, "impozit_profit": PROFIT_TAX,
                      "impozit_dividende": DIVIDEND_TAX, "cota_tva": VAT_RATE, "plafon_tva_lei": VAT_THRESHOLD},
        "surse": SOURCES, "avertisment": DISCLAIMER,
        "summary": "; ".join(f"{o['denumire']}: {o['bani_in_mana_lunar']:,.0f} lei/lună în mână".replace(",", ".") for o in options)
                   + f". Cel mai avantajos: {best['denumire']}.",
    }


CHECKLISTS = {
    "pfa": {
        "pasi": [
            "Alegi codurile CAEN (activitatea principală și secundare) — verifică dacă activitatea permite PFA.",
            "Rezervi denumirea și depui cererea de înregistrare la ONRC (online, portal.onrc.ro).",
            "Dovada sediului profesional (contract de comodat/închiriere sau acordul proprietarului).",
            "Primești CUI și certificatul de înregistrare; înregistrarea fiscală la ANAF se face automat.",
            "Deschizi un cont bancar dedicat activității (recomandat, chiar dacă nu e obligatoriu).",
            "Ții registrul de încasări și plăți (sau contabil) și depui Declarația unică până la 25 mai.",
        ],
        "documente": ["Carte de identitate", "Dovada sediului", "Dovada calificării (diplomă/certificat) pentru unele activități",
                      "Declarație pe propria răspundere privind îndeplinirea condițiilor de funcționare"],
        "costuri_estimate": "Înregistrare ONRC: costuri mici sau zero online (verifică pe onrc.ro); contabil: ~150–400 lei/lună (estimare de piață).",
    },
    "srl": {
        "pasi": [
            "Verifici și rezervi denumirea la ONRC.",
            "Stabilești asociații, administratorul, capitalul social și codurile CAEN.",
            "Redactezi actul constitutiv și declarațiile asociaților/administratorului.",
            "Dovada sediului social (contract de închiriere/comodat sau act de proprietate).",
            "Depui dosarul la ONRC (online); primești CUI și certificatul de înregistrare.",
            "Deschizi contul bancar al firmei și depui capitalul social.",
            "Angajezi cel puțin un salariat (necesar pentru regimul micro) și înregistrezi contractul în REVISAL.",
            "Contractezi un contabil: declarații lunare/trimestriale (D100, D112, D300 dacă ești plătitor de TVA), bilanț anual.",
        ],
        "documente": ["Acte de identitate asociați/administrator", "Act constitutiv", "Dovada sediului social",
                      "Dovada depunerii capitalului social", "Declarații pe propria răspundere (beneficiar real, condiții de funcționare)"],
        "costuri_estimate": "Taxe ONRC și capital social: verifică cerințele actuale pe onrc.ro; contabil: ~300–900 lei/lună (estimare de piață); salariul minim + CAM pentru angajat.",
    },
}


def checklist(form: str) -> dict:
    key = "srl" if form.lower().startswith("srl") else "pfa"
    data = CHECKLISTS[key]
    return {**data, "forma": key.upper(), "summary": f"Checklist {key.upper()}: {len(data['pasi'])} pași, {len(data['documente'])} documente."}
