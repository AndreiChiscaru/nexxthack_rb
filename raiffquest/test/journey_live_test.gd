extends Node
## Opt-in integration check against an existing backend. Real calls use synthetic data.
## RAIFF_TEST_API must point to the intended live server; never starts a mock server.
var failed := false
var last_payload: Dictionary = {}
var scene: Control
func check(ok: bool, message: String) -> bool:
	print("[live-flow] ", "PASS " if ok else "FAIL ", message)
	failed = failed or not ok
	return ok
func settle(c: Node) -> bool:
	var deadline := Time.get_ticks_msec() + 245000
	while c.busy and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	return check(not c.busy and c.last_error.is_empty(), "Request completed without server error")
func stop() -> void:
	print("[live-flow] ", "FAIL" if failed else "PASS")
	get_tree().quit(1 if failed else 0)
func _ready() -> void:
	var endpoint := OS.get_environment("RAIFF_TEST_API")
	if not check(not endpoint.is_empty(), "Explicit backend URL configured"):
		stop()
		return
	OS.set_environment("RAIFF_API", endpoint)
	scene = load("res://scenes/journey.tscn").instantiate()
	add_child(scene)
	var c: Node = scene.controller
	c.api.request_finished.connect(func(_id: int, response: Dictionary):
		last_payload = response.get("data", {}) if response.get("data") is Dictionary else {}
	)
	c.begin()
	if not await settle(c):
		stop()
		return
	if not check(c.agent_mode == "live", "Backend requires real agents (mock is rejected)"):
		stop()
		return
	var messages := [
		"Sunt Mara Test, am 29 de ani, sunt programatoare. Acestea sunt date fictive pentru testarea jocului. Vreau un fond de urgenta de 18600 lei in 12 luni. Nu vreau sa imi deschid o afacere.",
		"Salariul meu net lunar este 6173 lei, fara alte venituri sau bursa. Chiria este 1700 lei, utilitatile 420, abonamentele 85, mancarea 1100, transportul 250 si iesirile 350 lei lunar.",
		"Am 4321 lei in contul curent, 2345 lei economii, zero investitii si niciun credit. Toleranta mea la risc este scazuta. Nu am persoane in intretinere. Am terminat facultatea, nu platesc studii, nu am asigurare privata, am costuri medicale de 100 lei lunar. Confirm toate aceste date fictive."
	]
	for text in messages:
		c.send_message(text)
		if not await settle(c):
			stop()
			return
	for i in range(2):
		if c.phase == "review":
			break
		c.send_message("Confirm profilul si obiectivul de 18600 lei in 12 luni. Nu am alte cheltuieli sau venituri. Daca ai toate campurile obligatorii, finalizeaza onboardingul.")
		if not await settle(c):
			stop()
			return
	if not check(c.phase == "review", "Live onboarding completed the profile"):
		print("[live-flow] Missing fields: ", last_payload.get("missing_fields", []))
		stop()
		return
	check(c.profile.income.salary == 6173, "Agent extracted the supplied salary")
	check(c.profile.savings == 2345, "Agent extracted the supplied savings")
	check(c.profile.goal.target_amount == 18600, "Agent extracted the supplied goal")
	if failed:
		stop()
		return
	var initial_chat: int = c.transcript.size()
	c.confirm_profile(c.profile)
	if not await settle(c):
		stop()
		return
	check(c.phase == "map" and scene.city.visible, "Confirmed live profile opens the native map")
	check(c.state.monthly.income == 6173, "Game engine uses the live profile")
	scene.city._reduced_motion = true
	scene.city.navigate_to("bank")
	await get_tree().create_timer(0.3).timeout
	check(scene.selected == "bank" and scene.location.visible, "Avatar arrival opens bank actions")
	var before: Dictionary = c.state.balance.duplicate(true)
	c.act("bank", "save", {"amount": 137})
	if not await settle(c):
		stop()
		return
	check(c.state.balance.savings == before.savings + 137 and c.state.balance.cash == before.cash - 137, "Bank transfer changes both balances on the server")
	if check(not c.events.is_empty(), "Server supplies map events"):
		var event: Dictionary = c.events[0].duplicate(true)
		c.act(event.institution, event.id, {"option_id": event.options[0].id})
		if not await settle(c):
			stop()
			return
		c.refresh()
		if not await settle(c):
			stop()
			return
		check(c.events.all(func(item): return item.id != event.id), "Resolved event stays removed after server refresh")
	var month: int = c.state.month
	for pending: Dictionary in c.events.duplicate(true):
		c.act(pending.institution, pending.id, {"option_id": pending.options[0].id})
		await settle(c)
	c.advance()
	if not await settle(c):
		stop()
		return
	check(c.state.month == month + 1, "Month advances once in the game engine")
	var stable_state: Dictionary = c.state.duplicate(true)
	scene._open_chat()
	c.send_message("Verifica progresul obiectivului meu folosind instrumentele disponibile si calculeaza un plan de economisire pe baza soldurilor actuale, dupa transfer si noua luna. Nu modifica banii.")
	if not await settle(c):
		stop()
		return
	var calls: Array = last_payload.get("tool_calls", [])
	check(not calls.is_empty(), "Live advisor executed backend tools")
	for call in calls:
		print("[live-flow] Tool: ", call.get("name", ""))
	check(c.transcript.size() > initial_chat and scene.chat.visible, "Advisor retains the onboarding conversation")
	c.refresh()
	if not await settle(c):
		stop()
		return
	check(c.state == stable_state, "Advisor tools did not mutate financial state")
	stop()
