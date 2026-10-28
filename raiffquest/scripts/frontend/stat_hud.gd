extends PanelContainer
## Presentation only: every amount comes from the session snapshot or confirmed profile.
const Kit = preload("res://scripts/frontend/journey_theme.gd")
const POSITIVE := Color("416a38")
const NEGATIVE := Color("ad5939")
var month_label: Label
var horizon_label: Label
var score_label: Label
var score_box: VBoxContainer
var score_bar: ProgressBar
var score_pace: ColorRect
var score_hint: Label
var cash_value: Label
var savings_value: Label
var surplus_value: Label
var debt_value: Label
var investments_value: Label
var cashflow_label: Label
var goal_label: Label
var goal_amount: Label
var percentage: Label
var progress: ProgressBar

func label(text: String, points: int, bold := false, color := Kit.INK) -> Label:
	var node := Kit.strong(text, points, color) if bold else Kit.text(text, points, color)
	node.autowrap_mode = TextServer.AUTOWRAP_OFF
	node.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	node.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return node

func icon(name: String, side: float) -> TextureRect:
	var node := TextureRect.new()
	node.texture = load("res://assets/raiff/hud/%s.svg" % name)
	node.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	node.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	node.custom_minimum_size = Vector2(side, side)
	node.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return node

func rule() -> ColorRect:
	var node := ColorRect.new()
	node.color = Color("d5d9bb")
	node.custom_minimum_size.y = 1
	node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return node

func metric(parent: HBoxContainer, title: String, image: String, points: int, tint := Kit.INK) -> Label:
	var row := HBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_theme_constant_override("separation", 5)
	parent.add_child(row)
	row.add_child(icon(image, 30 if points >= 17 else 23))
	var stack := VBoxContainer.new()
	stack.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	stack.add_theme_constant_override("separation", 1)
	row.add_child(stack)
	stack.add_child(label(title, 10))
	var amount := label("—", points, true, tint)
	stack.add_child(amount)
	return amount

func _ready() -> void:
	theme = Kit.theme()
	var surface := Kit.box(Kit.PAPER, Kit.INK, 12)
	surface.set_corner_radius_all(17)
	surface.shadow_color = Color("7e8f66")
	surface.shadow_offset = Vector2(0, 5)
	add_theme_stylebox_override("panel", surface)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 7)
	add_child(col)
	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 5)
	col.add_child(header)
	header.add_child(icon("calendar", 19))
	month_label = label("LUNA —", 11, true)
	month_label.custom_minimum_size.x = 64
	month_label.size_flags_horizontal = Control.SIZE_FILL
	header.add_child(month_label)
	var title := label("Planul tău financiar", 13, true)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	header.add_child(title)
	horizon_label = label("", 10, false, Kit.MUTED)
	horizon_label.custom_minimum_size.x = 49
	horizon_label.size_flags_horizontal = Control.SIZE_FILL
	horizon_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	header.add_child(horizon_label)
	col.add_child(rule())
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 10)
	col.add_child(top)
	cash_value = metric(top, "Disponibil", "wallet", 17)
	savings_value = metric(top, "Economii", "pig", 17)
	surplus_value = metric(top, "Bilanț lunar", "growth", 17, POSITIVE)
	cashflow_label = label("", 10, false, Kit.MUTED)
	cashflow_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	col.add_child(cashflow_label)
	score_box = VBoxContainer.new()
	score_box.add_theme_constant_override("separation", 3)
	col.add_child(score_box)
	var score_row := HBoxContainer.new()
	score_box.add_child(score_row)
	score_row.add_child(label("Scor alegeri", 11, true))
	score_label = label("", 15, true)
	score_label.size_flags_horizontal = Control.SIZE_FILL
	score_label.custom_minimum_size.x = 80
	score_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	score_row.add_child(score_label)
	score_bar = ProgressBar.new()
	score_bar.custom_minimum_size.y = 10
	score_bar.show_percentage = false
	for key in ["background", "fill"]:
		var paint := Kit.box(Kit.YELLOW if key == "fill" else Color("d3d8b9"), Kit.INK if key == "fill" else Color("84906e"), 0)
		paint.set_corner_radius_all(5)
		paint.set_border_width_all(1)
		paint.shadow_size = 0
		paint.shadow_offset = Vector2.ZERO
		score_bar.add_theme_stylebox_override(key, paint)
	score_box.add_child(score_bar)
	# Where the score should be this month to reach 100 by the deadline.
	score_pace = ColorRect.new()
	score_pace.color = Kit.INK
	score_pace.mouse_filter = Control.MOUSE_FILTER_IGNORE
	score_pace.anchor_bottom = 1
	score_pace.offset_top = -4
	score_pace.offset_bottom = 4
	score_bar.add_child(score_pace)
	score_hint = label("", 10)
	score_box.add_child(score_hint)
	var secondary := PanelContainer.new()
	var inset := Kit.box(Color("ecefd6"), Color.TRANSPARENT, 7)
	inset.set_border_width_all(0)
	inset.set_corner_radius_all(9)
	inset.shadow_size = 0
	inset.shadow_offset = Vector2.ZERO
	secondary.add_theme_stylebox_override("panel", inset)
	col.add_child(secondary)
	var bottom := HBoxContainer.new()
	bottom.add_theme_constant_override("separation", 18)
	secondary.add_child(bottom)
	debt_value = metric(bottom, "Datorii", "debt", 15, NEGATIVE)
	investments_value = metric(bottom, "Investiții", "invest", 15, POSITIVE)
	col.add_child(rule())
	var goal := HBoxContainer.new()
	goal.add_theme_constant_override("separation", 7)
	col.add_child(goal)
	goal.add_child(icon("flag", 26))
	var detail := VBoxContainer.new()
	detail.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	detail.add_theme_constant_override("separation", 5)
	goal.add_child(detail)
	var captions := HBoxContainer.new()
	captions.add_theme_constant_override("separation", 8)
	detail.add_child(captions)
	goal_label = label("Obiectiv", 11, true)
	goal_label.size_flags_stretch_ratio = 1.1
	captions.add_child(goal_label)
	goal_amount = label("", 10, true)
	goal_amount.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	captions.add_child(goal_amount)
	var bar := HBoxContainer.new()
	detail.add_child(bar)
	progress = ProgressBar.new()
	progress.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	progress.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	progress.custom_minimum_size.y = 12
	progress.show_percentage = false
	for key in ["background", "fill"]:
		var paint := Kit.box(Kit.YELLOW if key == "fill" else Color("d3d8b9"), Color("84906e"), 0)
		paint.set_corner_radius_all(6)
		paint.set_border_width_all(1)
		paint.shadow_size = 0
		paint.shadow_offset = Vector2.ZERO
		progress.add_theme_stylebox_override(key, paint)
	bar.add_child(progress)
	percentage = label("0%", 11, true, Kit.MUTED)
	percentage.size_flags_horizontal = Control.SIZE_FILL
	percentage.custom_minimum_size.x = 32
	percentage.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	bar.add_child(percentage)

## pace: the score the player should have this month (negative hides the marker); hint: one line under the bar.
func set_score_pace(pace: float, hint: String, tint: Color) -> void:
	score_pace.visible = pace >= 0
	score_pace.anchor_left = clampf(pace, 0, 100) / 100.0
	score_pace.anchor_right = score_pace.anchor_left
	score_pace.offset_left = -1
	score_pace.offset_right = 1
	score_hint.text = hint
	score_hint.add_theme_color_override("font_color", tint)

static func number(value: float) -> String:
	var digits := str(int(round(absf(value))))
	var formatted := ""
	while digits.length() > 3:
		formatted = "." + digits.right(3) + formatted
		digits = digits.left(digits.length() - 3)
	return ("−" if value < 0 else "") + digits + formatted

static func money(value: float) -> String:
	return number(value) + " lei"

func update_state(state: Dictionary, profile: Dictionary) -> void:
	var balance: Dictionary = state.get("balance", {})
	var monthly: Dictionary = state.get("monthly", {})
	var goal: Dictionary = state.get("goal", {})
	var confirmed: Dictionary = profile.get("goal", {})
	var expenses := 0.0
	for amount in monthly.get("expenses", {}).values():
		expenses += float(amount)
	var income := float(monthly.get("income", 0))
	var surplus := income - expenses
	month_label.text = "LUNA %d" % int(state.get("month", 0))
	horizon_label.text = "%d luni" % int(confirmed.horizon_months) if confirmed.has("horizon_months") else ""
	cash_value.text = money(float(balance.get("cash", 0)))
	savings_value.text = money(float(balance.get("savings", 0)))
	surplus_value.text = ("+" if surplus > 0 else "") + money(surplus)
	surplus_value.add_theme_color_override("font_color", NEGATIVE if surplus < 0 else POSITIVE)
	debt_value.text = money(float(balance.get("debt", 0)))
	investments_value.text = money(float(balance.get("investments", 0)))
	cashflow_label.text = "Venit %s · Cheltuieli %s" % [money(income), money(expenses)]
	score_label.text = "%d / 100" % int(state.get("score", 0))
	score_bar.value = clampf(float(state.get("score", 0)), 0, 100)
	score_box.visible = state.has("score")
	var debt_goal: bool = goal.get("type", "") == "achitare_datorii"
	goal_label.text = "Achitare datorii" if debt_goal else str(confirmed.get("description", "Obiectivul tău"))
	if goal_label.text.strip_edges().is_empty():
		goal_label.text = "Obiectivul tău"
	goal_amount.text = "Rămas: " + money(float(balance.get("debt", 0))) if debt_goal else "%s / %s" % [number(float(balance.get("savings", 0)) + float(balance.get("investments", 0))), money(float(goal.get("target_amount", 0)))]
	progress.value = clampf(float(goal.get("progress", 0)) * 100, 0, 100)
	percentage.text = "%d%%" % int(round(progress.value))
	for value in [cash_value, savings_value, surplus_value]:
		value.add_theme_font_size_override("font_size", 14 if value.text.length() > 12 else 17)
