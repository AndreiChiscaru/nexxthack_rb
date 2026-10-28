extends RefCounted
## Motorul financiar al jocului Raiff Quest. Totul este fictiv și determinist:
## aceeași stare + aceeași decizie + același șoc de piață => același rezultat.
## Sumele sunt în lei (RON). O perioadă = 36 de luni (3 ani).

const MONTHS_PER_PERIOD := 36
const PERIODS := 10
const START_AGE := 22
const OVERDRAFT_APR := 0.30
const OVERDRAFT_LIMIT := 15000.0
const EMERGENCY_APR := 0.03
const DEPOSIT_APR := 0.045
const FUND_APR := 0.07
const SALARY_GROWTH := 0.04
const LIVING_INFLATION := 0.04
const LIFESTYLE_CREEP := 0.6
const CAR_DEPRECIATION := 0.12
const INSURANCE_COVERAGE := [0.0, 0.35, 0.85]

## `profile` (opțional): situația reală a jucătorului, calculată de server din extrasul de cont.
static func new_state(seed_value: int, profile: Dictionary = {}) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var shocks: Array = []
	for i in PERIODS:
		shocks.append(snappedf(rng.randf_range(-0.06, 0.04), 0.005))
	var s := {
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
		"from_statement": false,
	}
	if not profile.is_empty():
		apply_profile(s, profile)
	s["history"].append(snapshot(s))
	return s

static func apply_profile(s: Dictionary, p: Dictionary) -> void:
	if p.get("name") != null:
		s.name = str(p.name)
	for key: String in ["salary", "living", "cash", "emergency", "home_value", "stress", "confidence"]:
		if p.get(key) != null:
			s[key] = maxf(float(p[key]), 0.0)
	s.overdraft = clampf(float(p.get("overdraft", 0.0)), 0.0, OVERDRAFT_LIMIT)
	for loan: Dictionary in p.get("loans", []):
		if float(loan.get("principal", 0.0)) > 0.5 and int(loan.get("months", 0)) > 0:
			add_loan(s, str(loan.get("name", "Credit existent")), float(loan.principal), float(loan.get("apr", 0.1)), int(loan.months))
	s.from_statement = true

static func clone(s: Dictionary) -> Dictionary:
	return s.duplicate(true)

# ---------------------------------------------------------------- formatting

static func money(x: float) -> String:
	var v := int(round(absf(x)))
	var digits := str(v)
	var out := ""
	var count := 0
	for i in range(digits.length() - 1, -1, -1):
		out = digits[i] + out
		count += 1
		if count % 3 == 0 and i > 0:
			out = "." + out
	var sign := "-" if x < -0.5 else ""
	return "%s%s lei" % [sign, out]

static func signed_money(x: float) -> String:
	if absf(x) < 0.5:
		return "0 lei"
	return ("+" if x > 0.0 else "") + money(x)

static func pct(x: float) -> String:
	return ("%.1f" % (x * 100.0)).replace(".", ",") + "%"

# ---------------------------------------------------------------- derived values

static func pmt(principal: float, apr: float, months: int) -> float:
	if months <= 0:
		return principal
	if apr <= 0.00001:
		return principal / float(months)
	var r := apr / 12.0
	return principal * r / (1.0 - pow(1.0 + r, -float(months)))

static func months_left_for(principal: float, apr: float, payment: float) -> int:
	if principal <= 0.5:
		return 0
	if apr <= 0.00001:
		return int(ceil(principal / maxf(payment, 1.0)))
	var r := apr / 12.0
	if payment <= principal * r:
		return 999
	return int(ceil(-log(1.0 - principal * r / payment) / log(1.0 + r)))

static func income(s: Dictionary) -> float:
	return float(s.salary) + float(s.side_income)

static func debt_payments(s: Dictionary) -> float:
	var total := 0.0
	for loan: Dictionary in s.loans:
		if int(loan.months_left) > 0:
			total += minf(float(loan.payment), float(loan.principal) * (1.0 + float(loan.apr) / 12.0))
	return total

static func total_debt(s: Dictionary) -> float:
	var total := float(s.overdraft)
	for loan: Dictionary in s.loans:
		total += float(loan.principal)
	return total

static func investments(s: Dictionary) -> float:
	return float(s.deposit) + float(s.fund)

static func net_worth(s: Dictionary) -> float:
	return float(s.cash) + float(s.emergency) + investments(s) + float(s.car_value) + float(s.business_value) + float(s.get("home_value", 0.0)) - total_debt(s)

static func emergency_target(s: Dictionary) -> float:
	return float(s.living) * 6.0

static func emergency_months(s: Dictionary) -> float:
	return float(s.emergency) / maxf(float(s.living), 1.0)

static func dsr(s: Dictionary) -> float:
	return debt_payments(s) / maxf(income(s), 1.0)

static func monthly_surplus(s: Dictionary) -> float:
	return income(s) - float(s.living) - debt_payments(s) - float(s.insurance_premium)

static func snapshot(s: Dictionary) -> Dictionary:
	return {
		"age": int(s.age),
		"net_worth": net_worth(s),
		"cash": float(s.cash),
		"emergency": float(s.emergency),
		"investments": investments(s),
		"debt": total_debt(s),
		"stress": float(s.stress),
		"confidence": float(s.confidence),
	}

# ---------------------------------------------------------------- operations

## Plătește o sumă: numerar, apoi fond de urgență, apoi depozit; restul intră în descoperit.
static func spend(s: Dictionary, amount: float) -> void:
	var rest := amount
	for key: String in ["cash", "emergency", "deposit"]:
		var take := minf(float(s[key]), rest)
		s[key] = float(s[key]) - take
		rest -= take
	if rest > 0.0:
		s.overdraft = float(s.overdraft) + rest

static func add_loan(s: Dictionary, name: String, principal: float, apr: float, months: int) -> void:
	s.loans.append({
		"name": name,
		"principal": principal,
		"apr": apr,
		"months_left": months,
		"payment": pmt(principal, apr, months),
		"original": principal,
	})

## Rambursare anticipată: întâi descoperitul, apoi creditele cu dobânda cea mai mare. Rata rămâne, termenul scade.
static func prepay(s: Dictionary, amount: float) -> float:
	var rest := amount
	var od := minf(float(s.overdraft), rest)
	s.overdraft = float(s.overdraft) - od
	rest -= od
	var sorted: Array = s.loans.duplicate()
	sorted.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a.apr) > float(b.apr))
	for loan: Dictionary in sorted:
		if rest <= 0.0:
			break
		var pay := minf(float(loan.principal), rest)
		loan.principal = float(loan.principal) - pay
		rest -= pay
		loan.months_left = months_left_for(float(loan.principal), float(loan.apr), float(loan.payment))
	_remove_paid_loans(s)
	return rest

static func fill_safe(s: Dictionary, amount: float) -> void:
	var room := maxf(emergency_target(s) - float(s.emergency), 0.0)
	var to_em := minf(room, amount)
	s.emergency = float(s.emergency) + to_em
	s.deposit = float(s.deposit) + (amount - to_em)

static func _remove_paid_loans(s: Dictionary) -> void:
	var keep: Array = []
	for loan: Dictionary in s.loans:
		if float(loan.principal) > 0.5 and int(loan.months_left) > 0:
			keep.append(loan)
	s.loans = keep

## Aplică efectele imediate ale unei opțiuni. Returnează modificarea de dispoziție (stres/încredere) și note.
static func apply_ops(s: Dictionary, ops: Dictionary, notes: Array) -> Dictionary:
	if ops.has("spend"):
		spend(s, float(ops.spend))
	if ops.has("loan"):
		var l: Dictionary = ops.loan
		add_loan(s, str(l.name), float(l.principal), float(l.apr), int(l.months))
	if ops.has("salary_mult"):
		var raise_amount := float(s.salary) * (float(ops.salary_mult) - 1.0)
		s.salary = float(s.salary) + raise_amount
		s.living = float(s.living) + raise_amount * LIFESTYLE_CREEP
	if ops.has("salary_add"):
		s.salary = float(s.salary) + float(ops.salary_add)
		s.living = float(s.living) + float(ops.salary_add) * LIFESTYLE_CREEP
	if ops.has("living_add"):
		s.living = float(s.living) + float(ops.living_add)
	if ops.has("side_income_add"):
		s.side_income = float(s.side_income) + float(ops.side_income_add)
		s.living = float(s.living) + float(ops.side_income_add) * 0.3
	if ops.has("business_value"):
		s.business_value = float(s.business_value) + float(ops.business_value)
	if ops.has("car_value"):
		s.car_value = float(s.car_value) + float(ops.car_value)
	if ops.has("emergency_contrib"):
		s.emergency_contrib = float(ops.emergency_contrib)
	if ops.has("invest_contrib"):
		s.invest_contrib = float(ops.invest_contrib)
	if ops.has("insurance_level"):
		s.insurance_level = int(ops.insurance_level)
		s.insurance_premium = float(ops.get("insurance_premium", 0.0))
	if ops.has("medical_cost"):
		var coverage: float = INSURANCE_COVERAGE[clampi(int(s.insurance_level), 0, 2)]
		var gross := float(ops.medical_cost)
		var net := gross * (1.0 - coverage)
		notes.append("Asigurarea a acoperit %s din %s." % [money(gross - net), money(gross)])
		var fin := int(ops.get("finance_months", 0))
		if fin > 0:
			add_loan(s, "Plată în rate clinică", net, 0.0, fin)
		else:
			spend(s, net)
	if ops.has("bonus"):
		var b: Dictionary = ops.bonus
		var amount := float(b.amount)
		match str(b.mode):
			"prepay":
				var left := prepay(s, amount)
				if left > 0.0:
					fill_safe(s, left)
					notes.append("După rambursare au rămas %s, mutați în fondul de urgență/depozit." % money(left))
			"fund":
				s.fund = float(s.fund) + amount
			"safe":
				fill_safe(s, amount)
			"spend":
				var spent := float(b.spend)
				fill_safe(s, amount - spent)
	var mood: Dictionary = ops.get("mood", {})
	return {"stress": float(mood.get("stress", 0.0)), "confidence": float(mood.get("conf", 0.0))}

# ---------------------------------------------------------------- simulation

static func simulate_period(s: Dictionary, shock: float) -> Dictionary:
	var rep := {
		"interest_paid": 0.0,
		"overdraft_months": 0,
		"austerity_months": 0,
		"invest_gain": 0.0,
		"loans_closed": 0,
		"start": snapshot(s),
		"shock": shock,
	}
	var loans_before: int = s.loans.size()
	for m in MONTHS_PER_PERIOD:
		_month(s, shock, rep)
		if (m + 1) % 12 == 0:
			s.salary = float(s.salary) * (1.0 + SALARY_GROWTH)
			s.living = float(s.living) * (1.0 + LIVING_INFLATION)
			s.side_income = float(s.side_income) * 1.03
			s.car_value = float(s.car_value) * (1.0 - CAR_DEPRECIATION)
	rep["loans_closed"] = maxi(loans_before - s.loans.size(), 0)
	s.age = int(s.age) + 3
	s.period = int(s.period) + 1
	s.interest_paid_total = float(s.interest_paid_total) + float(rep.interest_paid)
	_update_wellbeing(s, rep)
	return rep

static func _month(s: Dictionary, shock: float, rep: Dictionary) -> void:
	var inc := income(s)
	var paid := 0.0
	for loan: Dictionary in s.loans:
		if int(loan.months_left) <= 0:
			continue
		var interest := float(loan.principal) * float(loan.apr) / 12.0
		var pay := minf(float(loan.payment), float(loan.principal) + interest)
		if int(loan.months_left) == 1:
			pay = float(loan.principal) + interest
		loan.principal = float(loan.principal) + interest - pay
		loan.months_left = int(loan.months_left) - 1
		rep.interest_paid = float(rep.interest_paid) + interest
		paid += pay
		if int(loan.months_left) <= 0:
			loan.principal = 0.0
	_remove_paid_loans(s)
	if float(s.overdraft) > 0.0:
		var od_interest := float(s.overdraft) * OVERDRAFT_APR / 12.0
		s.overdraft = float(s.overdraft) + od_interest
		rep.interest_paid = float(rep.interest_paid) + od_interest
	s.cash = float(s.cash) + inc - float(s.living) - paid - float(s.insurance_premium)
	# Contribuții automate (doar din numerar disponibil)
	if float(s.emergency_contrib) > 0.0 and float(s.emergency) < emergency_target(s):
		var ec := minf(minf(float(s.emergency_contrib), emergency_target(s) - float(s.emergency)), maxf(float(s.cash), 0.0))
		s.emergency = float(s.emergency) + ec
		s.cash = float(s.cash) - ec
	if float(s.invest_contrib) > 0.0:
		var ic := minf(float(s.invest_contrib), maxf(float(s.cash), 0.0))
		s.fund = float(s.fund) + ic
		s.cash = float(s.cash) - ic
	if float(s.cash) < 0.0:
		var deficit := -float(s.cash)
		s.cash = 0.0
		for key: String in ["emergency", "deposit"]:
			var take := minf(float(s[key]), deficit)
			s[key] = float(s[key]) - take
			deficit -= take
		s.overdraft = float(s.overdraft) + deficit
	elif float(s.overdraft) > 0.0 and float(s.cash) > 0.0:
		var repay := minf(float(s.cash), float(s.overdraft))
		s.cash = float(s.cash) - repay
		s.overdraft = float(s.overdraft) - repay
	if float(s.overdraft) > 0.5:
		rep.overdraft_months = int(rep.overdraft_months) + 1
	if float(s.overdraft) > OVERDRAFT_LIMIT:
		# Banca nu mai acordă descoperit: ajustezi forțat cheltuielile (austeritate).
		s.overdraft = OVERDRAFT_LIMIT
		rep.austerity_months = int(rep.austerity_months) + 1
	s.emergency = float(s.emergency) * (1.0 + EMERGENCY_APR / 12.0)
	s.deposit = float(s.deposit) * (1.0 + DEPOSIT_APR / 12.0)
	var gain := float(s.fund) * (FUND_APR + shock) / 12.0
	s.fund = float(s.fund) + gain
	rep.invest_gain = float(rep.invest_gain) + gain

static func _update_wellbeing(s: Dictionary, rep: Dictionary) -> void:
	var em := emergency_months(s)
	var ratio := dsr(s)
	var stress_target := 30.0
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
	if float(s.overdraft) > 0.5:
		stress_target += 14.0
	if int(rep.austerity_months) > 0:
		stress_target += 14.0
	var conf_target := 40.0
	if em >= 3.0:
		conf_target += 12.0
	if em >= 6.0:
		conf_target += 8.0
	if net_worth(s) > float(rep.start.net_worth):
		conf_target += 8.0
	if investments(s) > income(s) * 6.0:
		conf_target += 8.0
	if float(s.overdraft) > 0.5:
		conf_target -= 15.0
	if int(rep.austerity_months) > 0:
		conf_target -= 12.0
	if ratio > 0.35:
		conf_target -= 10.0
	s.stress = clampf(0.4 * float(s.stress) + 0.6 * stress_target, 0.0, 100.0)
	s.confidence = clampf(0.4 * float(s.confidence) + 0.6 * conf_target, 0.0, 100.0)

## Aplică opțiunea, rulează 36 de luni și aplică efectul emoțional al deciziei.
## `s` este modificat; pentru scenarii "ce-ar fi dacă" trimite o copie.
static func resolve(s: Dictionary, option: Dictionary, shock: float) -> Dictionary:
	var notes: Array = []
	var before := snapshot(s)
	var mood := apply_ops(s, option.get("ops", {}), notes)
	var after_ops := snapshot(s)
	var rep := simulate_period(s, shock)
	s.stress = clampf(float(s.stress) + float(mood.stress), 0.0, 100.0)
	s.confidence = clampf(float(s.confidence) + float(mood.confidence), 0.0, 100.0)
	rep["notes"] = notes
	rep["before"] = before
	rep["after_ops"] = after_ops
	rep["after"] = snapshot(s)
	rep["net_worth"] = net_worth(s)
	rep["monthly_payments"] = debt_payments(s)
	rep["emergency_months"] = emergency_months(s)
	rep["overdraft"] = float(s.overdraft)
	rep["value"] = decision_value(rep)
	return rep

## Scor folosit pentru a compara variante: patrimoniu net, ajustat cu stresul și încrederea.
static func decision_value(rep: Dictionary) -> float:
	var after: Dictionary = rep.after
	return float(after.net_worth) - 120.0 * float(after.stress) + 60.0 * float(after.confidence)

# ---------------------------------------------------------------- final score

static func resilience_score(s: Dictionary) -> int:
	var score := 0.0
	score += clampf(emergency_months(s) / 6.0, 0.0, 1.0) * 30.0
	score += (1.0 - clampf(dsr(s) / 0.4, 0.0, 1.0)) * 20.0
	score += clampf(net_worth(s) / (income(s) * 12.0 * 3.0), 0.0, 1.0) * 30.0
	score += (1.0 - float(s.stress) / 100.0) * 10.0
	score += float(s.confidence) / 100.0 * 10.0
	if float(s.overdraft) > 0.5:
		score -= 10.0
	return int(clampf(round(score), 0.0, 100.0))

static func archetype(score: int) -> String:
	if score >= 80:
		return "Arhitectul stabilității"
	if score >= 60:
		return "Constructor prudent"
	if score >= 40:
		return "Echilibrist în progres"
	return "Supraviețuitor de la lună la lună"

## Capital estimat la 67 de ani (15 ani după final), randament mediu 6%/an. Estimare, nu promisiune.
static func retirement_projection(s: Dictionary) -> float:
	var years := 67 - int(s.age)
	var r := 0.06
	var base := investments(s) + float(s.emergency) * 0.5
	var fv := base * pow(1.0 + r, years)
	fv += float(s.invest_contrib) * 12.0 * ((pow(1.0 + r, years) - 1.0) / r)
	return fv
