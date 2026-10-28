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


# ---------------------------------------------------------------- fiscal calendar and late payment

LATE_INTEREST_DAY = 0.0002   # Codul de procedură fiscală art. 174 alin. (5)
LATE_PENALTY_DAY = 0.0001    # Codul de procedură fiscală art. 176 alin. (2)
LATE_FILING_FINE = {"pfa": 50.0, "srl": 500.0}  # minimul amenzii, CPF art. 336 alin. (2) lit. d) / alin. (3)
QUARTER_MONTHS = [1, 4, 7, 10]
MONTHS_RO = ["ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie", "august", "septembrie",
             "octombrie", "noiembrie", "decembrie"]


def late_cost(amount: float, days: int, form: str) -> dict:
    interest = amount * LATE_INTEREST_DAY * days
    penalty = amount * LATE_PENALTY_DAY * days
    fine = LATE_FILING_FINE["pfa" if form.lower() == "pfa" else "srl"]
    return {"dobanzi": _r(interest), "penalitati": _r(penalty), "amenda_minima": fine, "total": _r(interest + penalty + fine),
            "temei": "CPF art. 174 (dobândă 0,02%/zi), art. 176 (penalitate 0,01%/zi), art. 336 (amenzi pentru nedepunere)"}


def obligations(regime: str, result: dict, d112_quarterly: bool = True) -> list[dict]:
    """Recurring tax payments for the game: each accrues `monthly` lei and is paid on the 25th of its due months."""
    t = result["taxe"]
    form = "pfa" if regime == "pfa" else "srl"

    def ob(oid, name, form_code, months, monthly, when):
        return {"id": oid, "name": name, "declaration": form_code, "months": months, "monthly": round(monthly, 2),
                "accrued": 0.0, "when": when, "form": form}

    if regime == "pfa":
        return [ob("du", "Impozit pe venit 10% + CAS + CASS", "Declarația unică", [5], result["total_taxe"] / 12,
                   "anual, până pe 25 mai, pentru venitul anului anterior")]
    out = []
    corp = t.get("impozit_micro_1", t.get("impozit_profit_16", 0.0))
    if corp:
        out.append(ob("d100", "Impozit micro 1%" if regime == "micro" else "Impozit pe profit 16% (plăți trimestriale)",
                      "D100" if regime == "micro" else "D100 / D101", QUARTER_MONTHS, corp / 12,
                      "trimestrial, până pe 25 a lunii următoare trimestrului"))
    salary = sum(t.get(k, 0.0) for k in ("salariu_cas", "salariu_cass", "salariu_impozit", "cam_angajator"))
    if salary:
        out.append(ob("d112", "Contribuții și impozit pe salarii (CAS, CASS, impozit, CAM)", "D112",
                      QUARTER_MONTHS if d112_quarterly else list(range(1, 13)), salary / 12,
                      "trimestrial (opțiune pentru max. 3 salariați)" if d112_quarterly else "lunar, până pe 25 a lunii următoare"))
    dividends = t.get("impozit_dividende_16", 0.0) + t.get("cass_dividende", 0.0)
    if dividends:
        out.append(ob("dividende", "Impozit pe dividende 16% + CASS pe dividende", "D100 + Declarația unică", [5], dividends / 12,
                      "la distribuirea anuală a dividendelor (aici: mai) și în Declarația unică"))
    return out


def fiscal_calendar(form: str, regime: str, start_year: int, start_month: int, months: int = 12,
                    has_salaried: bool = True, vat_payer: bool = False, d112_quarterly: bool = True) -> dict:
    regime = "pfa" if form.lower() == "pfa" else regime
    entries = []
    for i in range(months):
        y, m = start_year + (start_month - 1 + i) // 12, (start_month - 1 + i) % 12 + 1
        due = []
        if regime == "pfa":
            if m == 5:
                due.append(("Declarația unică", f"impozit pe venit, CAS și CASS pentru {y - 1}; și estimarea pentru {y}"))
        else:
            if m in QUARTER_MONTHS:
                q, qy = ((m - 2) % 12) // 3 + 1, y if m != 1 else y - 1
                due.append(("D100", f"impozit {'micro' if regime == 'micro' else 'pe profit'} pentru trimestrul {q} {qy}"))
            if has_salaried and (m in QUARTER_MONTHS or not d112_quarterly):
                due.append(("D112", "contribuții și impozit pe salarii" + (" (trimestrial)" if d112_quarterly else "")))
            if m == 5:
                due.append(("Situații financiare anuale", f"bilanțul pentru {y - 1} (în 150 de zile de la încheierea exercițiului)"))
                due.append(("Declarația unică (asociat)", "CASS pe dividende, dacă ai încasat dividende"))
            if regime == "profit" and m == 6:
                due.append(("D101", f"declarația anuală privind impozitul pe profit pentru {y - 1}"))
        if vat_payer and m in QUARTER_MONTHS:
            due.append(("D300 / D394", "decontul și declarația informativă de TVA (trimestrial)"))
        for code, what in due:
            day = 31 if code.startswith("Situații") else 25
            entries.append({"data": f"{day:02d}.{m:02d}.{y}", "declaratie": code, "ce": what})
    return {
        "forma": form.upper(), "regim": regime, "termene": entries,
        "intarziere": "Plata după termen: dobândă 0,02%/zi + penalitate 0,01%/zi (CPF art. 174, 176); "
                      "nedepunerea declarației: amendă 500–1.000 lei pentru persoane juridice mici, 50–500 lei pentru Declarația unică (CPF art. 336).",
        "avertisment": DISCLAIMER,
        "summary": f"{len(entries)} termene în următoarele {months} luni ({form.upper()}, {regime})",
    }


# ---------------------------------------------------------------- deductible expenses

PROFIT_TAX_SAVING = PROFIT_TAX
PFA_TAX_SAVING = INCOME_TAX + CASS_RATE * (1 - INCOME_TAX)  # impozit 10% + CASS 10% (în intervalul 6–72 salarii minime)

EXPENSE_RULES = {
    "software_abonamente": ("Licențe și abonamente software / cloud folosite în activitate", 1.0, None,
                            "Deductibile integral dacă sunt pentru activitate (CF art. 25 alin. (1); PFA art. 68 alin. (4))."),
    "echipament_sub_2500": ("Echipament (laptop, telefon, mobilier) cu valoare de intrare de cel mult 2.500 lei", 1.0, None,
                            "Se trece direct pe cheltuieli în luna achiziției."),
    "mijloc_fix_peste_2500": ("Echipament cu valoare peste 2.500 lei și durată de folosire peste 1 an (mijloc fix)", 1.0, "amortizare",
                              "Deductibil prin amortizare pe durata normală de folosire (ex. laptop ~3 ani), nu integral în luna cumpărării (CF art. 28)."),
    "chirie_birou": ("Chirie birou / coworking / spațiu comercial", 1.0, None, "Deductibilă integral, pe bază de contract și factură."),
    "locuinta_mixt_pfa": ("Utilități și chirie pentru locuința folosită parțial ca sediu (PFA)", None, "proportional",
                          "Deductibilă proporțional cu suprafața folosită pentru activitate (CF art. 68 alin. (4))."),
    "telefon_internet": ("Telefon, internet", 1.0, None, "Deductibile pentru activitate; la folosire mixtă, doar partea de business."),
    "protocol": ("Mese cu clienți, cadouri pentru parteneri (protocol)", None, "limita_2",
                 "Deductibile limitat: în cota de 2% din profitul contabil corectat (SRL, CF art. 25 alin. (3) lit. a)) "
                 "sau 2% din baza de calcul (PFA, art. 68 alin. (5) lit. a))."),
    "auto_mixt": ("Combustibil, reparații, leasing pentru autoturism folosit și personal", 0.5, None,
                  "Deductibile 50% (CF art. 25 alin. (3) lit. l); PFA art. 68). TVA dedus tot 50%."),
    "auto_exclusiv": ("Autoturism folosit exclusiv în activitate (cu foaie de parcurs)", 1.0, None,
                      "Deductibil 100% doar pentru categoriile prevăzute de lege și cu foi de parcurs."),
    "deplasari": ("Transport și cazare pentru deplasări de serviciu", 1.0, None, "Deductibile cu documente (facturi, ordin de deplasare)."),
    "marketing": ("Publicitate, marketing, site, reclame online", 1.0, None, "Deductibile integral pentru activitate."),
    "servicii_profesionale": ("Contabilitate, avocat, consultanță", 1.0, None, "Deductibile integral."),
    "formare_profesionala": ("Cursuri, cărți și conferințe legate de activitate", 1.0, None,
                             "Deductibile dacă sunt legate de activitate (PFA: art. 68 alin. (4))."),
    "asigurare_sanatate": ("Asigurare privată de sănătate / abonament medical", None, "plafon_400_eur",
                           "Deductibilă în limita a 400 euro/an/persoană."),
    "sponsorizare": ("Sponsorizări", 0.0, "credit_fiscal",
                     "Nu e cheltuială deductibilă; la SRL se scade din impozit (credit fiscal), în limitele legii (CF art. 25 alin. (4) lit. i))."),
    "amenzi_penalitati": ("Amenzi, penalități și dobânzi de întârziere datorate autorităților", 0.0, None,
                          "Nedeductibile (CF art. 25 alin. (4) lit. b))."),
    "personale": ("Cheltuieli personale (haine, mâncare zilnică, vacanțe)", 0.0, None, "Nedeductibile: nu sunt făcute în scopul activității."),
}
EXPENSE_CATEGORIES = list(EXPENSE_RULES)


def classify_expense(category: str, amount: float, regime: str, vat_payer: bool = False, business_share: float = 1.0) -> dict:
    if category not in EXPENSE_RULES:
        raise ValueError(f"categorie necunoscută; alege una din: {', '.join(EXPENSE_CATEGORIES)}")
    label, share, special, rule = EXPENSE_RULES[category]
    amount = float(amount)
    notes = []
    if special == "proportional":
        share = max(min(float(business_share), 1.0), 0.0)
        notes.append(f"Proporția folosită pentru activitate: {share:.0%}.")
    elif special == "limita_2":
        share = 1.0
        notes.append("Verifică plafonul de 2% la final de an; peste plafon, diferența devine nedeductibilă.")
    elif special == "plafon_400_eur":
        cap = 400 * EUR_RON
        share = min(1.0, cap / amount) if amount else 1.0
        notes.append(f"Plafon anual ~{cap:,.0f} lei/persoană.".replace(",", "."))
    elif special == "amortizare":
        share = 1.0
        notes.append(f"Amortizare liniară pe ~3 ani: ~{amount / 36:,.0f} lei/lună.".replace(",", "."))
    elif special == "credit_fiscal":
        notes.append("Poate fi scăzută din impozitul pe profit sau micro, în limitele legii.")
    deductible = amount * share
    if regime == "micro":
        saving = 0.0
        notes.append("La micro, impozitul de 1% se aplică pe venituri: cheltuiala NU reduce impozitul micro, "
                     "dar reduce profitul și deci dividendele (și impozitul pe dividende).")
    elif regime == "profit":
        saving = deductible * PROFIT_TAX_SAVING
    else:
        saving = deductible * PFA_TAX_SAVING
        notes.append("Economie estimată: impozit 10% + CASS 10% (dacă venitul net e între 6 și 72 de salarii minime).")
    vat = None
    if vat_payer:
        vat_share = 0.5 if category == "auto_mixt" else (0.0 if category in ("personale", "amenzi_penalitati") else 1.0)
        vat = f"TVA de dedus: {vat_share:.0%} din TVA-ul de pe factură (dacă factura e pe firmă și ai drept de deducere)."
    return {
        "categorie": label, "suma": _r(amount), "procent_deductibil": round(share * 100), "suma_deductibila": _r(deductible),
        "economie_impozit_estimata": _r(saving), "regula": rule, "note": notes, "tva": vat,
        "conditii": "Factura trebuie emisă pe PFA/firmă (cu CUI), cu plata dovedită și legată de activitate.",
        "summary": f"{label}: deductibil {share:.0%} ({deductible:,.0f} lei), economie impozit ~{saving:,.0f} lei".replace(",", "."),
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
