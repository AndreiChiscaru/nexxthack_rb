extends PanelContainer
## Panou financiar live: numerar, fond de urgență, datorii, investiții, patrimoniu net, stres, încredere.

const Sim := preload("res://scripts/raiff/finance_sim.gd")
const Kit := preload("res://scripts/raiff/ui_kit.gd")

var _rows: Dictionary = {}
var _stress_bar: ProgressBar
var _conf_bar: ProgressBar
var _stress_label: Label
var _conf_label: Label
var _age_label: Label
var _income_label: Label

func _ready() -> void:
	add_theme_stylebox_override("panel", Kit.box(Kit.PANEL, Kit.BORDER, 12, 14))
	var root := VBoxContainer.new()
	root.add_theme_constant_override("separation", 5)
	add_child(root)
	var head := HBoxContainer.new()
	root.add_child(head)
	head.add_child(Kit.label("Panou financiar", 17, Kit.YELLOW, true))
	head.add_child(Kit.hspacer())
	_age_label = Kit.label("", 14, Kit.MUTED)
	head.add_child(_age_label)
	var grid := GridContainer.new()
	grid.columns = 3
	grid.add_theme_constant_override("h_separation", 10)
	grid.add_theme_constant_override("v_separation", 3)
	root.add_child(grid)
	for def: Array in [
		["cash", "Numerar"], ["emergency", "Fond de urgență"], ["debt", "Datorii"],
		["invest", "Investiții"], ["networth", "Patrimoniu net"],
	]:
		var name_label := Kit.label(def[1], 14, Kit.MUTED)
		name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		grid.add_child(name_label)
		var value := Kit.label("-", 15, Kit.TEXT, true)
		value.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		value.custom_minimum_size.x = 112
		grid.add_child(value)
		var delta := Kit.label("", 12, Kit.MUTED)
		delta.custom_minimum_size.x = 82
		delta.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		grid.add_child(delta)
		_rows[def[0]] = {"value": value, "delta": delta}
	_income_label = Kit.wrapped("", 12, Kit.MUTED)
	root.add_child(_income_label)
	var stress := _bar_row("Stres", Kit.BAD)
	_stress_bar = stress.bar
	_stress_label = stress.value
	var conf := _bar_row("Încredere financiară", Kit.GOOD)
	_conf_bar = conf.bar
	_conf_label = conf.value
	root.add_child(stress.box)
	root.add_child(conf.box)

func _bar_row(title: String, color: Color) -> Dictionary:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 1)
	var top := HBoxContainer.new()
	top.add_child(Kit.label(title, 13, Kit.MUTED))
	top.add_child(Kit.hspacer())
	var value := Kit.label("", 13, Kit.TEXT, true)
	top.add_child(value)
	box.add_child(top)
	var bar := ProgressBar.new()
	bar.show_percentage = false
	bar.min_value = 0
	bar.max_value = 100
	bar.custom_minimum_size = Vector2(0, 10)
	bar.add_theme_stylebox_override("background", Kit.box(Kit.PANEL_2, Kit.PANEL_2, 5, 0, 0))
	bar.add_theme_stylebox_override("fill", Kit.box(color, color, 5, 0, 0))
	box.add_child(bar)
	return {"box": box, "bar": bar, "value": value}

func update_state(s: Dictionary, prev: Dictionary = {}) -> void:
	_age_label.text = "Vârsta %d" % int(s.age)
	var em := Sim.emergency_months(s)
	_set_row("cash", Sim.money(float(s.cash)), float(s.cash), prev.get("cash", null), true, "")
	_set_row("emergency", Sim.money(float(s.emergency)), float(s.emergency), prev.get("emergency", null), true, "")
	_set_row("debt", Sim.money(Sim.total_debt(s)), Sim.total_debt(s), prev.get("debt", null), false, "")
	_set_row("invest", Sim.money(Sim.investments(s)), Sim.investments(s), prev.get("investments", null), true, "")
	_set_row("networth", Sim.money(Sim.net_worth(s)), Sim.net_worth(s), prev.get("net_worth", null), true, "")
	(_rows["emergency"].value as Label).tooltip_text = "%s luni de cheltuieli (ținta: 6 luni)" % ("%.1f" % em).replace(".", ",")
	var parts: Array = ["Venit net %s/lună" % Sim.money(Sim.income(s)), "cheltuieli %s" % Sim.money(float(s.living))]
	var pay := Sim.debt_payments(s) + float(s.insurance_premium)
	if pay > 0.5:
		parts.append("rate și prime %s" % Sim.money(pay))
	_income_label.text = "%s. Fond de urgență: %s luni." % [", ".join(parts), ("%.1f" % em).replace(".", ",")]
	_stress_bar.value = float(s.stress)
	_conf_bar.value = float(s.confidence)
	_stress_label.text = _fmt_mood(float(s.stress), prev.get("stress", null))
	_conf_label.text = _fmt_mood(float(s.confidence), prev.get("confidence", null))

func _fmt_mood(value: float, prev: Variant) -> String:
	var text := "%d/100" % int(round(value))
	if prev != null:
		var d := int(round(value - float(prev)))
		if d != 0:
			text += "  (%s%d)" % ["+" if d > 0 else "", d]
	return text

func _set_row(key: String, text: String, value: float, prev: Variant, up_is_good: bool, _unused: String) -> void:
	var row: Dictionary = _rows[key]
	(row.value as Label).text = text
	var delta := row.delta as Label
	delta.text = ""
	if prev != null:
		var d := value - float(prev)
		if absf(d) >= 1.0:
			delta.text = Sim.signed_money(d).replace(" lei", "")
			var good := (d > 0.0) == up_is_good
			delta.add_theme_color_override("font_color", Kit.GOOD if good else Kit.BAD)
