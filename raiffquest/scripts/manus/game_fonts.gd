extends RefCounted
## Apply already imported project fonts at scene startup. No early
## project.godot font load, implicit system fallback, or repeated font acquisition.

static func create_theme(regular: Font, medium: Font = null, bold: Font = null) -> Theme:
	assert(regular != null, "A project font is required")
	var theme := Theme.new()
	theme.default_font = regular
	if medium != null:
		for control_type: String in ["Button", "CheckButton", "CheckBox", "OptionButton", "MenuButton"]:
			theme.set_font("font", control_type, medium)
	if bold != null:
		theme.set_font("normal_font", "RichTextLabel", regular)
		theme.set_font("bold_font", "RichTextLabel", bold)
	return theme

static func apply_world_label(label: Label3D, font: Font) -> void:
	assert(font != null, "A project font is required")
	# Label3D does not inherit a sibling Control's Theme.
	label.font = font

## Installed only in the verifier's existing finite boot. Observe resolved
## bindings on encountered text controls/world labels and record drawn characters
## their bound font chain lacks: Web exports have no system font fallback, so those
## characters render as boxes. Font families, file sizes and uploads stay unrestricted.
## Bindings come from the base text theme. Glyphs are checked against the drawing
## font: LabelSettings.font when set, or the RichTextLabel faces its [b]/[i]/[code]
## tags select. RichTextLabel [font] spans, content that push_*/append_text built
## instead of `text`, and custom draw calls are not inspected.
class BindingProbe extends Node:
	var _nodes: Dictionary = {}
	var _pending: Dictionary = {}
	var _fonts: Dictionary = {}
	var _font_resources: Dictionary = {}
	var _checked: Dictionary = {}
	var _own_fonts: Dictionary = {}
	var _texts: Dictionary = {}
	var _missing: Dictionary = {}

	func _ready() -> void:
		process_mode = Node.PROCESS_MODE_ALWAYS
		get_tree().node_added.connect(_observe)
		_visit(get_tree().root)

	func _process(_delta: float) -> void:
		# Text setters, Label3D.font and LabelSettings.font expose no change signal.
		# Compare drawn text and own font; unchanged labels do not rerun proof.
		for identity: int in _nodes:
			var node: Node = _nodes[identity].get_ref() as Node
			if node == null:
				continue
			if _visible_text(node) != _texts.get(identity, ""):
				_schedule(node)
			var own: Font = _own_font(node)
			if own != _own_fonts.get(identity):
				_own_fonts[identity] = own
				_schedule(node)

	func _visit(node: Node) -> void:
		_observe(node)
		for child: Node in node.get_children():
			_visit(child)

	func _observe(node: Node) -> void:
		if not (node is Label or node is Button or node is LineEdit or node is TextEdit or node is RichTextLabel or node is ItemList or node is Tree or node is PopupMenu or node is Label3D):
			return
		var identity: int = node.get_instance_id()
		if not _nodes.has(identity):
			_nodes[identity] = weakref(node)
			if node is Control:
				node.theme_changed.connect(_schedule.bind(node))
			_own_fonts[identity] = _own_font(node)
		_schedule(node)

	func _visible_text(node: Node) -> String:
		if not node.is_inside_tree():
			return ""
		if node is CanvasItem and not node.is_visible_in_tree():
			return ""
		if node is Label3D:
			return node.text if node.is_visible_in_tree() else ""
		if node is Label or node is Button:
			return node.text
		if node is LineEdit or node is TextEdit:
			return node.text + node.placeholder_text
		if node is RichTextLabel:
			return node.get_parsed_text()
		var parts: PackedStringArray = []
		if node is ItemList or node is PopupMenu:
			if node is PopupMenu and not node.visible:
				return ""
			for index: int in range(node.item_count):
				parts.append(node.get_item_text(index))
		if node is Tree:
			var item: TreeItem = node.get_root()
			if item != null and node.hide_root:
				item = item.get_next_visible()
			while item != null:
				for column: int in range(node.columns):
					parts.append(item.get_text(column))
				item = item.get_next_visible()
		return "\n".join(parts)

	## Whitespace, controls and default-ignorable format characters draw no glyph.
	static func _draws_glyph(codepoint: int) -> bool:
		if codepoint <= 0x20 or (codepoint >= 0x7F and codepoint <= 0xA0) or codepoint == 0xAD:
			return false
		if codepoint == 0x34F or codepoint == 0x61C or codepoint == 0x1680 or codepoint == 0x3000 or codepoint == 0xFEFF:
			return false
		if (codepoint >= 0x180B and codepoint <= 0x180F) or (codepoint >= 0x2000 and codepoint <= 0x200F):
			return false
		if (codepoint >= 0x2028 and codepoint <= 0x202F) or (codepoint >= 0x205F and codepoint <= 0x206F):
			return false
		return not ((codepoint >= 0xFE00 and codepoint <= 0xFE0F) or (codepoint >= 0xE0000 and codepoint <= 0xE0FFF))

	## Font set on the node itself rather than through its theme.
	static func _own_font(node: Node) -> Font:
		if node is Label3D:
			return node.font
		if node is Label and node.label_settings != null:
			return node.label_settings.font
		return null

	## Fonts that may draw this node's text; empty when inline font spans choose them.
	func _drawing_fonts(node: Node, binding: Font) -> Array[Font]:
		var fonts: Array[Font] = []
		if node is Label and _own_font(node) != null:
			fonts.append(_own_font(node))
		elif not node is RichTextLabel:
			fonts.append(binding)
		elif not (_built_outside_text(node as RichTextLabel) or node.text.contains("[font=") or node.text.contains("[font ")):
			fonts.append(binding)
			if node.bbcode_enabled:
				var bold: bool = node.text.contains("[b]")
				var italics: bool = node.text.contains("[i]")
				if bold:
					fonts.append(node.get_theme_font("bold_font"))
				if italics:
					fonts.append(node.get_theme_font("italics_font"))
				if bold and italics:
					fonts.append(node.get_theme_font("bold_italics_font"))
				if node.text.contains("[code]"):
					fonts.append(node.get_theme_font("mono_font"))
		return fonts

	## clear(), push_* and append_text leave `text` unchanged, so compare the drawn
	## content with what `text` alone parses to.
	static func _built_outside_text(node: RichTextLabel) -> bool:
		var parsed := RichTextLabel.new()
		parsed.auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
		parsed.bbcode_enabled = node.bbcode_enabled
		parsed.custom_effects = node.custom_effects
		parsed.text = node.atr(node.text)
		var differs: bool = parsed.get_parsed_text() != node.get_parsed_text()
		parsed.free()
		return differs

	## A character is missing when none of the node's drawing fonts has it.
	func _record_missing(node: Node, fonts: Array[Font], text: String) -> void:
		if fonts.all(func(font: Font) -> bool: return font == null):
			return
		for index: int in range(text.length()):
			var codepoint: int = text.unicode_at(index)
			if _missing.has(codepoint) or not _draws_glyph(codepoint):
				continue
			var drawn: bool = false
			for font: Font in fonts:
				if font != null and font.has_char(codepoint):
					drawn = true
					break
			if not drawn:
				_missing[codepoint] = str(node.get_path())

	func _schedule(node: Node) -> void:
		if not is_instance_valid(node):
			return
		var identity: int = node.get_instance_id()
		if _pending.has(identity):
			return
		_pending[identity] = true
		_check.call_deferred(identity)

	func _font_changed() -> void:
		_font_resources.clear()
		for reference: WeakRef in _nodes.values():
			var node: Node = reference.get_ref() as Node
			if node != null:
				_schedule(node)

	func _record_font(font: Font, seen: Dictionary) -> void:
		if font == null or seen.has(font):
			return
		seen[font] = true
		if not _fonts.has(font):
			_fonts[font] = true
			font.changed.connect(_font_changed)
		if font is FontVariation:
			_record_font(font.base_font, seen)
		else:
			_font_resources[font] = true
		for fallback: Font in font.fallbacks:
			_record_font(fallback, seen)

	func _check(identity: int) -> void:
		_pending.erase(identity)
		var node: Node = _nodes[identity].get_ref() as Node
		if node == null or not node.is_inside_tree():
			return
		var text: String = _visible_text(node)
		_texts[identity] = text
		if text.strip_edges().is_empty():
			return
		_checked[identity] = true
		var bindings: Dictionary = {}
		if node is Label3D:
			bindings["font"] = node.font
		elif node is RichTextLabel:
			bindings["normal_font"] = node.get_theme_font("normal_font")
		else:
			bindings["font"] = node.get_theme_font("font")
		for slot: String in bindings:
			_record_font(bindings[slot], {})
			_record_missing(node, _drawing_fonts(node, bindings[slot]), text)

	func _exit_tree() -> void:
		# Catch late property changes on Label3D (no Control.theme_changed signal).
		for identity: int in _nodes:
			_check(identity)
		var samples: Array[Dictionary] = []
		for codepoint: int in _missing:
			if samples.size() == 20:
				break
			samples.append({"codepoint": "U+%04X" % codepoint, "char": String.chr(codepoint), "node": _missing[codepoint]})
		print("[MANUS_FONT_BINDINGS]" + JSON.stringify({"scope": "boot-encountered-theme-and-Label3D-bindings", "nodes": _checked.size(), "fontResources": _font_resources.size(), "missingGlyphs": _missing.size(), "missingSamples": samples, "errors": 0}))
		for font: Font in _fonts:
			font.changed.disconnect(_font_changed)
		_fonts.clear()
		_font_resources.clear()
		_own_fonts.clear()
		_texts.clear()
		_missing.clear()
