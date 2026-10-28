extends "res://scripts/frontend/api_client.gd"
## Frontend entry points for docs/implementation-plan.md section 4.3.
## Session identity is explicit; this layer does not calculate financial state.

const INSTITUTIONS := ["home", "market", "education", "work", "business", "hospital", "bank", "entertainment"]

func create_session() -> int:
	return request_json("/api/session", HTTPClient.METHOD_POST)

func onboarding_message(session_id: String, text: String) -> int:
	return _message("/api/onboarding/message", session_id, text)

func start_game(session_id: String, profile: Dictionary) -> int:
	if session_id.strip_edges().is_empty() or profile.is_empty():
		return reject("Lipsesc sesiunea sau profilul confirmat.")
	return request_json("/api/game/start", HTTPClient.METHOD_POST, {"session_id": session_id, "profile": profile})

func get_game_state(session_id: String) -> int:
	if session_id.strip_edges().is_empty():
		return reject("Sesiunea de joc nu a fost creată.")
	return request_json("/api/game/state", HTTPClient.METHOD_GET, {}, {"session_id": session_id})

func perform_action(session_id: String, institution: String, action_id: String, params: Dictionary = {}) -> int:
	if session_id.strip_edges().is_empty() or institution not in INSTITUTIONS or action_id.strip_edges().is_empty():
		return reject("Sesiunea, instituția sau acțiunea nu este validă.")
	return request_json("/api/game/action", HTTPClient.METHOD_POST, {
		"session_id": session_id, "institution": institution, "action_id": action_id, "params": params,
	})

func advance_month(session_id: String) -> int:
	if session_id.strip_edges().is_empty():
		return reject("Sesiunea de joc nu a fost creată.")
	return request_json("/api/game/advance", HTTPClient.METHOD_POST, {"session_id": session_id})

func advisor_message(session_id: String, text: String, event_id: String = "") -> int:
	if session_id.strip_edges().is_empty() or text.strip_edges().is_empty():
		return reject("Introdu un mesaj și pornește o sesiune înainte de a continua.")
	var body := {"session_id": session_id, "text": text.strip_edges()}
	if not event_id.strip_edges().is_empty():
		body["event_id"] = event_id.strip_edges()
	return request_json("/api/advisor/message", HTTPClient.METHOD_POST, body)

func investments_message(session_id: String, text: String) -> int:
	return _message("/api/advisor/investments", session_id, text)

func business_message(session_id: String, text: String) -> int:
	return _message("/api/business/chat", session_id, text)

func get_products(category: String = "") -> int:
	return request_json("/api/products", HTTPClient.METHOD_GET, {}, {"category": category} if not category.is_empty() else {})

func _message(path: String, session_id: String, text: String) -> int:
	if session_id.strip_edges().is_empty() or text.strip_edges().is_empty():
		return reject("Introdu un mesaj și pornește o sesiune înainte de a continua.")
	return request_json(path, HTTPClient.METHOD_POST, {"session_id": session_id, "text": text.strip_edges()})
