extends Node
## Developer entry point for map work. Real backend, explicitly fictitious profile.
var screen: Control

func settle(controller: Node) -> bool:
	var deadline := Time.get_ticks_msec() + 20000
	while controller.busy and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	return not controller.busy and controller.last_error.is_empty()

func _ready() -> void:
	screen = preload("res://scenes/journey.tscn").instantiate()
	add_child(screen)
	var controller = screen.controller
	controller.changed.connect(_preview_label)
	controller.begin()
	if not await settle(controller):
		_fail("Nu am putut porni sesiunea de previzualizare.")
		return
	controller.phase = "review"
	controller.confirm_profile({
		"name": "Previzualizare hartă", "age": 25,
		"goal": {"type": "fond_urgenta", "description": "Fond de siguranță", "target_amount": 15000, "horizon_months": 12},
		"income": {"salary": 5800, "other": 0},
		"recurring": {"rent": 1800, "utilities": 300, "subscriptions": 100, "transport": 200},
		"spending": {"food": 1200, "leisure": 500},
		"savings": 6000, "investments": 1500, "cash": 2400,
		"debts": [], "risk_tolerance": "mediu", "business_interest": true
	})
	if not await settle(controller) or controller.phase != "map":
		_fail("Nu am putut încărca harta din backend.")
		return
	_preview_label()
	print("[map-preview] PASS: map ready, backend session created")
	if "--smoke-test" in OS.get_cmdline_user_args():
		get_tree().quit(0)

func _preview_label() -> void:
	screen.mode.text = screen.Kit.SLOGAN

func _fail(message: String) -> void:
	screen.error_label.text = message
	push_error(message + " " + screen.controller.last_error)
	if "--smoke-test" in OS.get_cmdline_user_args():
		get_tree().quit(1)
