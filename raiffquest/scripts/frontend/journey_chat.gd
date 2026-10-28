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
var face: TextureRect
var close_button: Button
var _rows: Array[Control] = []

func _ready() -> void:
	theme = Kit.theme()
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	add_child(column)
	var header := HBoxContainer.new()
	column.add_child(header)
	face = Kit.portrait("idle", 56)
	header.add_child(face)
	var title := Kit.text("AIngel\nConsilierul tău · pas cu pas", 18)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title)
	close_button = Kit.button("×", func(): closed.emit())
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
	var tip := Kit.text("opțional · sau trage fișierul în fereastră", 11, Kit.MUTED)
	tip.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	actions.add_child(tip)
	review = Kit.button("Verifică profilul →", func(): review_requested.emit(), true)
	review.hide()
	actions.add_child(review)
	resized.connect(_resize_rows)

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
	messages.add_child(row)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var user: bool = message.get("role") == "Tu"
	if user:
		row.add_child(spacer)
	else:
		row.add_child(Kit.portrait("explaining", 42))
	var bubble := PanelContainer.new()
	bubble.add_theme_stylebox_override("panel", Kit.box(Color("fff19a") if user else Color("fffdf3")))
	row.add_child(bubble)
	_rows.append(bubble)
	var contents := VBoxContainer.new()
	bubble.add_child(contents)
	contents.add_child(Kit.text(str(message.get("role", "AIngel")), 12, Kit.MUTED))
	contents.add_child(Kit.text(str(message.get("text", "")), 16))
	if user:
		row.add_child(Kit.text("●", 26))
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
		bubble.custom_minimum_size.x = maxf(120, size.x * 0.78 - 60)

func show_state(busy: bool, phase: String, error: String) -> void:
	send.disabled = busy
	input.editable = not busy
	attach.disabled = busy
	attach.visible = phase != "map"
	sample.disabled = busy
	sample.visible = phase != "map"
	review.visible = phase == "review"
	review.disabled = busy
	close_button.visible = phase == "map"
	status.text = "AIngel îți răspunde…" if busy else error
	status.add_theme_color_override("font_color", Color("963b2b") if not error.is_empty() else Kit.MUTED)
	face.texture = load("res://assets/raiff/consultant/consultant_%s.png" % ("thinking" if busy else "idle"))
