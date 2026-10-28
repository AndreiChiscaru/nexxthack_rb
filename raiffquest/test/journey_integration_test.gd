extends Node
var failed := false
func check(ok: bool, message: String) -> void:
	if not ok:
		failed = true
		push_error(message)
func settle(controller: Node) -> void:
	var deadline := Time.get_ticks_msec() + 15000
	while controller.busy and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	check(not controller.busy, "controller releases busy state")
func _ready() -> void:
	if not ResourceLoader.exists("res://scripts/frontend/session_controller.gd"):
		check(false, "Integrated session controller is not implemented")
		get_tree().quit(1)
		return
	var script = load("res://scripts/frontend/session_controller.gd")
	var c = script.new()
	c.api_base = OS.get_environment("RAIFF_TEST_API")
	add_child(c)
	c.begin()
	await settle(c)
	check(not c.session_id.is_empty(), "session created by backend")
	for text in ["Un fond de siguranta", "Venit 5800, cheltuieli 4100", "Economii 6000, risc mediu"]:
		c.send_message(text)
		await settle(c)
	check(c.phase == "review", "completed profile waits for confirmation")
	check(c.transcript.size() >= 7, "all onboarding messages preserved")
	c.profile.income.salary = 5100
	c.confirm_profile(c.profile)
	await settle(c)
	check(c.phase == "map", "confirmed profile starts real game")
	check(c.state.monthly.income == 5100, "edited profile reaches server")
	var before: float = c.state.balance.savings
	c.act("bank", "save", {"amount": 100})
	await settle(c)
	check(c.state.balance.savings == before + 100, "bank action updates authoritative state")
	var saved_state: Dictionary = c.state.duplicate(true)
	c.act("bank", "unknown-action")
	await settle(c)
	check(not c.last_error.is_empty() and c.state == saved_state, "rejected action preserves state and exposes error")
	c.advance()
	await settle(c)
	check(c.state.month == 1, "month advance connected")
	var count: int = c.transcript.size()
	c.send_message("Cum imi ating scopul?")
	await settle(c)
	check(c.transcript.size() >= count + 2, "advisor appends to the same transcript")
	check(c.transcript[0].role == "AIngel", "onboarding greeting still retained")
	# A lost mutation response must block further mutations until a full snapshot.
	c._track(99999, "advance")
	c._response(99999, {"ok": false, "status": 0, "data": null, "error": {"code": "timeout", "message": "timeout"}})
	c.advance()
	check(not c.busy, "ambiguous mutation blocks a repeated advance")
	if c.busy:
		await settle(c)
	c.events.clear()
	c.refresh()
	await settle(c)
	check(not c.events.is_empty(), "snapshot restores pending event cards")
	c.queue_free()
	print("[journey-integration] ", "FAIL" if failed else "PASS")
	get_tree().quit(1 if failed else 0)
