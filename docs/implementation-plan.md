# Raiff Quest — plan de implementare (24h, 4 roluri)

Tema: **Raiffeisen Bank — Scaling & Growth: cum pot agenții AI să ajute clienții să navigheze alegerile și serviciile financiare.**

Ideea: un joc 2D în care utilizatorul își definește un scop financiar, agentul de onboarding îi construiește profilul (conversație + extras de cont opțional), apoi joacă luni din viața lui pe o hartă cu 7 instituții, ghidat de un consultant AI care recomandă servicii Raiffeisen.

---

## 1. Ce avem deja (punct de plecare)

| Componentă | Stare | Unde |
|---|---|---|
| Analiză extras de cont (PDF text → OCR Tesseract → Claude → JSON) | funcțional, pe server | `app/extraction.py`, `app/analyzer.py` |
| Conversie analiză → profil de joc | funcțional | `app/game_profile.py` |
| Joc Godot 4.7 (hartă, 5 clădiri, 10 decizii, panou financiar, consilier local, raport final) | funcțional, 308 teste trec | `raiffquest/` |
| Motor financiar determinist (credite, dobânzi, economii, investiții, stres/încredere) | în GDScript | `raiffquest/scripts/raiff/finance_sim.gd` |
| Deploy (FastAPI + nginx + systemd + tunel HTTPS) | funcțional | `deploy/` |

Nu pornim de la zero: refolosim motorul financiar, UI kit-ul, harta și pipeline-ul de extras.

---

## 2. Probleme pe care le vedem în ideea actuală

1. **Scope prea mare pentru 24h.** 7 instituții + 3 agenți + catalog de produse + extrase + contabilitate. Dacă le facem pe toate la fel de adânc, nu termină niciuna. **Propunere:** 3 instituții „adânci” (Acasă, Muncă, Bancă) + consultantul; celelalte 4 „subțiri” (2-3 evenimente predefinite fiecare). Afacerea primește agentul ei doar dacă bucla de bază merge până la ora 14.
2. **Lipsește modelul de timp.** Fără un ceas, „bilanțul” nu are sens. **Propunere:** o tură = 1 lună; butonul „Luna următoare” aplică veniturile și cheltuielile recurente din toate instituțiile și declanșează 0-2 evenimente. Orizontul vine din scop (ex. avans casă în 36 de luni); demo-ul arată 6-12 luni.
3. **Cine calculează cifrele?** Dacă agenții LLM calculează, vor inventa. **Regula de bază:** motorul de simulare este singura sursă de adevăr pentru bani; agenții doar *apelează unelte* (`simulate_decision`, `get_state`) și explică rezultatul.
4. **„Harta se generează” — dar instituțiile sunt fixe.** Nu generați hărți procedural. Harta e fixă (7 clădiri mereu în același loc); ce se generează din profil sunt **cifrele, evenimentele și obiectivul**. Asta e și mai ușor de demonstrat.
5. **Agentul de onboarding poate pune întrebări la nesfârșit.** Trebuie o listă fixă de câmpuri obligatorii (vezi §4.1); agentul întreabă doar ce lipsește, maxim ~8 întrebări, apoi apelează `submit_profile` cu JSON validat. Utilizatorul fără scop primește un chestionar scurt cu variante (nu text liber).
6. **Agentul de afaceri „se ocupă de contabilitate”** = risc legal și scope uriaș. **Propunere:** ghid antreprenorial + checklist (PFA vs. SRL, CAEN, ONRC, impozit micro), estimare costuri de pornire și cash-flow lunar care intră în simulare. Fără „contabilitate reală”, cu disclaimer clar.
7. **Date personale (GDPR).** Extrasele conțin nume, IBAN, tranzacții. Nu le salvăm pe disc, mascăm IBAN/nume înainte de LLM, afișăm consimțământ la upload. **Demo-ul se face pe extrase sintetice**, nu pe extrase reale.
8. **„Sfat financiar”.** Raiffeisen va fi atent la asta: toate recomandările sunt educaționale, explicabile (arătăm apelurile de unelte și cifrele) și marcate ca simulare.
9. **Catalogul de produse lipsește încă.** Nu așteptați PDF-ul: definiți acum schema JSON a unui produs și puneți 8-10 produse mock; când vine PDF-ul, doar se înlocuiesc datele. Produsele **nu** se pun în prompt, agentul le caută cu o unealtă.
10. **Latență LLM.** Analiza unui extras durează 20-40 s. Chat-ul trebuie să fie rapid (model mic pentru conversație, model mare doar pentru analiză), cu indicator de încărcare și răspunsuri în streaming dacă rămâne timp.
11. **Godot pe web cere HTTPS.** Tunelul actual are URL temporar; fixați un domeniu + certificat în primele ore, nu în ultima.
12. **Verificați regulile hackathon-ului** (din documentele primite): ce modele/provideri sunt permiși (ex. Featherless), cerințe de livrare (repo public? video? README de rulare?), criterii de jurizare. Planul trebuie ajustat după ele.

## 3. Recomandări pentru pitch („Scaling & Growth”)

- Arătați **valoarea pentru bancă**, nu doar pentru utilizator: onboarding conversațional → profil complet → recomandare de produs *contextuală* (la momentul potrivit în viața simulată) → lead calificat. Metrici: % utilizatori care își ating scopul în simulare, produse recomandate/acceptate, timp până la profil complet.
- **Explicabilitate vizibilă**: panoul consultantului arată fiecare apel de unealtă (asta există deja în joc și e un punct forte la jurizare).
- **Un „golden path” de 3 minute** repetat de mai multe ori: scop „avans pentru apartament” → extras încărcat → 3-4 luni jucate → criză la spital → consultantul recomandă fond de urgență + asigurare → raport final cu progres spre scop.
- **Mod offline de rezervă**: răspunsuri înregistrate pentru golden path, dacă API-ul LLM cade în timpul prezentării.

---

## 4. Contracte comune (se îngheață la ora 2)

Toți patru lucrează în paralel doar dacă aceste formate sunt fixate devreme. Orice schimbare ulterioară se anunță pe canal și se actualizează aici.

### 4.1 Profil (ieșirea agentului de onboarding)

```json
{
  "name": "Andrei",
  "age": 22,
  "goal": {"type": "avans_casa", "description": "Avans de 15% pentru un apartament în Cluj", "target_amount": 25000, "horizon_months": 36},
  "income": {"salary": 4300, "other": 0},
  "recurring": {"rent": 1500, "utilities": 350, "subscriptions": 120, "transport": 200},
  "spending": {"food": 1200, "leisure": 400},
  "savings": 1200, "investments": 0, "cash": 4000,
  "debts": [{"name": "Credit nevoi personale", "monthly": 650, "remaining": 11000, "apr": 0.14}],
  "education": {"status": "student", "scholarship": 0, "tuition_monthly": 0},
  "health": {"insured": false, "monthly_costs": 0},
  "business_interest": false,
  "risk_tolerance": "medie",
  "dependents": 0,
  "source": {"statement_uploaded": true, "statement_score": 58, "risk_signals": ["Rată la IFN"]}
}
```

`health.monthly_costs` = costuri medicale recurente (lei/lună), afișate la `monthly.expenses.health`. `education.scholarship` se adună la venit în motor (împreună cu `income.other`).

Câmpuri obligatorii pentru `submit_profile`: `goal`, `age`, `income.salary`, cheltuieli recurente totale, `savings`, `debts` (poate fi listă goală), `risk_tolerance`.

### 4.2 Starea jocului (sursa de adevăr, ținută de backend)

```json
{
  "session_id": "abc123", "month": 3, "age": 22,
  "goal": {"type": "avans_casa", "target_amount": 25000, "progress": 0.18, "on_track": false},
  "balance": {"cash": 5310, "savings": 2400, "investments": 0, "debt": 10200, "net_worth": -2490},
  "monthly": {"income": 4300, "expenses": {"home": 1970, "market": 1800, "education": 0, "health": 0, "business": 0, "bank": 650}},
  "wellbeing": {"stress": 45, "confidence": 52},
  "institutions": [{"id": "home", "pending_events": 1}, {"id": "market", "pending_events": 0}],
  "products": [{"id": "cont_economii", "balance": 2400}],
  "log": [{"month": 2, "institution": "hospital", "text": "Urgență stomatologică: -1.200 lei"}]
}
```

ID-uri fixe de instituții: `home`, `market`, `education`, `work`, `business`, `hospital`, `bank`.

### 4.3 API (FastAPI, același domeniu cu jocul)

| Metodă | Endpoint | Rol |
|---|---|---|
| POST | `/api/session` | creează sesiune → `session_id` |
| POST | `/api/onboarding/message` | `{session_id, text}` → `{reply, missing_fields, done, profile?}` |
| POST | `/api/onboarding/statement` | upload extras → analiză + câmpuri de profil completate |
| POST | `/api/game/start` | profil → stare inițială + evenimente programate |
| GET | `/api/game/state` | starea curentă |
| POST | `/api/game/action` | `{institution, action_id, params}` → stare nouă + delta + notă consultant |
| POST | `/api/game/advance` | trece o lună → stare + evenimente noi |
| POST | `/api/advisor/message` | chat consultant → `{reply, tool_calls[]}` |
| POST | `/api/business/message` | chat agent afaceri (+ upload document) |
| GET | `/api/products?category=` | catalog produse Raiffeisen |

`tool_calls[]` are forma `{"name", "args", "summary"}`, exact ce afișează deja panoul consilierului din joc.

### 4.4 Evenimente

```json
{"id": "dentist", "institution": "hospital", "title": "Urgență stomatologică",
 "text": "...", "options": [{"id": "pay_cash", "label": "Plătesc din economii", "ops": {"spend": 1200}},
                            {"id": "installments", "label": "Plată în rate", "ops": {"loan": {"principal": 1200, "apr": 0, "months": 6}}}]}
```

Formatul `ops` este cel din `finance_sim.gd` (`spend`, `loan`, `salary_mult`, `living_add`, `emergency_contrib`, `invest_contrib`, `insurance_level`...), ca să refolosim motorul.

---

## 5. Decizie de arhitectură: unde rulează simularea

**Recomandare: mutăm motorul financiar în backend (Python)**, iar Godot doar afișează starea.

- Pro: agenții (consultant, afaceri) au nevoie să ruleze `simulate_decision` ca unealtă, deci trebuie să aibă acces direct la motor; o singură sursă de adevăr; testabil cu pytest.
- Contra: trebuie portat `finance_sim.gd` (~430 linii) în Python — cu AI asistat, ~1-2 ore; testele existente din `test_suite.gd` devin specificația.
- Alternativă dacă vă grăbiți: motorul rămâne în Godot, iar backend-ul primește doar snapshot-uri de stare. Agenții nu mai pot simula „ce-ar fi dacă”, deci pierdem cel mai bun argument de tool use. Nu o recomandăm.

```
Godot (web)  ──HTTPS──>  FastAPI
  hartă, HUD,             ├─ sim/        motor financiar (port din finance_sim.gd)
  chat, carduri           ├─ agents/     onboarding · consultant · afaceri (+ unelte)
                          ├─ ingest/     extras: text PDF → OCR → LLM (există)
                          ├─ catalog/    produse Raiffeisen (JSON, apoi din PDF)
                          └─ sessions    stare per sesiune (SQLite sau memorie)
```

---

## 6. Calendar (24h)

| Ora | Checkpoint | Toată echipa |
|---|---|---|
| 0-2 | **Kickoff** | citit regulamentul, înghețat contractele (§4), împărțit task-uri pe GitHub Issues |
| 2-8 | **Bucla minimă** | onboarding text → profil → hartă cu 7 clădiri → „Luna următoare” schimbă bilanțul |
| 8 | **Checkpoint 1** | demo intern cap-coadă, chiar urât |
| 8-14 | **Conținut + agenți** | evenimente pe instituții, consultant cu unelte, extras integrat, produse mock |
| 14 | **Checkpoint 2** | golden path jucabil; decidem dacă intră agentul de afaceri complet |
| 14-19 | **Adâncime + polish** | agent afaceri, catalog real (dacă a venit PDF-ul), grafică finală, raport final |
| 19 | **Feature freeze** | doar bugfix-uri de aici |
| 19-22 | **Demo** | repetiții, înregistrare video de rezervă, mod offline |
| 22-24 | **Livrare** | README, diagramă, pitch, submit |

Integrare obligatorie la fiecare 3-4 ore pe `main`: jocul rulează mereu cu ultima versiune a backend-ului.

---

## 7. Plan pe roluri

### 7.1 Grafică (UI/UX + asset-uri + materiale de pitch)

**Răspunde de:** cum arată jocul și pitch-ul. Lucrează cu frontend-ul pe aceeași paletă (`ui_kit.gd`: galben Raiffeisen `#ffe600`, fundal închis).

| Ore | Task | Livrabil |
|---|---|---|
| 0-2 | Moodboard + stil unic (pixel art top-down sau flat vector — alegeți unul și nu-l mai schimbați); paletă, font (Figtree e deja în proiect) | `docs/style-guide.md` cu 1 imagine de referință |
| 2-6 | Wireframe-uri: ecran onboarding (chat + upload), hartă cu 7 clădiri, HUD dreapta-sus (bilanț + progres scop), iconiță consultant stânga-sus, card de eveniment, raport final | imagini în `docs/wireframes/` |
| 2-8 | Sprite-uri pentru cele 7 clădiri (Acasă, Piață, Educație, Muncă, Afacere, Spital, Bancă), personaj (4 direcții), iconiță consultant | PNG în `raiffquest/assets/raiff/` |
| 8-12 | Iconițe pentru categorii (facturi, mâncare, transport, bursă, salariu, sănătate, economii, investiții, credit), ilustrații mici pentru evenimente | PNG 64-128 px |
| 12-16 | Fundal hartă/tileset, animații simple (puls pe clădirea cu eveniment, monede la venit) | asset-uri finale |
| 16-22 | Slide-uri pitch, diagrama de arhitectură, capturi de ecran, montaj video demo | `docs/pitch.pdf`, video |

**Atenție:** fiecare asset generat cu AI se trece în `asset-provenance.json` (licență/sursă). Nu folosiți logo-ul Raiffeisen fără acord; „inspirat de” e OK.

### 7.2 Frontend (Godot)

**Răspunde de:** tot ce vede și atinge utilizatorul. Refolosește `game_root.gd`, `world_map.gd`, `dashboard_panel.gd`, `advisor_panel.gd`, `event_card.gd`, `ui_kit.gd`.

| Ore | Task | Livrabil |
|---|---|---|
| 0-2 | Client API comun (`api_client.gd`: `HTTPRequest` + JSON, URL configurabil, timeout, eroare afișabilă), cu răspunsuri mock până e gata backend-ul | apeluri spre mock-uri locale |
| 2-6 | **Ecran onboarding**: chat (bule, input, „se gândește…”), buton upload extras (există `statement_import.gd`), variante rapide pentru cine nu are scop | profil primit și afișat |
| 2-8 | **Harta cu 7 instituții** (extinde `world_map.gd` de la 5 la 7 locații), marcaj „!” pe clădirile cu evenimente | jucătorul intră în orice clădire |
| 6-10 | **HUD dreapta-sus**: venituri/cheltuieli lunare, sold, economii, datorii, patrimoniu net, bară de progres spre scop; **iconiță consultant stânga-sus** care deschide panoul de chat | HUD legat de `/api/game/state` |
| 8-12 | **Panou instituție**: listă cheltuieli/venituri ale instituției + acțiunile disponibile (ex. Bancă: deschide cont economii, depozit, investiție, credit; Muncă: cere mărire, curs) | acțiuni → `/api/game/action` |
| 10-14 | Buton „Luna următoare” + card de eveniment cu opțiuni + rezultat (delta pe bilanț) | bucla lunară completă |
| 14-18 | Chat consultant cu afișare de `tool_calls`; chat agent afaceri în clădirea Afacere | ambii agenți folosibili |
| 18-22 | Raport final (refolosește `report_screen.gd`), polish, sunete, export web, test pe Chrome/Firefox | build web pe server |

**Atenție:** exportul web cere HTTPS; testați exportul la fiecare checkpoint, nu doar în editor.

### 7.3 Agenți (LLM, prompt-uri, unelte)

**Răspunde de:** inteligența jocului. Toate cifrele vin din unelte, niciodată din model.

| Ore | Task | Livrabil |
|---|---|---|
| 0-2 | Alegere model(e) conform regulamentului (Claude e deja integrat; dacă se cere Featherless, adaptor OpenAI-compatibil); un singur wrapper `llm.chat(messages, tools)` | `app/agents/llm.py` |
| 2-6 | **Agent onboarding**: listă de câmpuri obligatorii (§4.1), întreabă doar ce lipsește, max ~8 întrebări, încheie cu unealta `submit_profile` (validată cu Pydantic); integrează analiza de extras (există) ca sursă care completează câmpuri | conversație → profil valid |
| 2-8 | Chestionar pentru cei fără scop (5-6 întrebări cu variante) → agentul propune 2-3 scopuri, utilizatorul alege | scop ales |
| 6-12 | **Consultant financiar**: unelte `get_state`, `get_goal_progress`, `simulate_decision` (pe copia stării), `search_products`, `compare_products`, `create_action_plan`; ton prietenos, explicativ, în română; mereu leagă sfatul de scop | sfat cu tool calls vizibile |
| 10-14 | Generator de scenariu: din profil alege și parametrizează evenimentele (șabloane din §4.4); LLM-ul scrie doar textul narativ, cifrele vin din șablon + profil | listă de evenimente per sesiune |
| 14-18 | **Agent afaceri**: întrebări despre idee → PFA vs. SRL, pași (ONRC, CAEN, bancă, contabil), costuri de pornire + cash-flow lunar estimat care intră în simulare ca eveniment/credit; analiză de document încărcat (plan de afaceri) cu același pipeline de extragere | checklist + impact în simulare |
| 18-22 | Guardrails (refuză sfaturi reale de investiții, disclaimer), mascare date personale înainte de LLM, răspunsuri înregistrate pentru golden path (mod offline), 10-15 conversații de test | evals simple în `tests/agents/` |

**Atenție:** prompt-urile și catalogul de produse stau în fișiere separate (`app/agents/prompts/*.md`, `data/products.json`), nu în cod.

### 7.4 Backend (FastAPI, simulare, date, deploy)

**Răspunde de:** sursa de adevăr și infrastructură. Pornește de la `app/` existent.

| Ore | Task | Livrabil |
|---|---|---|
| 0-2 | Scheletul endpoint-urilor din §4.3 cu răspunsuri mock (ca frontend-ul să poată lucra imediat); sesiuni în memorie/SQLite | `/docs` Swagger cu toate rutele |
| 2-6 | **Port motor financiar** `finance_sim.gd` → `app/sim/engine.py` (aceleași formule, aceleași `ops`); portează testele din `test_suite.gd` în pytest | `pytest` verde |
| 6-10 | Model lunar: tura de o lună agregă venituri/cheltuieli pe cele 7 instituții, aplică dobânzi, contribuții automate, progres spre scop | `/api/game/advance` real |
| 8-12 | Biblioteca de evenimente (JSON, 2-4 pe instituție), planificare evenimente pe luni, `/api/game/action` | evenimente reale în joc |
| 10-14 | Catalog produse: schemă + 8-10 produse mock; ingest din PDF-ul băncii când vine (extragere text → LLM → JSON validat, verificat manual) | `data/products.json`, `/api/products` |
| 12-16 | Unelte expuse agenților ca funcții Python (aceleași funcții din motor), logare a fiecărui apel de unealtă | agenții folosesc motorul |
| 14-20 | Deploy stabil: domeniu + HTTPS (Let's Encrypt), build web Godot automat (`deploy/build_game.sh` există), rate limit simplu, fără salvare pe disc a extraselor | URL stabil pentru demo |
| 20-24 | README de rulare locală (o comandă), diagramă, curățenie repo | reproductibil |

**Atenție:** nu salvați extrase sau profile reale în repo sau în loguri. Cheia API stă doar în `.env` pe server.

---

## 8. Mod de lucru

- **Branch-uri scurte:** `grafica/*`, `frontend/*`, `agents/*`, `backend/*`; PR în `main` cu review rapid de la încă o persoană.
- **GitHub Projects:** Backlog → În lucru → Review → Gata; un issue per funcționalitate.
- **Fișiere „proprietate”**: fiecare rol are folderele lui (grafică: `raiffquest/assets/`, `docs/`; frontend: `raiffquest/scripts/`, `raiffquest/scenes/`; agenți: `app/agents/`; backend: `app/` restul, `deploy/`) ca să evitați conflicte de merge.
- **Contractele din §4 sunt sfinte**: dacă le schimbați, actualizați fișierul și anunțați.
- **Folosiți AI pentru cod**, dar cereți-i mereu să respecte contractele din acest fișier (dați-i link la el).

## 9. Ce tăiem dacă rămânem în urmă (în ordinea asta)

1. Agentul de afaceri devine un checklist static + 2 evenimente.
2. Educația și Spitalul rămân cu 2 evenimente predefinite fiecare.
3. Catalogul real din PDF → rămân produsele mock.
4. Chestionarul „fără scop” → 3 scopuri predefinite din care alegi.
5. Animații și sunete.

**Nu tăiem niciodată:** onboarding → profil → hartă → lună → bilanț → sfat consultant cu unelte → raport. Aceasta e bucla pe care o jurizează.
