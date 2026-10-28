extends Control
## Raportul final „Viitorul meu financiar” + plan de acțiune personalizat.

signal replay_requested
signal title_requested

const Sim := preload("res://scripts/raiff/finance_sim.gd")
const Kit := preload("res://scripts/raiff/ui_kit.gd")
const Advisor := preload("res://scripts/raiff/advisor.gd")
const Catalog := preload("res://scripts/raiff/catalog.gd")
const Chart := preload("res://scripts/raiff/net_worth_chart.gd")

var _scroll: ScrollContainer
var _root: VBoxContainer

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = Kit.BG
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	_scroll = ScrollContainer.new()
	_scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	add_child(_scroll)
	var margin := MarginContainer.new()
	margin.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	for side in ["left", "right"]:
		margin.add_theme_constant_override("margin_" + side, 48)
	margin.add_theme_constant_override("margin_top", 28)
	margin.add_theme_constant_override("margin_bottom", 36)
	_scroll.add_child(margin)
	_root = VBoxContainer.new()
	_root.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_root.add_theme_constant_override("separation", 14)
	margin.add_child(_root)
	visible = false

func _card(title: String) -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.add_theme_stylebox_override("panel", Kit.box(Kit.PANEL, Kit.BORDER, 12, 16))
	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 6)
	panel.add_child(vb)
	vb.add_child(Kit.label(title, 18, Kit.YELLOW, true))
	_root.add_child(panel)
	return vb

func show_report(s: Dictionary) -> void:
	Kit.clear_children(_root)
	visible = true
	_scroll.scroll_vertical = 0
	var score := Sim.resilience_score(s)
	_root.add_child(Kit.label("Viitorul meu financiar", 34, Kit.YELLOW, true))
	_root.add_child(Kit.wrapped("%s, %d de ani. Rezumatul celor 30 de ani și 10 decizii." % [s.name, int(s.age)], 16, Kit.MUTED))
	# scor + metrici
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 14)
	_root.add_child(top)
	var score_panel := PanelContainer.new()
	score_panel.add_theme_stylebox_override("panel", Kit.box(Kit.PANEL, Kit.YELLOW, 12, 18, 2))
	score_panel.custom_minimum_size = Vector2(300, 0)
	var sv := VBoxContainer.new()
	score_panel.add_child(sv)
	sv.add_child(Kit.label("Scor de reziliență", 14, Kit.MUTED))
	sv.add_child(Kit.label("%d / 100" % score, 52, Kit.YELLOW, true))
	sv.add_child(Kit.wrapped(Sim.archetype(score), 20, Kit.TEXT, true))
	sv.add_child(Kit.wrapped("Combină fondul de urgență, gradul de îndatorare, patrimoniul, stresul și încrederea.", 12, Kit.MUTED))
	top.add_child(score_panel)
	var metrics := GridContainer.new()
	metrics.columns = 2
	metrics.add_theme_constant_override("h_separation", 24)
	metrics.add_theme_constant_override("v_separation", 6)
	metrics.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var mp := PanelContainer.new()
	mp.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	mp.add_theme_stylebox_override("panel", Kit.box(Kit.PANEL, Kit.BORDER, 12, 16))
	mp.add_child(metrics)
	top.add_child(mp)
	var em := ("%.1f" % Sim.emergency_months(s)).replace(".", ",")
	for pair: Array in [
		["Patrimoniu net", Sim.money(Sim.net_worth(s))],
		["Fond de urgență", "%s (%s luni)" % [Sim.money(float(s.emergency)), em]],
		["Investiții", Sim.money(Sim.investments(s))],
		["Datorii", Sim.money(Sim.total_debt(s))],
		["Dobândă plătită în total", Sim.money(float(s.interest_paid_total))],
		["Stres / încredere", "%d / %d" % [int(round(float(s.stress))), int(round(float(s.confidence)))]],
		["Venit net lunar", Sim.money(Sim.income(s))],
		["Capital estimat la 67 de ani", Sim.money(Sim.retirement_projection(s))],
	]:
		var box := VBoxContainer.new()
		box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		box.add_child(Kit.label(pair[0], 12, Kit.MUTED))
		box.add_child(Kit.wrapped(pair[1], 17, Kit.TEXT, true))
		metrics.add_child(box)
	# grafic
	var chart_card := _card("Cum a evoluat patrimoniul tău")
	var chart := Chart.new()
	chart.custom_minimum_size = Vector2(0, 240)
	chart.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	chart_card.add_child(chart)
	chart.set_history(s.history)
	chart_card.add_child(Kit.wrapped("Capitalul la 67 de ani este o estimare cu randament mediu de 6%/an, nu o promisiune.", 12, Kit.MUTED))
	# decizii
	var dec_card := _card("Deciziile tale")
	var decisions: Array = s.decisions
	var best_good: Dictionary = {}
	var worst: Dictionary = {}
	for d: Dictionary in decisions:
		if best_good.is_empty() or float(d.regret) < float(best_good.regret):
			best_good = d
		if worst.is_empty() or float(d.regret) > float(worst.regret):
			worst = d
	if not best_good.is_empty():
		dec_card.add_child(Kit.wrapped("Cea mai bună decizie: la %d de ani, „%s” - ai ales „%s”." % [int(best_good.age), best_good.title, best_good.chosen_title], 15, Kit.GOOD))
	if not worst.is_empty() and float(worst.regret) > 300.0:
		dec_card.add_child(Kit.wrapped("Cel mai costisitor moment: la %d de ani, „%s”. Ai ales „%s”; „%s” ar fi dat un rezultat cu aproximativ %s mai bun (patrimoniu, stres și încredere luate în calcul)." % [int(worst.age), worst.title, worst.chosen_title, worst.best_title, Sim.money(float(worst.regret))], 15, Kit.BAD))
	for d: Dictionary in decisions:
		var ok := float(d.regret) < 300.0
		dec_card.add_child(Kit.wrapped("%d ani - %s: %s%s" % [int(d.age), d.title, d.chosen_title, "  (cea mai bună variantă)" if ok else "  (mai bun ar fi fost: %s)" % d.best_title], 13, Kit.MUTED))
	# plan
	var plan_card := _card("Plan de acțiune personalizat")
	var plan := Advisor.generate_action_plan(s)
	var i := 1
	for st: Dictionary in plan.data:
		var product := Catalog.by_id(str(st.product))
		plan_card.add_child(Kit.wrapped("%d. %s" % [i, st.title], 16, Kit.TEXT, true))
		plan_card.add_child(Kit.wrapped("%s Produs demo potrivit: %s (%s)" % [st.why, product.get("name", "-"), product.get("note", "")], 13, Kit.MUTED))
		i += 1
	plan_card.add_child(Kit.wrapped("Toate produsele, dobânzile și persoanele din joc sunt fictive. Nu reprezintă oferte, termeni sau recomandări reale ale Raiffeisen sau ale altei bănci.", 12, Kit.MUTED))
	# butoane
	var foot := HBoxContainer.new()
	foot.add_theme_constant_override("separation", 10)
	var again := Kit.button("Joacă din nou", true, 18)
	again.pressed.connect(func() -> void: replay_requested.emit())
	var menu := Kit.button("Înapoi la titlu", false, 16)
	menu.pressed.connect(func() -> void: title_requested.emit())
	foot.add_child(again)
	foot.add_child(menu)
	_root.add_child(foot)
	again.grab_focus()
