extends Control
## In-scene modal so the confirmation shares the game's palette and typography.
signal confirmed
const Kit = preload("res://scripts/frontend/journey_theme.gd")
var heading_text := "Închei luna curentă?"
var description_text := "Trecem la luna următoare și aplicăm veniturile și cheltuielile lunare."
var note_text := "Asigură-te că ai făcut alegerile dorite pe hartă."
var cancel_text := "Mai rămân"
var confirm_text := "Luna următoare →"
var panel: PanelContainer
var confirm_button: Button
var cancel_button: Button

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	z_index = 100
	mouse_filter = Control.MOUSE_FILTER_STOP
	var shade := ColorRect.new()
	shade.color = Color(0.19, 0.23, 0.16, 0.22)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(shade)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	panel = PanelContainer.new()
	panel.custom_minimum_size.x = 490
	var paper := Kit.box(Kit.PAPER, Kit.INK, 24)
	paper.set_corner_radius_all(22)
	paper.set_border_width_all(3)
	paper.shadow_offset = Vector2(0, 7)
	panel.add_theme_stylebox_override("panel", paper)
	center.add_child(panel)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 18)
	panel.add_child(col)
	var heading := HBoxContainer.new()
	heading.add_theme_constant_override("separation", 12)
	col.add_child(heading)
	var calendar := TextureRect.new()
	calendar.texture = load("res://assets/raiff/hud/calendar.svg")
	calendar.custom_minimum_size = Vector2(34, 34)
	calendar.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	calendar.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	heading.add_child(calendar)
	var title := Kit.strong(heading_text, 23)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	heading.add_child(title)
	var close := Kit.close_button(_cancel)
	close.tooltip_text = ""
	heading.add_child(close)
	var description := Kit.text(description_text, 17)
	description.custom_minimum_size.x = 420
	col.add_child(description)
	var note := Kit.text(note_text, 14, Kit.MUTED)
	col.add_child(note)
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 14)
	col.add_child(actions)
	cancel_button = Kit.button(cancel_text, _cancel)
	confirm_button = Kit.button(confirm_text, _confirm, true)
	for button in [cancel_button, confirm_button]:
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.custom_minimum_size.y = 46
		var focus := Kit.box(Color.TRANSPARENT, Kit.MUTED, 0)
		focus.shadow_size = 0
		focus.shadow_offset = Vector2.ZERO
		button.add_theme_stylebox_override("focus", focus)
		actions.add_child(button)
	hide()

func popup_centered() -> void:
	show()
	panel.pivot_offset = panel.size / 2
	cancel_button.grab_focus()
	if not get_parent().reduced_motion:
		panel.scale = Vector2.ONE * 0.96
		panel.modulate.a = 0.0
		var tween := create_tween().set_parallel(true)
		tween.tween_property(panel, "scale", Vector2.ONE, 0.18).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		tween.tween_property(panel, "modulate:a", 1.0, 0.15)

func _cancel() -> void:
	hide()
	get_parent().advance_button.grab_focus()

func _confirm() -> void:
	if not visible:
		return
	hide()
	confirmed.emit()

func _input(event: InputEvent) -> void:
	if visible and event.is_action_pressed("ui_cancel"):
		_cancel()
		get_viewport().set_input_as_handled()
