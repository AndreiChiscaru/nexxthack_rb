extends Node
var failures := 0
func check(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)
func _ready() -> void:
	var screen = load("res://scenes/journey.tscn").instantiate()
	add_child(screen)
	await get_tree().process_frame
	check(screen.controller.phase == "welcome", "Journey starts on welcome")
	check(screen.welcome.visible, "Welcome is visible")
	check(not screen.city.visible, "Map waits for onboarding")
	GameLocale.set_locale("en")
	check(screen.start_button.text == "Start playing →", "English welcome")
	GameLocale.set_locale("ro")
	check(screen.start_button.text == "Începe jocul →", "Romanian welcome")
	check(screen.city.PLACES.size() == 8, "Eight institutions available")
	print("[journey-boot] ", "PASS:" if failures == 0 else "FAIL:", " current game boot and localization")
	get_tree().quit(0 if failures == 0 else 1)
