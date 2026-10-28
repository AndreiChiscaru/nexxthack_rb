extends SceneTree
## Verifică pachetul Web exportat: identitate, font românesc, boot pe titlu și pornirea jocului.

var _failures: Array[String] = []

func _initialize() -> void:
	call_deferred("_verify")

func _verify() -> void:
	_check(ProjectSettings.get_setting("application/config/name") == "Raiff Quest", "identitate exportată")
	for path: String in [
		"res://assets/raiff/fonts/Figtree-Full-VF.ttf",
		"res://assets/share/favicon.png",
		"res://scripts/raiff/game_root.gd",
	]:
		_check(ResourceLoader.exists(path), "resursă în pachet: " + path)
	_check(not ResourceLoader.exists("res://test/test_suite.tscn"), "scena de test exclusă")
	_check(not ResourceLoader.exists("res://tools/capture_native.gd"), "unealta de captură exclusă")
	var font := load("res://assets/template/fonts/ui_regular.tres") as Font
	_check(font != null, "font UI exportat")
	if font != null:
		for ch in "ăâîșțĂÂÎȘȚ":
			_check(font.has_char(ch.unicode_at(0)), "glifă românească în pachet: " + ch)
	var packed := load("res://scenes/raiff_main.tscn") as PackedScene
	_check(packed != null, "scena principală exportată")
	if packed != null:
		var main := packed.instantiate()
		root.add_child(main)
		await process_frame
		await process_frame
		_check(str(main.get("phase")) == "title", "pachetul pornește pe ecranul de titlu")
		main.call("start_game")
		await process_frame
		_check(str(main.get("phase")) == "explore", "pachetul pornește jocul")
		var events: Array = main.get("events")
		_check(events.size() == 10, "10 decizii în pachet")
		main.queue_free()
		await process_frame
	if _failures.is_empty():
		print("[exported-pack] PASS: identitate, resurse, font RO, boot pe titlu, joc pornit")
		quit(0)
	else:
		for failure: String in _failures:
			push_error("[exported-pack] " + failure)
		quit(1)

func _check(condition: bool, context: String) -> void:
	if not condition and context not in _failures:
		_failures.append(context)
