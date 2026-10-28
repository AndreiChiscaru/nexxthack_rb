extends RefCounted
## Consilierul AI al jocului: cinci unelte locale, transparente, care folosesc motorul financiar.
## Nu există nicio conexiune externă și niciun model de limbaj. Orice cifră e calculată de simulare.
## Fiecare mesaj: {"type": "tool"|"say", ...}

const Sim := preload("res://scripts/raiff/finance_sim.gd")
const Catalog := preload("res://scripts/raiff/catalog.gd")

# ---------------------------------------------------------------- tool 1

static func get_player_profile(s: Dictionary) -> Dictionary:
	var em := Sim.emergency_months(s)
	var ratio := Sim.dsr(s)
	var risk := "ridicată"
	if em < 3.0 or ratio > 0.35:
		risk = "scăzută"
	elif em < 6.0 or ratio > 0.2:
		risk = "medie"
	var data := {
		"name": s.name, "age": s.age, "income": Sim.income(s), "living": s.living,
		"surplus": Sim.monthly_surplus(s), "dsr": ratio, "em_months": em,
		"risk_capacity": risk, "dependents": 0,
	}
	return {
		"type": "tool", "name": "get_player_profile", "args": "()", "data": data,
		"summary": "venit net %s/lună, cheltuieli %s, rate %s, surplus %s. Fond de urgență: %s luni. Capacitate de risc: %s." % [
			Sim.money(data.income), Sim.money(float(s.living)), Sim.money(Sim.debt_payments(s)),
			Sim.money(data.surplus), ("%.1f" % em).replace(".", ","), risk],
	}

# ---------------------------------------------------------------- tool 2

## Rulează simularea de 36 de luni pentru o opțiune, pe o copie a stării.
static func simulate_decision(s: Dictionary, option: Dictionary, shock: float) -> Dictionary:
	var copy := Sim.clone(s)
	var rep := Sim.resolve(copy, option, shock)
	rep["interest_total"] = float(rep.interest_paid)
	rep["stress"] = float(copy.stress)
	rep["confidence"] = float(copy.confidence)
	return rep

static func simulate_all(s: Dictionary, event: Dictionary, shock: float) -> Array:
	var out: Array = []
	var i := 0
	for option: Dictionary in event.options:
		var rep := simulate_decision(s, option, shock)
		rep["index"] = i
		rep["title"] = option.title
		out.append(rep)
		i += 1
	return out

static func best_index(results: Array) -> int:
	var best := 0
	var best_value := -INF
	for r: Dictionary in results:
		if float(r.value) > best_value:
			best_value = float(r.value)
			best = int(r.index)
	return best

static func letter(i: int) -> String:
	return char(65 + i)

# ---------------------------------------------------------------- tool 3 + 4

static func search_products(category: String) -> Dictionary:
	var found := Catalog.by_category(category)
	var names: Array = []
	for p: Dictionary in found:
		names.append(str(p.name))
	return {
		"type": "tool", "name": "search_products", "args": "(categorie=\"%s\")" % category, "data": found,
		"summary": "%d produse demo: %s." % [found.size(), ", ".join(names)] if not found.is_empty() else "niciun produs relevant.",
	}

static func compare_products(spec: Dictionary) -> Dictionary:
	var p := Catalog.by_id(str(spec.product))
	var amount := float(spec.amount)
	var lines: Array = []
	var rows: Array = []
	for months: int in spec.months:
		var pay := Sim.pmt(amount, float(p.apr), months)
		var total_interest := pay * months - amount
		rows.append({"months": months, "payment": pay, "interest": total_interest})
		lines.append("%d luni: %s/lună, dobândă totală %s" % [months, Sim.money(pay), Sim.money(total_interest)])
	var summary := "%s, %s la %s. %s." % [p.name, Sim.money(amount), Sim.pct(float(p.apr)), "; ".join(lines)]
	if rows.size() >= 2:
		var diff := absf(float(rows[0].interest) - float(rows[1].interest))
		summary += " Diferența de dobândă dintre variante: %s." % Sim.money(diff)
	return {
		"type": "tool", "name": "compare_products",
		"args": "(%s, %s, [%s])" % [p.id, Sim.money(amount), ", ".join(spec.months.map(func(m: int) -> String: return str(m)))],
		"data": rows, "summary": summary,
	}

# ---------------------------------------------------------------- tool 5

static func generate_action_plan(s: Dictionary) -> Dictionary:
	var steps: Array = []
	var em := Sim.emergency_months(s)
	if float(s.overdraft) > 0.5:
		steps.append({"title": "Închide descoperitul de cont", "why": "Plătești 30%% dobândă pe %s." % Sim.money(float(s.overdraft)), "product": "cont_economii"})
	var worst_apr := 0.0
	var worst_name := ""
	for loan: Dictionary in s.loans:
		if float(loan.apr) > worst_apr:
			worst_apr = float(loan.apr)
			worst_name = str(loan.name)
	if worst_apr >= 0.12:
		steps.append({"title": "Rambursează anticipat „%s”" % worst_name, "why": "Dobânda de %s este mai mare decât orice randament sigur." % Sim.pct(worst_apr), "product": "credit_nevoi"})
	if em < 6.0:
		var missing := Sim.emergency_target(s) - float(s.emergency)
		steps.append({"title": "Completează fondul de urgență", "why": "Mai ai nevoie de %s ca să ajungi la 6 luni de cheltuieli (acum: %s luni)." % [Sim.money(missing), ("%.1f" % em).replace(".", ",")], "product": "cont_economii"})
	if int(s.insurance_level) < 2:
		steps.append({"title": "Acoperă riscurile mari", "why": "Fără protecție completă, o urgență medicală îți poate consuma anii de economii.", "product": "asig_complet"})
	if em >= 3.0 and Sim.dsr(s) < 0.3:
		var amount := maxf(roundf(maxf(Sim.monthly_surplus(s), 0.0) * 0.3 / 50.0) * 50.0, 200.0)
		steps.append({"title": "Investește lunar %s" % Sim.money(amount), "why": "Pe termen lung, investițiile regulate bat banii ținuți în cont.", "product": "fond_diversificat"})
	if float(s.invest_contrib) < 400.0:
		steps.append({"title": "Începe o contribuție pentru pensie", "why": "Timpul este cel mai valoros ingredient: începe devreme, chiar și cu sume mici.", "product": "pilon3"})
	if steps.is_empty():
		steps.append({"title": "Păstrează direcția", "why": "Bugetul este echilibrat. Revizuiește-l o dată pe an.", "product": "cont_economii"})
	if steps.size() > 4:
		steps = steps.slice(0, 4)
	var titles: Array = []
	for st: Dictionary in steps:
		titles.append(str(st.title))
	return {
		"type": "tool", "name": "generate_action_plan", "args": "(profil, sold curent)", "data": steps,
		"summary": "%d pași: %s." % [steps.size(), "; ".join(titles)],
	}

# ---------------------------------------------------------------- orchestrare

## Sfat înainte de decizie: profil -> simulări -> produse -> comparație -> recomandare.
static func advise_before(s: Dictionary, event: Dictionary) -> Dictionary:
	var messages: Array = []
	var shock := 0.0
	messages.append({"type": "say", "text": "Să analizăm „%s”. Rulez instrumentele mele pe datele tale fictive." % event.title})
	messages.append(get_player_profile(s))
	var results := simulate_all(s, event, shock)
	for r: Dictionary in results:
		messages.append({
			"type": "tool", "name": "simulate_decision", "args": "(%s, 36 luni)" % letter(int(r.index)), "data": r,
			"summary": "%s: patrimoniu net la %d ani %s, dobândă plătită %s, rate %s/lună, stres %d/100." % [
				r.title, int(r.after.age), Sim.money(float(r.net_worth)), Sim.money(float(r.interest_paid)),
				Sim.money(float(r.monthly_payments)), int(round(float(r.stress)))],
		})
	var category := str(event.get("category", ""))
	if category != "":
		messages.append(search_products(category))
	if event.has("compare"):
		messages.append(compare_products(event.compare))
	var best := best_index(results)
	var best_r: Dictionary = results[best]
	var text := "Recomandarea mea: varianta %s, „%s”." % [letter(best), best_r.title]
	text += " " + _reasons(best_r, results)
	text += " (Estimare fără șocuri de piață; viitorul poate diferi.)"
	messages.append({"type": "say", "text": text})
	return {"messages": messages, "best": best}

## Explicație după decizie: compară alegerea cu celelalte variante, cu șocul real de piață.
static func explain_after(before: Dictionary, event: Dictionary, chosen: int, actual_shock: float, after_state: Dictionary) -> Dictionary:
	var results := simulate_all(before, event, actual_shock)
	var best := best_index(results)
	var mine: Dictionary = results[chosen]
	var best_r: Dictionary = results[best]
	var messages: Array = []
	messages.append({"type": "say", "text": "Ai ales %s, „%s”." % [letter(chosen), mine.title]})
	messages.append({
		"type": "tool", "name": "simulate_decision", "args": "(%s vs. %s, piață reală)" % [letter(chosen), letter(best)],
		"data": results,
		"summary": "ai %s patrimoniu net, față de %s la varianta %s." % [Sim.money(float(mine.net_worth)), Sim.money(float(best_r.net_worth)), letter(best)],
	})
	if event.has("compare"):
		messages.append(compare_products(event.compare))
	var diff := float(best_r.net_worth) - float(mine.net_worth)
	var verdict := ""
	if chosen == best or absf(float(best_r.value) - float(mine.value)) < 300.0:
		verdict = "Bună alegere: este printre cele mai bune variante pentru situația ta."
	else:
		verdict = "Varianta %s ar fi lăsat %s în plus în patrimoniul net." % [letter(best), Sim.money(maxf(diff, 0.0))] if diff > 300.0 else "Varianta %s ar fi redus stresul sau riscul." % letter(best)
	verdict += " " + _reasons(mine, results)
	verdict += " Lecție: " + str(event.lesson)
	messages.append({"type": "say", "text": verdict})
	messages.append(generate_action_plan(after_state))
	return {
		"messages": messages, "best": best, "results": results,
		"regret": maxf(float(best_r.value) - float(mine.value), 0.0),
	}

static func _reasons(r: Dictionary, all_results: Array) -> String:
	var parts: Array = []
	var lowest_interest := INF
	for other: Dictionary in all_results:
		lowest_interest = minf(lowest_interest, float(other.interest_paid))
	if float(r.interest_paid) - lowest_interest > 500.0:
		parts.append("Plătești cu %s mai multă dobândă decât cea mai ieftină variantă." % Sim.money(float(r.interest_paid) - lowest_interest))
	if float(r.overdraft) > 0.5 or int(r.overdraft_months) > 0:
		parts.append("Ajungi în descoperit de cont %d luni (dobândă 30%%), ceea ce e foarte scump." % int(r.overdraft_months))
	if float(r.emergency_months) < 3.0:
		parts.append("Fondul de urgență rămâne sub 3 luni de cheltuieli.")
	elif float(r.emergency_months) >= 6.0:
		parts.append("Fondul de urgență acoperă 6 luni sau mai mult.")
	if float(r.monthly_payments) > 0.0:
		parts.append("Ratele lunare ajung la %s." % Sim.money(float(r.monthly_payments)))
	if parts.is_empty():
		parts.append("Nu apar riscuri majore în următorii 3 ani.")
	return " ".join(parts)

## Răspuns la întrebările rapide din panou.
static func quick_profile(s: Dictionary) -> Array:
	return [
		{"type": "say", "text": "Iată situația ta de acum."},
		get_player_profile(s),
	]

static func quick_plan(s: Dictionary) -> Array:
	var plan := generate_action_plan(s)
	var messages: Array = [{"type": "say", "text": "Pe baza situației tale, ordinea mea de priorități este:"}, get_player_profile(s), plan]
	var i := 1
	for st: Dictionary in plan.data:
		var product := Catalog.by_id(str(st.product))
		messages.append({"type": "say", "text": "%d. %s - %s Produs demo potrivit: %s." % [i, st.title, st.why, product.get("name", "-")]})
		i += 1
	return messages

static func quick_products(s: Dictionary) -> Array:
	var messages: Array = [{"type": "say", "text": "Caut în catalogul demo ce se potrivește profilului tău."}, get_player_profile(s)]
	var em := Sim.emergency_months(s)
	var category := "savings" if em < 6.0 else "investment"
	messages.append(search_products(category))
	messages.append(generate_action_plan(s))
	messages.append({"type": "say", "text": "Reține: toate produsele sunt fictive, cu termeni inventați pentru joc."})
	return messages
