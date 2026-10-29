extends Control
## Raiff Quest: rădăcina jocului. Gestionează ecranul de titlu, explorarea hărții, deciziile,
## panoul financiar, Consilierul AI și raportul final.

const Sim := preload("res://scripts/raiff/finance_sim.gd")
const Events := preload("res://scripts/raiff/events.gd")
const Advisor := preload("res://scripts/raiff/advisor.gd")
const Catalog := preload("res://scripts/raiff/catalog.gd")
const Kit := preload("res://scripts/raiff/ui_kit.gd")
const WorldMap := preload("res://scripts/raiff/world_map.gd")
const Dashboard := preload("res://scripts/raiff/dashboard_panel.gd")
const AdvisorPanel := preload("res://scripts/raiff/advisor_panel.gd")
const EventCard := preload("res://scripts/raiff/event_card.gd")
const ReportScreen := preload("res://scripts/raiff/report_screen.gd")
const StatementImport := preload("res://scripts/raiff/statement_import.gd")

const DEMO_PERSONA_TITLE := "Personajul tău: Ana Ionescu, 22 de ani"
const DEMO_PERSONA_TEXT := "Specialistă în marketing într-un oraș mare. Venit net 4.300 lei/lună, cheltuieli 3.900 lei, 4.000 lei în cont și 1.200 lei pus deoparte. Ghideaz-o prin 10 decizii financiare, de la 22 la 52 de ani."

var state: Dictionary = {}
var events: Array = []
var current_index := 0
var phase := "title"  # title | explore | event | result | report

var _title_screen: Control
var _game_screen: Control
var _report: Control
var _menu: Control
var _banner: Label
var _progress: ProgressBar
var _progress_label: Label
var _map: Control
var _prompt: Button
var _card: PanelContainer
var _dashboard: PanelContainer
var _advisor: PanelContainer
var _pending_before: Dictionary = {}
var _resume_button: Button
## Răspunsul serverului pentru extrasul încărcat (`analysis` + `game_profile`); gol = personajul demo.
var statement: Dictionary = {}
var _importer: Node
var _persona_title: Label
var _persona_text: Label
var _import_status: Label
var _import_button: Button
var _demo_button: Button

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	events = Events.all()
	_importer = StatementImport.new()
	add_child(_importer)
	_importer.status_changed.connect(_on_import_status)
	_importer.profile_ready.connect(_on_statement_loaded)
	_importer.failed.connect(_on_import_failed)
	var bg := ColorRect.new()
	bg.color = Kit.BG
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	_build_game_screen()
	_build_title_screen()
	_report = ReportScreen.new()
	add_child(_report)
	_report.replay_requested.connect(start_game)
	_report.title_requested.connect(show_title)
	_build_menu()
	show_title()
	var stored: Dictionary = _importer.take_stored_profile()
	if not stored.is_empty():
		_on_statement_loaded(stored)

# ---------------------------------------------------------------- construcție UI

func _build_title_screen() -> void:
	_title_screen = Control.new()
	_title_screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_title_screen)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_title_screen.add_child(center)
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(760, 0)
	panel.add_theme_stylebox_override("panel", Kit.box(Kit.PANEL, Kit.YELLOW, 16, 32, 2))
	center.add_child(panel)
	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 12)
	panel.add_child(vb)
	vb.add_child(Kit.label("RAIFF QUEST", 58, Kit.YELLOW, true))
	vb.add_child(Kit.wrapped(preload("res://scripts/frontend/journey_theme.gd").SLOGAN, 20, Kit.TEXT, true))
	var persona := PanelContainer.new()
	persona.add_theme_stylebox_override("panel", Kit.box(Kit.PANEL_2, Kit.BORDER, 10, 14))
	var pv := VBoxContainer.new()
	persona.add_child(pv)
	_persona_title = Kit.label(DEMO_PERSONA_TITLE, 17, Kit.TEXT, true)
	pv.add_child(_persona_title)
	_persona_text = Kit.wrapped(DEMO_PERSONA_TEXT, 15, Kit.MUTED)
	pv.add_child(_persona_text)
	var import_row := HBoxContainer.new()
	import_row.add_theme_constant_override("separation", 8)
	pv.add_child(Kit.vspace(4))
	pv.add_child(import_row)
	_import_button = Kit.button("Încarcă extrasul tău de cont", false, 15)
	_import_button.pressed.connect(func() -> void: _importer.pick_and_upload())
	import_row.add_child(_import_button)
	_demo_button = Kit.button("Folosește personajul demo", false, 13)
	_demo_button.visible = false
	_demo_button.pressed.connect(_use_demo_persona)
	import_row.add_child(_demo_button)
	_import_status = Kit.wrapped("Joacă cu situația ta reală: extrasul (PDF sau imagine) este citit cu OCR și analizat de AI.", 13, Kit.MUTED)
	pv.add_child(_import_status)
	vb.add_child(persona)
	vb.add_child(Kit.wrapped("Cum se joacă", 16, Kit.YELLOW, true))
	for line in [
		"Mergi pe hartă cu WASD sau săgeți până la clădirea marcată cu „!”, apoi apasă E, Enter sau Spațiu.",
		"Alege o opțiune. Panoul financiar se actualizează, iar Consilierul AI îți explică compromisurile cu cifre.",
		"La 52 de ani primești raportul „Viitorul meu financiar” și un plan de acțiune personalizat.",
	]:
		vb.add_child(Kit.wrapped("•  " + line, 14, Kit.TEXT))
	var start := Kit.button("Începe jocul", true, 20)
	start.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	start.pressed.connect(start_game)
	vb.add_child(start)
	vb.add_child(Kit.wrapped("Joc educațional. Personajul, cifrele și produsele sunt fictive și nu reprezintă oferte sau termeni reali ai Raiffeisen sau ai altei bănci.", 12, Kit.MUTED))
	start.call_deferred("grab_focus")

func _build_game_screen() -> void:
	_game_screen = Control.new()
	_game_screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_game_screen)
	var root := VBoxContainer.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_theme_constant_override("separation", 0)
	_game_screen.add_child(root)
	# bara de sus
	var top := PanelContainer.new()
	top.add_theme_stylebox_override("panel", Kit.box(Color("0e1013"), Kit.BORDER, 0, 10, 0))
	root.add_child(top)
	var th := HBoxContainer.new()
	th.add_theme_constant_override("separation", 14)
	top.add_child(th)
	th.add_child(Kit.label("RAIFF QUEST", 20, Kit.YELLOW, true))
	_progress_label = Kit.label("", 14, Kit.MUTED)
	th.add_child(_progress_label)
	_progress = ProgressBar.new()
	_progress.show_percentage = false
	_progress.custom_minimum_size = Vector2(220, 10)
	_progress.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_progress.max_value = events.size()
	_progress.add_theme_stylebox_override("background", Kit.box(Kit.PANEL_2, Kit.PANEL_2, 5, 0, 0))
	_progress.add_theme_stylebox_override("fill", Kit.box(Kit.YELLOW, Kit.YELLOW, 5, 0, 0))
	th.add_child(_progress)
	th.add_child(Kit.hspacer())
	var menu_btn := Kit.button("Meniu (Esc)", false, 13)
	menu_btn.pressed.connect(func() -> void: _toggle_menu())
	th.add_child(menu_btn)
	# corp
	var body_margin := MarginContainer.new()
	body_margin.size_flags_vertical = Control.SIZE_EXPAND_FILL
	for side in ["left", "right", "top", "bottom"]:
		body_margin.add_theme_constant_override("margin_" + side, 12)
	root.add_child(body_margin)
	var body := HBoxContainer.new()
	body.add_theme_constant_override("separation", 12)
	body_margin.add_child(body)
	# stânga: banner + hartă
	var left := VBoxContainer.new()
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.add_theme_constant_override("separation", 8)
	body.add_child(left)
	var banner_panel := PanelContainer.new()
	banner_panel.add_theme_stylebox_override("panel", Kit.box(Kit.PANEL, Kit.BORDER, 10, 10))
	_banner = Kit.wrapped("", 15, Kit.TEXT)
	banner_panel.add_child(_banner)
	left.add_child(banner_panel)
	var holder := Control.new()
	holder.size_flags_vertical = Control.SIZE_EXPAND_FILL
	holder.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	holder.custom_minimum_size = Vector2(560, 380)
	holder.clip_contents = true
	left.add_child(holder)
	_map = WorldMap.new()
	_map.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	holder.add_child(_map)
	_map.near_changed.connect(_on_near_changed)
	_map.enter_requested.connect(_on_enter_requested)
	_prompt = Kit.button("", true, 17)
	_prompt.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_prompt.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_prompt.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_prompt.offset_bottom = -14
	_prompt.visible = false
	_prompt.focus_mode = Control.FOCUS_NONE
	_prompt.pressed.connect(func() -> void: _on_enter_requested(_map.near_location))
	holder.add_child(_prompt)
	_card = EventCard.new()
	_card.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_card.offset_left = 14
	_card.offset_top = 14
	_card.offset_right = -14
	_card.offset_bottom = -14
	holder.add_child(_card)
	_card.option_chosen.connect(_on_option_chosen)
	_card.advice_requested.connect(_on_advice_requested)
	_card.continue_pressed.connect(_on_continue)
	_card.close_pressed.connect(_on_info_closed)
	left.add_child(Kit.label("WASD / săgeți: mișcare   ·   E / Enter / Spațiu: intră   ·   Click pe o clădire: mergi la ușă", 12, Kit.MUTED))
	# dreapta: panou + consilier
	var right := VBoxContainer.new()
	right.custom_minimum_size = Vector2(430, 0)
	right.add_theme_constant_override("separation", 12)
	body.add_child(right)
	_dashboard = Dashboard.new()
	right.add_child(_dashboard)
	_advisor = AdvisorPanel.new()
	_advisor.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_advisor.quick_action.connect(_on_quick_action)
	right.add_child(_advisor)

func _build_menu() -> void:
	_menu = Control.new()
	_menu.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_menu.visible = false
	add_child(_menu)
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.7)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_menu.add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_menu.add_child(center)
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(340, 0)
	panel.add_theme_stylebox_override("panel", Kit.box(Kit.PANEL, Kit.YELLOW, 14, 24, 2))
	center.add_child(panel)
	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 10)
	panel.add_child(vb)
	vb.add_child(Kit.label("Pauză", 26, Kit.YELLOW, true))
	var resume := Kit.button("Continuă", true, 17)
	_resume_button = resume
	resume.pressed.connect(func() -> void: _toggle_menu())
	var restart := Kit.button("Reîncepe jocul", false, 16)
	restart.pressed.connect(func() -> void:
		_menu.visible = false
		start_game())
	var to_title := Kit.button("Înapoi la titlu", false, 16)
	to_title.pressed.connect(func() -> void:
		_menu.visible = false
		show_title())
	for b in [resume, restart, to_title]:
		vb.add_child(b)

# ---------------------------------------------------------------- flux

func show_title() -> void:
	phase = "title"
	_title_screen.visible = true
	_game_screen.visible = false
	_report.visible = false
	_menu.visible = false
	_map.enabled = false

func start_game() -> void:
	state = Sim.new_state(randi(), statement.get("game_profile", {}))
	events = Events.personalize(Events.all(), state) if state.from_statement else Events.all()
	current_index = 0
	phase = "explore"
	_title_screen.visible = false
	_report.visible = false
	_menu.visible = false
	_game_screen.visible = true
	_card.close()
	_map.reset()
	_advisor.reset()
	_dashboard.update_state(state)
	_advisor.set_source(state.from_statement)
	_advisor.post(_intro_messages())
	_refresh_quest()
	_map.enabled = true

func _intro_messages() -> Array:
	if not state.from_statement:
		return [
			{"type": "say", "text": "Bună, Ana! Sunt Consilierul tău AI (simulare locală). Voi folosi uneltele mele pe datele tale fictive și îți voi explica fiecare compromis."},
			Advisor.get_player_profile(state),
		]
	var insights: Dictionary = statement.game_profile.get("insights", {})
	var first_name := str(state.name).split(" ")[0]
	var messages: Array = [
		{"type": "say", "text": "Bună, %s! Am citit extrasul tău de cont și am pornit simularea de la situația ta reală de azi." % first_name},
		{"type": "tool", "name": "analyze_statement", "args": "(extras, OCR + Claude)",
			"summary": "scor de stabilitate %d/100, risc %s. %s" % [int(insights.get("score", 0)), str(insights.get("risk", "-")), str(insights.get("summary", ""))]},
	]
	for signal_text in insights.get("risk_signals", []):
		messages.append({"type": "say", "text": "Atenție: " + str(signal_text)})
	messages.append(Advisor.get_player_profile(state))
	return messages

func _on_import_status(text: String) -> void:
	_import_status.text = text
	_import_status.add_theme_color_override("font_color", Kit.INFO)
	_import_button.disabled = true

func _on_import_failed(message: String) -> void:
	_import_status.text = "Nu am putut analiza extrasul: " + message
	_import_status.add_theme_color_override("font_color", Kit.BAD)
	_import_button.disabled = false

func _on_statement_loaded(result: Dictionary) -> void:
	statement = result
	var preview := Sim.new_state(0, result.game_profile)
	var loans: Array = preview.loans
	_persona_title.text = "Personajul tău: %s (din extrasul de cont)" % preview.name
	_persona_text.text = "Venit net %s/lună, cheltuieli %s, rate %s (%d %s), %s în cont. Pornești de la 22 de ani cu situația ta de azi și treci prin 10 decizii, până la 52 de ani." % [
		Sim.money(Sim.income(preview)), Sim.money(float(preview.living)), Sim.money(Sim.debt_payments(preview)),
		loans.size(), "credit" if loans.size() == 1 else "credite", Sim.money(float(preview.cash))]
	var insights: Dictionary = result.game_profile.get("insights", {})
	_import_status.text = "Extras analizat: scor de stabilitate %d/100, risc %s. Apasă „Începe jocul”." % [int(insights.get("score", 0)), str(insights.get("risk", "-"))]
	_import_status.add_theme_color_override("font_color", Kit.GOOD)
	_import_button.disabled = false
	_import_button.text = "Încarcă alt extras"
	_demo_button.visible = true

func _use_demo_persona() -> void:
	statement = {}
	_persona_title.text = DEMO_PERSONA_TITLE
	_persona_text.text = DEMO_PERSONA_TEXT
	_import_status.text = "Joacă cu situația ta reală: extrasul (PDF sau imagine) este citit cu OCR și analizat de AI."
	_import_status.add_theme_color_override("font_color", Kit.MUTED)
	_import_button.text = "Încarcă extrasul tău de cont"
	_demo_button.visible = false

func _refresh_quest() -> void:
	_progress.value = current_index
	_progress_label.text = "Vârsta %d  →  52   ·   Decizii: %d/%d" % [int(state.age), current_index, events.size()]
	if current_index < events.size():
		var ev: Dictionary = events[current_index]
		_map.set_marker(str(ev.location))
		_banner.text = "Următoarea decizie: „%s” la %s (vârsta %d). Mergi la clădirea marcată cu „!”." % [ev.title, Events.LOCATION_NAMES[ev.location], int(ev.age)]
	else:
		_map.set_marker("")
		_banner.text = "Ai parcurs toate deciziile."

func _on_near_changed(location_id: String) -> void:
	_prompt.visible = location_id != "" and phase == "explore"
	if location_id != "":
		_prompt.text = "Intră: %s   [E]" % Events.LOCATION_NAMES[location_id]

func _on_enter_requested(location_id: String) -> void:
	if phase != "explore" or location_id == "":
		return
	_map.enabled = false
	_prompt.visible = false
	if current_index < events.size() and str(events[current_index].location) == location_id:
		phase = "event"
		var ev: Dictionary = events[current_index]
		_card.show_event(ev, current_index, events.size(), Events.LOCATION_NAMES[location_id])
	else:
		phase = "info"
		_show_location_info(location_id)

func _on_info_closed() -> void:
	_card.close()
	phase = "explore"
	_map.enabled = true
	_on_near_changed(_map.near_location)

func _on_advice_requested() -> void:
	if phase != "event":
		return
	var ev: Dictionary = events[current_index]
	var result := Advisor.advise_before(state, ev)
	_advisor.post(result.messages)
	_card.mark_recommended(int(result.best))

func _on_option_chosen(idx: int) -> void:
	if phase != "event":
		return
	phase = "result"
	var ev: Dictionary = events[current_index]
	var before := Sim.clone(state)
	var prev_snapshot := Sim.snapshot(state)
	var shock := float(state.shocks[current_index])
	var rep := Sim.resolve(state, ev.options[idx], shock)
	state.history.append(Sim.snapshot(state))
	var expl := Advisor.explain_after(before, ev, idx, shock, state)
	state.decisions.append({
		"event_id": ev.id, "title": ev.title, "age": ev.age, "chosen": idx,
		"chosen_title": ev.options[idx].title, "best": expl.best,
		"best_title": ev.options[int(expl.best)].title, "regret": expl.regret,
	})
	_dashboard.update_state(state, prev_snapshot)
	_advisor.post(expl.messages)
	var last := current_index == events.size() - 1
	_card.show_result(
		"Ai ales: %s" % ev.options[idx].title,
		"Au trecut 3 ani: de la %d la %d de ani." % [int(rep.before.age), int(state.age)],
		_result_lines(rep, shock),
		"Vezi „Viitorul meu financiar”" if last else "Continuă")
	_progress_label.text = "Vârsta %d  →  52   ·   Decizii: %d/%d" % [int(state.age), current_index + 1, events.size()]
	_progress.value = current_index + 1

func _result_lines(rep: Dictionary, shock: float) -> Array:
	var lines: Array = []
	var start: Dictionary = rep.before
	var end: Dictionary = rep.after
	for n: String in rep.notes:
		lines.append({"text": n})
	var d_nw := float(end.net_worth) - float(start.net_worth)
	lines.append({
		"text": "Patrimoniu net: %s → %s (%s)." % [Sim.money(float(start.net_worth)), Sim.money(float(end.net_worth)), Sim.signed_money(d_nw)],
		"color": Kit.GOOD if d_nw >= 0.0 else Kit.BAD,
	})
	var interest := float(rep.interest_paid)
	if interest > 0.5:
		lines.append({"text": "Dobândă plătită în acești 3 ani: %s." % Sim.money(interest), "color": Kit.BAD if interest > 1500.0 else Kit.TEXT})
	if float(rep.monthly_payments) > 0.5:
		lines.append({"text": "Rate lunare la finalul perioadei: %s." % Sim.money(float(rep.monthly_payments))})
	if int(rep.loans_closed) > 0:
		lines.append({"text": "Ai închis %d %s." % [int(rep.loans_closed), "credit" if int(rep.loans_closed) == 1 else "credite"], "color": Kit.GOOD})
	if int(rep.overdraft_months) > 0:
		lines.append({"text": "Ai stat %d luni în descoperit de cont (dobândă 30%%/an)." % int(rep.overdraft_months), "color": Kit.BAD})
	if int(rep.austerity_months) > 0:
		lines.append({"text": "Banca nu ți-a mai acordat descoperit: ai trăit %d luni cu buget redus la minim." % int(rep.austerity_months), "color": Kit.BAD})
	if float(state.fund) > 0.5 or float(start.investments) > 0.5:
		var annual := (Sim.FUND_APR + shock) * 100.0
		lines.append({"text": "Piața: fondurile au avut un randament de aproximativ %s%%/an (estimarea era 7%%)." % ("%.1f" % annual).replace(".", ","), "color": Kit.GOOD if shock >= 0.0 else Kit.MUTED})
	lines.append({"text": "Stres: %d → %d. Încredere financiară: %d → %d." % [int(round(float(start.stress))), int(round(float(end.stress))), int(round(float(start.confidence))), int(round(float(end.confidence)))]})
	return lines

func _on_continue() -> void:
	if phase != "result":
		return
	current_index += 1
	_card.close()
	if current_index >= events.size():
		phase = "report"
		_map.enabled = false
		_report.show_report(state)
		return
	phase = "explore"
	_refresh_quest()
	_map.enabled = true
	_on_near_changed(_map.near_location)

# ---------------------------------------------------------------- locații fără decizie

func _show_location_info(location_id: String) -> void:
	var blocks: Array = []
	var title := ""
	var subtitle := ""
	match location_id:
		"home":
			title = "Acasă: profilul și bugetul tău"
			subtitle = "Aici vezi cum arată o lună obișnuită."
			var profile := Advisor.get_player_profile(state)
			_advisor.post([profile])
			blocks.append({"title": "Buget lunar", "text": "Venit net %s. Cheltuieli %s. Rate %s. Prime de asigurare %s. Surplus lunar: %s." % [
				Sim.money(Sim.income(state)), Sim.money(float(state.living)), Sim.money(Sim.debt_payments(state)),
				Sim.money(float(state.insurance_premium)), Sim.money(Sim.monthly_surplus(state))]})
			blocks.append({"title": "Economii automate", "text": "Fond de urgență: %s/lună. Investiții: %s/lună. Ținta fondului de urgență: %s." % [
				Sim.money(float(state.emergency_contrib)), Sim.money(float(state.invest_contrib)), Sim.money(Sim.emergency_target(state))]})
		"bank":
			title = "Banca: catalog de produse demo"
			subtitle = "Produse fictive, cu termeni inventați pentru joc."
			_advisor.post([{"type": "tool", "name": "search_products", "args": "(categorie=\"toate\")", "summary": "%d produse demo în catalog." % Catalog.all().size()}])
			for p: Dictionary in Catalog.all():
				blocks.append({"title": str(p.name), "text": str(p.note)})
		"work":
			title = "Serviciu: carieră și venit"
			subtitle = "Aici apar deciziile despre salariu și bonusuri."
			blocks.append({"title": "Salariul tău", "text": "Venit net: %s/lună. Salariul crește cu aproximativ 4%% pe an, la fel ca cheltuielile." % Sim.money(float(state.salary))})
			blocks.append({"title": "Lifestyle creep", "text": "Când câștigi mai mult, cheltuielile tind să crească și ele (aici: ~60% din fiecare mărire). Fără un plan, mărirea nu devine economii."})
		"shop":
			title = "Magazin: cheltuielile de zi cu zi"
			subtitle = "Micile cheltuieli se adună."
			blocks.append({"title": "Cheltuieli lunare", "text": "%s pe lună (chirie, mâncare, transport, utilități, diverse). Cresc cu ~4%% pe an din cauza inflației." % Sim.money(float(state.living))})
			blocks.append({"title": "Regula 50/30/20", "text": "Un reper simplu: 50%% nevoi, 30%% dorințe, 20%% economii și datorii. Tu ești la %d%% pentru nevoi." % int(round(float(state.living) / maxf(Sim.income(state), 1.0) * 100.0))})
		"advisor":
			title = "Consilier: ce te pot ajuta să faci"
			subtitle = "Folosește butoanele din panoul din dreapta oricând."
			_advisor.post(Advisor.quick_plan(state))
			blocks.append({"title": "Cum stau?", "text": "Rulează get_player_profile() și îți arată situația curentă."})
			blocks.append({"title": "Plan de acțiune", "text": "Rulează generate_action_plan() și îți dă pașii în ordinea priorității."})
			blocks.append({"title": "Produse demo", "text": "Rulează search_products() pe baza profilului tău."})
	if current_index < events.size():
		var ev: Dictionary = events[current_index]
		blocks.append({"title": "Decizia care te așteaptă", "text": "„%s” la %s (vârsta %d)." % [ev.title, Events.LOCATION_NAMES[ev.location], int(ev.age)]})
	_card.show_info(title, subtitle, blocks, Events.LOCATION_NAMES[location_id])

func _on_quick_action(kind: String) -> void:
	if state.is_empty() or phase == "title":
		return
	match kind:
		"profile":
			_advisor.post(Advisor.quick_profile(state))
		"plan":
			_advisor.post(Advisor.quick_plan(state))
		"products":
			_advisor.post(Advisor.quick_products(state))

# ---------------------------------------------------------------- meniu

func _toggle_menu() -> void:
	if phase == "title" or phase == "report":
		return
	_menu.visible = not _menu.visible
	_map.enabled = (not _menu.visible) and phase == "explore"
	if _menu.visible:
		_resume_button.grab_focus()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("pause") and phase in ["explore", "event", "result", "info"]:
		_toggle_menu()
		get_viewport().set_input_as_handled()
