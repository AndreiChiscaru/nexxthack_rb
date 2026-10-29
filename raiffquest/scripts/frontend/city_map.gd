extends Control
## Native presentation/navigation only. Server state supplies event badges.
signal institution_selected(id: String)

## Approved image-space layout, enlarged 40% without changing relative placement.
const MAP_SIZE := Vector2(2150.4, 1433.6)
const FOUNTAIN_CENTER := Vector2(1127, 672)
const BUILDING_SIZE := Vector2(336, 257.6)
const BUILDING_ANCHOR := Vector2(168, 277.6)
const PLACES := {
	"home": {"name": "Acasă", "position": Vector2(500, 640)},
	"education": {"name": "Educație", "position": Vector2(910, 445.2)},
	"work": {"name": "Loc de muncă", "position": Vector2(1344, 462)},
	"bank": {"name": "Bancă", "position": Vector2(1820, 648.2)},
	"business": {"name": "Afacere", "position": Vector2(1834, 1092)},
	"hospital": {"name": "Spital", "position": Vector2(1428, 1316)},
	"entertainment": {"name": "Divertisment", "position": Vector2(875, 1288)},
	"market": {"name": "Piață", "position": Vector2(462, 1106)},
}
const NODES := {
	# Entrances: where the avatar parks beside each building.
	"home": Vector2(570, 632),
	"education": Vector2(980, 437.2),
	"work": Vector2(1414, 454),
	"bank": Vector2(1890, 640.2),
	"business": Vector2(1904, 1084),
	"hospital": Vector2(1498, 1308),
	"entertainment": Vector2(945, 1280),
	"market": Vector2(532, 1098),

	# Central plaza: four tips and the middle of each side.
	"west": Vector2(770, 672),
	"north": Vector2(1127, 434),
	"east": Vector2(1484, 672),
	"south": Vector2(1127, 910),
	"nw": Vector2(945, 553),
	"ne": Vector2(1309, 553),
	"se": Vector2(1309, 791),
	"sw": Vector2(945, 791),

	# Four diagonal streets leave the plaza sides, bend and join the outer ring.
	# Together with the four avenues they split the city into eight blocks, one per building.
	"homeEntry": Vector2(693, 424),
	"home_corner": Vector2(650, 304),
	"workEntry": Vector2(1561, 424),
	"work_corner": Vector2(1604, 304),
	"marketEntry": Vector2(693, 959),
	"market_corner": Vector2(650, 1098),
	"businessEntry": Vector2(1561, 959),
	"business_approach": Vector2(1604, 1084),

	# Outer ring, clockwise from the top-left, with the gates where avenues and streets join it.
	"nwCorner": Vector2(312, 304),
	"nwTurn": Vector2(560, 98),
	"topGate": Vector2(1127, 98),
	"neTurn": Vector2(1722, 98),
	"neCorner": Vector2(2100, 304),
	"eastGate": Vector2(2093, 676.2),
	"eastBusiness": Vector2(2097.2, 980),
	"seCorner": Vector2(2100, 1084),
	"seTurn": Vector2(1722, 1337),
	"hospital_approach": Vector2(1498, 1337),
	"bottomGate": Vector2(1127, 1337),
	"entertainment_approach": Vector2(945, 1337),
	"swTurn": Vector2(560, 1337),
	"swCorner": Vector2(252, 1098),
	"westMarket": Vector2(252, 994),
	"westGate": Vector2(266, 672),
	"home_approach": Vector2(570, 672),
	"bank_approach": Vector2(1890, 676.2),
	"bridge": Vector2(238, 651),
	"bridgewest": Vector2(21, 651),
}
const EDGES := [
	# Plaza.
	["west", "nw"],
	["nw", "north"],
	["north", "ne"],
	["ne", "east"],
	["east", "se"],
	["se", "south"],
	["south", "sw"],
	["sw", "west"],

	# Avenues from the plaza to the outer ring.
	["north", "topGate"],
	["west", "home_approach"],
	["home_approach", "westGate"],
	["east", "bank_approach"],
	["bank_approach", "eastGate"],
	["south", "bottomGate"],

	# Diagonal streets, mirrored top and bottom, left and right.
	["nw", "homeEntry"],
	["homeEntry", "home_corner"],
	["home_corner", "nwCorner"],
	["ne", "workEntry"],
	["workEntry", "work_corner"],
	["work_corner", "neCorner"],
	["sw", "marketEntry"],
	["marketEntry", "market_corner"],
	["market_corner", "market"],
	["market", "swCorner"],
	["se", "businessEntry"],
	["businessEntry", "business_approach"],
	["business_approach", "business"],
	["business", "seCorner"],

	# Driveways.
	["home_approach", "home"],
	["nw", "education"],
	["ne", "work"],
	["bank_approach", "bank"],
	["hospital_approach", "hospital"],
	["entertainment_approach", "entertainment"],

	# Outer ring.
	["westGate", "nwCorner"],
	["nwCorner", "nwTurn"],
	["nwTurn", "topGate"],
	["topGate", "neTurn"],
	["neTurn", "neCorner"],
	["neCorner", "eastGate"],
	["eastGate", "eastBusiness"],
	["eastBusiness", "seCorner"],
	["seCorner", "seTurn"],
	["seTurn", "hospital_approach"],
	["hospital_approach", "bottomGate"],
	["bottomGate", "entertainment_approach"],
	["entertainment_approach", "swTurn"],
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
var _hint: Label
var _at := "home"
const PLAY_ZOOM := 1.0
var _zoom := PLAY_ZOOM
var _camera: Tween
var _pan := Vector2.ZERO
var _dragging := false
var _walking := false
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
	_hint = Label.new()
	_hint.text = "Alege o clădire. Avatarul te conduce acolo."
	_hint.add_theme_font_size_override("font_size", 13)
	_hint.add_theme_color_override("font_color", INK)
	_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	_hint.offset_top = -28
	_hint.offset_bottom = -4
	add_child(_hint)
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

## roomy: the larger padding of the building name tags; map controls keep the compact one.
func _label_style(selected: bool, roomy := false) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color("fee600") if selected else Color("fffbef")
	style.border_color = Color("8f977c")
	style.set_border_width_all(1)
	style.set_corner_radius_all(6 if roomy else 4)
	style.shadow_color = Color("303a2830")
	style.shadow_size = 1
	style.shadow_offset = Vector2(0,3)
	style.content_margin_left = 18 if roomy else 10
	style.content_margin_right = 18 if roomy else 10
	style.content_margin_top = 6 if roomy else 4
	style.content_margin_bottom = 6 if roomy else 4
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
	label.add_theme_font_size_override("font_size",34)
	label.add_theme_font_override("font",load("res://assets/raiff/fonts/Figtree-Bold.ttf"))
	label.add_theme_color_override("font_color",INK)
	label.add_theme_stylebox_override("normal",_label_style(false, true))
	label.add_theme_stylebox_override("hover",_label_style(false, true))
	label.add_theme_stylebox_override("pressed",_label_style(true, true))
	label.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	world.add_child(label)
	label.reset_size()
	# Tucked against the building's front corner rather than floating below it.
	label.position = center + Vector2(-label.size.x / 2, -16)
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
	if not PLACES.has(origin) or not PLACES.has(destination):
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

func navigate_to(id: String) -> void:
	if _walking or not PLACES.has(id) or not is_instance_valid(_avatar):
		return
	if id == _at:
		institution_selected.emit(id)
		return
	_walking = true
	_hint.text = "În drum spre %s…" % PLACES[id].name
	for key in labels:
		labels[key].add_theme_stylebox_override("normal", _label_style(key == id, true))
	var points := path_to(_at, id)
	_route.points = points
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
		_hint.text = "Ai ajuns la %s." % PLACES[id].name
		institution_selected.emit(id)
	)

func enter_map() -> void:
	_pan = Vector2.ZERO
	_zoom = 0.88
	_transform_world()
	_zoom = PLAY_ZOOM
	_transform_world(true)

func focus_all() -> void:
	_zoom = 1.0
	_pan = Vector2.ZERO
	_transform_world(true)

func _set_zoom(value: float) -> void:
	_zoom = clampf(value, 0.8, 2.3)
	_transform_world(true)

func _transform_world(animated: bool = false) -> void:
	if not is_instance_valid(world):
		return
	var fit := maxf(0.05, minf(size.x / MAP_SIZE.x, (size.y - 40) / MAP_SIZE.y))
	var target_scale := Vector2.ONE * fit * _zoom
	var target_position := size * 0.5 + _pan - FOUNTAIN_CENTER * target_scale
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

