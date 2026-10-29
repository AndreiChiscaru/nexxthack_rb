extends Node
## JSON transport shared by frontend screens. Every request has its own ID and
## HTTPRequest, so overlapping reads cannot overwrite each other's results.
## Never automatically retry mutations: a timeout does not prove they failed.

signal request_finished(request_id: int, response: Dictionary)
signal busy_changed(busy: bool)

const Config := preload("res://scripts/frontend/api_config.gd")
const MAX_RESPONSE_BYTES := 2 * 1024 * 1024

var api_base := ""
var timeout_seconds := 30.0
var _next_id := 0
var _pending: Dictionary = {}

func is_busy() -> bool:
	return not _pending.is_empty()

func request_json(path: String, method: int = HTTPClient.METHOD_GET, payload: Dictionary = {}, query: Dictionary = {}) -> int:
	var id := _reserve()
	var base := api_base if not api_base.is_empty() else Config.resolve_base()
	var url := Config.build_url(base, path, query)
	if url.is_empty() or method not in [HTTPClient.METHOD_GET, HTTPClient.METHOD_POST, HTTPClient.METHOD_PUT, HTTPClient.METHOD_PATCH, HTTPClient.METHOD_DELETE]:
		_complete.call_deferred(id, failure("invalid_request", "Adresa sau metoda API nu este validă."))
		return id
	var http := HTTPRequest.new()
	http.timeout = maxf(timeout_seconds, 0.1)
	http.body_size_limit = MAX_RESPONSE_BYTES
	# Do not forward a mutation or its contents to a redirected destination.
	http.max_redirects = 0
	add_child(http)
	_pending[id] = http
	http.request_completed.connect(_on_response.bind(id))
	var body := "" if method == HTTPClient.METHOD_GET else JSON.stringify(payload)
	var error := http.request(url, PackedStringArray(["Accept: application/json", "Content-Type: application/json", "Accept-Language: " + GameLocale.locale]), method, body)
	if error != OK:
		_complete.call_deferred(id, failure("network", "Nu s-a putut porni conexiunea cu serverul."))
	return id

## Local validation errors have the same asynchronous completion contract.
func reject(message: String) -> int:
	var id := _reserve()
	_complete.call_deferred(id, failure("invalid_request", message))
	return id

func cancel(request_id: int) -> void:
	if not _pending.has(request_id):
		return
	var http: HTTPRequest = _pending[request_id]
	if is_instance_valid(http):
		http.cancel_request()
	_complete(request_id, failure("cancelled", "Cererea a fost anulată."))

func cancel_all() -> void:
	for id: int in _pending.keys():
		cancel(id)

func _reserve() -> int:
	_next_id += 1
	var id := _next_id
	var was_busy := is_busy()
	_pending[id] = null
	if not was_busy:
		busy_changed.emit(true)
	return id

func _on_response(result: int, status: int, _headers: PackedStringArray, body: PackedByteArray, id: int) -> void:
	_complete(id, decode_response(result, status, body))

func _complete(id: int, response: Dictionary) -> void:
	# Ignore late callbacks from a cancelled request or an old screen.
	if not _pending.has(id):
		return
	var http: HTTPRequest = _pending[id]
	_pending.erase(id)
	if is_instance_valid(http):
		http.queue_free()
	if not is_busy():
		busy_changed.emit(false)
	request_finished.emit(id, response)

func _exit_tree() -> void:
	for http: Variant in _pending.values():
		if is_instance_valid(http):
			http.cancel_request()
	_pending.clear()

static func failure(code: String, message: String, status: int = 0) -> Dictionary:
	return {"ok": false, "status": status, "data": null, "error": {"code": code, "message": message}}

static func decode_response(result: int, status: int, body: PackedByteArray) -> Dictionary:
	if result == HTTPRequest.RESULT_TIMEOUT:
		return failure("timeout", "Serverul nu a răspuns la timp. Verifică starea înainte să repeți o acțiune.", status)
	if result == HTTPRequest.RESULT_BODY_SIZE_LIMIT_EXCEEDED:
		return failure("response_too_large", "Răspunsul serverului depășește limita acceptată.", status)
	if result != HTTPRequest.RESULT_SUCCESS:
		return failure("network", "Conexiunea cu serverul a fost întreruptă.", status)
	var parser := JSON.new()
	var parsed_ok := parser.parse(body.get_string_from_utf8()) == OK
	if status < 200 or status >= 300:
		var message := "Serverul a returnat o eroare (HTTP %d)." % status
		if status == 422:
			message = "Datele trimise nu sunt valide. Verifică informațiile introduse."
		elif parsed_ok and parser.data is Dictionary and parser.data.get("detail") is String:
			message = str(parser.data.detail).left(400)
		return failure("http", message, status)
	if status == 204:
		return {"ok": true, "status": status, "data": {}, "error": null}
	if not parsed_ok:
		return failure("invalid_json", "Serverul a trimis un răspuns JSON invalid.", status)
	if not (parser.data is Dictionary or parser.data is Array):
		return failure("invalid_response", "Răspunsul serverului nu are structura așteptată.", status)
	return {"ok": true, "status": status, "data": parser.data, "error": null}
