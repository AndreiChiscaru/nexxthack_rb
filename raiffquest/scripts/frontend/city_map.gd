extends Control
## Native presentation/navigation only. Server state supplies event badges.
signal institution_selected(id: String)

## Approved image-space layout, enlarged 40% without changing relative placement.
const MAP_SIZE := Vector2(2150.4, 1433.6)
const FOUNTAIN_CENTER := Vector2(1127, 672)
const BUILDING_SIZE := Vector2(336, 257.6)
const BUILDING_ANCHOR := Vector2(168, 277.6)
const PLACES := {
	"home": {"name": "Acasă", "position": Vector2(490, 478.8)},
	"education": {"name": "Educație", "position": Vector2(910, 445.2)},
	"work": {"name": "Loc de muncă", "position": Vector2(1435, 462)},
	"bank": {"name": "Bancă", "position": Vector2(1820, 648.2)},
	"business": {"name": "Afacere", "position": Vector2(1834, 1092)},
	"hospital": {"name": "Spital", "position": Vector2(1428, 1316)},
	"entertainment": {"name": "Divertisment", "position": Vector2(875, 1288)},
	"market": {"name": "Piață", "position": Vector2(462, 1106)},
}
const NODES := {
	"market_corner": Vector2(650, 1098),

	"home": Vector2(560, 470.8),
	"education": Vector2(980, 437.2),
	"work": Vector2(1505, 454),
	"bank": Vector2(1890, 640.2),
	"business": Vector2(1904, 1084),
	"hospital": Vector2(1498, 1308),
	"entertainment": Vector2(945, 1280),
	"market": Vector2(532, 1098),

	"home_approach": Vector2(273, 476),
	"bank_approach": Vector2(1890, 676.2),
	"eastBusiness": Vector2(2097.2, 980),
	"hospital_approach": Vector2(1498, 1337),
	"entertainment_approach": Vector2(1127, 1232),
	"westMarket": Vector2(252, 994),
	"west": Vector2(770, 672),
	"north": Vector2(1127, 434),
	"east": Vector2(1484, 672),
	"south": Vector2(1127, 910),
	"nw": Vector2(945, 553),
	"ne": Vector2(1309, 553),
	"se": Vector2(1309, 791),
	"sw": Vector2(945, 791),
	"westGate": Vector2(266, 672),
	"nwCorner": Vector2(273, 329),
	"nwTurn": Vector2(546, 98),
	"topLeft": Vector2(1050, 98),
	"topGate": Vector2(1127, 140),
	"topRight": Vector2(1204, 98),
	"neTurn": Vector2(1596, 98),
	"neCorner": Vector2(2086, 455),
	"eastGate": Vector2(2093, 676.2),
	"seCorner": Vector2(2100, 1050),
	"seTurn": Vector2(1722, 1337),
	"bottomRight": Vector2(1204, 1337),
	"bottomGate": Vector2(1127, 1281),
	"bottomLeft": Vector2(1050, 1337),
	"swTurn": Vector2(560, 1337),
	"swCorner": Vector2(252, 1064),
	"bridge": Vector2(238, 651),
	"bridgewest": Vector2(21, 651),
	"marketEntry": Vector2(693, 959),
	"business_approach": Vector2(1719, 1084),
	"outerSEJoin": Vector2(1848, 1218),
}
const EDGES := [
	["marketEntry", "market_corner"],
	["market_corner", "market"],
	["bottomGate", "entertainment"],
	["business_approach", "business"],
	["home_approach", "home"],
	["nw", "education"],
	["ne", "work"],
	["bank_approach", "bank"],
	["hospital_approach", "hospital"],

	["west", "nw"],
	["nw", "north"],
	["north", "ne"],
	["ne", "east"],
	["east", "se"],
	["se", "south"],
	["south", "sw"],
	["sw", "west"],
	["sw", "marketEntry"],
	["se", "business_approach"],
	["business_approach", "outerSEJoin"],
	["north", "topGate"],
	["west", "westGate"],
	["east", "bank_approach"],
	["bank_approach", "eastGate"],
	["south", "entertainment_approach"],
	["entertainment_approach", "bottomGate"],
	["westGate", "home_approach"],
	["home_approach", "nwCorner"],
	["nwCorner", "nwTurn"],
	["nwTurn", "topLeft"],
	["topLeft", "topGate"],
	["topGate", "topRight"],
	["topRight", "neTurn"],
	["neTurn", "neCorner"],
	["neCorner", "eastGate"],
	["eastGate", "eastBusiness"],
	["eastBusiness", "seCorner"],
	["seCorner", "outerSEJoin"],
	["outerSEJoin", "seTurn"],
	["seTurn", "hospital_approach"],
	["hospital_approach", "bottomRight"],
	["bottomRight", "bottomGate"],
	["bottomGate", "bottomLeft"],
	["bottomLeft", "swTurn"],
	["swTurn", "swCorner"],
	["swCorner", "westMarket"],
	["westMarket", "westGate"],
	["westGate", "bridge"],
	["bridge", "bridgewest"],
]
const GRASS := Color("bccb91")
const INK := Color("303a28")
var world: Control
var badges: Dictionary = {}
var buttons: Dictionary = {}
var labels: Dictionary = {}
var _hover_tweens: Dictionary = {}
var _avatar: MapAvatar
var _route: Line2D
var _at := "home"
const PLAY_ZOOM := 1.0
var _zoom := PLAY_ZOOM
var _camera: Tween
var _pan := Vector2.ZERO
var _dragging := false
var _walking := false
var follow_enabled := false
var follow_view_rect := Rect2()
var _reduced_motion := false
var _travel: Tween
var _statuses: Array = []

class MapAvatar extends Node2D:
	var sprite: AnimatedSprite2D
	func _ready() -> void:
		sprite = AnimatedSprite2D.new()
		var frames := SpriteFrames.new()
		frames.remove_animation("default")
		for pose in ["idle", "happy", "thinking", "phone", "talking", "sad", "surprised"]:
			frames.add_animation(pose)
			frames.add_frame(pose, load("res://assets/raiff/characters/male/%s.png" % pose))
		for direction in ["up", "down", "left", "right"]:
			var anim: String = "walk_" + direction
			frames.add_animation(anim)
			frames.set_animation_speed(anim, 6)
			for i in range(4):
				frames.add_frame(anim, load("res://assets/raiff/characters/male/walk_%s_%02d.png" % [direction,i]))
		sprite.sprite_frames = frames
		sprite.scale = Vector2.ONE * 0.46
		sprite.position.y = -33
		add_child(sprite)
		sprite.play("idle")
	func face(delta: Vector2) -> void:
		var direction := ("right" if delta.x > 0 else "left") if absf(delta.x) > absf(delta.y) else ("down" if delta.y > 0 else "up")
		sprite.play("walk_" + direction)
	func rest() -> void:
		sprite.play("idle")
	func _draw() -> void:
		draw_set_transform(Vector2.ZERO, 0, Vector2(1.0,0.3))
		draw_circle(Vector2.ZERO, 15, Color("52633b40"))

func _ready() -> void:
	theme = preload("res://scripts/frontend/journey_theme.gd").theme()
	clip_contents = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	mouse_default_cursor_shape = Control.CURSOR_DRAG
	var backdrop := ColorRect.new()
	backdrop.color = GRASS
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(backdrop)
	world = Control.new()
	world.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(world)
	var terrain := TextureRect.new()
	terrain.texture = load("res://assets/raiff/city_cartoon_terrain.svg")
	terrain.position = Vector2.ZERO
	terrain.size = MAP_SIZE
	terrain.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	terrain.mouse_filter = Control.MOUSE_FILTER_IGNORE
	world.add_child(terrain)
	_route = Line2D.new()
	_route.width = 3
	_route.default_color = Color("b69d0070")
	world.add_child(_route)
	for id in PLACES:
		_add_building(id)
	_avatar = MapAvatar.new()
	_avatar.position = park_position(_at)
	world.add_child(_avatar)
	var controls := HBoxContainer.new()
	controls.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	controls.position = Vector2(-180,-52)
	controls.size = Vector2(164,36)
	add_child(controls)
	for item in [["−", "Micșorează harta"], ["+", "Mărește harta"], ["⌂", "Arată toată harta"], ["◌", "Redu animațiile"]]:
		var control := Button.new()
		control.text = item[0]
		control.custom_minimum_size = Vector2(36,36)
		control.add_theme_stylebox_override("normal", _label_style(false))
		control.add_theme_color_override("font_color", INK)
		controls.add_child(control)
		match item[0]:
			"−": control.pressed.connect(func(): _set_zoom(_zoom - 0.15))
			"+": control.pressed.connect(func(): _set_zoom(_zoom + 0.15))
			"⌂": control.pressed.connect(focus_all)
			"◌":
				control.toggle_mode = true
				control.toggled.connect(func(value: bool): _reduced_motion = value)
	resized.connect(_transform_world)
	_transform_world()
	set_institutions(_statuses)

func _label_style(selected: bool) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color("fee600") if selected else Color("fffbef")
	style.border_color = Color("8f977c")
	style.set_border_width_all(1)
	style.set_corner_radius_all(4)
	style.shadow_color = Color("303a2830")
	style.shadow_size = 1
	style.shadow_offset = Vector2(0,3)
	style.content_margin_left = 10
	style.content_margin_right = 10
	style.content_margin_top = 4
	style.content_margin_bottom = 4
	return style

func _add_building(id: String) -> void:
	var center: Vector2 = PLACES[id].position
	var button := TextureButton.new()
	button.texture_normal = load("res://assets/raiff/%s_flat_isometric.png" % id)
	button.ignore_texture_size = true
	button.stretch_mode = TextureButton.STRETCH_KEEP_ASPECT_CENTERED
	button.position = center - BUILDING_ANCHOR
	button.size = BUILDING_SIZE
	button.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	world.add_child(button)
	buttons[id] = button
	button.pressed.connect(navigate_to.bind(id))
	button.mouse_entered.connect(_hover.bind(id, true))
	button.mouse_exited.connect(_hover.bind(id, false))
	var label := Button.new()
	label.text = PLACES[id].name
	label.add_theme_font_size_override("font_size",20)
	label.add_theme_font_override("font",load("res://assets/raiff/fonts/Figtree-Bold.ttf"))
	label.add_theme_color_override("font_color",INK)
	label.add_theme_stylebox_override("normal",_label_style(false))
	label.add_theme_stylebox_override("hover",_label_style(false))
	label.add_theme_stylebox_override("pressed",_label_style(true))
	label.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	world.add_child(label)
	label.reset_size()
	label.position = center + Vector2(-label.size.x / 2, 12)
	label.pressed.connect(navigate_to.bind(id))
	labels[id] = label
	var badge := Label.new()
	badge.position = center + Vector2(50,-140)
	badge.add_theme_font_size_override("font_size",20)
	badge.add_theme_color_override("font_color",INK)
	badge.add_theme_stylebox_override("normal",_label_style(true))
	badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	world.add_child(badge)
	badges[id] = badge

func _hover(id: String, entered: bool) -> void:
	if _hover_tweens.has(id):
		_hover_tweens[id].kill()
	var tween := create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	_hover_tweens[id] = tween
	var rest: Vector2 = PLACES[id].position - BUILDING_ANCHOR
	tween.tween_property(buttons[id], "position", rest + Vector2(0,-7 if entered else 0), 0.16)

func set_institutions(statuses: Array) -> void:
	_statuses = statuses
	for badge in badges.values():
		badge.hide()
	for status in statuses:
		if not status is Dictionary:
			continue
		var id := str(status.get("id", ""))
		var count := int(status.get("pending_events", 0))
		if badges.has(id) and count > 0:
			badges[id].text = str(count)
			badges[id].show()

func park_position(id: String) -> Vector2:
	return NODES.get(id, Vector2.ZERO)

## Exact entrance-to-entrance shortest path; no extra parking movement.
func path_to(origin: String, destination: String) -> PackedVector2Array:
	if not NODES.has(origin) or not PLACES.has(destination):
		return PackedVector2Array()
	var distance := {}
	var previous := {}
	var remaining: Array = NODES.keys()
	for id in remaining:
		distance[id] = INF
	distance[origin] = 0.0
	while not remaining.is_empty():
		var current: String = remaining[0]
		for candidate in remaining:
			if distance[candidate] < distance[current]:
				current = candidate
		remaining.erase(current)
		if current == destination:
			break
		for edge in EDGES:
			var next: String = edge[1] if edge[0] == current else (edge[0] if edge[1] == current else "")
			if next.is_empty() or not remaining.has(next):
				continue
			var cost: float = distance[current] + NODES[current].distance_to(NODES[next])
			if cost < distance[next]:
				distance[next] = cost
				previous[next] = current
	var reverse: Array[String] = [destination]
	while reverse[-1] != origin:
		if not previous.has(reverse[-1]):
			return PackedVector2Array()
		reverse.append(previous[reverse[-1]])
	reverse.reverse()
	var points := PackedVector2Array()
	for id in reverse:
		points.append(NODES[id])
	return points

## Attach the current position to its road segment and compare both directions.
## This keeps redirects on roads instead of restarting from the last building.
func path_from_position(position: Vector2, destination: String) -> PackedVector2Array:
	var nearest_edge: Array = []
	var nearest := INF
	for edge in EDGES:
		var projected := Geometry2D.get_closest_point_to_segment(position, NODES[edge[0]], NODES[edge[1]])
		var gap := position.distance_squared_to(projected)
		if gap < nearest:
			nearest = gap
			nearest_edge = edge
	var best := PackedVector2Array()
	var best_cost := INF
	for endpoint: String in nearest_edge:
		var tail := path_to(endpoint, destination)
		if tail.is_empty():
			continue
		var candidate := PackedVector2Array([position])
		var cost := 0.0
		for point in tail:
			var step := candidate[-1].distance_to(point)
			if step > 0.01:
				cost += step
				candidate.append(point)
		if cost < best_cost:
			best_cost = cost
			best = candidate
	return best

func navigate_to(id: String) -> void:
	if not PLACES.has(id) or not is_instance_valid(_avatar):
		return
	var points := path_from_position(_avatar.position, id)
	if points.is_empty():
		return
	if _travel:
		_travel.kill()
	for key in labels:
		labels[key].add_theme_stylebox_override("normal", _label_style(key == id))
	follow_enabled = true
	if _camera:
		_camera.kill()
	# The sidebar follows the selected destination immediately, not arrival.
	institution_selected.emit(id)
	_route.points = points
	_walking = points.size() > 1
	if not _walking:
		_at = id
		_avatar.rest()
		_route.clear_points()
		return
	_travel = create_tween()
	for index in range(1, points.size()):
		var duration := 0.001 if _reduced_motion else points[index - 1].distance_to(points[index]) / 350.0
		_travel.tween_callback(_avatar.face.bind(points[index] - points[index - 1]))
		_travel.tween_property(_avatar, "position", points[index], duration)
	_travel.tween_callback(func():
		_at = id
		_walking = false
		_avatar.rest()
		_route.clear_points()
	)

func enter_map() -> void:
	follow_enabled = false
	_pan = Vector2.ZERO
	_zoom = 0.88
	_transform_world()
	_zoom = PLAY_ZOOM
	_transform_world(true)

func focus_all() -> void:
	follow_enabled = false
	_zoom = 1.0
	_pan = Vector2.ZERO
	_transform_world(true)

func _set_zoom(value: float) -> void:
	_zoom = clampf(value, 0.8, 2.3)
	_transform_world(true)

func _process(delta: float) -> void:
	if not visible or not follow_enabled or not is_instance_valid(_avatar):
		return
	if _camera and _camera.is_running():
		return
	var safe := follow_view_rect if follow_view_rect.has_area() else Rect2(Vector2(60, 100), size - Vector2(120, 190))
	var target := safe.get_center() - _avatar.position * world.scale
	if not _dragging:
		world.position = world.position.lerp(target, 1.0 if _reduced_motion else 1.0 - exp(-6.0 * delta))
	# Hard guard at the edge: the avatar cannot slip behind a newly opened panel.
	var avatar_screen := world.position + _avatar.position * world.scale
	var clamped := avatar_screen.clamp(safe.position, safe.end)
	world.position += clamped - avatar_screen
	_pan = world.position - size * 0.5 + FOUNTAIN_CENTER * world.scale

func _transform_world(animated: bool = false) -> void:
	if not is_instance_valid(world):
		return
	var fit := maxf(0.05, minf(size.x / MAP_SIZE.x, (size.y - 40) / MAP_SIZE.y))
	var target_scale := Vector2.ONE * fit * _zoom
	var target_position := size * 0.5 + _pan - FOUNTAIN_CENTER * target_scale
	if follow_enabled and follow_view_rect.has_area():
		target_position = follow_view_rect.get_center() - _avatar.position * target_scale
	if _camera:
		_camera.kill()
	if animated and not _reduced_motion:
		_camera = create_tween().set_parallel(true).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		_camera.tween_property(world, "scale", target_scale, 0.55)
		_camera.tween_property(world, "position", target_position, 0.55)
	else:
		world.scale = target_scale
		world.position = target_position

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			_dragging = event.pressed
		elif event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_UP:
			_set_zoom(_zoom + 0.1)
		elif event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_set_zoom(_zoom - 0.1)
		accept_event()
	elif event is InputEventMouseMotion and _dragging:
		if not Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
			_dragging = false
			return
		_pan += event.relative
		_pan = _pan.clamp(-size * 0.65, size * 0.65)
		_transform_world()
		accept_event()

