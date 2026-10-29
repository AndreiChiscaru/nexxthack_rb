extends Node
var failed := false
func check(ok: bool, message: String) -> void:
	if not ok:
		failed = true
		push_error(message)
func settle(c: Node) -> void:
	var deadline := Time.get_ticks_msec() + 15000
	while c.busy and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	for frame in range(8):
		await get_tree().process_frame
	check(not c.busy and c.last_error.is_empty(), "Backend request completed")
func _ready() -> void:
	OS.set_environment("RAIFF_API", OS.get_environment("RAIFF_TEST_API"))
	get_window().size = Vector2i(1280, 720)
	var screen = load("res://scenes/journey.tscn").instantiate()
	add_child(screen)
	var c = screen.controller
	c.begin()
	await settle(c)
	check(not c.session_id.is_empty(), "Backend created a dedicated test session")
	c.phase = "review"
	c.confirm_profile({"name":"Test HUD", "age":25,"goal":{"type":"fond_urgenta","description":"Fond de siguranță","target_amount":15000,"horizon_months":12},"income":{"salary":5800},"recurring":{"rent":1800,"utilities":300},"spending":{"food":1000,"leisure":1000},"savings":6000,"cash":2400,"investments":1500,"debts":[],"risk_tolerance":"mediu"})
	await settle(c)
	check(c.phase == "map", "Real backend started the simulation")
	check(screen.hud.cash_value.text == "2.400 lei", "HUD displays backend cash")
	check(screen.hud.surplus_value.text == "+1.700 lei", "HUD displays backend monthly balance")
	c.act("bank", "save", {"amount":100})
	await settle(c)
	check(screen.hud.cash_value.text == "2.300 lei" and screen.hud.savings_value.text == "6.100 lei", "Bank action updates HUD from server response")
	check(is_equal_approx(screen.hud.progress.value, float(c.state.goal.progress) * 100), "HUD reflects server goal progress after action")
	for pending: Dictionary in c.events.duplicate(true):
		c.act(pending.institution, pending.id, {"option_id": pending.options[0].id})
		await settle(c)
	c.advance()
	await settle(c)
	check(screen.hud.month_label.text == "LUNA 1", "Month comes from backend")
	check(screen.hud.cash_value.text == screen.hud.money(float(c.state.balance.cash)), "Month advancement updates cash")
	screen._institution("bank")
	await get_tree().process_frame
	check(screen.location.position.y >= screen.hud.get_global_rect().end.y, "Building actions do not overlap HUD")
	check(screen.location.get_rect().end.y <= screen.size.y - 60, "Building actions fit above map controls")
	print("[stat-hud-integration] mode=", c.agent_mode, " ", "FAIL" if failed else "PASS")
	get_tree().quit(1 if failed else 0)
