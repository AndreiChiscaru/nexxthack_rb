# Frontend: contracte si etape de integrare

Branch initial: `frontend/integration-foundation`.
Referinta comuna confirmata: `implementation-plan.md`, sectiunea 4.

## Etapa 1: transportul API (implementat)

- `raiffquest/scripts/frontend/api_config.gd`: URL comun. In browser se foloseste originea paginii. In editor/desktop se foloseste `http://127.0.0.1:8000`, suprascris explicit prin `RAIFF_API`.
- `api_client.gd`: JSON, ID unic per cerere, timeout, limita de raspuns, anulare, stare de incarcare si erori normalizate. Nu retrimite automat actiuni dupa un timeout.
- `game_api.gd`: metodele frontend pentru endpoint-urile convenite. Nu contine calcule financiare, prompt-uri sau catalog duplicat.
- Importul existent foloseste aceeasi configurare si ramane pe `/api/analyze`. Upload-ul web are timeout si limita de 25 MB; anularea selectiei permite o noua incercare.

Clientul nou este pregatit pentru ecranele urmatoare. Jocul existent ruleaza in continuare cu simulatorul local; nu sustinem ca a fost deja migrat la backend.

### Utilizare in ecrane

```gdscript
const GameApi := preload("res://scripts/frontend/game_api.gd")
var api := GameApi.new()
var pending_id := 0

func _ready() -> void:
    add_child(api)
    api.request_finished.connect(_on_api_finished)
    pending_id = api.create_session()

func _on_api_finished(id: int, response: Dictionary) -> void:
    if id != pending_id:
        return
    pending_id = 0
    if not response.ok:
        # Afiseaza response.error.message ca text simplu, nu HTML/BBCode.
        return
    # Valideaza schema endpoint-ului inainte sa actualizezi ecranul.
    # response.data contine JSON-ul serverului, nemodificat.
```

`request_finished(id, response)` este emis o singura data, inclusiv la anulare.
Eroarea de validare locala este emisa amanat, astfel incat ecranul poate salva ID-ul returnat.
`busy_changed` reflecta toate cererile active ale clientului. Fiecare ecran trebuie sa previna dublarea propriei actiuni si sa anuleze cererile cand este abandonat. Transportul nu transforma un esec de API in date demonstrative.

Raspuns normalizat:

```json
{"ok": true, "status": 200, "data": {"session_id": "..."}, "error": null}
```

La eroare: `ok=false`, `data=null`, `error={"code", "message"}`. Coduri: `invalid_request`, `network`, `timeout`, `http`, `invalid_json`, `invalid_response`, `response_too_large`, `cancelled`.

### Interfata pentru colegul de backend

| Metoda frontend | Cerere |
|---|---|
| `create_session()` | `POST /api/session`, `{}` |
| `onboarding_message(session_id, text)` | `POST /api/onboarding/message`, `{session_id, text}` |
| `start_game(session_id, profile)` | `POST /api/game/start`, `{session_id, profile}` |
| `get_game_state(session_id)` | `GET /api/game/state?session_id=...` |
| `perform_action(session_id, institution, action_id, params)` | `POST /api/game/action`, `{session_id, institution, action_id, params}` |
| `advance_month(session_id)` | `POST /api/game/advance`, `{session_id}` |
| `advisor_message(session_id, text)` | `POST /api/advisor/message`, `{session_id, text}` |
| `get_products(category)` | `GET /api/products?category=...` |

Clarificari adaugate de adaptor: planul nu precizeaza transportul sesiunii pe fiecare ruta. Frontend-ul propune `session_id` in JSON pentru POST si in query pentru GET; profilul de start este in cheia `profile`. Colegul de backend trebuie sa confirme aceste detalii inainte de conectarea ecranelor. Daca difera, se modifica doar `game_api.gd`.

Forma completa a raspunsurilor pentru start/action/advance si a evenimentelor active trebuie stabilita inainte de etapa 3. Clientul pastreaza raspunsurile nemodificate; nu presupune inca daca starea este directa sau in cheia `state`. `/api/onboarding/statement` si agentul de afaceri vor fi conectate separat cand exista contractele multipart.

Endpoint-urile noi nu exista in backend-ul acestui commit de baza. Un 404 este afisat drept eroare, nu drept succes demonstrativ. `session_id` identifica o sesiune; transportul sau nu reprezinta un mecanism de autentificare.

## Etapele urmatoare

1. Onboarding: sesiune, conversatie, stari de incarcare/eroare, rezumat editabil si confirmarea profilului. In dezvoltare folosim raspunsuri sintetice marcate explicit.
2. Stare centrala: preluarea starii de la backend si un adaptor de afisare pentru HUD; frontend-ul nu recalculeaza soldurile.
3. Harta cu cele sapte ID-uri convenite, panouri pe institutii si acoperire pentru stari fara actiuni disponibile. Grafica va furniza resursele separat de logica.
4. Actiune si luna urmatoare: alegere, trimitere, rezultat, evenimente noi; blocarea dublei trimiteri si recuperare dupa timeout prin recitirea starii.
5. AIngel: chat, indicatoare de asteptare, tool calls `{name, args, summary}` si sugestii legate de obiectiv.
6. Raport final, verificare in browser, rezolutii de ecran si demo end-to-end cu serviciile colegilor.

Pentru fiecare etapa: date de intrare confirmate, UI verificabil independent, apoi verificare cu backend-ul real. Nu portam motorul financiar si nu modificam prompt-urile din branch-ul frontend.

## Verificare locala

Este necesar Godot 4.7 compatibil si Python 3; fixture-ul HTTP foloseste numai biblioteca standard. Din `raiffquest/`:

```sh
godot --headless --path . --import
python tools/run_frontend_tests.py --godot /cale/catre/godot
node test/statement_import_web_test.cjs
godot --headless --path . res://test/test_suite.tscn
```

Testele frontend pornesc un server temporar doar pe loopback si nu apeleaza Claude, banca sau serverul de deploy. Acopera requesturile convenite, sesiunea, Unicode, query encoding, erori HTTP/JSON, concurenta, anulare, timeout, lipsa retry-ului automat si importul web. Testele de transport nu valideaza logica backend-ului sau layout-ul final.
