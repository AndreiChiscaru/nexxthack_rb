extends SceneTree
## Unealtă de dezvoltare (exclusă din export): rulează jocul sub Xvfb și salvează capturi PNG ale ecranelor cheie.
## xvfb-run -a godot --path . --rendering-driver opengl3 -s tools/capture_screens.gd -- /tmp/shots

const Events := preload("res://scripts/raiff/events.gd")
var out_dir := "/tmp/shots"

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		out_dir = args[0]
	DirAccess.make_dir_recursive_absolute(out_dir)
	call_deferred("_run")

func _shot(name: String) -> void:
	await process_frame
	await process_frame
	await process_frame
	await create_timer(0.25).timeout
	var img := root.get_texture().get_image()
	img.save_png("%s/%s.png" % [out_dir, name])
	print("saved ", name, " ", img.get_size())

func _run() -> void:
	var game: Control = (load("res://scenes/raiff_main.tscn") as PackedScene).instantiate()
	root.add_child(game)
	await _shot("01_title")
	game.start_game()
	await _shot("02_map")
	game._on_enter_requested("bank")
	await _shot("03_info_bank")
	game._on_info_closed()
	var plan := [2, 1, 0, 1, 2, 2, 0, 0, 0, 0]
	for i in Events.all().size():
		var ev: Dictionary = Events.all()[i]
		game._on_enter_requested(str(ev.location))
		if i == 2 or i == 3:
			game._on_advice_requested()
			await _shot("04_event%02d_advice" % [i + 1])
		game._on_option_chosen(mini(plan[i], ev.options.size() - 1))
		if i == 2 or i == 3 or i == 9:
			await _shot("05_result%02d" % [i + 1])
		game._on_continue()
		if i == 4:
			await _shot("06_map_midgame")
	await _shot("07_report_top")
	for pos in [520, 1100, 1700]:
		game._report._scroll.scroll_vertical = pos
		await _shot("08_report_%d" % pos)
	quit(0)
