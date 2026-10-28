extends PanelContainer
## Cardul care apare peste hartă: decizie cu opțiuni, rezultatul alegerii sau informații despre o locație.

signal option_chosen(index: int)
signal advice_requested
signal continue_pressed
signal close_pressed

const Kit := preload("res://scripts/raiff/ui_kit.gd")
const Advisor := preload("res://scripts/raiff/advisor.gd")

var mode := ""
var _scroll: ScrollContainer
var _content: VBoxContainer
var _option_cards: Array = []
var _option_count := 0
var _advice_button: Button

func _ready() -> void:
	add_theme_stylebox_override("panel", Kit.box(Color("1b1e24"), Kit.YELLOW, 14, 22, 2))
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_scroll = ScrollContainer.new()
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	add_child(_scroll)
	_content = VBoxContainer.new()
	_content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_content.add_theme_constant_override("separation", 10)
	_scroll.add_child(_content)
	visible = false
	var holder := get_parent() as Control
	if holder != null:
		holder.resized.connect(_fit)

func close() -> void:
	visible = false
	mode = ""

## Cardul își ia înălțimea conținutului (maxim cât harta) și rămâne centrat.
func _fit() -> void:
	if not visible:
		return
	var holder := get_parent() as Control
	if holder == null:
		return
	var want := _content.get_combined_minimum_size().y + 56.0
	var h := minf(want, holder.size.y - 28.0)
	anchor_left = 0.0
	anchor_right = 1.0
	anchor_top = 0.5
	anchor_bottom = 0.5
	offset_left = 14.0
	offset_right = -14.0
	offset_top = -h * 0.5
	offset_bottom = h * 0.5

func _fit_later() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	_fit()

func _reset(new_mode: String) -> void:
	mode = new_mode
	Kit.clear_children(_content)
	_option_cards.clear()
	_option_count = 0
	_advice_button = null
	_scroll.scroll_vertical = 0
	visible = true
	_fit_later()

func _chip(text: String) -> Control:
	var chip := PanelContainer.new()
	chip.add_theme_stylebox_override("panel", Kit.box(Kit.YELLOW, Kit.YELLOW, 6, 5))
	var l := Kit.label(text, 13, Color("14171c"), true)
	chip.add_child(l)
	return chip

# ---------------------------------------------------------------- decizie

func show_event(event: Dictionary, index: int, total: int, location_name: String) -> void:
	_reset("event")
	var head := HBoxContainer.new()
	head.add_child(_chip(location_name.to_upper()))
	head.add_child(Kit.hspacer())
	head.add_child(Kit.label("Decizia %d din %d  ·  vârsta %d" % [index + 1, total, int(event.age)], 13, Kit.MUTED))
	_content.add_child(head)
	_content.add_child(Kit.wrapped(str(event.title), 26, Kit.TEXT, true))
	_content.add_child(Kit.wrapped(str(event.scene), 15, Kit.TEXT))
	_advice_button = Kit.button("Cere sfatul Consilierului AI", false, 14)
	_advice_button.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	_advice_button.pressed.connect(func() -> void:
		_advice_button.disabled = true
		_advice_button.text = "Sfat primit: vezi panoul din dreapta"
		advice_requested.emit())
	_content.add_child(_advice_button)
	var options: Array = event.options
	_option_count = options.size()
	for i in options.size():
		var card := _option_card(i, options[i])
		_option_cards.append(card)
		_content.add_child(card)
	_content.add_child(Kit.label("Alege cu mouse-ul sau cu tastele 1-%d." % options.size(), 12, Kit.MUTED))
	_focus_later.call_deferred(_advice_button)

func _focus_later(btn: Variant) -> void:
	if is_instance_valid(btn) and btn is Button and btn.is_inside_tree() and btn.is_visible_in_tree() and not btn.disabled:
		btn.grab_focus()

func _option_card(i: int, opt: Dictionary) -> PanelContainer:
	var card := PanelContainer.new()
	var normal := Kit.box(Kit.PANEL_2, Kit.BORDER, 10, 12)
	var hover := Kit.box(Color("353b45"), Kit.YELLOW, 10, 12, 2)
	card.add_theme_stylebox_override("panel", normal)
	card.mouse_filter = Control.MOUSE_FILTER_STOP
	card.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	card.focus_mode = Control.FOCUS_ALL
	card.set_meta("normal", normal)
	card.set_meta("hover", hover)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(row)
	var letter := PanelContainer.new()
	letter.mouse_filter = Control.MOUSE_FILTER_IGNORE
	letter.add_theme_stylebox_override("panel", Kit.box(Color("14171c"), Kit.YELLOW, 8, 6))
	var ll := Kit.label(Advisor.letter(i), 18, Kit.YELLOW, true)
	ll.custom_minimum_size = Vector2(22, 0)
	ll.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	ll.mouse_filter = Control.MOUSE_FILTER_IGNORE
	letter.add_child(ll)
	letter.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	row.add_child(letter)
	var vb := VBoxContainer.new()
	vb.name = "Body"
	vb.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vb.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vb.add_theme_constant_override("separation", 3)
	row.add_child(vb)
	var t := Kit.wrapped(str(opt.title), 16, Kit.TEXT, true)
	t.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vb.add_child(t)
	var d := Kit.wrapped(str(opt.desc), 14, Kit.MUTED)
	d.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vb.add_child(d)
	card.mouse_entered.connect(func() -> void: card.add_theme_stylebox_override("panel", hover))
	card.mouse_exited.connect(func() -> void: card.add_theme_stylebox_override("panel", normal))
	card.gui_input.connect(func(ev: InputEvent) -> void:
		if mode != "event":
			return
		if ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT:
			option_chosen.emit(i)
		elif ev is InputEventKey and ev.pressed and ev.keycode in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
			option_chosen.emit(i))
	return card

func mark_recommended(index: int) -> void:
	if index < 0 or index >= _option_cards.size():
		return
	var card: PanelContainer = _option_cards[index]
	var body := card.find_child("Body", true, false) as VBoxContainer
	var badge := Kit.label("Recomandat de Consilier (estimare)", 12, Kit.YELLOW, true)
	badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(badge)
	_fit_later()

func _unhandled_input(event: InputEvent) -> void:
	if mode != "event" or not visible:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		var n := int(event.keycode) - KEY_1
		if n >= 0 and n < _option_count:
			option_chosen.emit(n)
			get_viewport().set_input_as_handled()

# ---------------------------------------------------------------- rezultat

func show_result(title: String, subtitle: String, lines: Array, button_text: String) -> void:
	_reset("result")
	var head := HBoxContainer.new()
	head.add_child(_chip("REZULTAT"))
	head.add_child(Kit.hspacer())
	_content.add_child(head)
	_content.add_child(Kit.wrapped(title, 24, Kit.TEXT, true))
	_content.add_child(Kit.wrapped(subtitle, 15, Kit.MUTED))
	for line: Dictionary in lines:
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 8)
		var dot := Kit.label("•", 16, line.get("color", Kit.YELLOW))
		dot.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
		row.add_child(dot)
		row.add_child(Kit.wrapped(str(line.text), 15, line.get("color", Kit.TEXT)))
		_content.add_child(row)
	_content.add_child(Kit.label("Explicația detaliată a Consilierului este în panoul din dreapta.", 12, Kit.MUTED))
	var btn := Kit.button(button_text, true, 17)
	btn.size_flags_horizontal = Control.SIZE_SHRINK_END
	btn.pressed.connect(func() -> void: continue_pressed.emit())
	var foot := HBoxContainer.new()
	foot.add_child(Kit.hspacer())
	foot.add_child(btn)
	_content.add_child(foot)
	btn.grab_focus()

# ---------------------------------------------------------------- informații

## `blocks`: listă de {"title","text"} sau {"product": Dictionary}
func show_info(title: String, subtitle: String, blocks: Array, location_name: String) -> void:
	_reset("info")
	var head := HBoxContainer.new()
	head.add_child(_chip(location_name.to_upper()))
	head.add_child(Kit.hspacer())
	_content.add_child(head)
	_content.add_child(Kit.wrapped(title, 24, Kit.TEXT, true))
	if subtitle != "":
		_content.add_child(Kit.wrapped(subtitle, 15, Kit.MUTED))
	for b: Dictionary in blocks:
		var panel := PanelContainer.new()
		panel.add_theme_stylebox_override("panel", Kit.box(Kit.PANEL_2, Kit.BORDER, 8, 10))
		var vb := VBoxContainer.new()
		vb.add_theme_constant_override("separation", 2)
		panel.add_child(vb)
		vb.add_child(Kit.wrapped(str(b.title), 15, Kit.TEXT, true))
		vb.add_child(Kit.wrapped(str(b.text), 14, Kit.MUTED))
		_content.add_child(panel)
	var btn := Kit.button("Închide", true, 16)
	btn.size_flags_horizontal = Control.SIZE_SHRINK_END
	btn.pressed.connect(func() -> void: close_pressed.emit())
	var foot := HBoxContainer.new()
	foot.add_child(Kit.hspacer())
	foot.add_child(btn)
	_content.add_child(foot)
	btn.grab_focus()
