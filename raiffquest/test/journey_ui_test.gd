extends Node
var failed := false
func check(ok: bool, message: String) -> void:
	if not ok:
		failed = true
		push_error(message)
func wait_for(c: Node) -> void:
	var end := Time.get_ticks_msec() + 15000
	while c.busy and Time.get_ticks_msec() < end:
		await get_tree().process_frame
	for i in range(8):
		await get_tree().process_frame
func capture(label: String) -> void:
	var folder := OS.get_environment("RAIFF_CAPTURE_DIR")
	if folder.is_empty():
		return
	await get_tree().create_timer(1.3).timeout
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(folder.path_join(label + ".png"))

func _ready() -> void:
	get_window().size = Vector2i(1280, 720)
	OS.set_environment("RAIFF_API", OS.get_environment("RAIFF_TEST_API"))
	var scene = load("res://scenes/journey.tscn").instantiate()
	add_child(scene)
	await get_tree().process_frame
	for button in [scene.start_button, scene.chat.send, scene.advance_button, scene.city.labels["bank"]]:
		for state in ["font_hover_color", "font_pressed_color", "font_hover_pressed_color", "font_focus_color"]:
			check(button.get_theme_color(state) == Color("303a28"), "Button text remains dark in " + state)
	await capture("welcome")
	var hover := InputEventMouseMotion.new()
	hover.position = scene.start_button.get_global_rect().get_center()
	get_viewport().push_input(hover)
	await capture("welcome-hover")
	scene.controller.begin()
	await wait_for(scene.controller)
	print("Screen: ",scene.size, " chat: ",scene.chat.size," min:",scene.chat.get_combined_minimum_size()," scroll:",scene.chat.scroll.size)
	check(scene.chat.get_global_rect().end.y <= scene.size.y, "chat composer fits within viewport")
	for text in ["Scop", "Venit", "Economii"]:
		scene.controller.send_message(text)
		await wait_for(scene.controller)
	await capture("chat")
	scene._show_profile()
	check(scene.profile_panel.visible, "profile review opens")
	scene.controller.upload_finished({"ok":true,"data":{"reply":"Updated profile"}})
	await get_tree().process_frame
	check(not scene.profile_panel.visible, "upload invalidates stale profile review")
	scene._confirm_profile()
	check(not scene.controller.busy, "stale profile confirmation is blocked")
	scene.controller.send_message("Confirm noul profil")
	await wait_for(scene.controller)
	scene.controller.confirm_profile(scene.controller.profile)
	await wait_for(scene.controller)
	check(scene.city.visible, "map visible after confirmed profile")
	check(not scene.map_controls.get_global_rect().intersects(Rect2(scene.size.x-200,scene.size.y-62,180,52)),"map controls do not overlap navigation")
	await capture("map")
	scene._open_chat()
	await wait_for(scene.controller)
	check(scene.chat.size.x <= 360, "map chat stays a compact left drawer")
	check(scene.chat.portraits.all(func(p): return p.visible and p.material is ShaderMaterial), "Both participants keep circular profile pictures on the map")
	await capture("map-chat")
	check(scene.chat.visible and scene.controller.transcript.size()>=10,"map advisor retains onboarding chat")
	for repeat in range(2):
		scene._show_investments()
		await get_tree().process_frame
		scene._show_business()
		await get_tree().process_frame
		scene._close_chat()
		await get_tree().process_frame
	check(scene.chat.portraits.all(func(p): return is_instance_valid(p)), "switching advisors clears old portrait references")
	print("[journey-ui] ","FAIL" if failed else "PASS")
	get_tree().quit(1 if failed else 0)
