extends Node
## Real local HTTP tests; no bank server, credentials, or model calls.

const Api := preload("res://scripts/frontend/game_api.gd")
const Config := preload("res://scripts/frontend/api_config.gd")
var _api: Node
var _responses := {}
var _completions := {}
var _failures := PackedStringArray()
var _checks := 0
var _busy_events: Array = []

func _ready() -> void:
	_run.call_deferred()

func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)

func _wait(id: int) -> Dictionary:
	var deadline := Time.get_ticks_msec() + 8000
	while not _responses.has(id) and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	_check(_responses.has(id), "cererea %d se încheie" % id)
	return _responses.get(id, {"ok": false, "status": 0, "data": {}, "error": {"code": "test_timeout"}})

func _run() -> void:
	var base := OS.get_environment("RAIFF_TEST_API")
	if base.is_empty():
		push_error("Run tools/run_frontend_tests.py to start the local HTTP fixture.")
		get_tree().quit(1)
		return
	_check(Config.normalize_base(" https://example.test/ ") == "https://example.test", "normalize base URL")
	_check(Config.normalize_base("file:///tmp/data").is_empty(), "reject non HTTP URL")
	_check(Config.normalize_base("https://user:secret@example.test").is_empty(), "reject credentials in base URL")
	_check(Config.build_url(base, "/api/state", {"id": "a & b"}).ends_with("id=a%20%26%20b"), "encode query parameters")
	_check(Config.build_url(base, "/api/../outside").is_empty(), "reject path traversal")
	_check(Config.build_url(base, "https://other.test/api/state").is_empty(), "reject external request path")
	_api = Api.new()
	_api.api_base = base
	add_child(_api)
	_api.request_finished.connect(func(id: int, response: Dictionary) -> void:
		_responses[id] = response
		_completions[id] = int(_completions.get(id, 0)) + 1)
	_api.busy_changed.connect(func(busy: bool) -> void: _busy_events.append(busy))

	var reply: Dictionary = await _wait(_api.create_session())
	_check(reply.ok and reply.data.session_id == "fixture-session", "create session")
	reply = await _wait(_api.onboarding_message("fixture-session", "  Vreau să economisesc  "))
	_check(reply.ok and reply.data.body.text == "Vreau să economisesc", "send Unicode onboarding message")
	_check(reply.data.body.session_id == "fixture-session", "onboarding includes session")
	reply = await _wait(_api.start_game("fixture-session", {"goal": {"target_amount": 12000}}))
	_check(reply.data.path == "/api/game/start" and reply.data.body.profile.goal.target_amount == 12000, "start uses confirmed profile")
	reply = await _wait(_api.get_game_state("a & b"))
	_check(reply.ok and reply.data.query.session_id[0] == "a & b", "state uses session query")
	reply = await _wait(_api.perform_action("fixture-session", "bank", "save", {"amount": 500}))
	_check(reply.ok and reply.data.body.params.amount == 500 and reply.data.body.institution == "bank", "action payload preserved")
	reply = await _wait(_api.advance_month("fixture-session"))
	_check(reply.data.path == "/api/game/advance" and reply.data.body.session_id == "fixture-session", "advance includes session")
	reply = await _wait(_api.advisor_message("fixture-session", "Ce alternative am?"))
	_check(reply.data.path == "/api/advisor/message", "advisor endpoint")
	reply = await _wait(_api.get_products("savings & deposits"))
	_check(reply.data.query.category[0] == "savings & deposits", "product category encoded")

	reply = await _wait(_api.onboarding_message("", "test"))
	_check(not reply.ok and reply.error.code == "invalid_request", "missing session fails locally")
	reply = await _wait(_api.perform_action("fixture-session", "unknown", "save"))
	_check(not reply.ok and reply.error.code == "invalid_request", "unknown institution rejected")
	reply = await _wait(_api.request_json("/api/invalid-json"))
	_check(not reply.ok and reply.error.code == "invalid_json", "malformed JSON is recoverable")
	reply = await _wait(_api.request_json("/api/invalid-shape"))
	_check(not reply.ok and reply.error.code == "invalid_response", "scalar JSON rejected")
	reply = await _wait(_api.request_json("/api/failure"))
	_check(not reply.ok and reply.status == 503 and reply.error.message == "Serviciu indisponibil", "HTTP error is exposed")
	reply = await _wait(_api.request_json("/api/validation"))
	_check(not reply.ok and reply.status == 422, "FastAPI validation array does not crash client")
	reply = await _wait(_api.request_json("/api/no-content"))
	_check(reply.ok and reply.data.is_empty(), "204 has no JSON requirement")
	reply = await _wait(_api.request_json("/api/large"))
	_check(not reply.ok and reply.error.code == "response_too_large", "large responses bounded")

	_busy_events.clear()
	var slow_id: int = _api.request_json("/api/delay")
	var fast_id: int = _api.get_products()
	_check(slow_id != fast_id and _api.is_busy(), "concurrent requests have distinct IDs")
	await _wait(fast_id)
	_check(_api.is_busy(), "finishing one request leaves the other busy")
	await _wait(slow_id)
	_check(not _api.is_busy() and _busy_events == [true, false], "busy spans all pending requests")
	var cancelled: int = _api.request_json("/api/slow")
	_api.cancel(cancelled)
	reply = await _wait(cancelled)
	_check(reply.error.code == "cancelled", "cancel completes immediately")
	_api.timeout_seconds = 0.15
	reply = await _wait(_api.request_json("/api/slow", HTTPClient.METHOD_POST, {"action": "test"}))
	_check(not reply.ok and reply.error.code == "timeout", "slow mutations time out")
	_api.timeout_seconds = 5.0
	reply = await _wait(_api.request_json("/api/stats"))
	_check(reply.data.slow_posts == 1, "mutation was not automatically retried")
	await get_tree().create_timer(1.3).timeout
	_check(_completions[cancelled] == 1, "cancelled request has no late completion")
	reply = await _wait(_api.create_session())
	_check(reply.ok, "client recovers after timeout and cancellation")
	var nested_ids: Array = []
	var on_busy := func(busy: bool) -> void:
		if busy:
			nested_ids.append(_api.get_products())
	_api.busy_changed.connect(on_busy)
	var outer_id: int = _api.create_session()
	_api.busy_changed.disconnect(on_busy)
	_check(nested_ids.size() == 1 and nested_ids[0] != outer_id, "busy listener can start a distinct request")
	reply = await _wait(outer_id)
	_check(reply.ok and reply.data.session_id == "fixture-session", "nested request preserves original result")
	await _wait(nested_ids[0])
	_api.queue_free()

	await get_tree().process_frame
	for failure: String in _failures:
		push_error(failure)
	print("[frontend-api] %s: %d checks" % ["PASS" if _failures.is_empty() else "FAIL", _checks])
	get_tree().quit(0 if _failures.is_empty() else 1)
