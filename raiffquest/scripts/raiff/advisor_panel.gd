extends PanelContainer
## Panou de chat al Consilierului AI. Afișează explicații și apelurile de unelte (tool calls) locale.

signal quick_action(kind: String)

const Kit := preload("res://scripts/raiff/ui_kit.gd")
const DEMO_NOTE := "Simulări locale explicabile. Nu e conectat la un model AI sau la date reale. Produse și cifre fictive."
const STATEMENT_NOTE := "Situația de start vine din extrasul tău, analizat cu OCR și Claude. Deciziile și produsele din joc rămân simulări fictive."

var _note: Label
var _log: RichTextLabel
var _count_label: Label
var _tool_calls := 0

func _ready() -> void:
	add_theme_stylebox_override("panel", Kit.box(Kit.PANEL, Kit.BORDER, 12, 14))
	var root := VBoxContainer.new()
	root.add_theme_constant_override("separation", 8)
	add_child(root)
	var head := HBoxContainer.new()
	root.add_child(head)
	head.add_child(Kit.label("Consilier AI", 17, Kit.YELLOW, true))
	head.add_child(Kit.hspacer())
	_count_label = Kit.label("0 apeluri de unelte", 12, Kit.MUTED)
	head.add_child(_count_label)
	_log = RichTextLabel.new()
	_log.bbcode_enabled = true
	_log.scroll_following = true
	_log.selection_enabled = true
	_log.fit_content = false
	_log.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_log.custom_minimum_size = Vector2(0, 120)
	_log.add_theme_font_size_override("normal_font_size", 13)
	_log.add_theme_font_size_override("bold_font_size", 13)
	_log.add_theme_color_override("default_color", Kit.TEXT)
	_log.add_theme_stylebox_override("normal", Kit.box(Color("171a1f"), Kit.PANEL_2, 8, 10))
	root.add_child(_log)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	root.add_child(row)
	for def: Array in [["profile", "Cum stau?"], ["plan", "Plan de acțiune"], ["products", "Produse demo"]]:
		var b := Kit.button(def[1], false, 13)
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.pressed.connect(func() -> void: quick_action.emit(def[0]))
		row.add_child(b)
	_note = Kit.wrapped(DEMO_NOTE, 11, Kit.MUTED)
	root.add_child(_note)

func set_source(from_statement: bool) -> void:
	_note.text = STATEMENT_NOTE if from_statement else DEMO_NOTE

func reset() -> void:
	_log.clear()
	_tool_calls = 0
	_count_label.text = _calls_text()

func post(messages: Array) -> void:
	for m: Dictionary in messages:
		if str(m.type) == "tool":
			_tool_calls += 1
			_log.append_text("[color=#7bd3f7][b]Tool: %s%s[/b][/color]\n" % [_esc(str(m.name)), _esc(str(m.args))])
			_log.append_text("[color=#a9afb8]%s[/color]\n\n" % _esc(str(m.summary)))
		else:
			_log.append_text("[color=#ffe600][b]Consilier[/b][/color]  %s\n\n" % _esc(str(m.text)))
	_count_label.text = _calls_text()

func _calls_text() -> String:
	if _tool_calls == 1:
		return "1 apel de unealtă"
	return "%d apeluri de unelte" % _tool_calls

func tool_call_count() -> int:
	return _tool_calls

func _esc(text: String) -> String:
	return text.replace("[", "[lb]")
