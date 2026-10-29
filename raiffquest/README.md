# RaiffQuest

Joc financiar 2D cu onboarding conversațional, opt instituții și agenți AI conectați la backend. Interfața oferă română și engleză.

## Pornire

Pornește backendul FastAPI din rădăcina repo-ului, apoi deschide `project.godot` în Godot 4.7 și apasă F5. Scena principală este `scenes/journey.tscn`. Variabila `RAIFF_API` poate indica adresa backendului local.

Pe hartă, selectează o clădire pentru deplasare și acțiuni. Poți deplasa harta cu mouse-ul și folosi butoanele de zoom. Selectorul de limbă se află în dreapta jos.

## Documente

Alege sau trage un fișier în conversație. Numele apare ca atașament pregătit; analiza începe numai la **Trimite / Send**. Extrasul merge la `/api/onboarding/statement`, iar documentele contabilului la `/api/business/document`.

## Arhitectură

- `scripts/frontend/`: interfață și client API; fără simulare financiară locală.
- `autoload/game_locale.gd`: localizarea activă RO/EN.
- `../app/api/`: onboarding, consiliere și contabilitate.
- `../app/sim/`: motorul financiar, sursa stării de joc.
- `../data/`: evenimente, produse, traduceri și legislație.

## Verificare și export

```sh
python tools/verify_current.py --godot godot
python tools/run_backend_integration.py --godot godot --scene res://test/journey_ui_test.tscn
python tools/run_backend_integration.py --godot godot --scene res://test/localization_test.tscn
```

Verificările locale folosesc date sintetice și agenți mock. Agenții reali necesită configurarea serverului în `.env`. Nu se includ cheile în Git.

Exportul Web folosește presetul `Web` și `web/loading.html`; creează folderul `dist` înainte de export. Nu mai este necesar runtime-ul Manus. Fonturile Figtree și licența lor sunt în `assets/raiff/fonts/`.
