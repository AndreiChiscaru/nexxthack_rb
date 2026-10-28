extends Control
## Grafic simplu: patrimoniul net și datoriile la fiecare vârstă (22 -> 52).

const Sim := preload("res://scripts/raiff/finance_sim.gd")
const Kit := preload("res://scripts/raiff/ui_kit.gd")

var history: Array = []

func set_history(h: Array) -> void:
	history = h
	queue_redraw()

func _draw() -> void:
	var font := get_theme_default_font()
	var area := Rect2(70, 14, size.x - 90, size.y - 52)
	draw_rect(Rect2(Vector2.ZERO, size), Color("171a1f"))
	if history.size() < 2:
		return
	var max_v := 1000.0
	var min_v := 0.0
	for h: Dictionary in history:
		max_v = maxf(max_v, maxf(float(h.net_worth), float(h.debt)))
		min_v = minf(min_v, float(h.net_worth))
	var span := max_v - min_v
	for i in 5:
		var t := float(i) / 4.0
		var y := area.end.y - t * area.size.y
		draw_line(Vector2(area.position.x, y), Vector2(area.end.x, y), Color("2a2f37"), 1.0)
		var value := min_v + span * t
		draw_string(font, Vector2(4, y + 4), _short(value), HORIZONTAL_ALIGNMENT_LEFT, 62, 12, Kit.MUTED)
	var nw := PackedVector2Array()
	var debt := PackedVector2Array()
	for i in history.size():
		var x := area.position.x + area.size.x * float(i) / float(history.size() - 1)
		var yn := area.end.y - (float(history[i].net_worth) - min_v) / span * area.size.y
		var yd := area.end.y - (float(history[i].debt) - min_v) / span * area.size.y
		nw.append(Vector2(x, yn))
		debt.append(Vector2(x, yd))
		draw_string(font, Vector2(x - 10, size.y - 8), str(int(history[i].age)), HORIZONTAL_ALIGNMENT_LEFT, 30, 12, Kit.MUTED)
	draw_polyline(debt, Kit.BAD, 2.0, true)
	draw_polyline(nw, Kit.YELLOW, 3.0, true)
	for p: Vector2 in nw:
		draw_circle(p, 4.0, Kit.YELLOW)
	draw_string(font, Vector2(area.position.x + 8, area.position.y + 14), "Patrimoniu net", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Kit.YELLOW)
	draw_string(font, Vector2(area.position.x + 120, area.position.y + 14), "Datorii", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Kit.BAD)

func _short(v: float) -> String:
	if absf(v) >= 1000000.0:
		return ("%.1f M" % (v / 1000000.0)).replace(".", ",")
	if absf(v) >= 1000.0:
		return "%d k" % int(round(v / 1000.0))
	return str(int(round(v)))
