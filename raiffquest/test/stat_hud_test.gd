extends Node
var failed := false
func check(ok: bool, label: String) -> void:
	if not ok:
		failed = true
		push_error(label)
func _ready() -> void:
	if not ResourceLoader.exists("res://scripts/frontend/stat_hud.gd"):
		push_error("Financial HUD component is missing")
		get_tree().quit(1)
		return
	var hud = load("res://scripts/frontend/stat_hud.gd").new()
	add_child(hud)
	hud.size = Vector2(440, 210)
	var state := {"score":72,"month":3,"balance":{"cash":2400,"savings":6000,"investments":1500,"debt":3200},"monthly":{"income":5800,"expenses":{"home":1800,"market":1700,"bank":600}},"goal":{"type":"fond_urgenta","target_amount":15000,"progress":0.5}}
	var profile := {"goal":{"description":"Fond de siguranță", "horizon_months":12}}
	hud.update_state(state, profile)
	await get_tree().process_frame
	check(hud.score_label.text == "72 / 100" and hud.score_bar.value == 72, "Choice score comes from backend")
	check(hud.cash_value.text == "2.400 lei", "Cash uses backend balance")
	check(hud.surplus_value.text == "+1.700 lei", "Monthly balance includes every backend expense")
	check(hud.debt_value.text == "3.200 lei", "Debt remains visible")
	check(hud.progress.value == 50, "Progress is authoritative, not recalculated from savings")
	check(hud.goal_amount.text == "7.500 / 15.000 lei", "Saved assets match backend goal semantics")
	state.monthly.expenses.market = 5000
	state.goal = {"type":"achitare_datorii","target_amount":10000,"progress":0.68}
	hud.update_state(state, profile)
	check(hud.surplus_value.text == "−1.600 lei", "Negative monthly balance stays negative")
	check(hud.goal_amount.text == "Rămas: 3.200 lei", "Debt goal shows remaining debt")
	check(hud.progress.value == 68, "Debt goal preserves backend progress")
	await get_tree().process_frame
	check(hud.size.x <= 440 and hud.size.y <= 270, "HUD stays compact")
	print("[stat-hud] ", "FAIL" if failed else "PASS")
	get_tree().quit(1 if failed else 0)
