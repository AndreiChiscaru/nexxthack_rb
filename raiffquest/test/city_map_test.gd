extends Node

var failures := 0
func check(value: bool, message: String) -> void:
	if not value:
		failures += 1
		push_error(message)

func _ready() -> void:
	var source = load("res://scripts/frontend/city_map.gd")
	check(source != null, "Native city map must exist")
	if source == null:
		get_tree().quit(1)
		return
	var city = source.new()
	add_child(city)
	city.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for origin in city.PLACES:
		for destination in city.PLACES:
			var route: PackedVector2Array = city.path_to(origin, destination)
			check(route.size() >= 3, "Every institution must be reachable from every other")
			check(route[0].is_equal_approx(city.park_position(origin)), "Travel starts beside origin label")
			check(route[-1].is_equal_approx(city.park_position(destination)), "Travel parks beside destination label")
			check(route[-1].x > city.NODES[destination].x + 40, "Avatar stays lateral to label")
	check(city.path_to("missing", "bank").is_empty(), "Unknown locations reject navigation")
	city.set_institutions([{"id": "bank", "pending_events": 2}])
	check(city.badges["bank"].text == "2", "Badges display server event counts")
	city.set_institutions([])
	check(not city.badges["bank"].visible, "Stale badges clear on refresh")
	city.focus_all()
	check(city.world.scale.x > 0, "Map fits viewport")
	for direction in ["up", "down", "left", "right"]:
		check(city._avatar.sprite.sprite_frames.get_frame_count("walk_" + direction) == 4, "Teammate walking frames available in every direction")
	city._reduced_motion = true
	var arrivals: Array = []
	city.institution_selected.connect(func(id: String): arrivals.append(id))
	city.navigate_to("hospital")
	await get_tree().create_timer(0.25).timeout
	check(arrivals == ["hospital"], "Arrival emits destination once")
	check(city._avatar.position.is_equal_approx(city.park_position("hospital")), "Avatar reaches parked destination")
	city._hover("bank", true)
	await get_tree().create_timer(0.2).timeout
	city._hover("bank", false)
	await get_tree().create_timer(0.2).timeout
	check(city.buttons["bank"].position.is_equal_approx(city.PLACES["bank"].position - Vector2(80,143)), "Hover exit restores building resting position")
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("C:/Users/ioana/Documents/ChatGPT/hackathon/map-native-qa.png")
	print("City map navigation tests: ", failures, " failures")
	get_tree().quit(1 if failures else 0)

