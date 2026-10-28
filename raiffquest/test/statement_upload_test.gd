extends SceneTree

const Upload := preload("res://scripts/frontend/statement_upload.gd")
var responses: Array[Dictionary] = []
var failures: Array[String] = []
var starts := 0

func _initialize() -> void:
	_run.call_deferred()

func check(value: bool, message: String) -> void:
	if not value:
		failures.append(message)

func _run() -> void:
	var upload := Upload.new()
	root.add_child(upload)
	upload.finished.connect(func(response: Dictionary) -> void: responses.append(response))
	upload.started.connect(func() -> void: starts += 1)
	upload.upload_path("missing.pdf")
	check(responses.size() == 1 and responses[-1].error.code == "invalid_request" and not upload.busy, "missing session rejected")
	upload.session_id = "fixture-session"
	upload.upload_path("bad.exe")
	check(responses.size() == 2 and not upload.busy, "extension rejected")
	var path := "user://statement-upload-test.txt"
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.close()
	upload.upload_path(path)
	check(responses.size() == 3 and not upload.busy, "empty file rejected")
	file = FileAccess.open(path, FileAccess.WRITE)
	file.seek(Upload.MAX_BYTES)
	file.store_8(0)
	file.close()
	upload.upload_path(path)
	check(responses.size() == 4 and not upload.busy, "oversized file rejected before reading bytes")
	file = FileAccess.open(path, FileAccess.WRITE)
	file.store_string("Synthetic statement only")
	file.close()
	upload.api_base = OS.get_environment("RAIFF_UPLOAD_TEST_API")
	upload.upload_path(path)
	upload.upload_path(path)
	var deadline := Time.get_ticks_msec() + 8000
	while responses.size() < 5 and Time.get_ticks_msec() < deadline:
		await process_frame
	check(responses.size() == 5, "upload completes once")
	if responses.size() == 5:
		check(responses[-1].ok and responses[-1].data.get("verified", false), "server verified multipart session/file content")
	check(starts == 5 and not upload.busy, "busy prevents duplicate uploads and clears on completion")
	var multipart := Upload._multipart("test-boundary", "fixture-session", "bad\"\r\n.txt", "data".to_utf8_buffer()).get_string_from_utf8()
	check(multipart.contains('filename="bad___.txt"'), "filename header sanitized")
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	upload.queue_free()
	await process_frame
	for failure in failures:
		push_error(failure)
	print("[statement-upload-native] %s" % ("PASS" if failures.is_empty() else "FAIL"))
	quit(0 if failures.is_empty() else 1)
