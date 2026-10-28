extends RefCounted
const INK := Color("303a28")
const PAPER := Color("fffbed")
const GRASS := Color("b9c98b")
const YELLOW := Color("fee600")
const MUTED := Color("697856")
static func box(color: Color = PAPER, border: Color = INK, padding: int = 14) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.border_color = border
	style.set_border_width_all(2)
	style.corner_radius_top_left = 8
	style.corner_radius_top_right = 20
	style.corner_radius_bottom_left = 20
	style.corner_radius_bottom_right = 8
	style.shadow_color = Color("303a2840")
	style.shadow_size = 1
	style.shadow_offset = Vector2(0, 5)
	style.content_margin_left = padding
	style.content_margin_right = padding
	style.content_margin_top = padding
	style.content_margin_bottom = padding
	return style
static func theme() -> Theme:
	var value := Theme.new()
	var font := FontVariation.new()
	font.base_font = load("res://assets/raiff/fonts/Figtree-Full-VF.ttf")
	font.variation_opentype = {"wght": 550.0}
	value.default_font = font
	value.default_font_size = 16
	for type in ["Label", "Button", "LineEdit", "CheckButton", "SpinBox"]:
		value.set_color("font_color", type, INK)
	value.set_color("font_placeholder_color", "LineEdit", MUTED)
	value.set_color("font_color", "TextEdit", INK)
	for type in ["LineEdit", "TextEdit"]:
		value.set_color("caret_color", type, INK)
		value.set_constant("caret_width", type, 2)
	value.set_stylebox("normal", "Button", box(Color("edf0d9")))
	value.set_stylebox("hover", "Button", box(Color("fff19a"), INK))
	var pressed := box(YELLOW, INK)
	pressed.shadow_offset = Vector2(0, 1)
	value.set_stylebox("pressed", "Button", pressed)
	value.set_stylebox("focus", "Button", box(Color("ffffff00"), Color("a36329"), 0))
	value.set_stylebox("disabled", "Button", box(Color("e3e6d5")))
	value.set_stylebox("normal", "LineEdit", box(PAPER))
	value.set_stylebox("focus", "LineEdit", box(PAPER, Color("6a4cad")))
	value.set_stylebox("panel", "PanelContainer", box())
	return value
static func text(value: String, size: int = 16, color: Color = INK) -> Label:
	var label := Label.new()
	label.text = value
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return label
static func button(value: String, action: Callable, primary: bool = false) -> Button:
	var b := Button.new()
	b.text = value
	b.custom_minimum_size.y = 38
	if primary:
		b.add_theme_stylebox_override("normal", box(YELLOW, INK, 10))
	b.pressed.connect(action)
	return b
static func close_button(action: Callable) -> Button:
	var b := Button.new()
	b.icon = load("res://assets/raiff/icon_close.svg")
	b.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
	b.tooltip_text = "Închide"
	b.custom_minimum_size = Vector2(36, 36)
	b.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	for state in ["normal", "hover", "pressed", "focus"]:
		var style: StyleBoxFlat = box(PAPER if state == "normal" else Color("fff19a"), INK, 0)
		if state == "focus":
			style.bg_color = Color("ffffff00")
		style.set_corner_radius_all(18)
		b.add_theme_stylebox_override(state, style)
	b.pressed.connect(action)
	return b
static func portrait(expression: String = "idle", side: float = 60.0) -> TextureRect:
	var image := TextureRect.new()
	image.texture = load("res://assets/raiff/consultant/consultant_%s.png" % expression)
	image.custom_minimum_size = Vector2(side, side)
	image.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	image.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	image.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return image
