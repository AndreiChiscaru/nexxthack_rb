extends RefCounted
## Stil comun pentru interfață: culori, fonturi, panouri, butoane. Totul desenat de motor, fără imagini.

const BG := Color("14171c")
const PANEL := Color("1f2329")
const PANEL_2 := Color("2a2f37")
const BORDER := Color("3a404a")
const YELLOW := Color("ffe600")
const TEXT := Color("f4f4ef")
const MUTED := Color("a9afb8")
const GOOD := Color("62d98f")
const BAD := Color("ff6f61")
const INFO := Color("7bd3f7")
const BOLD_FONT := preload("res://assets/template/fonts/ui_bold.tres")
const MEDIUM_FONT := preload("res://assets/template/fonts/ui_medium.tres")

static func box(bg: Color, border: Color = BORDER, radius: int = 10, pad: int = 14, border_width: int = 1) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.border_color = border
	sb.set_border_width_all(border_width)
	sb.set_corner_radius_all(radius)
	sb.set_content_margin_all(pad)
	return sb

static func label(text: String, size: int = 15, color: Color = TEXT, bold: bool = false) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	if bold:
		l.add_theme_font_override("font", BOLD_FONT)
	return l

static func wrapped(text: String, size: int = 15, color: Color = TEXT, bold: bool = false) -> Label:
	var l := label(text, size, color, bold)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return l

static func button(text: String, primary: bool = false, size: int = 16) -> Button:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_ALL
	b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	b.add_theme_font_size_override("font_size", size)
	b.add_theme_font_override("font", BOLD_FONT)
	var normal := box(YELLOW if primary else PANEL_2, YELLOW if primary else BORDER, 8, 10)
	normal.content_margin_left = 18
	normal.content_margin_right = 18
	var hover := normal.duplicate()
	hover.bg_color = Color("fff35a") if primary else Color("363c46")
	var pressed := normal.duplicate()
	pressed.bg_color = Color("e0c900") if primary else Color("20242a")
	var disabled := normal.duplicate()
	disabled.bg_color = Color("2a2f37")
	disabled.border_color = Color("2a2f37")
	b.add_theme_stylebox_override("normal", normal)
	b.add_theme_stylebox_override("hover", hover)
	b.add_theme_stylebox_override("pressed", pressed)
	b.add_theme_stylebox_override("disabled", disabled)
	b.add_theme_stylebox_override("focus", box(Color(0, 0, 0, 0), INFO, 8, 10, 2))
	var dark := Color("14171c")
	b.add_theme_color_override("font_color", dark if primary else TEXT)
	b.add_theme_color_override("font_hover_color", dark if primary else TEXT)
	b.add_theme_color_override("font_pressed_color", dark if primary else TEXT)
	b.add_theme_color_override("font_focus_color", dark if primary else TEXT)
	b.add_theme_color_override("font_disabled_color", MUTED)
	return b

static func hspacer() -> Control:
	var c := Control.new()
	c.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return c

static func vspace(px: int) -> Control:
	var c := Control.new()
	c.custom_minimum_size = Vector2(0, px)
	return c

static func clear_children(node: Node) -> void:
	for child in node.get_children():
		node.remove_child(child)
		child.queue_free()
