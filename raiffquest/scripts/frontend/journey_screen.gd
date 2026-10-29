extends Control
## Native frontend for the shared session API. Financial values are never simulated here.
const Kit = preload("res://scripts/frontend/journey_theme.gd")
const Controller = preload("res://scripts/frontend/session_controller.gd")
const Chat = preload("res://scripts/frontend/journey_chat.gd")
const CityMap = preload("res://scripts/frontend/city_map.gd")
const StatHud = preload("res://scripts/frontend/stat_hud.gd")
const Upload = preload("res://scripts/frontend/statement_upload.gd")
const GameEnd = preload("res://scripts/frontend/game_end.gd")
const NAMES := {"home": "Acasă", "market": "Piață", "education": "Educație", "work": "Loc de muncă", "business": "Afacere", "hospital": "Spital", "bank": "Bancă", "entertainment": "Divertisment"}
var controller: Node
var chat: PanelContainer
var city: Control
var uploader: Node
var welcome: Control
var greeting: PanelContainer
var hero: TextureRect
var start_button: Button
var mode: Label
var error_label: Label
var hud: PanelContainer
var _hud_expanded := false
var _hud_tween: Tween
var _hud_shade: ColorRect
var advisor_button: Button
var _advisor_hover_tween: Tween
var channel := "onboarding"
var map_controls: HBoxContainer
var advance_button: Button
var recovery_button: Button
var location: PanelContainer
var location_contents: VBoxContainer
var profile_panel: PanelContainer
var profile_fields: Dictionary = {}
var selected := ""
var last_phase := "welcome"
var reduced_motion := false
var landscape: TextureRect
var _panel_tweens: Dictionary = {}
var _landscape_tween: Tween
var month_dialog: Control
var ending: Control
var toast: PanelContainer
var _toast_delta: Label
var _toast_text: Label
var _toast_tween: Tween
# Score bookkeeping for the end screens: the server owns the score, these only remember how it moved.
var _last_score := -1
var _start := {}
var _score_log: Array = []
var _pending_cause := ""
var _shown_outcomes := {}
var _extra_months := 0
var _bank_amount := 100.0
var bank_amount_input: SpinBox
var _catalog_open := false
# Building the AIngel chat was opened from ("" = from the map); decides which decision the chat is about.
var _chat_place := ""

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	theme = Kit.theme()
	var bg := ColorRect.new()
	bg.color = Kit.GRASS
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	landscape = TextureRect.new()
	landscape.texture = load("res://assets/raiff/journey_landscape.svg")
	landscape.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	landscape.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	landscape.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	landscape.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(landscape)
	controller = Controller.new()
	controller.api_base = OS.get_environment("RAIFF_API")
	add_child(controller)
	uploader = Upload.new()
	uploader.api_base = controller.api_base
	add_child(uploader)
	uploader.started.connect(controller.upload_started)
	uploader.finished.connect(_upload_finished)
	city = CityMap.new()
	add_child(city)
	city.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	city.institution_selected.connect(_institution)
	city.hide()
	_build_header()
	_build_welcome()
	_build_hud()
	chat = Chat.new()
	add_child(chat)
	chat.hide()
	chat.sent.connect(_on_sent)
	controller.message_added.connect(_on_message)
	chat.upload_requested.connect(_pick_statement)
	chat.sample_requested.connect(_load_sample)
	chat.review_requested.connect(_show_profile)
	chat.closed.connect(_close_chat)
	location = PanelContainer.new()
	add_child(location)
	location.hide()
	var sc := ScrollContainer.new()
	sc.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	location.add_child(sc)
	location_contents = VBoxContainer.new()
	location_contents.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	location_contents.add_theme_constant_override("separation", 12)
	sc.add_child(location_contents)
	profile_panel = PanelContainer.new()
	add_child(profile_panel)
	profile_panel.hide()
	month_dialog = preload("res://scripts/frontend/month_dialog.gd").new()
	add_child(month_dialog)
	month_dialog.confirmed.connect(controller.advance)
	_build_toast()
	ending = GameEnd.new()
	ending.reduced_motion = reduced_motion
	add_child(ending)
	ending.chosen.connect(_on_ending_chosen)
	controller.changed.connect(_update)
	get_window().files_dropped.connect(_files_dropped)
	resized.connect(_layout)
	chat.minimum_size_changed.connect(_layout.call_deferred)
	greeting.minimum_size_changed.connect(_layout.call_deferred)
	profile_panel.minimum_size_changed.connect(_layout.call_deferred)
	hud.minimum_size_changed.connect(_layout.call_deferred)
	_layout()
	_update()
	if not reduced_motion:
		var target := hero.position
		hero.position -= Vector2(80, 85)
		hero.modulate.a = 0
		var tween := create_tween().set_parallel(true)
		tween.tween_property(hero, "position", target, 1.0).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		tween.tween_property(hero, "modulate:a", 1.0, 0.6)

func _build_header() -> void:
	var badge := TextureRect.new()
	badge.texture = load("res://assets/raiff/raiffeisen_logo.png")
	badge.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	badge.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	badge.position = Vector2(28, 21)
	badge.size = Vector2(36, 36)
	badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(badge)
	var brand := Kit.strong("RaiffQuest", 26)
	brand.position = Vector2(74, 19)
	brand.size = Vector2(260, 40)
	add_child(brand)
	mode = Kit.text(Kit.SLOGAN, 12, Kit.MUTED)
	mode.position = Vector2(29, 59)
	mode.size = Vector2(600, 24)
	add_child(mode)
	error_label = Kit.text("", 13, Color("963b2b"))
	add_child(error_label)
	recovery_button = Kit.button("Reîncearcă sincronizarea", controller.refresh, true)
	add_child(recovery_button)
	recovery_button.hide()
	advisor_button = Kit.button("", func():
		if channel == "business" and chat.visible:
			_show_business()
		else:
			_show_onboarding_chat()
	)
	advisor_button.position = Vector2(24, 100)
	advisor_button.icon = load("res://assets/raiff/consultant/consultant_cartoon.png")
	advisor_button.expand_icon = true
	advisor_button.add_theme_constant_override("icon_max_width", 106)
	advisor_button.custom_minimum_size = Vector2(126, 126)
	advisor_button.size = Vector2(126, 126)
	advisor_button.pivot_offset = Vector2(63, 63)
	advisor_button.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	for state in ["normal", "disabled", "pressed", "hover", "hover_pressed", "focus"]:
		advisor_button.add_theme_stylebox_override(state, StyleBoxEmpty.new())
	var outline := Shader.new()
	outline.code = """shader_type canvas_item;
render_mode unshaded;
varying vec4 tint;
void vertex() { tint = COLOR; }
void fragment() {
    vec4 sprite = texture(TEXTURE, UV);
    vec2 radius = fwidth(UV) * 2.5;
    float coverage = sprite.a;
    for (int i = 0; i < 24; i++) {
        float angle = float(i) * 6.2831853 / 24.0;
        vec2 sample_uv = UV + vec2(cos(angle), sin(angle)) * radius;
        if (all(greaterThanEqual(sample_uv, vec2(0.0))) && all(lessThanEqual(sample_uv, vec2(1.0)))) {
            coverage = max(coverage, texture(TEXTURE, sample_uv).a);
        }
    }
    float alpha = max(sprite.a, coverage);
    vec3 rgb = mix(vec3(1.0), sprite.rgb, sprite.a / max(alpha, 0.0001));
    COLOR = vec4(rgb, alpha) * tint;
}
"""
	var outline_material := ShaderMaterial.new()
	outline_material.shader = outline
	advisor_button.material = outline_material
	advisor_button.mouse_entered.connect(func(): _animate_advisor_icon(true))
	advisor_button.mouse_exited.connect(func(): _animate_advisor_icon(false))
	advisor_button.focus_entered.connect(func(): _animate_advisor_icon(true))
	advisor_button.focus_exited.connect(func(): _animate_advisor_icon(false))
	add_child(advisor_button)
	advisor_button.hide()

func _build_welcome() -> void:
	welcome = Control.new()
	welcome.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	welcome.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(welcome)
	hero = Kit.portrait("explaining", 210)
	hero.size = Vector2(235, 265)
	welcome.add_child(hero)
	greeting = PanelContainer.new()
	welcome.add_child(greeting)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 20)
	greeting.add_child(col)
	col.add_child(Kit.strong("Hei, sunt AIngel!", 28))
	col.add_child(Kit.text("Ce vis ai vrea să transformăm într-un plan?", 20))
	start_button = Kit.button("Începe jocul →", controller.begin, true)
	start_button.size_flags_horizontal = Control.SIZE_SHRINK_END
	var start_spacing := MarginContainer.new()
	start_spacing.add_theme_constant_override("margin_top", 18)
	col.add_child(start_spacing)
	start_spacing.add_child(start_button)

func _build_hud() -> void:
	_hud_shade = ColorRect.new()
	_hud_shade.color = Color(0.19, 0.23, 0.16, 0.28)
	_hud_shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_hud_shade.z_index = 30
	_hud_shade.hide()
	add_child(_hud_shade)
	_hud_shade.gui_input.connect(func(event: InputEvent):
		if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
			_toggle_hud())
	hud = StatHud.new()
	add_child(hud)
	hud.expand_requested.connect(_toggle_hud)
	map_controls = HBoxContainer.new()
	map_controls.add_theme_constant_override("separation", 8)
	add_child(map_controls)
	advance_button = Kit.button("Luna următoare →", func(): month_dialog.popup_centered(), true)
	map_controls.add_child(advance_button)
	hud.hide()
	map_controls.hide()

func _toggle_hud() -> void:
	_hud_expanded = not _hud_expanded
	if is_instance_valid(_hud_tween):
		_hud_tween.kill()
	_hud_shade.visible = _hud_expanded
	hud.z_index = 31 if _hud_expanded else 0
	hud.expand_button.text = "−" if _hud_expanded else "⤢"
	var target_scale := minf(1.5, minf((size.x - 64) / hud.size.x, (size.y - 64) / maxf(1, hud.size.y))) if _hud_expanded else 0.74
	var target_position := (size - hud.size * target_scale) / 2 if _hud_expanded else Vector2(size.x - hud.size.x * 0.74 - 20, 20)
	_hud_tween = create_tween().set_parallel(true).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	_hud_tween.tween_property(hud, "scale", Vector2.ONE * target_scale, 0.25 if not reduced_motion else 0.0)
	_hud_tween.tween_property(hud, "position", target_position, 0.25 if not reduced_motion else 0.0)

func _unhandled_key_input(event: InputEvent) -> void:
	if _hud_expanded and event.is_action_pressed("ui_cancel"):
		_toggle_hud()
		get_viewport().set_input_as_handled()

func _layout() -> void:
	var w := size.x
	var h := size.y
	landscape.pivot_offset = size * Vector2(0.5, 0.42)
	# AIngel and the greeting move as one group, centred on screen.
	var greeting_width := maxf(400, minf(530, w - 330))
	var group := Vector2(242 + greeting_width, 265)
	var origin := Vector2(maxf(24, (w - group.x) / 2 - 60), maxf(110, (h - group.y) / 2))
	hero.position = origin
	greeting.position = origin + Vector2(242, 40)
	greeting.size = Vector2(greeting_width, 210)
	chat.layout_width = 350.0 if controller.phase == "map" else minf(940, w - 40)
	chat._resize_rows()
	chat.position = Vector2(maxf(20, (w - 940) / 2), 105)
	chat.size = Vector2(minf(940, w - 40), maxf(400, h - 155))
	if controller.phase == "map":
		chat.position = Vector2(24, 190)
		chat.size = Vector2(350, maxf(330, h - 280))
	hud.size = Vector2(minf(440, w - 40), hud.get_combined_minimum_size().y)
	var hud_scale := minf(1.5, minf((w - 64) / hud.size.x, (h - 64) / maxf(1, hud.size.y))) if _hud_expanded else 0.74
	if not is_instance_valid(_hud_tween) or not _hud_tween.is_running():
		hud.scale = Vector2.ONE * hud_scale
		hud.position = (size - hud.size * hud_scale) / 2 if _hud_expanded else Vector2(w - hud.size.x * 0.74 - 20, 20)
	toast.position = Vector2((w - toast.size.x) / 2, h - 150)
	map_controls.position = Vector2(25, h - 60)
	map_controls.size = Vector2(400, 40)
	recovery_button.position = Vector2(25, h - 150)
	recovery_button.size = Vector2(270, 40)
	error_label.position = Vector2(25, h - 105)
	error_label.size = Vector2(maxf(400, w - 470), 40)
	location.position = Vector2(w - 365, maxf(178, 20 + hud.size.y * 0.74 + 18))
	location.size = Vector2(340, maxf(160, h - location.position.y - 72))
	profile_panel.position = Vector2(maxf(15, (w - 670) / 2), 95)
	profile_panel.size = Vector2(minf(670, w - 30), maxf(430, h - 125))

func _process(_delta: float) -> void:
	if is_instance_valid(advisor_button) and is_instance_valid(chat):
		var face: Texture2D = preload("res://assets/raiff/accountant/accountant_idle.png") if channel == "business" and chat.visible else preload("res://assets/raiff/consultant/consultant_cartoon.png")
		if advisor_button.icon != face:
			advisor_button.icon = face
	if not is_instance_valid(city) or controller.phase != "map":
		return
	var left := 70.0
	var right := size.x - 70.0
	if hud.visible:
		right = minf(right, size.x - hud.size.x * 0.74 - 65.0)
	if location.visible:
		right = minf(right, location.position.x - 45.0)
	if chat.visible:
		left = maxf(left, chat.position.x + chat.size.x + 45.0)
	city.follow_view_rect = Rect2(Vector2(left, 140), Vector2(maxf(100, right - left), maxf(100, size.y - 240)))

func _update() -> void:
	var phase: String = controller.phase
	start_button.disabled = controller.busy or controller.needs_recovery
	start_button.text = "Se conectează…" if controller.busy else "Începe jocul →"
	if not controller.last_error.is_empty():
		start_button.text = "Reîncearcă conectarea →"
	error_label.text = controller.last_error
	recovery_button.visible = controller.needs_recovery or (phase == "map" and not controller.last_error.is_empty())
	recovery_button.disabled = controller.busy
	if phase != "review":
		profile_panel.hide()
	mode.text = Kit.SLOGAN
	chat.show_state(controller.busy, phase, controller.last_error)
	uploader.session_id = controller.session_id
	welcome.visible = phase == "welcome"
	hud.visible = phase == "map"
	map_controls.visible = phase == "map"
	advisor_button.visible = phase == "map"
	advisor_button.disabled = controller.busy
	city.visible = phase == "map"
	if phase != last_phase:
		if phase in ["onboarding", "review"]:
			_reveal(chat)
			if _landscape_tween:
				_landscape_tween.kill()
			_landscape_tween = create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
			_landscape_tween.tween_property(landscape, "scale", Vector2.ONE * 1.1, 1.2 if not reduced_motion else 0.0)
		elif phase == "map":
			chat.hide()
			profile_panel.hide()
			city.enter_map()
			if not reduced_motion:
				city.modulate.a = 0
				create_tween().tween_property(city, "modulate:a", 1.0, 0.65)
		elif phase == "welcome":
			if _landscape_tween:
				_landscape_tween.kill()
			_landscape_tween = create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
			_landscape_tween.tween_property(landscape, "scale", Vector2.ONE, 0.8 if not reduced_motion else 0.0)
		last_phase = phase
		_layout()
	if phase == "map":
		var state: Dictionary = controller.state
		hud.update_state(state, controller.profile)
		city.set_institutions(state.get("institutions", []))
		var remaining: int = controller.events.size()
		advance_button.disabled = controller.busy or controller.needs_recovery or remaining > 0
		advance_button.text = "Rezolvă misiunea rămasă" if remaining == 1 else ("Rezolvă cele %d misiuni" % remaining if remaining > 1 else "Luna următoare →")
		_update_score(state)
		if not controller.busy:
			_check_outcome(state)
		if not selected.is_empty() and location.visible:
			if _catalog_open and selected == "bank":
				_render_products()
			else:
				_institution(selected)

func _horizon() -> int:
	var goal = controller.profile.get("goal", {})
	var months := int(goal.get("horizon_months", 0)) if goal is Dictionary else 0
	return months + _extra_months if months > 0 else 0

func _update_score(state: Dictionary) -> void:
	var score := int(state.get("score", 0))
	var month := int(state.get("month", 0))
	var horizon := _horizon()
	var balance: Dictionary = state.get("balance", {})
	if _last_score < 0:
		_start = {"score": score, "savings": float(balance.get("savings", 0)) + float(balance.get("investments", 0)), "debt": float(balance.get("debt", 0))}
	elif score != _last_score:
		var delta := score - _last_score
		var cause := _pending_cause if not _pending_cause.is_empty() else "Ajustare de la agenți"
		_score_log.append({"delta": delta, "text": cause, "month": month})
		_show_toast(delta, cause, "scor %d → %d" % [_last_score, score])
	_last_score = score
	if not controller.busy:
		_pending_cause = ""
	if horizon > 0:
		hud.month_label.text = "LUNA %d/%d" % [month, horizon]
	var start_score := int(_start.get("score", score))
	var pace := -1.0
	if horizon > 0 and score < 100:
		pace = clampf(start_score + (100.0 - start_score) * month / horizon, 0, 100)
	if score >= 100:
		hud.set_score_pace(pace, "Scor maxim! Acum termină obiectivul.", GOOD)
	elif score >= 90:
		hud.set_score_pace(pace, "Mai ai nevoie de %d puncte" % (100 - score), Kit.INK)
	elif pace >= 0 and score + 0.5 < pace:
		hud.set_score_pace(pace, "● Rămâi în urmă · ritmul cerut acum: %.0f" % pace, Color("8a4708"))
	else:
		hud.set_score_pace(pace, "● În grafic spre 100", GOOD)

# The server has no game-over state yet, so the outcome is read from its figures: score, goal progress, month.
func _check_outcome(state: Dictionary) -> void:
	if ending.visible:
		return
	var score := int(state.get("score", 0))
	var month := int(state.get("month", 0))
	var horizon := _horizon()
	var goal: Dictionary = state.get("goal", {})
	var reached := float(goal.get("progress", 0)) >= 1.0
	var kind := ""
	if reached and score >= 100:
		kind = "won"
	elif reached:
		kind = "goal_only"
	elif horizon > 0 and month >= horizon:
		kind = "score_only" if score >= 100 else "expired"
	var key := kind if kind in ["won", "goal_only"] else "%s@%d" % [kind, horizon]
	if kind.is_empty() or _shown_outcomes.has(key):
		return
	_shown_outcomes[key] = true
	chat.hide()
	location.hide()
	ending.show_outcome(kind, _outcome_data(state))

func _outcome_data(state: Dictionary) -> Dictionary:
	var balance: Dictionary = state.get("balance", {})
	var goal: Dictionary = state.get("goal", {})
	var profile_goal = controller.profile.get("goal", {})
	var described := str(profile_goal.get("description", "")) if profile_goal is Dictionary else ""
	var target := float(goal.get("target_amount", 0))
	var progress := float(goal.get("progress", 0))
	var debt_goal := str(goal.get("type", "")) == "achitare_datorii"
	var goal_text := described if not described.is_empty() else ("achitarea datoriilor" if debt_goal else "%.0f lei" % target)
	var ranked := _score_log.duplicate()
	ranked.sort_custom(func(a, b): return int(a.delta) > int(b.delta))
	var best := ranked.filter(func(item): return int(item.delta) > 0).slice(0, 3)
	ranked.reverse()
	var worst := ranked.filter(func(item): return int(item.delta) < 0).slice(0, 3)
	return {
		"month": int(state.get("month", 0)),
		"horizon": _horizon(),
		"score": int(state.get("score", 0)),
		"score_start": int(_start.get("score", 0)),
		"progress": progress,
		"goal_text": goal_text,
		"savings_start": float(_start.get("savings", 0)),
		"savings": float(balance.get("savings", 0)) + float(balance.get("investments", 0)),
		"debt_start": float(_start.get("debt", 0)),
		"debt": float(balance.get("debt", 0)),
		"missing": float(balance.get("debt", 0)) if debt_goal else maxf(0, target * (1.0 - progress)),
		"best": best,
		"worst": worst,
	}

func _on_ending_chosen(action: String) -> void:
	ending.hide()
	match action:
		"raiffeisen":
			_ask_raiffeisen_for_goal()
		"raiffeisen_save":
			_ask_raiffeisen_savings()
		"new_game":
			_new_game()
		"extend":
			_extra_months += 3
			_update()
		"talk":
			_show_onboarding_chat()

func _new_game() -> void:
	chat.hide()
	chat.clear_messages()
	location.hide()
	profile_panel.hide()
	selected = ""
	_last_score = -1
	_start = {}
	_score_log = []
	_pending_cause = ""
	_shown_outcomes = {}
	_extra_months = 0
	_chat_place = ""
	controller.reset_game()

func _ask_raiffeisen_for_goal() -> void:
	if controller.busy:
		return
	var goal_text := str(_outcome_data(controller.state).get("goal_text", "obiectivul meu"))
	_show_onboarding_chat()
	chat.append({"role": "AIngel", "text": "Ai atins obiectivul în joc. Hai să vedem cum îl atingi și în realitate, cu Raiffeisen."})
	controller.send_message("Am atins în joc obiectivul meu (%s). Ce produse Raiffeisen mă ajută să-l ating și în realitate? Dă-mi câteva recomandări și explică-mi beneficiile lor." % goal_text)

func _ask_raiffeisen_savings() -> void:
	if controller.busy:
		return
	_show_onboarding_chat()
	chat.append({"role": "AIngel", "text": "Ai ajuns la obiectiv, dar se putea și mai bine. Hai să vedem ce soluții Raiffeisen te ajută să economisești mai ușor."})
	controller.send_message("Ce soluții Raiffeisen mă ajută să economisesc mai ușor, pornind de la cheltuielile mele și de la alegerile care m-au costat puncte? Dă-mi câteva recomandări și explică-mi beneficiile lor.")

func _build_toast() -> void:
	toast = PanelContainer.new()
	var style := Kit.box(Kit.INK, Kit.INK, 14)
	style.set_corner_radius_all(12)
	toast.add_theme_stylebox_override("panel", style)
	toast.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(toast)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	toast.add_child(row)
	_toast_delta = Kit.strong("+0", 20)
	_toast_delta.autowrap_mode = TextServer.AUTOWRAP_OFF
	_toast_delta.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(_toast_delta)
	var texts := VBoxContainer.new()
	row.add_child(texts)
	_toast_text = Kit.strong("", 16, Kit.PAPER)
	_toast_text.autowrap_mode = TextServer.AUTOWRAP_OFF
	texts.add_child(_toast_text)
	var detail := Kit.text("", 13, Color("d9dcc8"))
	detail.autowrap_mode = TextServer.AUTOWRAP_OFF
	texts.add_child(detail)
	toast.hide()

func _show_toast(delta: int, cause: String, detail: String) -> void:
	var chip := Kit.box(Color("dcefc9") if delta > 0 else Color("f1c9c1"), Color("dcefc9") if delta > 0 else Color("f1c9c1"), 8)
	chip.set_corner_radius_all(8)
	chip.shadow_size = 0
	chip.shadow_offset = Vector2.ZERO
	_toast_delta.add_theme_stylebox_override("normal", chip)
	_toast_delta.add_theme_color_override("font_color", Color("24561f") if delta > 0 else Color("7d2417"))
	_toast_delta.text = ("+%d" if delta > 0 else "%d") % delta
	_toast_text.text = cause.left(70)
	(_toast_text.get_parent().get_child(1) as Label).text = detail
	toast.reset_size()
	toast.show()
	_layout()
	if _toast_tween:
		_toast_tween.kill()
	toast.modulate.a = 1.0
	_toast_tween = create_tween()
	_toast_tween.tween_interval(3.2)
	_toast_tween.tween_property(toast, "modulate:a", 0.0, 0.4 if not reduced_motion else 0.0)
	_toast_tween.tween_callback(toast.hide)

func _on_sent(text: String) -> void:
	if channel == "investments":
		controller.ask_investments(text)
	elif channel == "business":
		controller.ask_business(text)
	else:
		var event_id := ""
		if controller.phase == "map":
			event_id = str(_decision_on_screen().get("id", ""))
		controller.send_message(text, event_id)

func _on_message(message: Dictionary) -> void:
	var incoming := str(message.get("channel", "onboarding"))
	var current := channel if channel in ["investments", "business"] else "onboarding"
	if incoming == current:
		chat.append(message)

func _animate_advisor_icon(raised: bool) -> void:
	if _advisor_hover_tween:
		_advisor_hover_tween.kill()
	var target := Vector2.ONE * (1.1 if raised and not advisor_button.disabled else 1.0)
	_advisor_hover_tween = create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	_advisor_hover_tween.tween_property(advisor_button, "scale", target, 0.18 if not reduced_motion else 0.0)

func _toggle_investments() -> void:
	if controller.busy or controller.phase != "map":
		return
	if channel == "investments":
		_show_onboarding_chat()
	else:
		_show_investments()

## greet: AIngel opens with a line of its own; off when the player's question is sent right away.
func _show_onboarding_chat(greet := true) -> void:
	channel = "onboarding"
	chat.invest_mode = false
	chat.attach_kind = "statement"
	chat.set_agent("")
	chat.set_heading("AIngel · ghidul tău")
	chat.clear_messages()
	for message: Dictionary in controller.transcript:
		if controller.phase == "map" and _is_game_log(message):
			continue
		chat.append(message)
	if controller.phase == "map":
		_chat_place = selected if location.visible else ""
		if greet:
			chat.append({"role": "AIngel", "text": _advice_for_screen()})
	_open_chat()

func _is_game_log(message: Dictionary) -> bool:
	var text := str(message.get("text", ""))
	return str(message.get("role", "")) == "Joc" or text.begins_with("Am pregătit orașul") or "a dispărut din cheltuielile lunare" in text or text == "Decizia a fost înregistrată."

# Inside a building only that building's decision counts; another building's cut is not "on screen".
# From the map, the first open cut is what the player is asked to resolve before the next month.
func _decision_on_screen() -> Dictionary:
	for event: Dictionary in controller.events:
		if _chat_place.is_empty():
			if str(event.get("id", "")).begins_with("taie_"):
				return event
		elif str(event.get("institution", "")) == _chat_place:
			return event
	return {}

func _advice_for_screen() -> String:
	# Opened from a building: one open question; a pending decision there still reaches the agent with the message.
	if not _chat_place.is_empty():
		return "Cu ce sfat financiar te pot ajuta în zona de %s?" % NAMES.get(_chat_place, _chat_place)
	var event := _decision_on_screen()
	if event.is_empty():
		return "Nu ai o decizie deschisă. Spune-mi ce vrei să schimbi la bani în luna asta."
	var place: String = NAMES.get(str(event.get("institution", "")), "hartă")
	var title := str(event.get("title", "alegerea asta"))
	var labels: PackedStringArray = []
	for option: Dictionary in event.get("options", []):
		labels.append(str(option.get("label", "")))
	return "La %s ai deschis: %s. Variantele sunt: %s. Scrie «ce aleg?» și compar efectul fiecăreia pe lunile următoare." % [place, title, ", ".join(labels)]

func _show_business() -> void:
	channel = "business"
	chat.invest_mode = true
	chat.attach_kind = "business"
	chat.set_agent("accountant")
	chat.set_heading("Contabil")
	chat.clear_messages()
	if controller.business_transcript.is_empty():
		chat.append({
			"role": "Contabil",
			"text": "Sunt contabilul de la Afacere. Spune-mi ideea, veniturile și cheltuielile. Cu «Adaugă un document» îmi trimiți dosarul sau o factură. Când confirmi cifrele, pornesc firma în oraș, iar taxele apar aici la termen. Cifrele pentru 2026 sunt orientative.",
		})
	else:
		for message: Dictionary in controller.business_transcript:
			chat.append(message)
	_open_chat()

func _show_investments() -> void:
	if controller.busy or controller.phase != "map":
		return
	channel = "investments"
	chat.invest_mode = true
	chat.attach_kind = ""
	chat.set_agent("")
	chat.set_heading("Consultant de investiții\nFonduri și orizont, din catalog")
	chat.clear_messages()
	if controller.advisor_transcript.is_empty():
		chat.append({
			"role": "Consultant de investiții",
			"text": "Spune-mi orizontul și cât poți pune deoparte. Îți arăt produse din catalog; un fond nu are randament garantat, iar un scop sub 3 ani rămâne în economii.",
		})
	else:
		for message: Dictionary in controller.advisor_transcript:
			chat.append(message)
	_open_chat()

func _close_chat() -> void:
	channel = "onboarding"
	chat.invest_mode = false
	chat.attach_kind = "statement"
	_dismiss(chat)
	# Refill only once the panel is hidden, so fresh portraits never flash over the map.
	_panel_tweens[chat].chain().tween_callback(_refill_onboarding_chat)

func _refill_onboarding_chat() -> void:
	if chat.visible:
		return
	chat.set_agent("")
	chat.set_heading("AIngel · ghidul tău")
	chat.clear_messages()
	for message: Dictionary in controller.transcript:
		chat.append(message)

func _open_chat() -> void:
	_layout()
	location.hide()
	profile_panel.hide()
	_reveal(chat)
	chat.input.grab_focus()

func _load_sample() -> void:
	if controller.busy or controller.phase == "map":
		return
	uploader.load_sample()

func _upload_finished(response: Dictionary) -> void:
	if uploader.last_purpose == "business":
		controller.finish_business_document(response)
	else:
		controller.upload_finished(response)

func _pick_statement() -> void:
	if controller.busy:
		return
	if channel == "business":
		uploader.pick_business_document()
		return
	if controller.phase == "map":
		return
	uploader.pick()

func _files_dropped(files: PackedStringArray) -> void:
	if controller.busy or controller.phase not in ["onboarding", "review"]:
		return
	if files.size() != 1:
		controller.last_error = "Adaugă un singur extras."
		_update()
		return
	uploader.upload_path(files[0])

func _show_profile() -> void:
	for child in profile_panel.get_children():
		profile_panel.remove_child(child)
		child.queue_free()
	profile_fields.clear()
	var sc := ScrollContainer.new()
	sc.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	profile_panel.add_child(sc)
	var col := VBoxContainer.new()
	col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	col.add_theme_constant_override("separation", 10)
	sc.add_child(col)
	col.add_child(Kit.text("Verifică profilul tău", 25))
	col.add_child(Kit.text("Aceste date vor porni simularea. Poți corecta valorile sau reveni la conversație.", 14, Kit.MUTED))
	var p: Dictionary = controller.profile
	for field in [["name", "Nume"], ["goal.description", "Obiectiv"]]:
		col.add_child(Kit.text(field[1], 13))
		var entry := LineEdit.new()
		entry.text = str(_profile_value(p, field[0]))
		col.add_child(entry)
		profile_fields[field[0]] = entry
	for field in [["age", "Vârstă"], ["goal.target_amount", "Suma obiectivului (lei)"], ["goal.horizon_months", "Orizont (luni)"], ["income.salary", "Salariu lunar"], ["income.other", "Alte venituri"], ["cash", "Bani disponibili"], ["savings", "Economii"], ["recurring.rent", "Chirie / locuință"], ["recurring.utilities", "Utilități"], ["recurring.subscriptions", "Abonamente"], ["recurring.transport", "Transport"], ["spending.food", "Mâncare"], ["spending.leisure", "Timp liber"]]:
		var row := HBoxContainer.new()
		var label := Kit.text(field[1], 14)
		label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(label)
		var entry := SpinBox.new()
		entry.max_value = 100000000
		entry.min_value = 1 if field[0] in ["age", "goal.horizon_months", "goal.target_amount"] else 0
		entry.value = float(_profile_value(p, field[0]))
		entry.custom_minimum_size.x = 190
		row.add_child(entry)
		col.add_child(row)
		profile_fields[field[0]] = entry
	col.add_child(Kit.text("Toleranță la risc: %s\nCredite: %d · Pentru detalii sau corectarea creditelor, revino la conversație." % [p.get("risk_tolerance", ""), p.get("debts", []).size()], 13, Kit.MUTED))
	if not p.get("categories", []).is_empty():
		col.add_child(Kit.text("Medii lunare din extras", 16))
		for cat: Dictionary in p.get("categories", []):
			col.add_child(Kit.text("%s: %.0f lei/lună" % [cat.get("label", ""), float(cat.get("monthly", 0))], 14))
	col.add_child(Kit.button("Confirmă și deschide harta →", _confirm_profile, true))
	col.add_child(Kit.button("Înapoi la conversație", func(): profile_panel.hide()))
	profile_panel.show()

func _profile_value(p: Dictionary, path: String) -> Variant:
	var value: Variant = p
	for part in path.split("."):
		value = value.get(part, 0) if value is Dictionary else 0
	return value

func _confirm_profile() -> void:
	if controller.busy or controller.needs_recovery or controller.phase != "review" or controller.profile.is_empty():
		return
	var p: Dictionary = controller.profile.duplicate(true)
	for path: String in profile_fields:
		var input: Control = profile_fields[path]
		var value: Variant = input.value if input is SpinBox else input.text
		var parts := path.split(".")
		if parts.size() == 1:
			p[path] = value
		else:
			p[parts[0]][parts[1]] = value
	controller.confirm_profile(p)
	profile_panel.hide()

func _institution(id: String) -> void:
	_catalog_open = false
	selected = id
	chat.hide()
	for child in location_contents.get_children():
		location_contents.remove_child(child)
		child.queue_free()
	location_contents.add_child(Kit.button("← Înapoi pe hartă", func(): location.hide()))
	location_contents.add_child(Kit.text(NAMES.get(id, id), 26))
	var expenses: Dictionary = controller.state.get("monthly", {}).get("expenses", {})
	if id == "work":
		location_contents.add_child(Kit.text("Venit lunar: %.0f lei" % controller.state.get("monthly", {}).get("income", 0), 16))
	else:
		location_contents.add_child(Kit.text("Cheltuieli lunare: %.0f lei" % expenses.get("health" if id == "hospital" else id, 0), 16))
	if id == "business" and controller.state.get("firm") is Dictionary:
		var firm: Dictionary = controller.state["firm"]
		location_contents.add_child(Kit.text("%s · %s" % [firm.get("name", ""), firm.get("regime_label", "")], 16))
		location_contents.add_child(Kit.text("Încasări %.0f lei/lună, cheltuieli de firmă %.0f, taxe de plătit %.0f." % [float(firm.get("monthly_revenue", 0)), float(firm.get("monthly_expenses", 0)), float(firm.get("taxes_due", 0))], 14))
		if str(firm.get("next_due", "")) != "":
			location_contents.add_child(Kit.text("Următorul termen: %s" % firm.get("next_due", ""), 14, Kit.MUTED))
	for cat: Dictionary in controller.state.get("categories", []):
		if str(cat.get("institution", "")) != id:
			continue
		location_contents.add_child(Kit.text("%s · medie %.0f lei/lună" % [cat.get("label", ""), float(cat.get("monthly", 0))], 14))
	var pending := 0
	for event: Dictionary in controller.events:
		if event.get("institution") != id:
			continue
		pending += 1
		if str(event.get("id", "")).begins_with("taie_"):
			location_contents.add_child(Kit.text("Sugestie de reducere", 12, Kit.MUTED))
		location_contents.add_child(Kit.text(str(event.title), 18))
		location_contents.add_child(Kit.text(str(event.text), 14))
		for option: Dictionary in event.get("options", []):
			var button := Kit.button(str(option.label), func():
				_pending_cause = "%s: %s" % [str(event.title), str(option.label)]
				controller.act(id, str(event.id), {"option_id": str(option.id)}))
			button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			button.disabled = controller.busy or controller.needs_recovery
			location_contents.add_child(button)
	if pending == 0:
		location_contents.add_child(Kit.text("Nu ai evenimente de rezolvat aici în această lună. Poți discuta opțiunile cu AIngel.", 14, Kit.MUTED))
	if id == "bank":
		_bank_stats()
		_bank_actions()
	if id == "business":
		var contabil := Kit.button("Contabil", _show_business, true)
		contabil.icon = load("res://assets/raiff/accountant/accountant_idle.png")
		contabil.expand_icon = true
		contabil.add_theme_constant_override("icon_max_width", 40)
		location_contents.add_child(contabil)
	if id != "bank":
		location_contents.add_child(Kit.button("Întreabă-l pe AIngel", func():
			var question := "Ce opțiuni am la %s pentru obiectivul meu?" % NAMES.get(id, id)
			_show_onboarding_chat()
			chat.input.text = question
		))
	if not location.visible:
		_reveal(location)

# AIngel opens on the Raiffeisen offer and immediately asks the agent, which picks products from the catalog.
func _ask_raiffeisen_offer() -> void:
	if controller.busy:
		return
	_show_onboarding_chat(false)
	controller.send_message("Ce produse și servicii Raiffeisen mi se potrivesc acum, pentru obiectivul și cheltuielile mele? Dă-mi câteva recomandări și explică-mi beneficiile lor.")

const EXPENSE_LABELS := {"entertainment": "Divertisment", "home": "Locuință", "market": "Cumpărături", "education": "Educație", "health": "Sănătate", "business": "Firmă", "bank": "Rate la bancă"}
const GOOD := Color("3f7d3a")
const BAD := Color("963b2b")

# Read-only summary of the server state; every figure comes from the snapshot, nothing is recomputed here
# except sums and the monthly difference.
func _bank_stats() -> void:
	var state: Dictionary = controller.state
	var balance: Dictionary = state.get("balance", {})
	var monthly: Dictionary = state.get("monthly", {})
	var expenses: Dictionary = monthly.get("expenses", {})
	var income := float(monthly.get("income", 0))
	var spent := 0.0
	for amount in expenses.values():
		spent += float(amount)
	var left := income - spent
	var panel := PanelContainer.new()
	var surface := Kit.box(Color("f4f1dc"), Color("8e9f73"), 12)
	surface.set_border_width_all(1)
	surface.shadow_size = 0
	surface.shadow_offset = Vector2.ZERO
	panel.add_theme_stylebox_override("panel", surface)
	location_contents.add_child(panel)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 6)
	panel.add_child(col)
	col.add_child(Kit.strong("Statistica ta · luna %d" % int(state.get("month", 0)), 17))
	col.add_child(_stat_row("Venit lunar", income))
	col.add_child(_stat_row("Cheltuieli lunare", spent))
	col.add_child(_stat_row("Îți rămân pe lună", left, GOOD if left >= 0 else BAD))
	col.add_child(HSeparator.new())
	col.add_child(Kit.text("Pe ce se duc banii", 13, Kit.MUTED))
	var rows: Array = []
	for key in expenses.keys():
		if float(expenses[key]) > 0.5:
			rows.append([str(key), float(expenses[key])])
	rows.sort_custom(func(a, b): return a[1] > b[1])
	for row in rows:
		col.add_child(_expense_bar(EXPENSE_LABELS.get(row[0], row[0]), row[1], spent))
	if rows.is_empty():
		col.add_child(Kit.text("Nu ai cheltuieli lunare înregistrate.", 13, Kit.MUTED))
	col.add_child(HSeparator.new())
	col.add_child(Kit.text("Ce ai acum", 13, Kit.MUTED))
	col.add_child(_stat_row("Disponibil", float(balance.get("cash", 0))))
	col.add_child(_stat_row("Economii", float(balance.get("savings", 0))))
	col.add_child(_stat_row("Investiții", float(balance.get("investments", 0))))
	col.add_child(_stat_row("Datorii", float(balance.get("debt", 0)), BAD if float(balance.get("debt", 0)) > 0.5 else Kit.INK))
	var worth := float(balance.get("net_worth", 0))
	col.add_child(_stat_row("Avere netă", worth, GOOD if worth >= 0 else BAD))
	var wellbeing: Dictionary = state.get("wellbeing", {})
	col.add_child(Kit.text("Stres %.0f · Încredere %.0f" % [float(wellbeing.get("stress", 0)), float(wellbeing.get("confidence", 0))], 13, Kit.MUTED))
	var averages: Array = state.get("categories", [])
	if not averages.is_empty():
		col.add_child(HSeparator.new())
		col.add_child(Kit.text("Medii din extras", 13, Kit.MUTED))
		for cat: Dictionary in averages:
			col.add_child(_stat_row(str(cat.get("label", "")), float(cat.get("monthly", 0))))

func _stat_row(caption: String, amount: float, color: Color = Kit.INK) -> HBoxContainer:
	var row := HBoxContainer.new()
	var name_label := Kit.text(caption, 14)
	name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(name_label)
	var value := Kit.strong("%.0f lei" % amount, 14, color)
	value.autowrap_mode = TextServer.AUTOWRAP_OFF
	row.add_child(value)
	return row

func _expense_bar(caption: String, amount: float, total: float) -> VBoxContainer:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 2)
	var share := amount / total * 100.0 if total > 0 else 0.0
	box.add_child(_stat_row("%s · %.0f%%" % [caption, share], amount))
	var bar := ProgressBar.new()
	bar.custom_minimum_size.y = 6
	bar.show_percentage = false
	bar.value = share
	var fill := Kit.box(Color("cdb800"), Color("cdb800"), 0)
	fill.shadow_size = 0
	fill.shadow_offset = Vector2.ZERO
	bar.add_theme_stylebox_override("fill", fill)
	bar.add_theme_stylebox_override("background", Kit.box(Color("dce0c7"), Color("dce0c7"), 0))
	box.add_child(bar)
	return box

func _bank_actions() -> void:
	location_contents.add_child(Kit.strong("Ce vrei să faci cu banii tăi?", 17))
	location_contents.add_child(Kit.text("Suma (lei)", 13, Kit.MUTED))
	var amount := SpinBox.new()
	bank_amount_input = amount
	amount.update_on_text_changed = true
	amount.min_value = 0
	amount.max_value = 100000000
	amount.value = _bank_amount
	amount.value_changed.connect(func(value: float): _bank_amount = value)
	amount.suffix = " lei"
	location_contents.add_child(amount)
	var offer_button := Kit.button("Întreabă-l pe AIngel de serviciile Raiffeisen", _ask_raiffeisen_offer, true)
	offer_button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	offer_button.disabled = controller.busy or controller.needs_recovery
	location_contents.add_child(offer_button)
	for spec in [["save", "Mută în economii"], ["invest", "Investește"], ["repay", "Rambursează datorii"], ["set_monthly_saving", "Economisire lunară automată"], ["set_monthly_invest", "Investiție lunară automată"]]:
		var button := Kit.button(spec[1], func():
			amount.apply()
			_pending_cause = "%s · %.0f lei" % [spec[1], amount.value]
			controller.act("bank", spec[0], {"amount": amount.value}))
		button.disabled = controller.busy or controller.needs_recovery
		location_contents.add_child(button)
	var catalog_button := Kit.button("Vezi catalogul de produse", _products)
	catalog_button.disabled = controller.busy or controller.needs_recovery
	location_contents.add_child(catalog_button)

func _products() -> void:
	controller.load_products()
	while controller.busy:
		await get_tree().process_frame
	if not controller.last_error.is_empty():
		return
	_catalog_open = true
	_render_products()

func _render_products() -> void:
	for child in location_contents.get_children():
		location_contents.remove_child(child)
		child.queue_free()
	location_contents.add_child(Kit.button("← Înapoi la bancă", func(): _institution("bank")))
	location_contents.add_child(Kit.strong("Catalog Raiffeisen", 22))
	location_contents.add_child(Kit.text("Descoperă opțiunile pentru planurile tale.", 14, Kit.MUTED))
	var categories := {"cont": "Banii de zi cu zi", "card": "Carduri", "economii": "Pune bani deoparte", "investitii": "Investește în viitor", "credit": "Credite și refinanțare", "locuinta": "Casa ta", "asigurare": "Protecție și siguranță", "pensie": "Planuri pe termen lung"}
	for product: Dictionary in controller.products:
		var category := str(product.get("category", "altele"))
		if not categories.has(category):
			categories[category] = "Alte opțiuni"
	for category: String in categories:
		var matching: Array = controller.products.filter(func(p: Dictionary): return str(p.get("category", "altele")) == category)
		if matching.is_empty():
			continue
		location_contents.add_child(Kit.strong(categories[category], 16, Kit.MUTED))
		for product: Dictionary in matching:
			var card := PanelContainer.new()
			card.add_theme_stylebox_override("panel", Kit.box(Color("edf0d9"), Kit.INK, 12))
			location_contents.add_child(card)
			var col := VBoxContainer.new()
			col.add_theme_constant_override("separation", 9)
			card.add_child(col)
			col.add_child(Kit.strong(str(product.get("name", "")), 17))
			var summary := str(product.get("best_for", product.get("description", "")))
			if not summary.is_empty():
				col.add_child(Kit.text(summary.capitalize().substr(0, 1) + summary.substr(1), 14))
			var details := VBoxContainer.new()
			details.add_theme_constant_override("separation", 7)
			var toggle := Kit.button("Vezi detaliile +", func(): pass)
			toggle.pressed.connect(func():
				details.visible = not details.visible
				toggle.text = "Închide detaliile −" if details.visible else "Vezi detaliile +")
			col.add_child(toggle)
			col.add_child(details)
			details.hide()
			for field in [["terms", "Ce oferă"], ["conditions", "Condiții"]]:
				var value := str(product.get(field[0], ""))
				if not value.is_empty():
					details.add_child(Kit.strong(field[1], 13))
					details.add_child(Kit.text(value, 13))
			# Agent-facing cautions remain in the backend; the catalog shows product facts.
	if controller.products.is_empty():
		location_contents.add_child(Kit.text("Catalogul nu conține încă produse.", 14))
	if not location.visible:
		_reveal(location)

# Scale around the panel centre, leaving layout and scroll positions untouched.
func _reveal(panel: Control) -> void:
	if _panel_tweens.has(panel):
		_panel_tweens[panel].kill()
	panel.show()
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	panel.pivot_offset = panel.size * 0.5
	panel.scale = Vector2.ONE * (1.0 if reduced_motion else 0.94)
	panel.modulate.a = 1.0 if reduced_motion else 0.0
	var tween := create_tween().set_parallel(true).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	_panel_tweens[panel] = tween
	tween.tween_property(panel, "scale", Vector2.ONE, 0.45)
	tween.tween_property(panel, "modulate:a", 1.0, 0.3)

func _dismiss(panel: Control) -> void:
	if _panel_tweens.has(panel):
		_panel_tweens[panel].kill()
	var tween := create_tween().set_parallel(true).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN)
	_panel_tweens[panel] = tween
	tween.tween_property(panel, "scale", Vector2.ONE * 0.96, 0.2 if not reduced_motion else 0.0)
	tween.tween_property(panel, "modulate:a", 0.0, 0.2 if not reduced_motion else 0.0)
	tween.chain().tween_callback(panel.hide)
