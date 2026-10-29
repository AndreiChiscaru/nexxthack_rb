extends Node
var failed := false
func check(ok: bool, message: String) -> void:
	if not ok:
		failed = true
		push_error(message)
func settle(controller: Node) -> void:
	var end := Time.get_ticks_msec() + 15000
	while controller.busy and Time.get_ticks_msec() < end:
		await get_tree().process_frame
	await get_tree().create_timer(0.2).timeout
func capture(label: String) -> void:
	var folder := OS.get_environment("RAIFF_CAPTURE_DIR")
	if folder.is_empty():
		return
	await get_tree().create_timer(0.25).timeout
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(folder.path_join(label + ".png"))
func _ready() -> void:
	OS.set_environment("RAIFF_API", OS.get_environment("RAIFF_TEST_API"))
	GameLocale.set_locale("ro")
	var screen = load("res://scenes/journey.tscn").instantiate()
	add_child(screen)
	await get_tree().process_frame
	check(screen.start_button.text == "Începe jocul →", "Romanian remains the default")
	screen.language_picker.item_selected.emit(1)
	await get_tree().create_timer(0.2).timeout
	check(screen.start_button.text == "Start playing →", "Welcome is translated")
	check(screen.language_picker.get_global_rect().end.y <= screen.size.y, "Language picker stays visible")
	await capture("locale-welcome-en")
	screen.start_button.pressed.emit()
	await settle(screen.controller)
	check(screen.chat.send.text == "Send →", "Onboarding composer is translated")
	screen.uploader.busy = true
	screen.controller.upload_started()
	await get_tree().create_timer(0.3).timeout
	check(screen.chat.status.text.begins_with("Analyzing your document"), "Upload shows analysis status in English")
	screen.uploader.busy = false
	screen.controller.upload_finished({"ok": false, "error": {"code": "cancelled"}})
	check(screen.chat.input.editable, "Composer unlocks when upload finishes")
	var old_mode: String = screen.controller.agent_mode
	screen.controller.agent_mode = "live"
	screen.controller.upload_started()
	screen.controller.upload_finished({"ok": true, "data": {"reply": "Your statement is ready."}})
	check(screen.chat.input.editable, "Live upload response unlocks the composer")
	check(screen.controller.transcript.back().text == "Your statement is ready.", "Live upload reply reaches chat")
	screen.controller.agent_mode = old_mode
	var sample := FileAccess.open("user://pending-test.txt", FileAccess.WRITE)
	sample.store_string("Fictional statement for attachment test.")
	sample.close()
	screen.uploader.upload_path(ProjectSettings.globalize_path("user://pending-test.txt"))
	check(not screen.controller.busy and not screen.uploader.busy, "Selecting a file never starts analysis")
	check(screen.chat.attachment_row.visible, "Selected attachment is visible before Send")
	check(screen.chat.input.editable, "Can compose text while a file is attached")
	screen.chat.remove_attachment.pressed.emit()
	check(not screen.uploader.has_pending(), "Remove discards attachment without sending")
	screen.uploader.upload_path(ProjectSettings.globalize_path("user://pending-test.txt"))
	screen.chat.input.clear()
	screen.chat.send.pressed.emit()
	await settle(screen.controller)
	check(not screen.uploader.has_pending() and not screen.chat.attachment_row.visible, "Successful Send clears attachment")
	check(screen.chat.input.editable, "Attachment Send restores composer")
	screen.chat.input.text = "Economii"
	GameLocale.set_locale("ro")
	check(screen.chat.input.text == "Economii", "Typed user input never changes")
	GameLocale.set_locale("en")
	for answer in ["My goal", "Income", "Savings"]:
		screen.controller.send_message(answer)
		await settle(screen.controller)
	screen.controller.confirm_profile(screen.controller.profile)
	await settle(screen.controller)
	check(screen.controller.phase == "map", "English flow reaches map")
	screen._institution("entertainment")
	for control in screen.location_contents.get_children():
		if control is Button and "AIngel" in control.text:
			control.pressed.emit()
	check(screen.chat.input.text == "What are my options at Entertainment for reaching my goal?", "Suggested location question uses English, including institution name")
	var before: Dictionary = screen.controller.state.duplicate(true)
	var sid: String = screen.controller.session_id
	screen._institution("bank")
	screen.bank_amount_input.value = 735
	GameLocale.refresh()
	check(screen.city.labels["bank"].text.begins_with("Bank"), "Map labels translated")
	check(screen.hud.month_label.text.begins_with("MONTH"), "HUD translated")
	check(GameLocale.english("Rezolvă cele 3 misiuni") == "Complete the 3 missions", "Formatted mission count")
	check(GameLocale.english("Venit lunar: 5800 lei") == "Monthly income: 5800 lei", "Formatted currency preserved")
	await screen._products()
	GameLocale.refresh()
	await capture("locale-catalog-en")
	GameLocale.set_locale("ro")
	screen._institution("bank")
	GameLocale.refresh()
	check(screen.bank_amount_input.value == 735, "Language switch preserves typed bank amount")
	check(screen.controller.state == before and screen.controller.session_id == sid, "Language never changes game state or session")
	check(screen.chat.send.text == "Trimite →", "Romanian restores exact source")
	GameLocale.set_locale("en")
	GameLocale.refresh()
	check(screen.hud.month_label.text.begins_with("MONTH"), "Repeated language switches remain stable")
	GameLocale.set_locale("ro")
	print("[localization] ", "FAIL" if failed else "PASS")
	get_tree().quit(1 if failed else 0)
