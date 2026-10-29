extends Node
## Render-only localization. Canonical API IDs and editable player input never change.
signal changed(locale: String)
const CATALOG = "res://localization/game_en.json"
var locale := "ro"
var _catalog: Dictionary = {}
var _patterns: Array = []
var _cache: Dictionary = {}
var _elapsed := 0.0

func _ready() -> void:
	_catalog = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
	var token := RegEx.new()
	token.compile("%[0-9.]*[sdf]")
	for source: String in _catalog:
		var target := str(_catalog[source])
		var matches := token.search_all(source)
		if matches.is_empty():
			continue
		var expression := "^"
		var last := 0
		for match in matches:
			var capture := "(.+?)" if match.get_string().ends_with("s") else "([+−-]?[0-9][0-9.,]*)"
			expression += _escape(source.substr(last, match.get_start() - last)) + capture
			last = match.get_end()
		expression += _escape(source.substr(last)) + "$"
		var regex := RegEx.new()
		if regex.compile(expression) == OK:
			_patterns.append([regex, target, token.search_all(target), source.length() - matches.size() * 3])
	_patterns.sort_custom(func(a, b): return a[3] > b[3])
	var config := ConfigFile.new()
	if config.load("user://game_locale.cfg") == OK:
		locale = str(config.get_value("game", "language", "ro"))
	var forced := OS.get_environment("RAIFF_LOCALE")
	if forced in ["ro", "en"]:
		locale = forced
	if OS.has_feature("web"):
		var stored = JavaScriptBridge.eval("(()=>{try{return localStorage.getItem('raiffquest.locale')||'';}catch(e){return '';}})()")
		if stored in ["ro", "en"]:
			locale = stored
	if locale not in ["ro", "en"]:
		locale = "ro"

func _escape(value: String) -> String:
	var result := ""
	for character in value:
		if character in ["\\", ".", "^", "$", "|", "?", "*", "+", "(", ")", "[", "]", "{", "}"]:
			result += "\\"
		result += character
	return result

func set_locale(value: String) -> void:
	if value not in ["ro", "en"]:
		return
	locale = value
	if OS.has_feature("web"):
		JavaScriptBridge.eval("try { localStorage.setItem('raiffquest.locale', '%s'); document.documentElement.lang = '%s'; } catch(e) {}" % [value, value])
	var config := ConfigFile.new()
	config.set_value("game", "language", value)
	config.save("user://game_locale.cfg")
	changed.emit(locale)
	refresh()

func english(value: String, depth: int = 0) -> String:
	if value.is_empty() or depth > 3:
		return value
	if _catalog.has(value):
		return str(_catalog[value])
	var lower_first := value.substr(0, 1).to_lower() + value.substr(1)
	if _catalog.has(lower_first):
		var translated := str(_catalog[lower_first])
		return translated.substr(0, 1).to_upper() + translated.substr(1)
	if _cache.has(value):
		return _cache[value]
	for pattern in _patterns:
		var match = pattern[0].search(value)
		if match == null:
			continue
		var result: String = pattern[1]
		var tokens: Array = pattern[2]
		if tokens.size() != match.get_group_count():
			continue
		for i in range(tokens.size() - 1, -1, -1):
			var replacement := english(match.get_string(i + 1), depth + 1)
			result = result.substr(0, tokens[i].get_start()) + replacement + result.substr(tokens[i].get_end())
		_cache[value] = result
		return result
	var parts := value.split("\n")
	if parts.size() > 1:
		for i in range(parts.size()):
			parts[i] = english(parts[i], depth + 1)
		return "\n".join(parts)
	var sentences := value.split(". ")
	if sentences.size() > 1:
		for i in range(sentences.size()):
			var punctuation := "." if i < sentences.size() - 1 else ""
			var translated := english(sentences[i] + punctuation, depth + 1)
			sentences[i] = translated.trim_suffix(".") if not punctuation.is_empty() else translated
		return ". ".join(sentences)
	_cache[value] = value
	return value

func text(value: String) -> String:
	return english(value) if locale == "en" else value

func _process(delta: float) -> void:
	_elapsed += delta
	if _elapsed >= 0.12:
		_elapsed = 0.0
		refresh()

func refresh() -> void:
	_walk(get_tree().root)

func _walk(node: Node) -> void:
	if node.get_meta("keep_original_language", false):
		return
	if node is Label or node is Button:
		_property(node, "text")
	elif node is LineEdit or node is TextEdit:
		_property(node, "placeholder_text")
	if node is FileDialog:
		_property(node, "title")
	for child in node.get_children():
		_walk(child)

func _property(node: Node, property: String) -> void:
	var current := str(node.get(property))
	var previous := str(node.get_meta("locale_last_" + property, ""))
	if current != previous or not node.has_meta("locale_source_" + property):
		node.set_meta("locale_source_" + property, current)
	var source := str(node.get_meta("locale_source_" + property))
	var translated := text(source)
	if current != translated:
		node.set(property, translated)
	node.set_meta("locale_last_" + property, translated)
