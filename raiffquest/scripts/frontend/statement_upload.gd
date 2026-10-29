extends Node
## Session-scoped statement import. File contents are never persisted by this component.
signal attachment_changed(filename: String)
signal started
signal finished(response: Dictionary)

const Api := preload("res://scripts/frontend/api_client.gd")
const Config := preload("res://scripts/frontend/api_config.gd")
const MAX_BYTES := 25 * 1024 * 1024
const TIMEOUT_SECONDS := 240.0
const EXTENSIONS := ["pdf", "png", "jpg", "jpeg", "txt", "csv", "tif", "tiff", "webp", "bmp"]
const JS_SETUP := """
window.raiffStatementUpload = {
 state: 'idle', result: '', status: 0, error: '', errorCode: '',
  pick: function(sessionId, timeoutMs, path, language) {
  if (this.state === 'picking' || this.state === 'uploading') return;
  var target = (typeof path === 'string' && path) ? path : '/api/onboarding/statement';
  var self = this;
  self.result = ''; self.status = 0; self.error = ''; self.errorCode = '';
  function fail(message, code) { self.error = message; self.errorCode = code || 'invalid_request'; self.state = 'error'; }
  if (!sessionId || !sessionId.trim()) { fail('Lipsește sesiunea.'); return; }
  var input = document.createElement('input');
  input.type = 'file'; input.accept = '.pdf,.png,.jpg,.jpeg,.txt,.csv,.tif,.tiff,.webp,.bmp';
  self.state = 'picking';
  input.addEventListener('cancel', function() { self.state = 'cancelled'; input.remove(); });
  input.onchange = function() {
   var file = input.files[0];
   if (!file) { self.state = 'cancelled'; input.remove(); return; }
   var extension = file.name.split('.').pop().toLowerCase();
   if (['pdf','png','jpg','jpeg','txt','csv','tif','tiff','webp','bmp'].indexOf(extension) < 0) { fail('Tip de fișier neacceptat.'); input.remove(); return; }
   if (file.size <= 0 || file.size > 25*1024*1024) { fail('Fișierul trebuie să aibă între 1 octet și 25 MB.'); input.remove(); return; }
   self.pendingFile = file; self.state = 'attached'; input.remove();
   self.sendPending = function(sessionId, timeoutMs, target, language) {
   var safeName = Array.from(file.name).map(function(c) { var n = c.charCodeAt(0); return n < 32 || n === 34 || n === 47 || n === 92 || n === 127 ? '_' : c; }).join('');
   var body = new FormData(); body.append('session_id', sessionId); body.append('file', file, safeName);
   var controller = new AbortController();
   var timer = setTimeout(function() { controller.abort(); }, timeoutMs);
   self.state = 'uploading';
   Promise.resolve().then(function() {
    return fetch(target, {method:'POST', headers:{'Accept-Language':language || 'ro'}, body:body, signal:controller.signal, redirect:'error'});
   }).then(function(response) {
    self.status = response.status;
    return response.text();
   }).then(function(text) {
    if (text.length > 2*1024*1024) { fail('Răspuns prea mare.', 'response_too_large'); return; }
    self.result = text; self.state = 'done';
   }).catch(function(error) {
    fail(error.name === 'AbortError' ? 'Serverul nu a răspuns la timp.' : 'Conexiunea cu serverul a fost întreruptă.', error.name === 'AbortError' ? 'timeout' : 'network');
   }).finally(function() { clearTimeout(timer); });
   };
  };
  input.style.display = 'none'; document.body.appendChild(input);
  try { input.click(); } catch (_) { input.remove(); fail('Nu am putut deschide selectorul de fișiere.'); }
 },
 loadSample: function(sessionId, timeoutMs, language) {
  if (this.state === 'picking' || this.state === 'uploading') return;
  var self = this;
  self.result = ''; self.status = 0; self.error = ''; self.errorCode = '';
  function fail(message, code) { self.error = message; self.errorCode = code || 'invalid_request'; self.state = 'error'; }
  if (!sessionId || !sessionId.trim()) { fail('Lipsește sesiunea.'); return; }
  var body = new FormData(); body.append('session_id', sessionId);
  var controller = new AbortController();
  var timer = setTimeout(function() { controller.abort(); }, timeoutMs);
  self.state = 'uploading';
  fetch('/api/onboarding/sample', {method:'POST', headers:{'Accept-Language':language || 'ro'}, body:body, signal:controller.signal, redirect:'error'})
   .then(function(response) { self.status = response.status; return response.text(); })
   .then(function(text) {
    if (text.length > 2*1024*1024) { fail('Răspuns prea mare.', 'response_too_large'); return; }
    self.result = text; self.state = 'done';
   }).catch(function(error) {
    fail(error.name === 'AbortError' ? 'Serverul nu a răspuns la timp.' : 'Conexiunea cu serverul a fost întreruptă.', error.name === 'AbortError' ? 'timeout' : 'network');
   }).finally(function() { clearTimeout(timer); });
 }
};
"""

var api_base: String = ""
var session_id: String = ""
var busy: bool = false
var endpoint := "/api/onboarding/statement"
var purpose := "statement"
var last_purpose := "statement"
var pending_name := ""
var _pending_path := ""
var _dialog: FileDialog
var _http: HTTPRequest
var _poll: Timer
var _request_session := ""

func _ready() -> void:
	if OS.has_feature("web"):
		JavaScriptBridge.eval(JS_SETUP, true)
		_poll = Timer.new()
		_poll.wait_time = 0.2
		_poll.timeout.connect(_poll_web)
		add_child(_poll)

func _begin() -> bool:
	if busy:
		return false
	busy = true
	_request_session = session_id
	started.emit()
	if _request_session.strip_edges().is_empty():
		_finish(Api.failure("invalid_request", "Lipsește sesiunea. Începe conversația înainte de încărcare."))
		return false
	return true

func pick_business_document() -> void:
	endpoint = "/api/business/document"
	purpose = "business"
	pick()

func pick() -> void:
	if purpose != "business":
		endpoint = "/api/onboarding/statement"
		purpose = "statement"
	if busy:
		return
	_request_session = session_id
	if OS.has_feature("web"):
		JavaScriptBridge.eval("window.raiffStatementUpload.pick(%s, %d, %s, %s)" % [JSON.stringify(_request_session), int(TIMEOUT_SECONDS * 1000), JSON.stringify(endpoint), JSON.stringify(GameLocale.locale)], true)
		_poll.start()
		return
	if _dialog == null:
		_dialog = FileDialog.new()
		_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
		_dialog.access = FileDialog.ACCESS_FILESYSTEM
		_dialog.use_native_dialog = true
		_dialog.filters = PackedStringArray(["*.pdf,*.png,*.jpg,*.jpeg,*.txt,*.csv,*.tif,*.tiff,*.webp,*.bmp ; Document"])
		_dialog.file_selected.connect(upload_path)
		_dialog.canceled.connect(func() -> void: _finish(Api.failure("cancelled", "Selecția fișierului a fost anulată.")))
		add_child(_dialog)
	_dialog.title = GameLocale.text("Alege documentul pentru contabil" if purpose == "business" else "Alege extrasul de cont")
	_dialog.popup_centered_ratio(0.7)

func load_sample() -> void:
	if not _begin():
		return
	if OS.has_feature("web"):
		JavaScriptBridge.eval("window.raiffStatementUpload.loadSample(%s, %d, %s)" % [JSON.stringify(_request_session), int(TIMEOUT_SECONDS * 1000), JSON.stringify(GameLocale.locale)], true)
		_poll.start()
		return
	var base := api_base if not api_base.is_empty() else Config.resolve_base()
	var url := Config.build_url(base, "/api/onboarding/sample")
	if url.is_empty():
		_finish(Api.failure("invalid_request", "Adresa serverului nu este validă."))
		return
	_http = HTTPRequest.new()
	_http.timeout = TIMEOUT_SECONDS
	_http.max_redirects = 0
	_http.body_size_limit = Api.MAX_RESPONSE_BYTES
	_http.request_completed.connect(_on_response)
	add_child(_http)
	var body := ("session_id=" + _request_session.uri_encode()).to_utf8_buffer()
	var error := _http.request_raw(url, PackedStringArray(["Accept-Language: " + GameLocale.locale, "Content-Type: application/x-www-form-urlencoded"]), HTTPClient.METHOD_POST, body)
	if error != OK:
		_finish(Api.failure("network", "Nu s-a putut porni conexiunea cu serverul."))

func has_pending() -> bool:
	return not pending_name.is_empty()

func clear_pending() -> void:
	pending_name = ""
	_pending_path = ""
	if OS.has_feature("web"):
		JavaScriptBridge.eval("window.raiffStatementUpload.pendingFile = null; window.raiffStatementUpload.sendPending = null;")
	attachment_changed.emit("")

func upload_path(path: String) -> void:
	if busy:
		return
	if path.get_extension().to_lower() not in EXTENSIONS:
		_finish(Api.failure("invalid_request", "Tip de fișier neacceptat."))
		return
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		_finish(Api.failure("invalid_request", "Nu am putut citi fișierul selectat."))
		return
	var length := file.get_length()
	file.close()
	if length <= 0 or length > MAX_BYTES:
		_finish(Api.failure("invalid_request", "Fișierul trebuie să aibă între 1 octet și 25 MB."))
		return
	_pending_path = path
	pending_name = path.get_file()
	attachment_changed.emit(pending_name)

func send_pending() -> void:
	if not has_pending() or not _begin():
		return
	if OS.has_feature("web"):
		JavaScriptBridge.eval("window.raiffStatementUpload.sendPending(%s, %d, %s, %s)" % [JSON.stringify(_request_session), int(TIMEOUT_SECONDS * 1000), JSON.stringify(endpoint), JSON.stringify(GameLocale.locale)], true)
		_poll.start()
	else:
		_send_path(_pending_path)

func _send_path(path: String) -> void:
	if path.get_extension().to_lower() not in EXTENSIONS:
		_finish(Api.failure("invalid_request", "Tip de fișier neacceptat."))
		return
	var source := FileAccess.open(path, FileAccess.READ)
	if source == null:
		_finish(Api.failure("invalid_request", "Nu am putut citi fișierul selectat."))
		return
	var length := source.get_length()
	if length <= 0 or length > MAX_BYTES:
		source.close()
		_finish(Api.failure("invalid_request", "Fișierul trebuie să aibă între 1 octet și 25 MB."))
		return
	var data := source.get_buffer(length)
	source.close()
	if data.size() != length:
		_finish(Api.failure("invalid_request", "Fișierul nu a putut fi citit complet."))
		return
	var base := api_base if not api_base.is_empty() else Config.resolve_base()
	var url := Config.build_url(base, endpoint)
	if url.is_empty():
		_finish(Api.failure("invalid_request", "Adresa serverului nu este validă."))
		return
	var boundary := "----RaiffStatement%s" % Crypto.new().generate_random_bytes(16).hex_encode()
	var body := _multipart(boundary, _request_session, path.get_file(), data)
	_http = HTTPRequest.new()
	_http.timeout = TIMEOUT_SECONDS
	_http.max_redirects = 0
	_http.body_size_limit = Api.MAX_RESPONSE_BYTES
	_http.request_completed.connect(_on_response)
	add_child(_http)
	var error := _http.request_raw(url, PackedStringArray(["Accept-Language: " + GameLocale.locale, "Content-Type: multipart/form-data; boundary=" + boundary]), HTTPClient.METHOD_POST, body)
	if error != OK:
		_finish(Api.failure("network", "Nu s-a putut porni conexiunea cu serverul."))

static func _multipart(boundary: String, sid: String, filename: String, data: PackedByteArray) -> PackedByteArray:
	var safe := ""
	for character in filename:
		var code := character.unicode_at(0)
		safe += "_" if code < 32 or code == 127 or character in ["\"", "/", "\\"] else character
	var body := ("--%s\r\nContent-Disposition: form-data; name=\"session_id\"\r\n\r\n%s\r\n" % [boundary, sid]).to_utf8_buffer()
	body.append_array(("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\nContent-Type: application/octet-stream\r\n\r\n" % [boundary, safe]).to_utf8_buffer())
	body.append_array(data)
	body.append_array(("\r\n--%s--\r\n" % boundary).to_utf8_buffer())
	return body

func _on_response(result: int, status: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	_finish(Api.decode_response(result, status, body))

func _poll_web() -> void:
	var state := str(JavaScriptBridge.eval("window.raiffStatementUpload.state", true))
	if state == "attached":
		pending_name = str(JavaScriptBridge.eval("window.raiffStatementUpload.pendingFile.name", true))
		_poll.stop()
		attachment_changed.emit(pending_name)
	elif state == "done":
		var status := int(JavaScriptBridge.eval("window.raiffStatementUpload.status", true))
		var raw := str(JavaScriptBridge.eval("window.raiffStatementUpload.result", true))
		_finish(Api.decode_response(HTTPRequest.RESULT_SUCCESS, status, raw.to_utf8_buffer()))
	elif state == "error":
		_finish(Api.failure(str(JavaScriptBridge.eval("window.raiffStatementUpload.errorCode", true)), str(JavaScriptBridge.eval("window.raiffStatementUpload.error", true))))
	elif state == "cancelled":
		_finish(Api.failure("cancelled", "Selecția fișierului a fost anulată."))

func _finish(response: Dictionary) -> void:
	busy = false
	last_purpose = purpose
	if response.get("ok", false):
		clear_pending()
	if not has_pending():
		purpose = "statement"
		endpoint = "/api/onboarding/statement"
	_request_session = ""
	if is_instance_valid(_http):
		_http.queue_free()
		_http = null
	if is_instance_valid(_poll):
		_poll.stop()
		JavaScriptBridge.eval("window.raiffStatementUpload.state = 'idle'; window.raiffStatementUpload.result = '';", true)
	finished.emit(response)
