# Frontend: contracte si etape de integrare

Branch initial: `frontend/integration-foundation`.
Referinta comuna confirmata: `implementation-plan.md`, sectiunea 4.
Detaliile HTTP implementate de backend: [`api.md`](api.md).

## Mod de lucru convenit

Pentru fiecare punct din lista de task-uri:

1. `git fetch origin --prune`, verificarea commit-urilor noi si integrarea schimbarilor relevante din `main` si din branch-urile colegilor. Se pastreaza istoricul si se rezolva conflictele in branch-ul frontend.
2. Implementare limitata la punctul curent si verificarea contractelor cu backend-ul.
3. Testele relevante, apoi pornirea aplicatiei pentru verificare manuala.
4. Utilizatoarea verifica aplicatia. Orice observatie se rezolva si se retesteaza.
5. Dupa confirmarea verificarii, o ultima sincronizare, retestare daca au aparut modificari, commit si push pe branch-ul frontend. Fara force-push sau modificari directe pe `main`.

Integrarea curenta include `main` (`6af45b6`), `backend/gabi` (`0cb9bc0`, API mock, motor portat si teste), `feature/ui-ux` (`d062c15`, ghid vizual actualizat) si `agenti` (`a504d30`, demo agenti si corectii de conversatie). Conflictul din `app/main.py` este rezolvat pastrand ambele familii de rute.

**Limita actuala intre backend si agenti:** API-ul comun din `api.md` foloseste inca mock-uri. Branch-ul agentilor adauga separat `/api/demo/...`, un alt format de profil si alte sesiuni. Codul coexista, dar nu este inca legat in acelasi flux. Frontend-ul ramane pe contractul comun confirmat; conectarea agentilor cere un adaptor in backend sau o modificare coordonata a contractului. Nu schimbam implicit endpoint-urile clientului.

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

Implementarea backend integrata confirma `session_id` in JSON pentru POST si in query pentru GET; profilul de start este in cheia `profile`. Frontend-ul cere un profil confirmat pentru start, chiar daca serverul permite si pornirea fara profil explicit.

`start` si `advance` returneaza `{state, events}`; `action` returneaza `{state, delta, advisor_note}`; `GET state` returneaza starea direct. `products` returneaza `{products}`. Clientul pastreaza aceste raspunsuri nemodificate. `/api/onboarding/statement` si `/api/business/message` au acum contracte multipart documentate in `api.md`; conectarea lor in frontend ramane o etapa separata.

Endpoint-urile noi exista in backend-ul integrat, dar agentii si simularea folosesc inca date mock. Testele de integrare verifica compatibilitatea clientului Godot cu aceasta implementare, nu existenta agentilor LLM finali. Un 404 este afisat drept eroare, nu drept succes demonstrativ. `session_id` identifica o sesiune; transportul sau nu reprezinta un mecanism de autentificare.

Pentru recuperarea completa dupa timeout mai trebuie ca backend-ul sa expuna si lista evenimentelor active: `GET state` ofera doar numarul lor pe institutie, iar `advance.events` contine doar evenimentele noi. Pana atunci, nu putem reconstrui numai din `GET state` optiunile unui eveniment al carui raspuns s-a pierdut.

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

Pentru integrarea cu aplicatia FastAPI a echipei, instaleaza dependintele din `requirements.txt` intr-un mediu virtual, apoi ruleaza din `raiffquest/`:

```sh
python tools/run_backend_integration.py --godot /cale/catre/godot
```

Acest test porneste automat backend-ul pe un port local liber si il opreste la final. Foloseste clientul Godot pentru sesiune, onboarding, profil confirmat, stare, eveniment, economisire, luna urmatoare, consultant, produse si erori 400/404/409/422. Din radacina repository-ului, `python -m pytest -q` ruleaza si testele backend-ului.

### Rezultatul verificarii integrarii curente

- 308 verificari Godot ale jocului: PASS.
- 59 verificari ale transportului frontend: PASS.
- 26 verificari Godot - FastAPI (inclusiv coexistenta rutelor demo): PASS.
- 65 teste backend si motor financiar: PASS.
- Testele JavaScript ale importului web: PASS.
- `python deploy/demo_selftest.py`: toate verificarile offline ale agentilor au trecut.
- Aplicatia desktop porneste; `/api/health`, `/docs` si `/demo` raspund local.

Apelurile LLM reale si exportul web complet nu au fost verificate in acest checkpoint. Verificarea utilizatoarei si push-ul sunt urmatorul pas al fluxului convenit.

### Integrare backend — 28 octombrie 2026

Integrate `backend/gabi` la `311e64c` (include `main` la `035a542`) si grafica `feature/ui-ux` la `99ab40c`.

- `/api/onboarding/message` foloseste acum agentul real cand exista cheia configurata si `MOCK_LLM` nu este `true`. Contractul frontend ramane compatibil.
- `/api/onboarding/statement` analizeaza documentul si poate returna suplimentar `reply`; profilul agentului este convertit la contractul comun.
- Evenimentele sunt planificate din biblioteca noua; o actiune inexistenta returneaza 404. Testul clientului verifica acest comportament.
- Runnerul de integrare seteaza explicit `MOCK_LLM=true` pentru a evita apelurile externe chiar daca exista credentiale in mediu.
- Verificari dupa merge: 148 teste backend, 26 verificari Godot–FastAPI si 59 verificari transport frontend, toate trecute. Un avertisment de depreciere pytest/anyio.
- Apelurile reale Claude nu au fost testate. Onboardingul Godot nu este implementat in acest checkpoint; macheta vizuala V2 este un prototip separat, cu dialog demonstrativ si avatar provizoriu, aflat in evaluare.