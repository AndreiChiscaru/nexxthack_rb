extends PanelContainer
signal sent(text: String)
signal upload_requested
signal sample_requested
signal review_requested
signal closed
const Kit = preload("res://scripts/frontend/journey_theme.gd")
var scroll: ScrollContainer
var messages: VBoxContainer
var input: LineEdit
var send: Button
var attach: Button
var sample: Button
var review: Button
var status: Label
var close_button: Button
var tip: Label
var layout_width := 940.0
var compact := false
var portraits: Array[Control] = []
var heading: Label
var invest_mode := false
var attach_kind := "statement"
var _rows: Array[Control] = []

func _ready() -> void:
	theme = Kit.theme()
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	add_child(column)
	var header := HBoxContainer.new()
	column.add_child(header)
	heading = Kit.strong("AIngel · ghidul tău", 18)
	heading.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(heading)
	close_button = Kit.close_button(func(): closed.emit())
	header.add_child(close_button)
	scroll = ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	column.add_child(scroll)
	messages = VBoxContainer.new()
	messages.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	messages.add_theme_constant_override("separation", 16)
	scroll.add_child(messages)
	status = Kit.text("", 13, Kit.MUTED)
	column.add_child(status)
	var composer := HBoxContainer.new()
	column.add_child(composer)
	input = LineEdit.new()
	input.placeholder_text = "Spune-mi, în cuvintele tale…"
	input.max_length = 4000
	input.custom_minimum_size.y = 44
	input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	input.text_submitted.connect(func(_value): submit())
	composer.add_child(input)
	send = Kit.button("Trimite →", submit, true)
	composer.add_child(send)
	var actions := HBoxContainer.new()
	column.add_child(actions)
	attach = Kit.button("＋ Adaugă un extras", func(): upload_requested.emit())
	attach.add_theme_font_size_override("font_size", 12)
	attach.custom_minimum_size.y = 30
	actions.add_child(attach)
	sample = Kit.button("Extras de student", func(): sample_requested.emit())
	sample.add_theme_font_size_override("font_size", 12)
	sample.custom_minimum_size.y = 30
	actions.add_child(sample)
	tip = Kit.text("opțional · sau trage fișierul în fereastră", 11, Kit.MUTED)
	tip.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	actions.add_child(tip)
	review = Kit.button("Verifică profilul →", func(): review_requested.emit(), true)
	review.hide()
	actions.add_child(review)
	resized.connect(_resize_rows)

func set_heading(text: String) -> void:
	heading.text = text

func clear_messages() -> void:
	for child in messages.get_children():
		messages.remove_child(child)
		child.queue_free()
	_rows.clear()
	portraits.clear()

func submit() -> void:
	if send.disabled or input.text.strip_edges().is_empty():
		return
	var value := input.text
	input.clear()
	sent.emit(value)

func append(message: Dictionary) -> void:
	var bar := scroll.get_v_scroll_bar()
	var was_bottom := bar.value >= bar.max_value - bar.page - 35
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	messages.add_child(row)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var user: bool = message.get("role") == "Tu"
	if user:
		row.add_child(spacer)
	else:
		var portrait := Kit.profile_picture(false, 36)
		row.add_child(portrait)
		portraits.append(portrait)
	var bubble := PanelContainer.new()
	var surface := Kit.box(Color("fff19a") if user else Color("eef0db"))
	surface.set_border_width_all(0)
	surface.set_corner_radius_all(8)
	surface.shadow_size = 0
	surface.shadow_offset = Vector2.ZERO
	bubble.add_theme_stylebox_override("panel", surface)
	row.add_child(bubble)
	_rows.append(bubble)
	var contents := VBoxContainer.new()
	bubble.add_child(contents)
	contents.add_child(Kit.strong(str(message.get("role", "AIngel")), 12))
	var body := Kit.text(str(message.get("text", "")), 14)
	body.add_theme_constant_override("line_spacing", 5)
	contents.add_child(body)
	if user:
		var portrait := Kit.profile_picture(true, 36)
		row.add_child(portrait)
		portraits.append(portrait)
	else:
		row.add_child(spacer)
	_resize_rows()
	bubble.modulate.a = 0
	create_tween().tween_property(bubble, "modulate:a", 1.0, 0.28)
	if was_bottom or user:
		_scroll_end.call_deferred()

func _scroll_end() -> void:
	await get_tree().process_frame
	scroll.scroll_vertical = int(scroll.get_v_scroll_bar().max_value)

func _resize_rows() -> void:
	for bubble in _rows:
		bubble.custom_minimum_size.x = maxf(120, layout_width - 105 if compact else layout_width * 0.78 - 60)
	for portrait in portraits:
		portrait.visible = true

func show_state(busy: bool, phase: String, error: String) -> void:
	compact = phase == "map"
	_resize_rows()
	send.disabled = busy
	input.editable = not busy
	attach.disabled = busy
	var documents := attach_kind == "business"
	var angel := phase != "map" and not invest_mode
	attach.visible = angel or documents
	attach.text = "＋ Adaugă un document" if documents else "＋ Adaugă un extras"
	tip.visible = angel
	sample.disabled = busy
	sample.visible = angel
	review.visible = phase == "review"
	review.disabled = busy
	close_button.visible = phase == "map"
	status.text = "AIngel îți răspunde…" if busy else error
	status.add_theme_color_override("font_color", Color("963b2b") if not error.is_empty() else Kit.MUTED)
