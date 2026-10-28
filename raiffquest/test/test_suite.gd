extends Node
## Teste Raiff Quest: motor financiar, unelte Consilier, glife românești și un joc complet de la titlu la raport.

const Sim := preload("res://scripts/raiff/finance_sim.gd")
const Events := preload("res://scripts/raiff/events.gd")
const Advisor := preload("res://scripts/raiff/advisor.gd")
const Catalog := preload("res://scripts/raiff/catalog.gd")
const GameScene := preload("res://scenes/raiff_main.tscn")

var _failures := PackedStringArray()
var _checks := 0

func _ready() -> void:
	call_deferred("_run")

func _run() -> void:
	_test_math()
	_test_events_and_catalog()
	_test_every_option_is_finite()
	_test_strategies_differ()
	_test_advisor_tools()
	_test_statement_profile()
	_test_glyph_coverage()
	await _test_full_playthrough()
	_finish()

func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)

func _approx(a: float, b: float, tolerance: float) -> bool:
	return absf(a - b) <= tolerance

func _play(strategy: Array, seed_value: int = 1) -> Dictionary:
	var s := Sim.new_state(seed_value)
	var events := Events.all()
	for i in events.size():
		var idx: int = mini(int(strategy[i]), events[i].options.size() - 1)
		Sim.resolve(s, events[i].options[idx], float(s.shocks[i]))
	return s

# ---------------------------------------------------------------- teste

func _test_math() -> void:
	var payment := Sim.pmt(12000.0, 0.12, 12)
	_check(_approx(payment, 1066.19, 0.5), "pmt 12000 la 12%% pe 12 luni ≈ 1066,19 (primit %s)" % payment)
	_check(_approx(Sim.pmt(1200.0, 0.0, 12), 100.0, 0.001), "pmt fără dobândă = principal / luni")
	var s := Sim.new_state(7)
	_check(int(s.age) == 22, "personajul începe la 22 de ani")
	_check(s.shocks.size() == 10, "zece șocuri de piață, câte unul per decizie")
	var again := Sim.new_state(7)
	_check(s.shocks == again.shocks, "aceeași sămânță dă aceleași șocuri")
	_check(Sim.money(1234.0).contains("1.234"), "formatul banilor folosește punct pentru mii: " + Sim.money(1234.0))
	_check(Sim.money(1234.0).contains("lei"), "formatul banilor conține lei")
	var loan_state := Sim.new_state(1)
	var option := {"ops": {"loan": {"name": "Test", "principal": 10000.0, "apr": 0.1, "months": 36}}}
	Sim.resolve(loan_state, option, 0.0)
	_check(_approx(Sim.total_debt(loan_state), 0.0, 5.0), "creditul de 36 de luni este achitat după 36 de luni (rest %s)" % Sim.total_debt(loan_state))

func _test_events_and_catalog() -> void:
	var events := Events.all()
	_check(events.size() == 10, "exact 10 decizii")
	var locations := {}
	var age := 0
	for ev: Dictionary in events:
		locations[ev.location] = true
		_check(int(ev.age) > age, "vârstele cresc: %s" % ev.title)
		age = int(ev.age)
		_check(ev.options.size() >= 3 and ev.options.size() <= 4, "3-4 opțiuni la " + str(ev.title))
		_check(str(ev.lesson) != "", "lecție la " + str(ev.title))
	_check(locations.size() == 5, "toate cele 5 locații au decizii (%d)" % locations.size())
	for loc: String in ["home", "bank", "work", "shop", "advisor"]:
		_check(locations.has(loc), "locație folosită: " + loc)
	_check(Catalog.all().size() >= 8, "catalog de produse demo")
	_check(Catalog.by_category("savings").size() >= 1, "produse pentru economii")
	_check(Catalog.by_id("credit_auto").has("apr"), "credit auto are dobândă")

func _test_every_option_is_finite() -> void:
	var events := Events.all()
	for seed_value in [1, 2, 3]:
		var s := Sim.new_state(seed_value)
		for i in events.size():
			for opt: Dictionary in events[i].options:
				var rep := Sim.resolve(Sim.clone(s), opt, float(s.shocks[i]))
				var nw := float(rep.after.net_worth)
				_check(not is_nan(nw) and not is_inf(nw) and absf(nw) < 100000000.0, "valoare finită: %s / %s" % [events[i].id, opt.title])
				_check(float(rep.after.stress) >= 0.0 and float(rep.after.stress) <= 100.0, "stres în 0-100")
			Sim.resolve(s, events[i].options[0], float(s.shocks[i]))
		_check(float(s.overdraft) <= Sim.OVERDRAFT_LIMIT + 1.0, "descoperitul respectă plafonul")

func _test_strategies_differ() -> void:
	var prudent := _play([0, 2, 0, 0, 0, 0, 0, 0, 1, 1])
	var careless := _play([1, 0, 3, 0, 0, 2, 2, 1, 3, 2])
	var reckless := _play([1, 1, 0, 3, 2, 2, 3, 1, 0, 2])
	var p := Sim.resilience_score(prudent)
	var c := Sim.resilience_score(careless)
	var r := Sim.resilience_score(reckless)
	_check(p > c and c > r, "scorul diferențiază strategiile: prudent %d > neglijent %d > riscant %d" % [p, c, r])
	_check(p <= 100 and r >= 0, "scorul rămâne în 0-100")
	_check(Sim.net_worth(prudent) > Sim.net_worth(reckless), "strategia prudentă ajunge la patrimoniu mai mare")
	_check(Sim.archetype(p) != Sim.archetype(r), "arhetipuri diferite")
	_check(int(prudent.age) == 52, "la final personajul are 52 de ani (%d)" % int(prudent.age))

func _test_advisor_tools() -> void:
	var s := Sim.new_state(3)
	var events := Events.all()
	var profile := Advisor.get_player_profile(s)
	_check(profile.name == "get_player_profile" and str(profile.summary).length() > 20, "get_player_profile are rezumat")
	var ev: Dictionary = events[2]
	var results := Advisor.simulate_all(s, ev, 0.0)
	_check(results.size() == ev.options.size(), "simulate_decision rulează pentru toate opțiunile")
	var advice := Advisor.advise_before(s, ev)
	var tools := 0
	for m: Dictionary in advice.messages:
		if m.type == "tool":
			tools += 1
	_check(tools >= 5, "sfatul rulează cel puțin 5 apeluri de unelte (%d)" % tools)
	_check(int(advice.best) >= 0 and int(advice.best) < ev.options.size(), "opțiune recomandată validă")
	var compare := Advisor.compare_products(ev.compare)
	_check(str(compare.summary).contains("Diferența de dobândă"), "compare_products calculează diferența de dobândă")
	var plan := Advisor.generate_action_plan(s)
	_check(plan.data.size() >= 1, "planul de acțiune are pași")
	var before := Sim.clone(s)
	Sim.resolve(s, ev.options[0], 0.0)
	var after := Advisor.explain_after(before, ev, 0, 0.0, s)
	_check(after.messages.size() >= 3, "explicația de după decizie are mesaje")
	_check(float(after.regret) >= 0.0, "regretul nu e negativ")

func _test_statement_profile() -> void:
	var profile := {
		"name": "Ion Popescu", "salary": 6850.0, "living": 2320.0, "cash": 5309.81, "overdraft": 0.0,
		"emergency": 0.0, "home_value": 387000.0, "stress": 45.0, "confidence": 55.0,
		"loans": [
			{"name": "Credit ipotecar", "principal": 309828.76, "apr": 0.065, "months": 240},
			{"name": "Credius IFN", "principal": 11107.58, "apr": 0.35, "months": 24},
		],
	}
	var s := Sim.new_state(5, profile)
	_check(s.from_statement and s.name == "Ion Popescu", "profilul din extras setează numele")
	_check(_approx(Sim.income(s), 6850.0, 0.01) and _approx(float(s.cash), 5309.81, 0.01), "venitul și soldul vin din extras")
	_check(s.loans.size() == 2 and _approx(Sim.debt_payments(s), 2960.0, 5.0), "creditele existente au ratele din extras (%s)" % Sim.debt_payments(s))
	_check(Sim.net_worth(s) > 0.0, "locuința compensează creditul ipotecar în patrimoniu")
	var personalized := Events.personalize(Events.all(), s)
	_check(str(personalized[0].scene).contains("extrasul"), "prima decizie folosește cifrele din extras")
	_check(float(personalized[0].options[0].ops.emergency_contrib) >= 100.0, "contribuția propusă e pozitivă")
	_check(str(Events.all()[0].scene).contains("4.300"), "evenimentele originale rămân neschimbate")
	var final_state := Sim.new_state(5, profile)
	for i in personalized.size():
		Sim.resolve(final_state, personalized[i].options[0], float(final_state.shocks[i]))
	_check(int(final_state.age) == 52 and not is_nan(Sim.net_worth(final_state)), "jocul complet rulează pe profilul din extras")

func _test_glyph_coverage() -> void:
	var font := load("res://assets/template/fonts/ui_regular.tres") as Font
	var bold := load("res://assets/template/fonts/ui_bold.tres") as Font
	_check(font != null and bold != null, "fonturile UI se încarcă")
	var texts: Array = ["ăâîșțĂÂÎȘȚ „”→•·–"]
	for ev: Dictionary in Events.all():
		texts.append(ev.title)
		texts.append(ev.scene)
		texts.append(ev.lesson)
		for opt: Dictionary in ev.options:
			texts.append(opt.title)
			texts.append(opt.desc)
	for p: Dictionary in Catalog.all():
		texts.append(p.name)
		texts.append(p.note)
	var missing := {}
	for line: String in texts:
		for i in line.length():
			var cp := line.unicode_at(i)
			if cp >= 32 and cp != 160 and not (font.has_char(cp) and bold.has_char(cp)):
				missing[cp] = true
	_check(missing.is_empty(), "glife lipsă în fontul UI: %s" % str(missing.keys()))

func _test_full_playthrough() -> void:
	var game := GameScene.instantiate()
	add_child(game)
	await get_tree().process_frame
	_check(game.phase == "title", "jocul pornește pe ecranul de titlu")
	game.start_game()
	await get_tree().process_frame
	_check(game.phase == "explore", "după start: explorare")
	_check(game._map.marker_location == "home", "prima decizie este marcată pe hartă la Acasă")
	game._on_enter_requested("bank")
	await get_tree().process_frame
	_check(game.phase == "info", "intrarea la o locație fără decizie deschide informații")
	game._on_info_closed()
	_check(game.phase == "explore", "informațiile se pot închide")
	var plan := [0, 2, 1, 0, 0, 0, 0, 0, 1, 1]
	for i in Events.all().size():
		var ev: Dictionary = Events.all()[i]
		game._on_enter_requested(str(ev.location))
		await get_tree().process_frame
		_check(game.phase == "event", "decizia %d se deschide la %s" % [i + 1, ev.location])
		game._on_advice_requested()
		game._on_option_chosen(mini(int(plan[i]), ev.options.size() - 1))
		await get_tree().process_frame
		_check(game.phase == "result", "rezultatul deciziei %d" % [i + 1])
		game._on_continue()
		await get_tree().process_frame
	_check(game.phase == "report", "după 10 decizii apare raportul")
	_check(game._report.visible, "raportul final este vizibil")
	_check(game.state.decisions.size() == 10, "toate cele 10 decizii sunt înregistrate")
	_check(game._advisor.tool_call_count() >= 30, "Consilierul a rulat multe apeluri de unelte (%d)" % game._advisor.tool_call_count())
	_check(int(game.state.age) == 52, "final la 52 de ani")
	game.queue_free()
	await get_tree().process_frame

func _finish() -> void:
	if _failures.is_empty():
		print("[game-generic-tests] PASS: %d verificări (motor financiar, Consilier AI, conținut RO, joc complet)" % _checks)
		get_tree().quit(0)
	else:
		for failure in _failures:
			push_error("[game-generic-tests] " + failure)
		print("[game-generic-tests] FAIL: %d din %d verificări" % [_failures.size(), _checks])
		get_tree().quit(1)
