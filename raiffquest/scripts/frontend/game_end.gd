extends Control
## End-of-game overlay. Shows figures it is given; it never decides the outcome or computes finances.
const Kit = preload("res://scripts/frontend/journey_theme.gd")
const RED := Color("7d2417")
const RED_STRONG := Color("b3321f")
const GREEN := Color("24561f")

signal chosen(action: String)

var reduced_motion := false
var _dim: ColorRect
var _confetti: Control
var _panel: PanelContainer
var _angel: TextureRect
var _kind := ""

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_dim = ColorRect.new()
	_dim.color = Color(0.141, 0.173, 0.118, 0.62)
	_dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_dim)
	_confetti = Control.new()
	_confetti.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_confetti.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_confetti)
	resized.connect(_layout)
	hide()

## kind: "won", "goal_only", "score_only" or "expired". data keys are filled by the caller from the server state.
func show_outcome(kind: String, data: Dictionary) -> void:
	_kind = kind
	for child in _confetti.get_children():
		child.queue_free()
	if _panel:
		_panel.queue_free()
	if _angel:
		_angel.queue_free()
		_angel = null
	match kind:
		"won":
			_build_won(data)
		"goal_only":
			_build_card(data, false)
		_:
			_build_card(data, true)
	# Wrapped labels report their real height only once they know their width.
	_panel.minimum_size_changed.connect(_layout.call_deferred)
	show()
	_layout()
	if kind == "won":
		_throw_confetti.call_deferred()
	modulate.a = 1.0 if reduced_motion else 0.0
	if not reduced_motion:
		create_tween().tween_property(self, "modulate:a", 1.0, 0.35)

func _build_won(data: Dictionary) -> void:
	_panel = _surface(Kit.PAPER, Kit.INK)
	add_child(_panel)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 16)
	_panel.add_child(col)
	col.add_child(_tag("OBIECTIV ATINS · 100 / 100", Kit.YELLOW, Kit.INK))
	col.add_child(Kit.strong("Ai reușit!", 46))
	var month := int(data.get("month", 0))
	var horizon := int(data.get("horizon", 0))
	var line := "Ai atins obiectivul (%s) în %d %s" % [data.get("goal_text", ""), month, "lună" if month == 1 else "luni"]
	if horizon > 0:
		line += " din %d" % horizon
		if horizon - month > 0:
			line += ", cu %d %s mai devreme" % [horizon - month, "lună" if horizon - month == 1 else "luni"]
	col.add_child(Kit.text(line + ".", 18))
	var grid := GridContainer.new()
	grid.columns = 3
	grid.add_theme_constant_override("h_separation", 12)
	col.add_child(grid)
	var saved := float(data.get("savings", 0)) - float(data.get("savings_start", 0))
	var owed := float(data.get("debt", 0)) - float(data.get("debt_start", 0))
	grid.add_child(_stat("Scor", "%d → %d" % [int(data.get("score_start", 0)), int(data.get("score", 100))], "", true))
	grid.add_child(_stat("Economii", "%s → %s" % [_lei(data.get("savings_start", 0)), _lei(data.get("savings", 0))], _signed(saved), saved >= 0))
	grid.add_child(_stat("Datorii", "%s → %s" % [_lei(data.get("debt_start", 0)), _lei(data.get("debt", 0))], _signed(owed), owed <= 0))
	var best: Array = data.get("best", [])
	if not best.is_empty():
		col.add_child(Kit.strong("Alegerile care au contat cel mai mult", 15))
		for item: Dictionary in best:
			col.add_child(_choice_row(item, false))
	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	col.add_child(spacer)
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 12)
	col.add_child(actions)
	var real := Kit.button("Planul meu cu Raiffeisen →", func(): chosen.emit("raiffeisen"), true)
	real.icon = load("res://assets/raiff/raiffeisen_logo.png")
	real.expand_icon = true
	real.add_theme_constant_override("icon_max_width", 24)
	real.custom_minimum_size.y = 48
	actions.add_child(real)
	var again := Kit.button("Joc nou ↺", func(): chosen.emit("new_game"))
	again.custom_minimum_size.y = 48
	actions.add_child(again)
	_angel = Kit.portrait("happy", 380)
	add_child(_angel)

func _build_card(data: Dictionary, negative: bool) -> void:
	_panel = _surface(Color("fbeae6") if negative else Kit.PAPER, RED if negative else Kit.INK)
	add_child(_panel)
	if negative:
		var style: StyleBoxFlat = _panel.get_theme_stylebox("panel")
		style.border_width_top = 8
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 14)
	_panel.add_child(col)
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 12)
	col.add_child(top)
	var face := Kit.portrait("thinking" if negative else "happy", 96)
	top.add_child(face)
	var horizon := int(data.get("horizon", 0))
	var month := int(data.get("month", 0))
	var score := int(data.get("score", 0))
	var progress := float(data.get("progress", 0)) * 100.0
	var actions: Array = []
	match _kind:
		"goal_only":
			top.add_child(_tag("OBIECTIV ATINS", Color("dcefc9"), GREEN))
			col.add_child(Kit.strong("Ai ajuns la obiectiv!", 28))
			col.add_child(Kit.text("Ai atins obiectivul (%s) în %d %s%s. Scorul tău e %d din 100: banii sunt acolo, dar unele alegeri te-au costat puncte." % [data.get("goal_text", ""), month, "lună" if month == 1 else "luni", (" din %d" % horizon) if horizon > 0 else "", score], 16))
			_add_list(col, "Unde mai puteai câștiga puncte", data.get("worst", []), Color("eef0db"), Kit.INK)
			var offer := Kit.button("Planul meu cu Raiffeisen →", func(): chosen.emit("raiffeisen_save"))
			offer.icon = load("res://assets/raiff/raiffeisen_logo.png")
			offer.expand_icon = true
			offer.add_theme_constant_override("icon_max_width", 28)
			offer.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			offer.alignment = HORIZONTAL_ALIGNMENT_LEFT
			offer.custom_minimum_size.y = 56
			var offer_style := Kit.box(Color("fff19a"), Kit.INK, 12)
			offer_style.set_corner_radius_all(10)
			offer.add_theme_stylebox_override("normal", offer_style)
			var offer_hover := offer_style.duplicate() as StyleBoxFlat
			offer_hover.bg_color = Kit.YELLOW
			offer.add_theme_stylebox_override("hover", offer_hover)
			col.add_child(offer)
			actions = [["Setează alt scop →", "new_game", true], ["Încearcă pentru 100 de puncte", "continue", false]]
		"score_only":
			top.add_child(_tag("TIMP EXPIRAT", RED_STRONG, Color.WHITE))
			col.add_child(Kit.strong("Alegeri bune, dar n-a fost destul", 28, RED))
			var missing := float(data.get("missing", 0))
			var text := "Scorul e %d, dar după %d luni obiectivul a rămas la %.0f%%." % [score, month, progress]
			if missing > 0.5:
				text += " Îți mai lipsesc %s." % _lei(missing)
			col.add_child(Kit.text(text + " Cu venitul tău, termenul ales a fost prea scurt.", 16))
			col.add_child(_bar(progress))
			actions = [["Planul meu cu Raiffeisen →", "raiffeisen", true], ["Mai joacă 3 luni", "extend", false], ["Joc nou", "new_game", false]]
		_:
			top.add_child(_tag("OBIECTIV RATAT", Color("8f1f12"), Color.WHITE))
			col.add_child(Kit.strong("Timpul s-a terminat", 28, RED))
			col.add_child(Kit.text("Au trecut cele %d luni și obiectivul a rămas la %.0f%%. Scorul tău e doar %d din 100. Cheltuielile au mâncat banii pe care trebuia să-i pui deoparte." % [month, progress, score], 16))
			_add_list(col, "Ce te-a costat", data.get("worst", []), Color("f1c9c1"), RED)
			actions = [["Planul meu cu Raiffeisen →", "raiffeisen", true], ["Încearcă din nou", "new_game", false]]
	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	col.add_child(spacer)
	for spec in actions:
		var action: String = spec[1]
		var button := Kit.button(spec[0], func(): chosen.emit(action), spec[2])
		button.custom_minimum_size.y = 46
		if negative and not spec[2]:
			var outline := Kit.box(Kit.PAPER, RED)
			button.add_theme_stylebox_override("normal", outline)
			button.add_theme_color_override("font_color", RED)
		col.add_child(button)

func _layout() -> void:
	if not _panel:
		return
	var w := size.x
	var h := size.y
	if _kind == "won":
		var pw := minf(860, w - 300)
		var ph := minf(590, h - 90)
		_panel.position = Vector2(maxf(240, (w - pw) / 2 + 110), (h - ph) / 2)
		_panel.size = Vector2(pw, 0)
		_panel.size = Vector2(pw, maxf(ph, _panel.get_combined_minimum_size().y))
		_panel.get_theme_stylebox("panel").content_margin_left = 150
		if _angel:
			_angel.size = Vector2(380, 380)
			_angel.position = Vector2(_panel.position.x - 230, (h - 380) / 2)
	else:
		var pw := minf(540, w - 40)
		_panel.size = Vector2(pw, 0)
		_panel.size = Vector2(pw, maxf(380, _panel.get_combined_minimum_size().y))
		_panel.position = Vector2((w - pw) / 2, maxf(20, (h - _panel.size.y) / 2))

# Pieces fall from above and settle in a band around the window, never over its text.
func _throw_confetti() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var colors := [Kit.YELLOW, Kit.PAPER, Color("9fcc47"), Kit.YELLOW, Color("f2b46b")]
	var keep_out := Rect2(_panel.position - Vector2(12, 12), _panel.size + Vector2(24, 24))
	if _angel:
		keep_out = keep_out.merge(Rect2(_angel.position + Vector2(60, 40), _angel.size - Vector2(120, 80)))
	var placed := 0
	var tries := 0
	while placed < 110 and tries < 2000:
		tries += 1
		var target := Vector2(rng.randf_range(0, size.x), rng.randf_range(0, size.y))
		if keep_out.has_point(target):
			continue
		var piece := ColorRect.new()
		var side := rng.randf_range(6, 16)
		piece.size = Vector2(side, side if rng.randf() < 0.4 else rng.randf_range(4, 9))
		piece.pivot_offset = piece.size / 2
		piece.color = colors[rng.randi() % colors.size()]
		piece.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var turn := rng.randf_range(-1.6, 1.6)
		_confetti.add_child(piece)
		placed += 1
		if reduced_motion:
			piece.position = target
			piece.rotation = turn
			continue
		piece.position = Vector2(target.x + rng.randf_range(-60, 60), -30)
		var tween := create_tween().set_parallel(true).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		var delay := rng.randf_range(0, 0.8)
		var time := rng.randf_range(1.2, 2.2)
		tween.tween_property(piece, "position", target, time).set_delay(delay)
		tween.tween_property(piece, "rotation", turn + rng.randf_range(-6, 6), time).set_delay(delay)

func _surface(color: Color, border: Color) -> PanelContainer:
	var panel := PanelContainer.new()
	var style := Kit.box(color, border, 28)
	style.corner_radius_top_right = 24
	style.corner_radius_bottom_left = 24
	style.shadow_color = Color(0.188, 0.227, 0.157, 0.45)
	style.shadow_offset = Vector2(0, 8)
	panel.add_theme_stylebox_override("panel", style)
	return panel

func _tag(value: String, fill: Color, ink: Color) -> Label:
	var tag := Kit.strong(value, 13, ink)
	tag.autowrap_mode = TextServer.AUTOWRAP_OFF
	tag.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	tag.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var style := Kit.box(fill, Kit.INK if fill == Kit.YELLOW else fill, 4)
	style.content_margin_left = 10
	style.content_margin_right = 10
	style.set_corner_radius_all(6)
	style.shadow_size = 0
	style.shadow_offset = Vector2.ZERO
	tag.add_theme_stylebox_override("normal", style)
	return tag

func _stat(caption: String, value: String, change: String, good: bool) -> PanelContainer:
	var card := PanelContainer.new()
	card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var style := Kit.box(Color("eef0db"), Color("eef0db"), 14)
	style.set_corner_radius_all(10)
	style.shadow_size = 0
	style.shadow_offset = Vector2.ZERO
	card.add_theme_stylebox_override("panel", style)
	var col := VBoxContainer.new()
	card.add_child(col)
	col.add_child(Kit.text(caption, 13, Kit.MUTED))
	var big := Kit.strong(value, 22)
	big.autowrap_mode = TextServer.AUTOWRAP_OFF
	col.add_child(big)
	if not change.is_empty():
		col.add_child(Kit.strong(change, 13, Color("2f6a2b") if good else RED))
	return card

func _choice_row(item: Dictionary, negative: bool) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	var delta := int(item.get("delta", 0))
	var chip := _tag(("+%d" if delta > 0 else "%d") % delta, Kit.PAPER if negative else Color("dcefc9"), RED if negative else GREEN)
	chip.custom_minimum_size.x = 44
	chip.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	row.add_child(chip)
	var label := Kit.text("%s (luna %d)" % [item.get("text", ""), int(item.get("month", 0))], 15)
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(label)
	return row

func _add_list(col: VBoxContainer, title: String, items: Array, fill: Color, ink: Color) -> void:
	if items.is_empty():
		return
	var box := PanelContainer.new()
	var style := Kit.box(fill, fill, 12)
	style.set_corner_radius_all(10)
	style.shadow_size = 0
	style.shadow_offset = Vector2.ZERO
	box.add_theme_stylebox_override("panel", style)
	col.add_child(box)
	var inner := VBoxContainer.new()
	inner.add_theme_constant_override("separation", 6)
	box.add_child(inner)
	inner.add_child(Kit.strong(title, 14, ink))
	for item: Dictionary in items:
		inner.add_child(_choice_row(item, true))

func _bar(percent: float) -> ProgressBar:
	var bar := ProgressBar.new()
	bar.custom_minimum_size.y = 12
	bar.show_percentage = false
	bar.value = percent
	var fill := Kit.box(RED_STRONG, RED, 0)
	fill.shadow_size = 0
	fill.shadow_offset = Vector2.ZERO
	bar.add_theme_stylebox_override("fill", fill)
	var back := Kit.box(Color("f1cfc8"), Color("f1cfc8"), 0)
	back.shadow_size = 0
	back.shadow_offset = Vector2.ZERO
	bar.add_theme_stylebox_override("background", back)
	return bar

static func _lei(value) -> String:
	return "%.0f lei" % float(value)

static func _signed(value: float) -> String:
	if absf(value) < 0.5:
		return ""
	return ("+%.0f lei" if value > 0 else "%.0f lei") % value
