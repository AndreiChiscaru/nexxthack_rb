# Raiff Quest API (mock skeleton)

All endpoints below return **mock** data so the Godot frontend can integrate now. Shapes follow
`docs/implementation-plan.md` §4. Each mock in the code is marked `# TODO(real): ...`.

- Base URL: same origin as the game (`/joc`). CORS is open (`*`) for local dev.
- Swagger: `GET /docs`. Raw schema: `GET /openapi.json`.
- Sessions are in memory, so a server restart drops them. An unknown `session_id` returns **404**. Calling a `/api/game/*` route before `/api/game/start` returns **409**.
- Uploads are read into memory only and never written to disk.

| Method | Endpoint | Body / query | Response |
|---|---|---|---|
| POST | `/api/session` | none | `{session_id}` |
| POST | `/api/onboarding/message` | JSON `{session_id, text}` | `{reply, missing_fields[], done, profile?}` |
| POST | `/api/onboarding/statement` | multipart `session_id`, `file` | `{analysis, profile_fields, missing_fields[]}` |
| POST | `/api/game/start` | JSON `{session_id, profile?}` | `{state, events[]}` |
| GET | `/api/game/state` | `?session_id=` | `GameState` (§4.2) |
| POST | `/api/game/action` | JSON `{session_id, institution, action_id, params}` | `{state, delta, advisor_note}` |
| POST | `/api/game/advance` | JSON `{session_id}` | `{state, events[]}` |
| POST | `/api/advisor/message` | JSON `{session_id, text}` | `{reply, tool_calls[]}` |
| POST | `/api/business/message` | multipart `session_id`, `text`, optional `file` | `{reply, tool_calls[]}` |
| GET | `/api/products` | `?category=` (optional) | `{products[]}` |

Shared shapes:

- `ToolCall = {name, args, summary}`
- `Event` uses the §4.4 format: `{id, institution, title, text, options: [{id, label, ops}]}`
- `Product = {id, category, name, apr, min_months, max_months, note, mock}`, the same fields as `catalog.gd`
- Institutions: `home | market | education | work | business | hospital | bank`

Mock behaviour:

- **Onboarding.** The 3rd message returns `done: true` with the Andrei profile.
- **Game start.** Without a `profile` in the body, it uses the profile saved during onboarding, or Andrei if there is none.
- **Advance.** `month + 1`, `cash += income - all expenses`, `debt -= bank` expense, plus 0–2 new events (deterministic per session and month).
- **Action.** Either answer a pending event with `action_id = <event id>` and `params.option_id`, or use a free action: `save`, `invest` or `repay` with `params.amount`.

---

## Examples

### POST /api/session
```json
// response
{"session_id": "c3dbe4516f584770a96ccffbb30c0d9a"}
```

### POST /api/onboarding/message
```json
// request
{"session_id": "c3db...", "text": "Vreau să strâng avans pentru o casă"}
// response (1st message)
{"reply": "Super. Cât câștigi pe lună și cât dai pe chirie, utilități și alte cheltuieli fixe?",
 "missing_fields": ["savings", "debts", "risk_tolerance"], "done": false, "profile": null}
```
On the 3rd message: `"done": true, "missing_fields": [], "profile": { ...§4.1 Andrei... }`.

### POST /api/onboarding/statement
```bash
curl -F session_id=c3db... -F file=@extras.pdf http://localhost:8000/api/onboarding/statement
```
```json
{"analysis": {"mock": true, "statement_score": 58, "risk_signals": ["Rată la IFN"]},
 "profile_fields": {"income": {"salary": 4300, "other": 0},
                    "recurring": {"rent": 1500, "utilities": 350, "subscriptions": 120, "transport": 200},
                    "debts": [{"name": "Credit nevoi personale", "monthly": 650, "remaining": 11000, "apr": 0.14}],
                    "source": {"statement_uploaded": true, "statement_score": 58, "risk_signals": ["Rată la IFN"]}},
 "missing_fields": ["goal", "age", "savings", "risk_tolerance"]}
```

### POST /api/game/start
```json
// request
{"session_id": "c3db..."}
// response
{"state": {"session_id": "c3db...", "month": 0, "age": 22,
           "goal": {"type": "avans_casa", "target_amount": 25000, "progress": 0.048, "on_track": true},
           "balance": {"cash": 4000, "savings": 1200, "investments": 0, "debt": 11000, "net_worth": -5800},
           "monthly": {"income": 4300, "expenses": {"home": 1970, "market": 1800, "education": 0, "health": 0, "business": 0, "bank": 650}},
           "wellbeing": {"stress": 40, "confidence": 50},
           "institutions": [{"id": "home", "pending_events": 0}, "...", {"id": "hospital", "pending_events": 1}, {"id": "bank", "pending_events": 1}],
           "products": [{"id": "cont_economii", "balance": 1200}],
           "log": [{"month": 0, "institution": "home", "text": "Andrei începe aventura."}]},
 "events": [{"id": "dentist", "institution": "hospital", "title": "Urgență stomatologică", "text": "...",
             "options": [{"id": "pay_cash", "label": "Plătesc din economii", "ops": {"spend": 1200}},
                         {"id": "installments", "label": "Plată în rate", "ops": {"loan": {"principal": 1200, "apr": 0, "months": 6}}}]},
            {"id": "economisire_automata", "institution": "bank", "...": "..."}]}
```

### GET /api/game/state?session_id=c3db...
Returns the same `GameState` object as `state` above.

### POST /api/game/action
```json
// request: answer a pending event
{"session_id": "c3db...", "institution": "hospital", "action_id": "dentist", "params": {"option_id": "installments"}}
// request: free action
{"session_id": "c3db...", "institution": "bank", "action_id": "save", "params": {"amount": 500}}
// response (event example)
{"state": { "...": "GameState" },
 "delta": {"debt": 1200, "net_worth": -1200},
 "advisor_note": "Atenție: datoria a crescut, verifică dobânda."}
```
Errors: unknown `action_id` or `option_id` returns 400. An invalid `institution` returns 422.

### POST /api/game/advance
```json
// request
{"session_id": "c3db..."}
// response
{"state": {"month": 1, "balance": {"cash": 3880, "...": "..."}, "...": "..."},
 "events": [{"id": "promovare", "institution": "work", "title": "Ofertă de promovare", "...": "..."}]}
```

### POST /api/advisor/message
```json
// request
{"session_id": "c3db...", "text": "Merită să iau un credit?"}
// response
{"reply": "Îți recomand să pui întâi deoparte un fond de urgență de 3 luni, apoi să accelerezi plata creditului.",
 "tool_calls": [
   {"name": "get_player_profile", "args": {}, "summary": "Luna 0, cash 4000 lei, stres 40/100."},
   {"name": "search_products", "args": {"category": "savings"}, "summary": "2 produse demo: Cont de Economii Automat Demo, Depozit Flexibil Demo."},
   {"name": "simulate_decision", "args": {"option": "A", "months": 36}, "summary": "Varianta A: dobândă totală plătită 2.310 lei, rată 650 lei/lună."}]}
```

### POST /api/business/message
```bash
curl -F session_id=c3db... -F text="Vreau o cafenea" -F file=@plan.pdf http://localhost:8000/api/business/message
```
```json
{"reply": "Ideea pare viabilă dacă poți acoperi 6 luni de costuri fixe. Hai să vedem un plan de finanțare.",
 "tool_calls": [
   {"name": "read_document", "args": {"filename": "plan.pdf"}, "summary": "Document primit (9 octeți), analiză mock."},
   {"name": "search_products", "args": {"category": "credit_business"}, "summary": "1 produs demo: Credit Micro-Business Demo."},
   {"name": "simulate_decision", "args": {"principal": 20000, "apr": 0.099, "months": 36}, "summary": "Rată estimată 644 lei/lună, dobândă totală 3.190 lei."}]}
```

### GET /api/products?category=savings
```json
{"products": [
  {"id": "cont_economii", "category": "savings", "name": "Cont de Economii Automat Demo", "apr": 0.03,
   "min_months": 0, "max_months": 0, "note": "Dobândă fictivă 3%/an, transfer automat lunar, bani disponibili oricând.", "mock": true},
  {"id": "depozit", "category": "savings", "name": "Depozit Flexibil Demo", "apr": 0.045,
   "min_months": 0, "max_months": 0, "note": "Dobândă fictivă 4,5%/an, pentru sume care nu sunt necesare imediat.", "mock": true}]}
```
Categories: `credit_auto`, `credit_personal`, `credit_business`, `savings`, `investment`, `insurance`.
