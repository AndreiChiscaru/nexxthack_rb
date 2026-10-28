extends Node
## Încarcă extrasul de cont al jucătorului și îl trimite serverului de analiză (OCR + Claude).
## Serverul răspunde cu `game_profile`: situația financiară reală, gata de folosit în simulare.
## Web: <input type="file"> din pagină + fetch pe același domeniu. Desktop: FileDialog + HTTPRequest.

signal status_changed(text: String)
signal profile_ready(result: Dictionary)
signal failed(message: String)

const DEFAULT_API := "http://158.180.47.250:8787"
const TIMEOUT_SECONDS := 240.0
const STORAGE_KEY := "raiffQuestProfile"
const ACCEPT := ".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp,.txt,.csv"

const JS_SETUP := """
window.raiffQuest = window.raiffQuest || {
	state: 'idle', result: '', error: '',
	pick: function (accept) {
		var self = this;
		var input = document.createElement('input');
		input.type = 'file';
		input.accept = accept;
		self.state = 'picking';
		input.addEventListener('cancel', function () { self.state = 'idle'; });
		input.onchange = function () {
			var file = input.files[0];
			if (!file) { self.state = 'idle'; return; }
			self.state = 'uploading';
			var body = new FormData();
			body.append('file', file);
			fetch('/api/analyze', { method: 'POST', body: body })
				.then(function (r) {
					return r.json().catch(function () { return {}; }).then(function (d) {
						if (!r.ok) { throw new Error(d.detail || ('Eroare ' + r.status)); }
						return d;
					});
				})
				.then(function (d) { self.result = JSON.stringify(d); self.state = 'done'; })
				.catch(function (e) { self.error = String(e.message || e); self.state = 'error'; });
		};
		input.click();
	},
	takeStored: function (key) {
		var v = window.localStorage.getItem(key) || '';
		window.localStorage.removeItem(key);
		return v;
	}
};
"""

var api_base := DEFAULT_API
var busy := false
var _poll: Timer
var _dialog: FileDialog
var _http: HTTPRequest

func _ready() -> void:
	var env_api := OS.get_environment("RAIFF_API")
	if env_api != "":
		api_base = env_api.trim_suffix("/")
	if _is_web():
		JavaScriptBridge.eval(JS_SETUP, true)
		_poll = Timer.new()
		_poll.wait_time = 0.25
		_poll.timeout.connect(_poll_web)
		add_child(_poll)

func _is_web() -> bool:
	return OS.has_feature("web")

## Profilul trimis de pagina de analiză („Joacă cu acest profil”), dacă există.
func take_stored_profile() -> Dictionary:
	if not _is_web():
		return {}
	var raw = JavaScriptBridge.eval("window.raiffQuest.takeStored('%s')" % STORAGE_KEY, true)
	if typeof(raw) != TYPE_STRING or str(raw) == "":
		return {}
	var data = JSON.parse_string(str(raw))
	if typeof(data) == TYPE_DICTIONARY and data.has("game_profile"):
		return data
	return {}

func pick_and_upload() -> void:
	if busy:
		return
	if _is_web():
		JavaScriptBridge.eval("window.raiffQuest.pick('%s')" % ACCEPT, true)
		_poll.start()
	else:
		_open_dialog()

# ---------------------------------------------------------------- web

func _poll_web() -> void:
	var state := str(JavaScriptBridge.eval("window.raiffQuest.state", true))
	match state:
		"uploading":
			if not busy:
				busy = true
				status_changed.emit("Se extrage textul și se analizează extrasul… (30-90 de secunde)")
		"done":
			_poll.stop()
			JavaScriptBridge.eval("window.raiffQuest.state = 'idle'", true)
			_finish(JSON.parse_string(str(JavaScriptBridge.eval("window.raiffQuest.result", true))))
		"error":
			_poll.stop()
			JavaScriptBridge.eval("window.raiffQuest.state = 'idle'", true)
			_fail(str(JavaScriptBridge.eval("window.raiffQuest.error", true)))
		"idle":
			_poll.stop()

# ---------------------------------------------------------------- desktop

func _open_dialog() -> void:
	if _dialog == null:
		_dialog = FileDialog.new()
		_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
		_dialog.access = FileDialog.ACCESS_FILESYSTEM
		_dialog.use_native_dialog = true
		_dialog.title = "Alege extrasul de cont"
		_dialog.filters = PackedStringArray(["*.pdf,*.png,*.jpg,*.jpeg,*.tif,*.tiff,*.bmp,*.webp,*.txt,*.csv ; Extras de cont"])
		_dialog.file_selected.connect(_upload_file)
		add_child(_dialog)
	_dialog.popup_centered_ratio(0.7)

func _upload_file(path: String) -> void:
	var data := FileAccess.get_file_as_bytes(path)
	if data.is_empty():
		_fail("Nu am putut citi fișierul %s." % path.get_file())
		return
	if _http == null:
		_http = HTTPRequest.new()
		_http.timeout = TIMEOUT_SECONDS
		_http.request_completed.connect(_on_request_completed)
		add_child(_http)
	var boundary := "----RaiffQuest%d" % Time.get_ticks_usec()
	var body := PackedByteArray()
	body.append_array(("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\nContent-Type: application/octet-stream\r\n\r\n" % [boundary, path.get_file()]).to_utf8_buffer())
	body.append_array(data)
	body.append_array(("\r\n--%s--\r\n" % boundary).to_utf8_buffer())
	var headers := PackedStringArray(["Content-Type: multipart/form-data; boundary=" + boundary])
	var err := _http.request_raw(api_base + "/api/analyze", headers, HTTPClient.METHOD_POST, body)
	if err != OK:
		_fail("Nu m-am putut conecta la serverul de analiză (%s)." % api_base)
		return
	busy = true
	status_changed.emit("Se extrage textul și se analizează extrasul… (30-90 de secunde)")

func _on_request_completed(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS:
		_fail("Serverul de analiză nu a răspuns (cod %d)." % result)
		return
	var data = JSON.parse_string(body.get_string_from_utf8())
	if code != 200:
		var detail := str(data.get("detail", "")) if typeof(data) == TYPE_DICTIONARY else ""
		_fail(detail if detail != "" else "Eroare %d de la server." % code)
		return
	_finish(data)

# ---------------------------------------------------------------- rezultat

func _finish(data) -> void:
	busy = false
	if typeof(data) != TYPE_DICTIONARY or not data.has("game_profile"):
		_fail("Răspunsul serverului nu conține profilul de joc.")
		return
	profile_ready.emit(data)

func _fail(message: String) -> void:
	busy = false
	failed.emit(message)
