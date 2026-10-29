extends Node
func _ready() -> void:
	OS.set_environment("RAIFF_API", OS.get_environment("RAIFF_TEST_API"))
	var screen = load("res://scenes/journey.tscn").instantiate()
	add_child(screen)
	var c = screen.controller
	c.begin()
	var startup_deadline := Time.get_ticks_msec() + 15000
	while c.busy and Time.get_ticks_msec() < startup_deadline:
		await get_tree().process_frame
	if c.busy or c.session_id.is_empty():
		push_error("Session initialization failed")
		get_tree().quit(1)
		return
	var channel_ok: bool = not screen.advisor_button.visible
	var path := "user://statement-flow-test.txt"
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string("Synthetic statement: monthly salary 5000 lei; groceries 800 lei; rent 1500 lei.")
	file.close()
	screen.uploader.upload_path(path)
	channel_ok = channel_ok and screen.uploader.has_pending() and not c.busy and not screen.uploader.busy
	screen.chat.submit()
	channel_ok = channel_ok and screen.channel == "onboarding"
	var deadline := Time.get_ticks_msec() + 240000
	while c.busy and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	for i in range(10):
		await get_tree().process_frame
	print("[statement-flow] controller busy=", c.busy, " uploader busy=", screen.uploader.busy, " editable=",screen.chat.input.editable," disabled=",screen.chat.send.disabled," messages=",c.transcript.size())
	var ok: bool = channel_ok and not c.busy and not screen.uploader.busy and screen.chat.input.editable and not screen.chat.send.disabled and c.last_error.is_empty() and c.transcript.size() >= 2
	if not c.last_error.is_empty():
		print("[statement-flow] error=", c.last_error)
	if ok:
		var before: int = c.transcript.size()
		screen.chat.input.text = "Vreau sa economisesc 3000 lei in 12 luni."
		screen.chat.submit()
		deadline = Time.get_ticks_msec() + 240000
		while c.busy and Time.get_ticks_msec() < deadline:
			await get_tree().process_frame
		ok = not c.busy and screen.chat.input.editable and not screen.chat.send.disabled and c.last_error.is_empty() and c.transcript.size() == before + 2
		print("[statement-flow] follow-up editable=", screen.chat.input.editable, " messages=", c.transcript.size())
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	print("[statement-flow] ", "PASS" if ok else "FAIL")
	get_tree().quit(0 if ok else 1)
