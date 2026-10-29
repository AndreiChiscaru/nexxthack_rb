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
	check(scene.advance_button.disabled, "Pending missions block next month")
	var missions: Array = scene.controller.events.duplicate(true)
	for mission: Dictionary in missions:
		scene.controller.act(mission.institution, mission.id, {"option_id":mission.options[0].id})
		await wait_for(scene.controller)
		check(scene.advance_button.disabled == not scene.controller.events.is_empty(), "Next month unlocks only after last mission")

	check(scene.map_controls.get_child_count() == 1 and not scene.recovery_button.visible, "Healthy map has no manual refresh button")
	var original_state: Dictionary = scene.controller.state.duplicate(true)
	scene.controller._track(99999, "advance")
	scene.controller._response(99999, {"ok":false,"status":0,"error":{"code":"timeout","message":"Conexiune întreruptă"}})
	check(scene.recovery_button.visible and scene.controller.needs_recovery, "Ambiguous failure offers synchronization")
	check(scene.advance_button.disabled, "Recovery blocks repeated mutations")
	scene.recovery_button.pressed.emit()
	check(scene.recovery_button.disabled, "Synchronization cannot be submitted twice")
	await wait_for(scene.controller)
	check(not scene.recovery_button.visible and not scene.controller.needs_recovery, "Successful synchronization hides recovery option")
	check(scene.controller.state == original_state, "Synchronization does not replay the failed action")
	scene.controller.last_error = "Cererea nu a reușit."
	scene.controller.changed.emit()
	check(scene.recovery_button.visible, "Other map errors also offer synchronization")
	scene.recovery_button.pressed.emit()
	await wait_for(scene.controller)
	check(not scene.recovery_button.visible, "Recovery disappears after other errors clear")
	check(not scene.map_controls.get_global_rect().intersects(Rect2(scene.size.x-200,scene.size.y-62,180,52)),"map controls do not overlap navigation")
	await get_tree().create_timer(0.7).timeout
	var fountain_screen: Vector2 = scene.city.world.position + scene.city.FOUNTAIN_CENTER * scene.city.world.scale
	check(fountain_screen.distance_to(scene.city.size * 0.5) < 2.0, "Fountain stays centered in the initial camera")
	for building in scene.city.buttons.values():
		check(not building.get_global_rect().intersects(scene.hud.get_global_rect()), "Buildings are visible outside the HUD")
	await capture("map")
	var month_before: int = scene.controller.state.month
	scene.month_dialog.popup_centered()
	await get_tree().create_timer(0.3).timeout
	check(scene.month_dialog.visible, "Monthly confirmation opens")
	check(scene.month_dialog.panel.get_theme_stylebox("panel").bg_color == scene.Kit.PAPER, "Monthly confirmation uses cream game surface")
	await capture("month-confirmation")
	scene.month_dialog.cancel_button.pressed.emit()
	check(not scene.month_dialog.visible and scene.controller.state.month == month_before, "Cancel closes confirmation without advancing")

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
		check(scene.advisor_button.icon.resource_path.ends_with("accountant_idle.png"), "Accountant chat shows accountant map icon")
		if repeat == 0:
			var accountant_face := false
			for portrait in scene.chat.portraits:
				if portrait is TextureRect and portrait.texture and "accountant_idle" in portrait.texture.resource_path:
					accountant_face = true
			check(accountant_face, "accountant chat uses the accountant avatar")
			check(is_instance_valid(scene.chat.agent_face) and scene.chat.agent_face.texture and "accountant_idle" in scene.chat.agent_face.texture.resource_path, "accountant header shows the accountant avatar")
		scene._close_chat()
		await get_tree().process_frame
	check(scene.chat.portraits.all(func(p): return is_instance_valid(p)), "switching advisors clears old portrait references")
	for origin in scene.city.PLACES:
		for destination in scene.city.PLACES:
			check(not scene.city.path_to(origin, destination).is_empty(), "All buildings remain reachable: " + origin + " to " + destination)
			var route: PackedVector2Array = scene.city.path_to(origin, destination)
			check(route[0].is_equal_approx(scene.city.NODES[origin]), "Route starts at actual entrance")
			check(route[-1].is_equal_approx(scene.city.NODES[destination]), "Route ends directly at actual entrance")
			for i in range(1, route.size()):
				check(route[i].distance_to(route[i-1]) > 0.1, "Route has no duplicated stops")
			for i in range(1, route.size()-1):
				check((route[i]-route[i-1]).normalized().dot((route[i+1]-route[i]).normalized()) > -0.999, "Route has no positioning U-turn")
	# Test actual opaque sprite pixels, not transparent corners of isometric assets.
	var masks := {}
	for id in scene.city.buttons:
		masks[id] = scene.city.buttons[id].texture_normal.get_image()
	for edge in scene.city.EDGES:
		for step in range(41):
			var point: Vector2 = scene.city.NODES[edge[0]].lerp(scene.city.NODES[edge[1]], step / 40.0)
			for id in scene.city.buttons:
				var button: TextureButton = scene.city.buttons[id]
				var mask: Image = masks[id]
				var pixels := Vector2(mask.get_width(), mask.get_height())
				var factor: float = minf(button.size.x / pixels.x, button.size.y / pixels.y)
				var offset := (button.size - pixels * factor) * 0.5
				var sample := (point - button.position - offset) / factor
				if sample.x >= 0 and sample.y >= 0 and sample.x < pixels.x and sample.y < pixels.y:
					check(mask.get_pixel(int(sample.x), int(sample.y)).a < 0.5, "Route avoids opaque building pixels: " + id + " / " + str(edge))
	scene.city._reduced_motion = false
	scene.city.navigate_to("bank")
	check(scene.selected == "bank" and scene.location.visible, "Destination panel opens before arrival")
	await get_tree().create_timer(0.2).timeout
	var avatar_screen: Vector2 = scene.city.world.position + scene.city._avatar.position * scene.city.world.scale
	check(scene.city.follow_view_rect.has_point(avatar_screen), "Following camera keeps avatar in unobscured map area")
	check(avatar_screen.x < scene.location.position.x - 25, "Right sidebar never covers walking avatar")
	var redirect_position: Vector2 = scene.city._avatar.position
	scene.city.navigate_to("hospital")
	check(scene.selected == "hospital", "Click while walking immediately changes sidebar")
	check(scene.city._avatar.position.is_equal_approx(redirect_position), "Rerouting never teleports avatar")
	check(scene.city._route.points[0].is_equal_approx(redirect_position), "Rerouting starts at current position")
	check(scene.city._route.points[-1] == scene.city.park_position("hospital"), "Rerouting targets new building")
	scene.city._reduced_motion = true
	scene.city.navigate_to("home")
	await get_tree().create_timer(0.3).timeout
	check(not scene.city._walking and scene.city._at == "home", "Returning to previous origin mid-route reaches it correctly")
	check(scene.selected == "home", "Cancelled route cannot reopen stale destination")
	var camera_before: Vector2 = scene.city.world.position
	scene.city._pan_by(Vector2(35, 20))
	check(not scene.city.follow_enabled, "Manual pan releases automatic camera follow")
	check(scene.city.world.position.distance_to(camera_before + Vector2(35, 20)) < 0.1, "Manual pan moves camera by mouse displacement")
	await get_tree().create_timer(0.2).timeout
	check(scene.city.world.position.distance_to(camera_before + Vector2(35, 20)) < 0.1, "Camera does not snap back after manual pan")
	scene.city.navigate_to("home")
	await get_tree().process_frame
	check(scene.city.follow_enabled, "Selecting a destination restores avatar follow")

	var arrival_screen: Vector2 = scene.city.world.position + scene.city._avatar.position * scene.city.world.scale
	check(scene.city.follow_view_rect.has_point(arrival_screen), "Avatar remains visible after arrival and rerouting")

	scene.city._reduced_motion = true
	scene.city.navigate_to("entertainment")
	await get_tree().create_timer(0.5).timeout
	check(scene.selected == "entertainment" and scene.location.visible, "Entertainment arrival opens its panel")
	check(scene.city.buttons.has("entertainment"), "Entertainment texture button exists")
	await capture("entertainment")
	scene.month_dialog.confirmed.disconnect(scene.controller.advance)
	var confirmations := [0]
	scene.month_dialog.confirmed.connect(func(): confirmations[0] += 1)
	scene.month_dialog.popup_centered()
	scene.month_dialog.confirm_button.pressed.emit()
	scene.month_dialog.confirm_button.pressed.emit()
	check(confirmations[0] == 1 and not scene.month_dialog.visible, "Confirmation submits once and closes immediately")
	print("[journey-ui] ","FAIL" if failed else "PASS")
	get_tree().quit(1 if failed else 0)
