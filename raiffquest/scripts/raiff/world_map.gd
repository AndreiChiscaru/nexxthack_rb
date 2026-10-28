extends Control
## Harta 2D top-down: o stradă, cinci clădiri interactive (Acasă, Banca, Serviciu, Magazin, Consilier).
## Mișcare: WASD / săgeți. Intrare: E, Enter sau Spațiu lângă ușă. Click pe o clădire: mergi la ușa ei.

signal near_changed(location_id: String)
signal enter_requested(location_id: String)

const MAP_SIZE := Vector2(800.0, 560.0)
const SPEED := 220.0
const PLAYER_RADIUS := 10.0
const INTERACT_RADIUS := 64.0
const GRASS := Color("5d8f55")
const GRASS_DARK := Color("507f49")
const ROAD := Color("464c55")
const SIDEWALK := Color("b9bdc4")

const BUILDINGS := {
	"home": {"rect": Rect2(50, 46, 180, 124), "door": Vector2(140, 188), "wall": Color("e6c9a3"), "roof": Color("a9593f"), "name": "ACASĂ", "top": true},
	"bank": {"rect": Rect2(310, 36, 190, 134), "door": Vector2(405, 188), "wall": Color("d9dde3"), "roof": Color("ffe600"), "name": "BANCA", "top": true},
	"work": {"rect": Rect2(570, 46, 180, 124), "door": Vector2(660, 188), "wall": Color("9fb4cc"), "roof": Color("46607e"), "name": "SERVICIU", "top": true},
	"shop": {"rect": Rect2(100, 396, 190, 120), "door": Vector2(195, 378), "wall": Color("9fd1bf"), "roof": Color("2f8068"), "name": "MAGAZIN", "top": false},
	"advisor": {"rect": Rect2(500, 396, 200, 120), "door": Vector2(600, 378), "wall": Color("cdbfe8"), "roof": Color("6a4fa3"), "name": "CONSILIER", "top": false},
}
const TREES := [
	Vector2(268, 90), Vector2(278, 140), Vector2(534, 92), Vector2(540, 142), Vector2(22, 24), Vector2(778, 24),
	Vector2(28, 470), Vector2(772, 500), Vector2(400, 480), Vector2(340, 430), Vector2(450, 520), Vector2(24, 330), Vector2(778, 340),
]

var player_pos := Vector2(400.0, 250.0)
var marker_location := ""
var enabled := false
var near_location := ""
var _bold_font: Font

func _ready() -> void:
	clip_contents = true
	focus_mode = Control.FOCUS_NONE
	mouse_filter = Control.MOUSE_FILTER_STOP
	_bold_font = load("res://assets/template/fonts/ui_bold.tres") as Font
	set_process(true)

func reset() -> void:
	player_pos = Vector2(400.0, 250.0)
	marker_location = ""
	near_location = ""
	queue_redraw()
	near_changed.emit("")

func set_marker(location_id: String) -> void:
	marker_location = location_id
	queue_redraw()

func _process(delta: float) -> void:
	if not enabled or not is_visible_in_tree():
		return
	var dir := Input.get_vector("move_left", "move_right", "move_up", "move_down")
	if dir != Vector2.ZERO:
		var step := dir * SPEED * delta
		var try_x := player_pos + Vector2(step.x, 0.0)
		if _free(try_x):
			player_pos = try_x
		var try_y := player_pos + Vector2(0.0, step.y)
		if _free(try_y):
			player_pos = try_y
		queue_redraw()
	_update_near()

func _free(p: Vector2) -> bool:
	if p.x < 12.0 or p.y < 12.0 or p.x > MAP_SIZE.x - 12.0 or p.y > MAP_SIZE.y - 12.0:
		return false
	for id: String in BUILDINGS:
		var r: Rect2 = BUILDINGS[id].rect
		if r.grow(PLAYER_RADIUS).has_point(p):
			return false
	return true

func _update_near() -> void:
	var best := ""
	var best_d := INTERACT_RADIUS
	for id: String in BUILDINGS:
		var d := player_pos.distance_to(BUILDINGS[id].door)
		if d < best_d:
			best_d = d
			best = id
	if best != near_location:
		near_location = best
		near_changed.emit(best)
		queue_redraw()

func _unhandled_input(event: InputEvent) -> void:
	if not enabled or near_location == "" or not is_visible_in_tree():
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode in [KEY_E, KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
			enter_requested.emit(near_location)
			get_viewport().set_input_as_handled()

func _gui_input(event: InputEvent) -> void:
	if not enabled:
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var p := _to_map(event.position)
		for id: String in BUILDINGS:
			var r: Rect2 = BUILDINGS[id].rect
			if r.grow(14.0).has_point(p):
				player_pos = BUILDINGS[id].door
				_update_near()
				queue_redraw()
				return

# ---------------------------------------------------------------- desenare

func _scale() -> float:
	return minf(size.x / MAP_SIZE.x, size.y / MAP_SIZE.y)

func _origin() -> Vector2:
	return (size - MAP_SIZE * _scale()) * 0.5

func _to_map(local: Vector2) -> Vector2:
	return (local - _origin()) / _scale()

func _p(v: Vector2) -> Vector2:
	return _origin() + v * _scale()

func _r(r: Rect2) -> Rect2:
	return Rect2(_p(r.position), r.size * _scale())

func _draw() -> void:
	var sc := _scale()
	draw_rect(Rect2(Vector2.ZERO, size), GRASS_DARK)
	draw_rect(_r(Rect2(Vector2.ZERO, MAP_SIZE)), GRASS)
	# stradă + treceri
	draw_rect(_r(Rect2(0, 215, 800, 70)), ROAD)
	for i in 16:
		draw_rect(_r(Rect2(10 + i * 50, 248, 28, 4)), Color("d8d9dc"))
	draw_rect(_r(Rect2(0, 207, 800, 8)), SIDEWALK)
	draw_rect(_r(Rect2(0, 285, 800, 8)), SIDEWALK)
	for id: String in BUILDINGS:
		var b: Dictionary = BUILDINGS[id]
		var door: Vector2 = b.door
		var path_rect := Rect2(door.x - 16, 170, 32, 45) if b.top else Rect2(door.x - 16, 293, 32, 85)
		draw_rect(_r(path_rect), SIDEWALK)
	for t: Vector2 in TREES:
		draw_circle(_p(t + Vector2(3, 4)), 16.0 * sc, Color(0, 0, 0, 0.18))
		draw_circle(_p(t), 15.0 * sc, Color("2f6b3a"))
		draw_circle(_p(t + Vector2(-4, -4)), 8.0 * sc, Color("3d8248"))
	# fântână decorativă
	draw_circle(_p(Vector2(400, 440)), 30.0 * sc, SIDEWALK)
	draw_circle(_p(Vector2(400, 440)), 22.0 * sc, Color("6cb8e0"))
	draw_circle(_p(Vector2(400, 440)), 6.0 * sc, Color("dff3ff"))
	for id: String in BUILDINGS:
		_draw_building(id, BUILDINGS[id], sc)
	_draw_player(sc)

func _draw_building(id: String, b: Dictionary, sc: float) -> void:
	var rect: Rect2 = b.rect
	var wall: Color = b.wall
	var roof: Color = b.roof
	draw_rect(_r(Rect2(rect.position + Vector2(6, 8), rect.size)), Color(0, 0, 0, 0.2))
	draw_rect(_r(rect), wall)
	draw_rect(_r(Rect2(rect.position, Vector2(rect.size.x, 30))), roof)
	draw_rect(_r(rect), roof.darkened(0.35), false, 2.0 * sc)
	# ferestre (lateral, ușa rămâne liberă în centru)
	for wx: float in [rect.position.x + 16.0, rect.end.x - 16.0 - 34.0]:
		draw_rect(_r(Rect2(wx, rect.position.y + 76, 34, 26)), Color("5b7fa6"))
		draw_rect(_r(Rect2(wx, rect.position.y + 76, 34, 26)), Color("30465f"), false, 1.5 * sc)
	# ușă pe latura dinspre stradă
	var door: Vector2 = b.door
	var door_y: float = rect.end.y - 34.0 if b.top else rect.position.y
	draw_rect(_r(Rect2(door.x - 14, door_y, 28, 34)), Color("4b3a2c"))
	# firmă
	var font_size := int(round(17.0 * sc))
	var text: String = b.name
	var text_w := _bold_font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	var sign_rect := Rect2(rect.position.x + rect.size.x * 0.5 - (text_w / sc) * 0.5 - 8, rect.position.y + 40, text_w / sc + 16, 26)
	draw_rect(_r(sign_rect), Color("14171c"))
	draw_string(_bold_font, _p(Vector2(sign_rect.position.x + 8, sign_rect.position.y + 19)), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color("ffe600"))
	# marcaj de misiune
	if id == marker_location:
		var top_center := Vector2(rect.position.x + rect.size.x * 0.5, rect.position.y - 16.0)
		if not b.top:
			top_center = Vector2(rect.position.x + rect.size.x * 0.5, rect.position.y - 16.0)
		draw_circle(_p(top_center), 16.0 * sc, Color("14171c"))
		draw_circle(_p(top_center), 13.0 * sc, Color("ffe600"))
		draw_string(_bold_font, _p(top_center + Vector2(-5, 8)), "!", HORIZONTAL_ALIGNMENT_LEFT, -1, int(round(22.0 * sc)), Color("14171c"))
		draw_arc(_p(door), 20.0 * sc, 0.0, TAU, 32, Color("ffe600"), 3.0 * sc)
	elif id == near_location:
		draw_arc(_p(door), 20.0 * sc, 0.0, TAU, 32, Color("ffffff"), 2.0 * sc)

func _draw_player(sc: float) -> void:
	var p := _p(player_pos)
	draw_circle(p + Vector2(2, 6) * sc, 11.0 * sc, Color(0, 0, 0, 0.25))
	draw_circle(p + Vector2(0, 3) * sc, 10.0 * sc, Color("ffe600"))
	draw_arc(p + Vector2(0, 3) * sc, 10.0 * sc, 0.0, TAU, 24, Color("14171c"), 2.0 * sc)
	draw_circle(p + Vector2(0, -8) * sc, 7.0 * sc, Color("f2c9a5"))
	draw_arc(p + Vector2(0, -8) * sc, 7.0 * sc, 0.0, TAU, 20, Color("14171c"), 1.5 * sc)
	draw_arc(p + Vector2(0, -10) * sc, 7.5 * sc, PI, TAU, 14, Color("3b2a1e"), 3.0 * sc)
