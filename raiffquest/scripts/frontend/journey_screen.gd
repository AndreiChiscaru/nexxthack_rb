extends Control
## Native frontend for the shared session API. Financial values are never simulated here.
const Kit = preload("res://scripts/frontend/journey_theme.gd")
const Controller = preload("res://scripts/frontend/session_controller.gd")
const Chat = preload("res://scripts/frontend/journey_chat.gd")
const CityMap = preload("res://scripts/frontend/city_map.gd")
const Upload = preload("res://scripts/frontend/statement_upload.gd")
const NAMES := {"home": "Acasă", "market": "Piață", "education": "Educație", "work": "Loc de muncă", "business": "Afacere", "hospital": "Spital", "bank": "Bancă"}
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
var hud_text: Label
var goal_text: Label
var progress: ProgressBar
var advisor_button: Button
var invest_button: Button
var channel := "onboarding"
var map_controls: HBoxContainer
var advance_button: Button
var recovery_button: Button
var refresh_button: Button
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
var month_dialog: ConfirmationDialog

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
	uploader.finished.connect(controller.upload_finished)
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
	month_dialog = ConfirmationDialog.new()
	month_dialog.title = "Închei luna curentă?"
	month_dialog.dialog_text = "Veniturile și cheltuielile se aplică o singură dată. Sugestia de reducere trebuie aleasă înainte."
	month_dialog.ok_button_text = "Luna următoare"
	month_dialog.cancel_button_text = "Mai rămân"
	month_dialog.confirmed.connect(controller.advance)
	add_child(month_dialog)
	controller.changed.connect(_update)
	get_window().files_dropped.connect(_files_dropped)
	resized.connect(_layout)
	chat.minimum_size_changed.connect(_layout.call_deferred)
	greeting.minimum_size_changed.connect(_layout.call_deferred)
	profile_panel.minimum_size_changed.connect(_layout.call_deferred)
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
	var badge := Kit.text("Q", 24)
	badge.position = Vector2(28, 21)
	badge.size = Vector2(34, 34)
	badge.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	badge.add_theme_stylebox_override("normal", Kit.box(Kit.YELLOW, Kit.INK, 0))
	badge.rotation = -0.06
	add_child(badge)
	var brand := Kit.text("RaiffQuest", 28)
	brand.position = Vector2(74, 19)
	brand.size = Vector2(260, 40)
	add_child(brand)
	mode = Kit.text("Conectare la backend după pornire", 12, Kit.MUTED)
	mode.position = Vector2(29, 59)
	mode.size = Vector2(600, 24)
	add_child(mode)
	error_label = Kit.text("", 13, Color("963b2b"))
	add_child(error_label)
	recovery_button = Kit.button("Verifică starea serverului", controller.refresh, true)
	add_child(recovery_button)
	recovery_button.hide()
	advisor_button = Kit.button("AIngel · Hai să vorbim", _show_onboarding_chat)
	advisor_button.icon = load("res://assets/raiff/consultant/consultant_idle.png")
	advisor_button.expand_icon = true
	advisor_button.add_theme_constant_override("icon_max_width", 52)
	advisor_button.position = Vector2(24, 94)
	advisor_button.size = Vector2(225, 64)
	add_child(advisor_button)
	advisor_button.hide()
	invest_button = Kit.button("Consultant de investiții", _toggle_investments)
	invest_button.position = Vector2(24, 166)
	invest_button.size = Vector2(250, 48)
	add_child(invest_button)
	invest_button.hide()

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
	col.add_child(Kit.text("AINGEL · CONSILIERUL TĂU", 13, Kit.MUTED))
	col.add_child(Kit.text("Hei, bine ai venit!", 30))
	col.add_child(Kit.text("Sunt aici să te ascult și să te însoțesc în aventura ta financiară. Începem cu tine: ce vis ai vrea să transformăm într-un plan?", 20))
	start_button = Kit.button("Începe jocul →", controller.begin, true)
	col.add_child(start_button)
	col.add_child(Kit.text("Simulare educațională · tu alegi ce informații împărtășești.", 12, Kit.MUTED))

func _build_hud() -> void:
	hud = PanelContainer.new()
	add_child(hud)
	var col := VBoxContainer.new()
	hud.add_child(col)
	hud_text = Kit.text("", 13)
	col.add_child(hud_text)
	goal_text = Kit.text("", 12, Kit.MUTED)
	col.add_child(goal_text)
	progress = ProgressBar.new()
	progress.custom_minimum_size.y = 8
	progress.show_percentage = false
	progress.add_theme_stylebox_override("fill", Kit.box(Kit.YELLOW, Kit.YELLOW, 0))
	col.add_child(progress)
	map_controls = HBoxContainer.new()
	map_controls.add_theme_constant_override("separation", 8)
	add_child(map_controls)
	refresh_button = Kit.button("Actualizează", controller.refresh)
	map_controls.add_child(refresh_button)
	advance_button = Kit.button("Luna următoare →", func(): month_dialog.popup_centered(Vector2i(460, 190)), true)
	map_controls.add_child(advance_button)
	hud.hide()
	map_controls.hide()

func _layout() -> void:
	var w := size.x
	var h := size.y
	landscape.pivot_offset = size * Vector2(0.5, 0.42)
	hero.position = Vector2(28, 130)
	greeting.position = Vector2(275, 180)
	greeting.size = Vector2(maxf(420, minf(700, w - 310)), 320)
	chat.position = Vector2(maxf(20, (w - 940) / 2), 105)
	chat.size = Vector2(minf(940, w - 40), maxf(400, h - 155))
	hud.position = Vector2(400, 20)
	hud.size = Vector2(maxf(400, w - 425), 118)
	map_controls.position = Vector2(25, h - 60)
	map_controls.size = Vector2(400, 40)
	recovery_button.position = Vector2(25, h - 150)
	recovery_button.size = Vector2(270, 40)
	error_label.position = Vector2(25, h - 105)
	error_label.size = Vector2(maxf(400, w - 470), 40)
	location.position = Vector2(w - 365, 178)
	location.size = Vector2(340, maxf(260, h - 245))
	profile_panel.position = Vector2(maxf(15, (w - 670) / 2), 95)
	profile_panel.size = Vector2(minf(670, w - 30), maxf(430, h - 125))

func _update() -> void:
	var phase: String = controller.phase
	start_button.disabled = controller.busy or controller.needs_recovery
	start_button.text = "Se conectează…" if controller.busy else "Începe jocul →"
	if not controller.last_error.is_empty():
		start_button.text = "Reîncearcă conectarea →"
	error_label.text = controller.last_error
	recovery_button.visible = controller.needs_recovery
	recovery_button.disabled = controller.busy
	if phase != "review":
		profile_panel.hide()
	mode.text = "Agenți AI conectați · simulare educațională" if controller.agent_mode == "live" else "Mod demonstrativ · răspunsuri de test" if controller.agent_mode == "mock" else "Server neconectat"
	chat.show_state(controller.busy, phase, controller.last_error)
	uploader.session_id = controller.session_id
	welcome.visible = phase == "welcome"
	hud.visible = phase == "map"
	map_controls.visible = phase == "map"
	advisor_button.visible = phase == "map"
	invest_button.visible = phase != "welcome"
	invest_button.position = Vector2(24, 166 if phase == "map" else 94)
	invest_button.text = "Înapoi la AIngel" if channel == "investments" else "Consultant de investiții"
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
		last_phase = phase
	if phase == "map":
		var state: Dictionary = controller.state
		var balance: Dictionary = state.get("balance", {})
		var monthly: Dictionary = state.get("monthly", {})
		var expense := 0.0
		for amount in monthly.get("expenses", {}).values():
			expense += float(amount)
		var wellbeing: Dictionary = state.get("wellbeing", {})
		hud_text.text = "Luna %d  ·  Disponibil: %.0f lei  ·  Economii: %.0f  ·  Investiții: %.0f\nVenit: %.0f  ·  Cheltuieli: %.0f  ·  Stres: %.0f  ·  Încredere: %.0f" % [state.get("month", 0), balance.get("cash", 0), balance.get("savings", 0), balance.get("investments", 0), monthly.get("income", 0), expense, wellbeing.get("stress", 0), wellbeing.get("confidence", 0)]
		var averages: Array = state.get("categories", [])
		if not averages.is_empty():
			var bits: PackedStringArray = []
			for cat: Dictionary in averages:
				if bits.size() == 4:
					break
				bits.append("%s %.0f" % [cat.get("label", ""), float(cat.get("monthly", 0))])
			hud_text.text += "\nMedii din extras: " + ", ".join(bits)
		var goal: Dictionary = state.get("goal", {})
		progress.value = float(goal.get("progress", 0)) * 100
		goal_text.text = "Obiectiv: %.0f lei · %.0f%%" % [goal.get("target_amount", 0), progress.value]
		city.set_institutions(state.get("institutions", []))
		var must_choose := false
		for event: Dictionary in controller.events:
			if str(event.get("id", "")).begins_with("taie_"):
				must_choose = true
				break
		advance_button.disabled = controller.busy or controller.needs_recovery or must_choose
		advance_button.text = "Alege sugestia" if must_choose else "Luna următoare →"
		refresh_button.disabled = controller.busy
		if not selected.is_empty() and location.visible:
			_institution(selected)

func _on_sent(text: String) -> void:
	if channel == "investments":
		controller.ask_investments(text)
	elif channel == "business":
		controller.ask_business(text)
	else:
		controller.send_message(text)

func _on_message(message: Dictionary) -> void:
	var incoming := str(message.get("channel", "onboarding"))
	var current := channel if channel in ["investments", "business"] else "onboarding"
	if incoming == current:
		chat.append(message)

func _toggle_investments() -> void:
	if channel == "investments":
		_show_onboarding_chat()
	else:
		_show_investments()

func _show_onboarding_chat() -> void:
	channel = "onboarding"
	chat.invest_mode = false
	chat.set_heading("AIngel\nConsilierul tău · pas cu pas")
	chat.clear_messages()
	for message: Dictionary in controller.transcript:
		chat.append(message)
	_open_chat()

func _show_business() -> void:
	channel = "business"
	chat.invest_mode = true
	chat.set_heading("Contabil\nAfacere · taxe 2026, PFA sau SRL")
	chat.clear_messages()
	if controller.business_transcript.is_empty():
		chat.append({
			"role": "Contabil",
			"text": "Sunt contabilul de la Afacere. Spune-mi ideea, veniturile și cheltuielile estimate, iar eu compar PFA, SRL micro și impozitul pe profit. Cifrele sunt orientative pentru 2026.",
		})
	else:
		for message: Dictionary in controller.business_transcript:
			chat.append(message)
	_open_chat()

func _show_investments() -> void:
	channel = "investments"
	chat.invest_mode = true
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
	chat.set_heading("AIngel\nConsilierul tău · pas cu pas")
	chat.clear_messages()
	for message: Dictionary in controller.transcript:
		chat.append(message)
	_dismiss(chat)

func _open_chat() -> void:
	location.hide()
	profile_panel.hide()
	_reveal(chat)
	chat.input.grab_focus()

func _load_sample() -> void:
	if controller.busy or controller.phase == "map":
		return
	uploader.load_sample()

func _pick_statement() -> void:
	if controller.busy or controller.phase == "map":
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
			var button := Kit.button(str(option.label), func(): controller.act(id, str(event.id), {"option_id": str(option.id)}))
			button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			button.disabled = controller.busy or controller.needs_recovery
			location_contents.add_child(button)
	if pending == 0:
		location_contents.add_child(Kit.text("Nu ai evenimente de rezolvat aici în această lună. Poți discuta opțiunile cu AIngel.", 14, Kit.MUTED))
	if id == "bank":
		_bank_actions()
	if id == "business":
		location_contents.add_child(Kit.button("Contabil", _show_business, true))
	location_contents.add_child(Kit.button("Întreabă-l pe AIngel", func():
		var question := "Ce opțiuni am la %s pentru obiectivul meu?" % NAMES.get(id, id)
		_show_onboarding_chat()
		chat.input.text = question
	))
	if not location.visible:
		_reveal(location)

func _bank_actions() -> void:
	location_contents.add_child(Kit.text("Transfer în simulare", 17))
	var amount := SpinBox.new()
	amount.min_value = 0
	amount.max_value = 100000000
	amount.value = 100
	amount.suffix = " lei"
	location_contents.add_child(amount)
	for spec in [["save", "Mută în economii"], ["invest", "Investește"], ["repay", "Rambursează datorii"], ["set_monthly_saving", "Economisire lunară automată"], ["set_monthly_invest", "Investiție lunară automată"]]:
		var button := Kit.button(spec[1], func(): controller.act("bank", spec[0], {"amount": amount.value}))
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
	for child in location_contents.get_children():
		location_contents.remove_child(child)
		child.queue_free()
	location_contents.add_child(Kit.button("← Înapoi la bancă", func(): _institution("bank")))
	location_contents.add_child(Kit.text("Catalog Raiffeisen", 22))
	for product: Dictionary in controller.products:
		location_contents.add_child(Kit.text(str(product.get("name", "")), 17))
		location_contents.add_child(Kit.text(str(product.get("description", product.get("suitable_for", ""))), 13))
		if product.has("cautions"):
			location_contents.add_child(Kit.text(str(product.cautions), 12, Kit.MUTED))
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
