extends Node
## Exercises the actual GameApi client against the team's FastAPI application.
## Uses mock agents and the actual financial engine for deterministic tests.

const Api := preload("res://scripts/frontend/game_api.gd")
var _api: Node
var _responses: Dictionary = {}
var _checks := 0
var _failed := false

func _ready() -> void:
	_run.call_deferred()

func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failed = true
		push_error(message)

func _wait(id: int) -> Dictionary:
	var deadline := Time.get_ticks_msec() + 8000
	while not _responses.has(id) and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	if not _responses.has(id):
		_check(false, "request %d completed before timeout" % id)
		get_tree().quit(1)
		return {}
	var response: Dictionary = _responses[id]
	_responses.erase(id)
	return response

func _run() -> void:
	var base := OS.get_environment("RAIFF_TEST_API")
	if base.is_empty():
		push_error("Run tools/run_backend_integration.py to start the local backend.")
		get_tree().quit(1)
		return
	_api = Api.new()
	_api.api_base = base
	add_child(_api)
	_api.request_finished.connect(func(id: int, response: Dictionary) -> void: _responses[id] = response)
	var response: Dictionary = await _wait(_api.request_json("/api/health"))
	_check(response.ok and response.data.get("status") == "ok" and response.data.get("agent_model") is String, "merged backend exposes agent configuration")
	response = await _wait(_api.request_json("/api/demo/session", HTTPClient.METHOD_POST))
	_check(not response.ok and response.status == 404, "obsolete demo routes are absent")
	response = await _wait(_api.create_session())
	_check(response.ok and response.data is Dictionary and response.data.has("session_id"), "session response contract")
	if _failed:
		get_tree().quit(1)
		return
	var session_id: String = response.data.session_id
	response = await _wait(_api.get_game_state(session_id))
	_check(not response.ok and response.status == 409, "unstarted session reports HTTP 409")
	for message: String in ["Vreau un fond de urgență.", "Câștig 4300 lei, chiria este 1500 lei.", "Am 1200 lei economii și risc mediu."]:
		response = await _wait(_api.onboarding_message(session_id, message))
		_check(response.ok and response.data.reply is String and response.data.missing_fields is Array, "onboarding reply contract")
	_check(response.data.done and response.data.profile is Dictionary, "mock onboarding provides a completed profile")
	if _failed:
		get_tree().quit(1)
		return
	var profile: Dictionary = response.data.profile.duplicate(true)
	# Verify that start sends the user's confirmed profile, not a fallback.
	profile.income.salary = 5100
	profile.goal.target_amount = 18000
	response = await _wait(_api.start_game(session_id, profile))
	_check(response.ok and response.data.has("state") and response.data.events is Array, "start returns state and events")
	if _failed:
		get_tree().quit(1)
		return
	var initial: Dictionary = response.data.state
	var events: Array = response.data.events
	_check(initial.session_id == session_id and initial.month == 0, "initial state belongs to the active session")
	_check(initial.monthly.income == 5100 and initial.goal.target_amount == 18000, "confirmed profile reaches the backend")
	_check(initial.institutions.size() == 8, "all eight institutions are present")
	response = await _wait(_api.get_game_state(session_id))
	_check(response.ok and response.data == initial, "GET state returns state directly")
	response = await _wait(_api.perform_action(session_id, "bank", "save", {"amount": 500}))
	_check(response.ok and response.data.delta.savings == 500 and response.data.advisor_note is String, "action returns state, delta and advisor note")
	_check(response.data.state.balance.savings == initial.balance.savings + 500, "savings action is reflected by the server")
	response = await _wait(_api.advance_month(session_id))
	_check(not response.ok and response.status == 409, "pending missions block the next month")
	for event: Dictionary in events:
		response = await _wait(_api.perform_action(session_id, event.institution, event.id, {"option_id": event.options[0].id}))
		_check(response.ok and response.data.state.log[-1].institution == event.institution, "event id and option_id are accepted")
	response = await _wait(_api.advance_month(session_id))
	_check(response.ok and response.data.state.month == 1 and response.data.events is Array, "advance returns the next state and new events")
	var advanced: Dictionary = response.data.state
	response = await _wait(_api.get_game_state(session_id))
	_check(response.ok and response.data == advanced, "read after advance returns authoritative state")
	response = await _wait(_api.advisor_message(session_id, "Ce alternative am pentru credit?"))
	_check(response.ok and response.data.reply is String and not response.data.tool_calls.is_empty(), "advisor returns text and tool calls")
	for call: Dictionary in response.data.tool_calls:
		_check(call.name is String and call.args is Dictionary and call.summary is String, "tool call contract")
	response = await _wait(_api.get_products("economii"))
	_check(response.ok and response.data.products is Array and not response.data.products.is_empty(), "catalog response wraps products")
	response = await _wait(_api.get_game_state("nonexistent-frontend-test-session"))
	_check(not response.ok and response.status == 404 and response.error.code == "http", "missing session is a recoverable HTTP error")
	response = await _wait(_api.perform_action(session_id, "bank", "unknown-test-action"))
	_check(not response.ok and response.status == 404 and response.error.code == "http", "unknown action is a recoverable HTTP 404")
	response = await _wait(_api.request_json("/api/game/start", HTTPClient.METHOD_POST, {"session_id": session_id, "profile": {}}))
	_check(not response.ok and response.status == 422 and response.error.message is String, "FastAPI schema validation is displayed safely")
	_api.queue_free()
	await get_tree().process_frame
	print("[backend-contract] %s: %d checks" % ["FAIL" if _failed else "PASS", _checks])
	get_tree().quit(1 if _failed else 0)
