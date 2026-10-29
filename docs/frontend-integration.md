# Integrarea frontendului actual

Scena principală este `raiffquest/scenes/journey.tscn`. Codul activ este în `scripts/frontend/`; motorul financiar rulează pe backend, în `app/sim/`. Contractele HTTP sunt documentate în [api.md](api.md).

## Transport și stare

`api_config.gd` folosește originea paginii în Web, respectiv `http://127.0.0.1:8000` în modul nativ. `RAIFF_API` poate suprascrie adresa nativă (de exemplu portul 8010). `api_client.gd` gestionează cererile și erorile, `game_api.gd` expune operațiile, iar `session_controller.gd` păstrează starea și conversația interfeței. Deciziile se trimit backendului; interfața afișează răspunsul fără un al doilea motor financiar.

Agenții curenți sunt integrați în `app/api/`. Pentru testare se folosește `MOCK_LLM=true`; modul real necesită configurarea locală a cheii și `MOCK_LLM=false`. `/api/health` raportează modul activ.

## Importul documentelor

`statement_upload.gd` validează și pregătește fișierul selectat sau tras în fereastră. Selectarea nu îl trimite. Chatul afișează numele și permite eliminarea atașamentului; **Trimite / Send** pornește cererea. Extrasul folosește `/api/onboarding/statement`, iar documentele contabilului `/api/business/document`. După eroare, atașamentul rămâne disponibil pentru reîncercare.

## Aspect și localizare

`journey_theme.gd` definește paleta cartoon și fontul Figtree. `tools/build_cartoon_map.py` generează terenul curent. Harta conține opt instituții, inclusiv Divertisment; clădirile și traseele sunt definite de componentele hărții.

`autoload/game_locale.gd` gestionează RO/EN. Sursa traducerilor este `data/localization/en.json`, sincronizată în `raiffquest/localization/game_en.json` prin `tools/sync_game_localization.py`. Cererile trimit limba în `Accept-Language`.

## Verificare

Din rădăcina repo-ului:

```sh
python -m pytest -q
python raiffquest/tools/verify_current.py --godot godot
python raiffquest/tools/run_frontend_tests.py --godot godot
python raiffquest/tools/run_statement_upload_tests.py --godot godot
node raiffquest/test/statement_upload_web_test.cjs
python raiffquest/tools/run_backend_integration.py --godot godot --scene res://test/statement_flow_test.tscn
python raiffquest/tools/run_backend_integration.py --godot godot --scene res://test/journey_ui_test.tscn
python raiffquest/tools/run_backend_integration.py --godot godot --scene res://test/localization_test.tscn
```

Aceste teste folosesc date sintetice și agenți mock. Testarea manuală cu agenți reali se face separat. Exportul Web folosește presetul `Web`; deployul servește exportul din `game/` la `/joc/`. Adresa `/` redirecționează la joc.

Modificările se verifică local înainte de publicare. Push-ul și integrarea pe `main` se fac doar la cererea utilizatoarei.
