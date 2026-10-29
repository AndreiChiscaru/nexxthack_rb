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
	style.shadow_color = Color("303a2880")
	style.shadow_size = 1
	style.shadow_offset = Vector2(0, 5)
	style.content_margin_left = padding
	style.content_margin_right = padding
	style.content_margin_top = padding
	style.content_margin_bottom = padding
	return style
static func theme() -> Theme:
	var value := Theme.new()
	value.default_font = load("res://assets/raiff/fonts/Figtree-Regular.ttf")
	value.default_font_size = 16
	for type in ["Label", "Button", "LineEdit", "CheckButton", "SpinBox"]:
		for state in ["font_color", "font_hover_color", "font_pressed_color", "font_hover_pressed_color", "font_focus_color"]:
			value.set_color(state, type, INK)
		value.set_color("font_disabled_color", type, Color("626b55"))
	value.set_color("font_placeholder_color", "LineEdit", MUTED)
	value.set_color("font_color", "TextEdit", INK)
	for type in ["LineEdit", "TextEdit"]:
		value.set_color("caret_color", type, INK)
		value.set_constant("caret_width", type, 2)
	value.set_stylebox("normal", "Button", box(Color("edf0d9")))
	value.set_stylebox("hover", "Button", box(Color("fff19a"), INK))
	value.set_stylebox("hover_pressed", "Button", box(YELLOW, INK))
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
static func strong(value: String, size: int = 18, color: Color = INK) -> Label:
	var label := text(value, size, color)
	label.add_theme_font_override("font", load("res://assets/raiff/fonts/Figtree-Bold.ttf"))
	return label

static func button(value: String, action: Callable, primary: bool = false) -> Button:
	var b := Button.new()
	b.text = value
	b.add_theme_font_override("font", load("res://assets/raiff/fonts/Figtree-Bold.ttf"))
	b.custom_minimum_size.y = 38
	if primary:
		var primary_style := box(YELLOW, INK, 12)
		primary_style.set_corner_radius_all(5)
		primary_style.shadow_offset = Vector2(0, 3)
		b.add_theme_stylebox_override("normal", primary_style)
		var hovered := primary_style.duplicate() as StyleBoxFlat
		hovered.bg_color = Color("fff19a")
		b.add_theme_stylebox_override("hover", hovered)
		var down := primary_style.duplicate() as StyleBoxFlat
		down.shadow_offset = Vector2(0,1)
		b.add_theme_stylebox_override("pressed", down)
		b.add_theme_stylebox_override("hover_pressed", down)
	b.pressed.connect(action)
	return b
static func close_button(action: Callable) -> Button:
	var b := Button.new()
	b.icon = load("res://assets/raiff/icon_close.svg")
	b.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
	b.custom_minimum_size = Vector2(36, 36)
	b.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	for state in ["normal", "hover", "pressed", "hover_pressed", "focus"]:
		var style: StyleBoxFlat = box(PAPER if state == "normal" else Color("fff19a"), INK, 0)
		if state == "focus":
			style.bg_color = Color("ffffff00")
		style.set_corner_radius_all(18)
		b.add_theme_stylebox_override(state, style)
	b.pressed.connect(action)
	return b
static func player_portrait(expression: String = "talking", side: float = 40) -> TextureRect:
	var image := portrait("idle", side)
	image.texture = load("res://assets/raiff/characters/male/%s.png" % expression)
	return image

static func portrait(expression: String = "idle", side: float = 60.0) -> TextureRect:
	var image := TextureRect.new()
	image.texture = load("res://assets/raiff/consultant/consultant_%s.png" % expression)
	image.custom_minimum_size = Vector2(side, side)
	image.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	image.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	image.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return image

static func accountant_portrait(side: float = 60.0) -> TextureRect:
	var image := portrait("idle", side)
	image.texture = load("res://assets/raiff/accountant/accountant_idle.png")
	return image

static func profile_picture(user: bool, side: float = 36, agent: String = "") -> TextureRect:
	var image := player_portrait("talking", side) if user else (accountant_portrait(side) if agent == "accountant" else portrait("idle", side))
	image.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	image.stretch_mode = TextureRect.STRETCH_SCALE
	var shader := Shader.new()
	shader.code = """shader_type canvas_item;
render_mode unshaded;
uniform vec4 backdrop : source_color = vec4(0.93, 0.94, 0.85, 1.0);
uniform vec4 crop = vec4(0.1, 0.0, 0.8, 0.68);
varying vec4 tint;
void vertex() {
    tint = COLOR;
}
void fragment() {
    float radius = length(UV - vec2(0.5));
    float edge = max(fwidth(radius), 0.003);
    vec4 portrait = texture(TEXTURE, crop.xy + UV * crop.zw);
    vec3 painted = mix(backdrop.rgb, portrait.rgb, portrait.a);
    float rim = smoothstep(0.46 - edge, 0.46, radius);
    painted = mix(painted, vec3(0.188, 0.227, 0.157), rim);
    COLOR = vec4(painted, 1.0 - smoothstep(0.5 - edge, 0.5, radius)) * tint;
}"""
	var material := ShaderMaterial.new()
	material.shader = shader
	material.set_shader_parameter("backdrop", Color("fff19a") if user else Color("e7edcd"))
	var crop := Vector4(0.18, 0.02, 0.64, 0.55) if user else Vector4(0.08, 0.0, 0.84, 0.65)
	if agent == "accountant":
		crop = Vector4(0.06, 0.0, 0.88, 0.58)
	material.set_shader_parameter("crop", crop)
	image.material = material
	return image
