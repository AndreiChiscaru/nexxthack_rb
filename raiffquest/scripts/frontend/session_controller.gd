extends Node
## One in-memory session; only the server changes financial state.
signal changed
signal message_added(message: Dictionary)
const Api = preload("res://scripts/frontend/game_api.gd")
var api_base := ""
var api: Node
var session_id := ""
var phase := "welcome"
var busy := false
var needs_recovery := false
var agent_mode := "unknown"
var last_error := ""
var profile: Dictionary = {}
var state: Dictionary = {}
var events: Array = []
var products: Array = []
var transcript: Array = []
var advisor_transcript: Array = []
var business_transcript: Array = []
var _id := -1
var _operation := ""
var _event_id := ""

func _ready() -> void:
	api = Api.new()
	api.api_base = api_base
	api.timeout_seconds = 240.0
	add_child(api)
	api.request_finished.connect(_response)

func add_message(role: String, text: String, channel: String = "onboarding") -> void:
	var message := {"role": role, "text": text, "channel": channel}
	if channel == "investments":
		advisor_transcript.append(message)
	elif channel == "business":
		business_transcript.append(message)
	else:
		transcript.append(message)
	message_added.emit(message)

func ask_investments(text: String) -> void:
	text = text.strip_edges()
	if busy or session_id.is_empty() or text.is_empty():
		return
	add_message("Tu", text, "investments")
	_track(api.investments_message(session_id, text), "investments")

func ask_business(text: String) -> void:
	text = text.strip_edges()
	if busy or session_id.is_empty() or text.is_empty():
		return
	add_message("Tu", text, "business")
	_track(api.business_message(session_id, text), "business")

func _track(id: int, operation: String) -> void:
	_id = id
	_operation = operation
	busy = true
	last_error = ""
	changed.emit()

func begin() -> void:
	if busy or not session_id.is_empty():
		return
	_track(api.request_json("/api/health"), "health")

func send_message(text: String) -> void:
	text = text.strip_edges()
	if busy or session_id.is_empty() or text.is_empty():
		return
	add_message("Tu", text)
	if phase == "map":
		_track(api.advisor_message(session_id, text), "advisor")
	else:
		profile = {}
		phase = "onboarding"
		_track(api.onboarding_message(session_id, text), "onboarding")

func confirm_profile(value: Dictionary) -> void:
	if busy or needs_recovery or phase != "review" or value.is_empty():
		return
	profile = value.duplicate(true)
	_track(api.start_game(session_id, profile), "start")

func act(institution: String, action: String, params: Dictionary = {}) -> void:
	if busy or needs_recovery or phase != "map":
		return
	_event_id = action
	_track(api.perform_action(session_id, institution, action, params), "action")

func advance() -> void:
	if not busy and not needs_recovery and phase == "map":
		_track(api.advance_month(session_id), "advance")

func refresh() -> void:
	if not busy and not session_id.is_empty():
		_track(api.request_json("/api/game/snapshot", HTTPClient.METHOD_GET, {}, {"session_id": session_id}), "refresh")

func load_products() -> void:
	if not busy:
		_track(api.get_products(), "products")

func upload_started() -> void:
	busy = true
	last_error = ""
	changed.emit()

func upload_finished(response: Dictionary) -> void:
	busy = false
	if not response.get("ok", false):
		last_error = "" if response.get("error", {}).get("code") == "cancelled" else str(response.get("error", {}).get("message", "Nu am putut analiza extrasul."))
	else:
		var data: Dictionary = response.data
		add_message("AIngel", str(data.get("reply") if data.get("reply") else "Am primit datele extrasului. Spune-mi ce obiectiv ai sau ce informații vrei să corectezi."))
		# A statement can alter a previously complete draft; require a new agent confirmation.
		profile = {}
		phase = "onboarding"
	changed.emit()

func _response(id: int, response: Dictionary) -> void:
	if id != _id:
		return
	busy = false
	var operation := _operation
	if not response.get("ok", false):
		last_error = str(response.get("error", {}).get("message", "Cererea nu a reușit."))
		if operation == "refresh" and response.get("status", 0) == 409:
			needs_recovery = false
		if response.get("status", 0) == 404 and operation in ["onboarding", "advisor", "refresh"]:
			last_error += " Sesiunea poate fi expirată. Repornește aplicația pentru o sesiune nouă; conversația curentă rămâne vizibilă aici."
		if operation in ["start", "action", "advance"] and (response.get("status", 0) == 0 or response.get("status", 0) >= 500):
			needs_recovery = true
			last_error += " Nu repeta tranzacția înainte să verifici starea prin «Actualizează»."
		changed.emit()
		return
	if not response.get("data") is Dictionary:
		last_error = "Răspunsul serverului nu are formatul așteptat."
		changed.emit()
		return
	var data: Dictionary = response.data
	match operation:
		"health":
			agent_mode = str(data.get("agent_mode", "unknown"))
			_track(api.create_session(), "session")
			return
		"session":
			session_id = str(data.get("session_id", ""))
			if session_id.is_empty():
				last_error = "Serverul nu a returnat o sesiune."
			else:
				phase = "onboarding"
				add_message("AIngel", "Bine ai venit! Ce ți-ai dori să poți face cu banii tăi? Spune-mi în cuvintele tale; dacă nu ai încă un obiectiv, îl descoperim împreună.")
		"onboarding":
			add_message("AIngel", str(data.get("reply", "")))
			if data.get("done", false) and data.get("profile") is Dictionary:
				profile = data.profile.duplicate(true)
				phase = "review"
		"start", "action", "advance":
			if data.get("state") is Dictionary:
				state = data.state.duplicate(true)
				phase = "map"
				if data.get("pending_events") is Array:
					events = _unique_events(data.pending_events)
				elif operation == "start":
					events = _unique_events(data.get("events", []))
				elif operation == "advance":
					events = _unique_events(events + data.get("events", []))
				else:
					events = events.filter(func(e: Dictionary) -> bool: return str(e.get("id", "")) != _event_id)
			else:
				last_error = "Starea jocului lipsește din răspuns."
		"refresh":
			if data.get("state") is Dictionary and data.get("events") is Array:
				state = data.state.duplicate(true)
				events = _unique_events(data.events)
				needs_recovery = false
				phase = "map"
		"advisor":
			add_message("AIngel", str(data.get("reply", "")))
		"investments":
			add_message("Consultant de investiții", str(data.get("reply", "")), "investments")
		"business":
			add_message("Contabil", str(data.get("reply", "")), "business")
		"products":
			products = data.get("products", [])
	changed.emit()

func _unique_events(items: Array) -> Array:
	var by_id: Dictionary = {}
	for item in items:
		if item is Dictionary and not str(item.get("id", "")).is_empty():
			by_id[str(item.id)] = item.duplicate(true)
	return by_id.values()
