# Raiff Quest API

Shapes follow `docs/implementation-plan.md` §4. `/api/game/*` runs on the real financial engine
(`app/sim/engine.py`, port of `finance_sim.gd`) with events from `data/events.json`. Onboarding runs the real
agent when an API key is set (see [Onboarding](#onboarding)). Products come from `data/products.json`
(see [Products & campaigns](#products--campaigns)). Advisor and business reply with fixed text, but their `tool_calls` are real tool runs
(see [Tools for agents](#tools-for-agents));
each mock in the code is marked `# TODO(real): ...`.

- Base URL: same origin as the game (`/joc`). CORS is open (`*`) for local dev.
- Swagger: `GET /docs`. Raw schema: `GET /openapi.json`.
- Sessions are in memory, so a server restart drops them. An unknown `session_id` returns **404**. Calling a `/api/game/*` route before `/api/game/start` returns **409**.
- Uploads are read into memory only and never written to disk. See [Data & privacy](#data--privacy).

| Method | Endpoint | Body / query | Response |
|---|---|---|---|
| POST | `/api/session` | none | `{session_id}` |
| POST | `/api/onboarding/message` | JSON `{session_id, text}` | `{reply, missing_fields[], done, profile?}` |
| POST | `/api/onboarding/statement` | multipart `session_id`, `file` | `{analysis, profile_fields, missing_fields[], reply}` |
| POST | `/api/game/start` | JSON `{session_id, profile?}` | `{state, events[]}` |
| GET | `/api/game/state` | `?session_id=` | `GameState` (§4.2) |
| POST | `/api/game/action` | JSON `{session_id, institution, action_id, params}` | `{state, delta, advisor_note}` |
| POST | `/api/game/advance` | JSON `{session_id}` | `{state, delta, events[]}` |
| POST | `/api/advisor/message` | JSON `{session_id, text}` | `{reply, tool_calls[]}` |
| POST | `/api/business/message` | multipart `session_id`, `text`, optional `file` | `{reply, tool_calls[]}` |
| GET | `/api/products` | `?category=` (optional) | `{products[]}` |
| GET | `/api/products/{id}` | none | `Product` (404 if unknown) |
| GET | `/api/campaigns` | none | `{campaigns[]}`, only the ones not expired |

Shared shapes:

- `ToolCall = {name, args, summary}`
- `Event` uses the §4.4 format: `{id, institution, title, text, options: [{id, label, ops}]}`
- `Product = {id, category, name, terms, conditions, best_for, cautions, as_of_date, disclaimer}`; see [Products & campaigns](#products--campaigns)
- Institutions: `home | market | education | work | business | hospital | bank`

Mock behaviour:

- **Onboarding (no API key or `MOCK_LLM=true`).** The 3rd message returns `done: true` with the Andrei profile; a statement upload uses a fixed analysis of the synthetic sample statement.

## Game loop (engine)

- **Start.** Builds the engine state from the profile in the body, else the one saved during onboarding, else Andrei.
  - `debts[]` become loans that keep the profile's real monthly payment.
  - All randomness comes from a `random.Random` seeded with `session_id`, so the same session gives the same game.
- **Advance = one month.**
  - Loan payments with interest, overdraft interest, `cash += income - living - payments - insurance`.
  - Automatic contributions, interest on savings and a return on the fund (shock of the current 3-year period).
  - Every 12 months: age +1, salary +4%, living costs +4%, car value −12%, and a stress/confidence update.
  - One `"Luna N: ..."` log line per month.
- **`delta`** (advance and action): change in `cash`, `savings`, `investments`, `debt`, `net_worth`.

How the engine maps onto `GameState` (§4.2):

| `GameState` field | Engine source |
|---|---|
| `balance.savings` | `emergency + deposit` |
| `balance.investments` | `fund` |
| `balance.debt` | `total_debt` (loans + overdraft) |
| `balance.net_worth` | `net_worth`, which also includes car, home and business value, so it isn't always cash + savings + investments − debt |
| `goal.progress` | `(savings + investments) / target_amount`, clamped to 0..1 |
| `goal.on_track` | `progress >= month / profile.goal.horizon_months` |
| `monthly.expenses.home` / `.market` / `.education` | `living`, split by the profile's starting proportions (rent + utilities + subscriptions / food + leisure + transport / tuition) |
| `monthly.expenses.health` | its share of `living` (profile `health.monthly_costs`) + `insurance_premium` |
| `monthly.income` | `salary + side_income`; side income starts as `income.other + education.scholarship` |
| `monthly.expenses.business` | `0` for now |
| `monthly.expenses.bank` | loan payments |
| `products` | catalog ids: `super_acces_plus` = emergency, `depozit_1_an` = deposit, `fonduri_smartinvest` = fund (only if > 0) |

The six expense keys always add up to what the month deducts.

### Actions (`POST /api/game/action`)

| `action_id` | `params` | Effect | 400 when |
|---|---|---|---|
| `<pending event id>` | `{option_id}` | answers the event (see [Events](#events)) | unknown `option_id`, or `institution` isn't the event's |
| `save` | `{amount}` | one-off transfer cash → savings (emergency fund) | `amount <= 0` or `> cash` |
| `invest` | `{amount}` | one-off transfer cash → investments (fund) | `amount <= 0` or `> cash` |
| `repay` | `{amount}` | early repayment: overdraft first, then highest-APR loan; any leftover returns to cash | `amount <= 0` or `> cash` |
| `set_monthly_saving` | `{amount}` | automatic monthly amount into savings; **replaces** the previous value, `0` stops it | `amount < 0` or `>` monthly income |
| `set_monthly_invest` | `{amount}` | automatic monthly amount into the fund; **replaces**, `0` stops it | `amount < 0` or `>` monthly income |

Free actions are checked first. Any other `action_id` is treated as an event id: **404** if no such event exists, **409** if it exists but isn't pending for this session.

## Events

The library lives in `data/events.json`: 22 events, 2–4 per institution. It's validated strictly when the app starts, and the server refuses to start on bad data:
- an unknown op or sub-key, or a negative `spend`
- an unknown institution or condition
- a duplicate event id, or a duplicate option id within an event
- an option without ops
- an event id equal to a free action

### Format

What the API sends is exactly §4.4:

```json
{"id": "dentist", "institution": "hospital", "title": "Urgență stomatologică", "text": "...",
 "options": [{"id": "pay_cash", "label": "Plătesc din economii", "ops": {"spend": 1200.0}},
             {"id": "installments", "label": "Plată în rate", "ops": {"loan": {"principal": 1200.0, "apr": 0.0, "months": 6}}}]}
```

The JSON file can also have two fields that are **never** sent to the client:
- `conditions`: `min_month`, `requires_debt`, `requires_no_insurance`, `goal_types[]`
- `weight` (default 1)

`ops` uses only what the engine's `apply_ops` understands:

| Op | Effect |
|---|---|
| `spend` | ≥ 0; paid from cash, then savings, then overdraft |
| `loan{name?, principal, apr, months}` | adds a loan |
| `salary_mult`, `salary_add` | salary changes; 60% of the difference also goes into living costs |
| `living_add` | changes living costs directly |
| `side_income_add` | adds side income; living costs rise by 30% of it |
| `business_value`, `car_value` | adds to the asset's value |
| `emergency_contrib`, `invest_contrib` | monthly contribution; **replaces** the current value |
| `insurance_level` (0–2) + `insurance_premium` | coverage 0 / 35% / 85% |
| `medical_cost` + optional `finance_months` | cost after insurance, paid now or in 0% installments |
| `bonus{amount, mode}` | one-off income. `mode`: `prepay` (leftover → savings), `fund`, `safe` (emergency fund up to 6 months of living costs, then deposit), `spend` (+ `spend`: the part spent; the rest goes to savings) |
| `mood{stress, conf}` | applied immediately |

One-off income always goes through `bonus`, and the option label says where the money goes (e.g. "în fondul de urgență").

### How events arrive
- **Start:** `POST /api/game/start` schedules exactly **2** events eligible in month 0 and returns them in `events`.
- **Each advance:** `POST /api/game/advance` schedules **0–2** new events and returns them in `events`. The picks are weighted, and deterministic per `session_id`.
- **One per institution:** an institution with a pending event gets no new one, so `state.institutions[].pending_events` is 0 or 1.
- **Cycles:** an event doesn't repeat until every currently eligible event of its institution has been used. A new cycle never starts with the event that ended the previous one.
- **Lifetime:** pending events never expire. They stay until answered.

### How to answer one

`POST /api/game/action` with `action_id` = event id, `institution` = the event's institution, and `params.option_id` = the chosen option. The server:
1. applies the option's ops through the engine
2. removes the event from pending
3. adds a log line, `"<title>: <option label>"`
4. returns `advisor_note`, a short Romanian note built from the option (no LLM)

| Status | When |
|---|---|
| 200 | answered |
| 400 | unknown `option_id`, or `institution` isn't the event's institution |
| 404 | no event with this id (and it isn't a free action) |
| 409 | the event exists but isn't pending (already answered, or never scheduled for this session) |

Real example (Andrei, month 1):

```json
// POST /api/game/advance → events contains
{"id": "cashback_rambursare", "institution": "bank", "title": "Cashback de la bancă",
 "text": "Ai primit 800 lei cashback din campania cardului. Ai încă un credit activ.",
 "options": [{"id": "rambursare", "label": "Folosesc cei 800 lei pentru rambursare anticipată", "ops": {"bonus": {"amount": 800.0, "mode": "prepay"}, "mood": {"stress": -2.0, "conf": 3.0}}},
             {"id": "fond_urgenta", "label": "Pun cei 800 lei în fondul de urgență", "ops": {"bonus": {"amount": 800.0, "mode": "safe"}, "mood": {"stress": 0, "conf": 2.0}}},
             {"id": "cumparaturi", "label": "Îi cheltui pe haine", "ops": {"bonus": {"amount": 800.0, "mode": "spend", "spend": 800.0}, "mood": {"stress": -2.0, "conf": 0}}}]}

// POST /api/game/action
{"session_id": "c3db...", "institution": "bank", "action_id": "cashback_rambursare", "params": {"option_id": "fond_urgenta"}}
// 200
{"state": {"...": "...", "institutions": [..., {"id": "bank", "pending_events": 0}],
           "log": [..., {"month": 1, "institution": "bank", "text": "Cashback de la bancă: Pun cei 800 lei în fondul de urgență"}]},
 "delta": {"cash": 0.0, "savings": 800.0, "investments": 0.0, "debt": 0.0, "net_worth": 800.0},
 "advisor_note": "Ai pus 800 lei deoparte, în fondul de urgență (surplusul merge în depozit)."}

// the same request again → 409
{"detail": "Evenimentul cashback_rambursare nu este în așteptare."}
```

### Future work
- **Personalized amounts:** scale event amounts (rent increases, bonuses, repair costs) and the suggested monthly contributions to the player's bank-statement profile. The Godot game does this for its first decision (`Events.personalize`); the backend library uses fixed amounts for now.

## Onboarding

**Real mode** is on when the server has `ANTHROPIC_API_KEY` and `MOCK_LLM` isn't `true`. Otherwise the endpoints use the mock behaviour. Tests force `MOCK_LLM=true` (`tests/conftest.py`).

- **`POST /api/onboarding/message`**: one turn of the onboarding agent (`app/agents/onboarding.py`) on the session's conversation. Not streamed: the response comes when the turn ends.
  - When the agent finishes, the profile is mapped and validated against §4.1. Only if it's valid does the response have `done: true` with `profile`; it's then stored where `/api/game/start` reads it.
  - If validation fails, the response has `done: false` and `missing_fields` lists the invalid paths.
- **`POST /api/onboarding/statement`**: the `/api/analyze` pipeline, in memory (`extract_text` → `analyze_statement` → `to_game_profile`).
  - The agent merges the confident fields (name, income, balance, savings, loans) into the draft profile, so it stops asking for them, and replies with what it understood: `reply`.
  - Mock: a fixed analysis of the synthetic statement in `deploy/sample_statement.py`, merged the same way, with `reply: null`.
- **`missing_fields`** uses §4.1 paths in both modes, e.g. `["age", "goal.description", "recurring.rent", "cash"]`. `occupation` is the only one with no §4.1 equivalent: the agent requires it, but it isn't kept in the profile.
- **Errors:** a failed agent or Claude call returns 502 and the turn isn't saved. The statement endpoint returns 400/413/415/422 like `/api/analyze`.

Mapping from the agent profile (`app/agents/profile.py`) to §4.1, in one place (`app/profile_mapping.py`):

| Agent | §4.1 |
|---|---|
| `home.housing` (rent **or** mortgage payment) | `recurring.rent` |
| `home.utilities`, `home.subscriptions` | `recurring.utilities`, `recurring.subscriptions` |
| `market.transport` | `recurring.transport` |
| `market.food`, `market.leisure` | `spending.food`, `spending.leisure` |
| `bank.cash`, `bank.savings`, `bank.investments` | `cash`, `savings`, `investments` |
| `bank.debts[]{name, monthly_payment, remaining?, apr?}` | `debts[]{name, monthly, remaining, apr}`; a missing `apr`/`remaining` is estimated from the loan name (mortgage / IFN / default), no debts → `[]` |
| `income.scholarship` | `education.scholarship` (counted as income in the engine) |
| `health.monthly_costs` | `health.monthly_costs` |
| `goal.type` (optional) | `goal.type` (default `"altul"`) |
| `business.interest` | `business_interest` |
| `occupation`, `business.idea` | not kept |
| statement analysis | `source{statement_uploaded, statement_score, risk_signals}` |

Same names in both: `name`, `age`, `goal.description/target_amount/horizon_months`, `income.salary/other`, `education.status/tuition_monthly`, `health.insured`, `risk_tolerance` (`scazuta|medie|ridicata`), `dependents`.

## Products & campaigns

The catalog is `data/products.json`: the public Raiffeisen offer as of 28 October 2026, the same file the consultant agent (`app/agents/consultant.py`) searches. `app/catalog.py` validates it once at startup. The server refuses to start on:
- a duplicate id or an id that isn't `snake_case`
- a missing required field
- an unknown category

### Product schema

| Field | Type | Notes |
|---|---|---|
| `id` | string | `snake_case`, unique |
| `category` | string | `credit`, `locuinta`, `economii`, `cont`, `card`, `investitii`, `pensie`, `asigurare` |
| `name` | string | commercial name |
| `terms` | string | rates, amounts, terms, as published |
| `conditions` | string | eligibility (may be empty) |
| `best_for` | string | who it suits |
| `cautions` | string | what to watch out for |
| `as_of_date` | date | **optional in the file**, defaults to `2026-10-28`; always present in the API |
| `disclaimer` | string | **optional in the file**, defaults to the standard text; always present in the API |

**Rates are not guaranteed.** Loan rates are "de la" (minimums, checked by a test for `credit`/`locuinta`) and the final cost is set by the bank. Savings rates are gross and can change. The `disclaimer` says this on every product.

Unknown extra keys in the file are ignored, so a teammate's additions don't block startup.

### Campaigns

Time-limited campaigns are in `data/campaigns.json`: the same text fields plus `start_date?`, `end_date` (required), `product_id?` (must exist in the catalog), `as_of_date` and `disclaimer`. `GET /api/campaigns` returns only campaigns whose `end_date` hasn't passed (the end date itself still counts), soonest-ending first.

The 4 old `category: "campanie"` entries stay in `products.json` for now, because the consultant searches them there. `/api/products` hides them: `?category=campanie` returns 400 pointing to `/api/campaigns`, and `/api/products/campanie_*` returns 404.

### Endpoints

| Request | Response |
|---|---|
| `GET /api/products` | every catalog product |
| `GET /api/products?category=economii` | one category; an unknown category returns **400** |
| `GET /api/products/{id}` | one product; **404** if unknown |
| `GET /api/campaigns` | active campaigns |

### Updating the catalog from the bank's PDF

```bash
python -m tools.ingest_products oferta_raiffeisen.pdf --dry-run          # print the result, write nothing
python -m tools.ingest_products oferta_raiffeisen.pdf --as-of 2026-11-15  # write data/products.from_pdf.json
```

1. **Read and extract.** The script reads the PDF with `app/extraction.py` (OCR fallback) and asks Claude for a JSON list in the catalog's shape. Structured output is used, the model is `INGEST_MODEL` (default `claude-opus-5-5`), and `ANTHROPIC_API_KEY` must be set.
2. **Validate.** It validates the list with the same `Product` model used at startup.
3. **Review file.** It writes `data/products.from_pdf.json` and prints a review report: `added`, `changed` and `missing_from_pdf` ids.
4. **Manual merge.** It **never** writes `data/products.json` and refuses `--out` pointing at it. A person reviews the file and copies over what's correct.

## Tools for agents

`app/tools.py` exposes the engine (`app/sim/`) and the catalog (`app/catalog.py`) as tools for the agents.
- **What a tool is:** a plain Python function that returns a JSON-safe dict with a short Romanian `summary`.
- **`TOOL_SCHEMAS`:** a list of `{name, description, input_schema}`, ready for Claude tool use.
- **`run_tool(name, args, session_id)`** is the only entry point. It validates the arguments and runs the tool. Unknown tool or bad arguments → `ToolError`, also logged.
- **`llm_tools(session_id)`** returns the same tools as `app/agents/llm.py` `Tool` objects, ready for `chat_turn()`.
- **Logging:** every call goes into `session.tool_log` as `{name, args, summary, duration_ms}`, the `ToolCall` shape plus the duration. Server logs get only the name, status and duration, never arguments or results.
- **Simulations:** they run on a **deep copy** of the session's engine state (and rng), so they never change the game. Random events aren't simulated.

| Tool | Arguments | Returns |
|---|---|---|
| `get_state` | — | the current `GameState` (§4.2) |
| `get_goal_progress` | — | `target_amount, saved, remaining, progress, on_track, months_elapsed, months_left, monthly_needed, monthly_contributions` |
| `simulate_decision` | `ops` (engine ops, as in events), `months` 1–120 (default 12) | `before` (now), `after` (with the decision), `baseline` (no change), `delta` = after − before, `impact_vs_no_change` = after − baseline |
| `compare_scenarios` | `scenarios: {name: ops}` (1–5), `months` | one row per scenario plus `"fără schimbări"`, and `best` (highest goal progress, then net worth) |
| `search_products` | `category?`, `query?` (accent-insensitive words in name/terms/best_for) | catalog products |
| `compare_products` | `ids[]` (1–6), `amount` (lei), `months` | loans (`credit`, `locuinta`): `monthly_payment` (engine `pmt`), `total_paid`, `total_interest`. Savings (`economii`): `gross_interest`, `tax` (10%), `net_interest`. Each row has `notes` and the product `disclaimer` |
| `create_action_plan` | — | 3–5 `steps: [{title, why, action?, product_id?}]`. Rule-based priority: overdraft → budget deficit → expensive debt (APR ≥ 15%) → emergency fund (< 3 months) → life insurance (dependents) → goal savings → investing. `action` is a ready `/api/game/action` body |

**Limits of `compare_products`:**
- **The rate is the first percentage in `terms`.** The catalog is text, so for tiered rates or several variants, the first one is used (a note says so).
- **Mortgages:** the calculation uses the initial fixed rate for the whole term (a note says the rate later follows IRCC).
- **Deposits:** simple interest over the requested months, even if the deposit has its own term.

Examples (Andrei, month 0):

```json
// run_tool("get_goal_progress", {}, sid)
{"goal_type": "avans_casa", "target_amount": 25000.0, "saved": 1200.0, "remaining": 23800.0, "progress": 0.048, "on_track": true,
 "months_elapsed": 0, "months_left": 36, "monthly_needed": 661.11, "monthly_contributions": 0.0,
 "summary": "Progres 5% (1.200 lei din 25.000 lei); mai sunt 36 luni, ai nevoie de ~661 lei/lună; pui deoparte automat 0 lei/lună."}

// run_tool("simulate_decision", {"ops": {"emergency_contrib": 300}, "months": 12}, sid)  (shortened)
{"impact_vs_no_change": {"cash": -2560.0, "savings": 2614.38, "investments": 0.0, "debt": 0.0, "net_worth": 54.38, "goal_progress": 0.1},
 "summary": "În 12 luni: patrimoniu +54 lei față de fără schimbare, datorii 0 lei, progres scop 15% (fără schimbare 5%)."}

// run_tool("compare_scenarios", {"scenarios": {"economisesc": {"emergency_contrib": 500}, "cheltui mai mult": {"living_add": 300}}, "months": 12}, sid)
{"best": "economisesc", "scenarios": [{"scenario": "fără schimbări", "...": "..."}, "..."],
 "summary": "3 scenarii pe 12 luni; cel mai bun progres spre scop: „economisesc” (16%, patrimoniu -456 lei)."}

// run_tool("search_products", {"category": "economii", "query": "depozit"}, sid)
{"products": ["..."], "summary": "4 produse (economii) pentru „depozit”: Depozit Fresh Money, Flexidepozit, Depozit la termen până la 1 an, Depozit la 24 de luni"}

// run_tool("compare_products", {"ids": ["credit_nevoi", "fresh_money"], "amount": 10000, "months": 12}, sid)  (shortened)
{"products": [
   {"id": "credit_nevoi", "rate": 0.0595, "kind": "loan", "monthly_payment": 860.43, "total_paid": 10325.21, "total_interest": 325.21,
    "notes": ["dobândă „de la”; costul final îl stabilește banca"], "disclaimer": "..."},
   {"id": "fresh_money", "rate": 0.062, "kind": "deposit", "gross_interest": 620.0, "tax": 62.0, "net_interest": 558.0, "notes": ["..."], "disclaimer": "..."}],
 "summary": "10.000 lei pe 12 luni. Credit de nevoi personale: 860 lei/lună, dobândă totală 325 lei; Depozit Fresh Money: dobândă netă 558 lei"}

// run_tool("create_action_plan", {}, sid)
{"steps": [
   {"title": "Echilibrează bugetul lunar", "why": "Cheltuielile și ratele depășesc venitul cu 120 lei/lună; diferența se ia din economii sau din descoperit.", "action": null, "product_id": null},
   {"title": "Construiește fondul de urgență", "why": "Acoperă 0,3 luni de cheltuieli; ținta e 3-6 luni.",
    "action": {"action_id": "set_monthly_saving", "params": {"amount": 100.0}}, "product_id": "super_acces_plus"},
   {"title": "Caută un venit suplimentar", "why": "...", "action": null, "product_id": null}],
 "summary": "3 pași: Echilibrează bugetul lunar; Construiește fondul de urgență; Caută un venit suplimentar"}
```

### Status: consultant agent

`app/agents/consultant.py` **can't take these tools yet**:
- **Fixed tool list:** `user_turn(session_id, convo, text)` builds its own list with `_tools(session_id)`.
- **Its own copy of the game:** the profile, statement and game come from the SQLite store, in the `app/demo/engine.py` format.
- **Prompt:** it names its own tools (`get_financial_state`, `simulate_event_options`, `simulate_plan`).

Until that changes, `/api/advisor/message` returns a fixed reply, but its `tool_calls` are real `run_tool` calls: `get_goal_progress`, `search_products`, then `compare_products` (if the message mentions a loan) or `create_action_plan`.

Proposed change for the agents owner, backwards compatible, so the demo keeps working:

```python
# app/agents/consultant.py
def user_turn(session_id: str, convo: dict, text: str, tools: list[Tool] | None = None,
              profile: dict | None = None, statement: dict | None = None):
    profile = profile if profile is not None else store.load(session_id, "profile", {}).get("data", {})
    statement = statement if statement is not None else (store.load(session_id, "statement") or {}).get("analysis")
    ...
    yield from chat_turn(convo, system, tools if tools is not None else _tools(session_id))
```

The backend would then call:
```python
consultant.user_turn(session.id, convo, text, tools=llm_tools(session.id),
                     profile=session.profile.model_dump(), statement=session.statement)
```

The `SYSTEM` prompt should then name the tools generically, or accept the tool list as a parameter, instead of hard-coding the demo's three names.

## Data & privacy

- **Uploaded files** are read into memory and never written to disk. Neither the file nor its extracted text is kept in the session; the session keeps only `{score, risk_signals}` from the analysis.
- **Session data** (draft profile, conversation, §4.1 profile, game) lives in server memory only and is lost on restart.
- **`data/demo.sqlite3`**: in real mode the agents write the shared "user file" there (`app/agents/memory.py`, keyed by `session_id`), which also holds the `/api/demo/*` sessions. These short notes can include facts from the conversation and the statement summary (stability score, risk level, up to 3 risk signals). The file is in `.gitignore` (`data/*.sqlite3`) and its contents are never logged.
- **Use only synthetic statements** (like `deploy/sample_statement.py`) for the demo. Real bank statements must not be uploaded: their text is sent to the Claude API, and facts from them can end up in `data/demo.sqlite3`.

## Errors

Every error uses FastAPI's default body, `{"detail": "<message>"}`. Validation errors (422) return `detail` as a list.

| Status | When | Example `detail` |
|---|---|---|
| **404** | `session_id` doesn't exist (any route that takes it, including `/api/onboarding/*`, `/api/advisor/*` and `/api/business/*`) | `"Sesiune inexistentă."` |
| **404** | `POST /api/game/action` with an `action_id` that's neither a free action nor a known event | `"Eveniment sau acțiune necunoscută: teleport."` |
| **409** | `GET /api/game/state`, `POST /api/game/action` or `POST /api/game/advance` before `POST /api/game/start` | `"Jocul nu a pornit încă (POST /api/game/start)."` |
| **409** | answering an event that isn't pending (already answered, or never scheduled) | `"Evenimentul dentist nu este în așteptare."` |
| 400 | invalid `option_id`, event answered with the wrong `institution`, `amount` out of range (see the actions table), empty uploaded file | `"option_id invalid; alege din ['pay_cash', 'installments']."` |
| 413 | upload over 25 MB | `"Fișierul depășește 25 MB."` |
| 422 | body or query fails validation (e.g. `institution` not one of the 7 ids, missing `session_id`) | `[{"type": "literal_error", "loc": ["body", "institution"], ...}]` |

Example:
```http
GET /api/game/state?session_id=nope
→ 404 {"detail": "Sesiune inexistentă."}

POST /api/game/advance  {"session_id": "<new session, not started>"}
→ 409 {"detail": "Jocul nu a pornit încă (POST /api/game/start)."}
```

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
// response (not done yet; missing_fields are §4.1 paths)
{"reply": "Notat! Cât dai pe chirie și pe utilități?",
 "missing_fields": ["recurring.rent", "recurring.utilities", "spending.food", "cash", "savings", "risk_tolerance"],
 "done": false, "profile": null}
```
When done: `"done": true, "missing_fields": [], "profile": { ...§4.1... }`, and `/api/game/start` uses that profile.

### POST /api/onboarding/statement
```bash
curl -F session_id=c3db... -F file=@extras.pdf http://localhost:8000/api/onboarding/statement
```
```json
// response (synthetic sample statement; analysis shortened)
{"analysis": {"titular": "ION POPESCU", "venit_lunar_estimat": 6850.0, "sold_final": 5309.81, "scor_stabilitate_financiara": 58, "...": "..."},
 "profile_fields": {"name": "Ion Popescu", "income": {"salary": 6850.0}, "cash": 5309.81, "savings": 0.0,
                    "debts": [{"name": "Rata credit ipotecar BT", "monthly": 2310.0, "remaining": 309828.76, "apr": 0.065},
                              {"name": "Credius IFN rata", "monthly": 650.0, "remaining": 11107.58, "apr": 0.35}],
                    "source": {"statement_uploaded": true, "statement_score": 58, "risk_signals": ["Rată la IFN", "Pariuri online"]}},
 "missing_fields": ["age", "occupation", "goal.description", "goal.target_amount", "goal.horizon_months",
                    "recurring.rent", "recurring.utilities", "spending.food", "risk_tolerance"],
 "reply": "Am citit extrasul: venit de ~6.850 lei, două rate (ipotecar și un IFN). Cât dai pe utilități și pe mâncare?"}
```
`reply` is `null` in mock mode.

### POST /api/game/start
```json
// request
{"session_id": "c3db..."}
// response
{"state": {"session_id": "c3db...", "month": 0, "age": 22,
           "goal": {"type": "avans_casa", "target_amount": 25000, "progress": 0.048, "on_track": true},
           "balance": {"cash": 4000, "savings": 1200, "investments": 0, "debt": 11000, "net_worth": -5800},
           "monthly": {"income": 4300, "expenses": {"home": 1970, "market": 1800, "education": 0, "health": 0, "business": 0, "bank": 650}},
           "wellbeing": {"stress": 35, "confidence": 45},
           "institutions": [{"id": "home", "pending_events": 0}, "...", {"id": "hospital", "pending_events": 1}, {"id": "bank", "pending_events": 1}],
           "products": [{"id": "super_acces_plus", "balance": 1200}],
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
// request: one-off transfer / monthly contribution
{"session_id": "c3db...", "institution": "bank", "action_id": "save", "params": {"amount": 500}}
{"session_id": "c3db...", "institution": "bank", "action_id": "set_monthly_saving", "params": {"amount": 300}}
// response (event example)
{"state": { "...": "GameState" },
 "delta": {"cash": 0, "savings": 0, "investments": 0, "debt": 1200, "net_worth": -1200},
 "advisor_note": "Ai luat un credit de 1.200 lei la 0,0% pe 6 luni: rată de 200 lei/lună."}
```
Errors: see the actions table and [Events](#events). An `institution` outside the 7 ids returns 422.

### POST /api/game/advance
```json
// request
{"session_id": "c3db..."}
// response
{"state": {"month": 1, "age": 22,
           "balance": {"cash": 3880, "savings": 1203, "investments": 0, "debt": 10478.33, "net_worth": -5395.33},
           "log": [..., {"month": 1, "institution": "bank", "text": "Luna 1: venit 4.300 lei, cheltuieli 4.420 lei, sold 3.880 lei"}],
           "...": "..."},
 "delta": {"cash": -120, "savings": 3, "investments": 0, "debt": -521.67, "net_worth": 404.67},
 "events": [{"id": "promovare", "institution": "work", "title": "Ofertă de promovare", "...": "..."}]}
```

### POST /api/advisor/message
```json
// request
{"session_id": "c3db...", "text": "Merită să iau un credit?"}
// response
{"reply": "Îți recomand să pui întâi deoparte un fond de urgență de 3 luni, apoi să accelerezi plata creditului.",
 "tool_calls": [
   {"name": "get_goal_progress", "args": {}, "summary": "Progres 5% (1.200 lei din 25.000 lei); mai sunt 36 luni, ai nevoie de ~661 lei/lună; pui deoparte automat 0 lei/lună."},
   {"name": "search_products", "args": {"category": "economii"}, "summary": "6 produse (economii): Cont de economii Super Acces Plus, Plătești și economisești, Depozit Fresh Money, Flexidepozit, Depozit la termen până la 1 an, Depozit la 24 de luni"},
   {"name": "compare_products", "args": {"ids": ["credit_nevoi", "refinantare"], "amount": 10000, "months": 36}, "summary": "10.000 lei pe 36 luni. Credit de nevoi personale: 304 lei/lună, dobândă totală 944 lei; Refinanțare fără ipotecă: 304 lei/lună, dobândă totală 944 lei"}]}
```
The reply is still fixed; the tool calls are real (see [Tools for agents](#tools-for-agents)).

### POST /api/business/message
```bash
curl -F session_id=c3db... -F text="Vreau o cafenea" -F file=@plan.pdf http://localhost:8000/api/business/message
```
```json
{"reply": "Ideea pare viabilă dacă poți acoperi 6 luni de costuri fixe. Hai să vedem un plan de finanțare.",
 "tool_calls": [
   {"name": "read_document", "args": {"filename": "plan.pdf"}, "summary": "Document primit (9 octeți), analiză mock."},
   {"name": "search_products", "args": {"category": "credit"}, "summary": "4 produse (credit): Credit de nevoi personale, Refinanțare fără ipotecă, Refinanțare cu ipotecă – Flexicredit Integral, Overdraft"},
   {"name": "compare_products", "args": {"ids": ["credit_nevoi"], "amount": 20000, "months": 36}, "summary": "20.000 lei pe 36 luni. Credit de nevoi personale: 608 lei/lună, dobândă totală 1.887 lei"}]}
```

### GET /api/products?category=economii
```json
{"products": [
  {"id": "super_acces_plus", "category": "economii", "name": "Cont de economii Super Acces Plus",
   "terms": "Dobândă brută în lei 2% / 2,5% / 3% pe tranșe; 0,5% la euro; 0,3% la dolar. Acces oricând, fără sumă minimă efectivă. Dobânda se capitalizează lunar.",
   "conditions": "Dobânda brută este impozitată cu 10%. Depozitele sunt acoperite de Fondul de Garantare a Depozitelor în Sistemul Bancar.",
   "best_for": "fondul de urgență: banii rămân disponibili oricând",
   "cautions": "Nu e produsul cu dobânda cea mai mare. Alege-l pentru siguranță și acces, nu pentru randament.",
   "as_of_date": "2026-10-28",
   "disclaimer": "Informații publice Raiffeisen Bank, cu titlu educativ. Dobânzile la credite sunt „de la” (minime) și nu sunt garantate: ..."},
  "... platesti_si_economisesti, fresh_money, flexidepozit, depozit_1_an, depozit_24_luni"]}
```
`GET /api/products/super_acces_plus` returns that object on its own; `GET /api/products/nu_exista` → 404 `{"detail": "Produs necunoscut: nu_exista."}`.

### GET /api/campaigns
```json
{"campaigns": [
  {"id": "campanie_credit", "name": "Bonus pentru carduri de credit Standard sau eMAG",
   "terms": "Bonus de 150 lei după primii 1.000 lei cheltuiți. Campania se termină la 2 noiembrie 2026.",
   "conditions": "Doar pentru anumite carduri Standard sau eMAG.", "best_for": "...", "cautions": "...",
   "start_date": null, "end_date": "2026-11-02", "product_id": "carduri_credit",
   "as_of_date": "2026-10-28", "disclaimer": "..."},
  "... campanie_premium (2026-12-31), campanie_debit (2027-01-31)"]}
```
