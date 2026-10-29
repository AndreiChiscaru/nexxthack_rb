extends SceneTree
## Verifică pachetul Web exportat: identitate, font românesc, boot pe titlu și pornirea jocului.

var _failures: Array[String] = []

func _initialize() -> void:
	call_deferred("_verify")

func _verify() -> void:
	_check(ProjectSettings.get_setting("application/config/name") == "Raiff Quest", "identitate exportată")
	for path: String in [
		"res://assets/raiff/fonts/Figtree-Regular.ttf",
		"res://assets/share/favicon.png",
		"res://scripts/frontend/journey_screen.gd",
	]:
		_check(ResourceLoader.exists(path), "resursă în pachet: " + path)
	_check(not ResourceLoader.exists("res://test/journey_boot_test.tscn"), "scena de test exclusă")
	_check(not ResourceLoader.exists("res://tools/map_preview.gd"), "unealta de captură exclusă")
	var font := load("res://assets/raiff/fonts/Figtree-Regular.ttf") as Font
	_check(font != null, "font UI exportat")
	if font != null:
		for ch in "ăâîșțĂÂÎȘȚ":
			_check(font.has_char(ch.unicode_at(0)), "glifă românească în pachet: " + ch)
	var packed := load("res://scenes/journey.tscn") as PackedScene
	_check(packed != null, "scena principală exportată")
	if packed != null:
		var main := packed.instantiate()
		root.add_child(main)
		await process_frame
		await process_frame
		_check(main.controller.phase == "welcome", "pachetul pornește pe welcome")
		_check(main.welcome.visible, "introducerea este vizibilă")
		_check(main.city.PLACES.size() == 8, "opt instituții în pachet")
		root.get_node("GameLocale").set_locale("en")
		_check(main.start_button.text == "Start playing →", "traducerea engleză exportată")
		root.get_node("GameLocale").set_locale("ro")
		main.queue_free()
		await process_frame
	if _failures.is_empty():
		print("[exported-pack] PASS: identitate, resurse, font RO, boot welcome, opt instituții, traduceri")
		quit(0)
	else:
		for failure: String in _failures:
			push_error("[exported-pack] " + failure)
		quit(1)

func _check(condition: bool, context: String) -> void:
	if not condition and context not in _failures:
		_failures.append(context)
