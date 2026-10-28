# Integrated frontend implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development for independent units and verification-before-completion before reporting results.

**Goal:** Run the approved onboarding and map in Godot against the current FastAPI backend, with the real consultant artwork.
**Architecture:** Native Control screens consume one session controller and GameApi transport; map provides navigation signals only. Backend owns all money and event state.
**Tech Stack:** Godot 4.7 / GDScript; FastAPI / Python; existing Claude agent tool loop.
**Spec:** docs/superpowers/specs/2026-10-28-integrated-frontend.md

## Global constraints
- Work in existing frontend/integration-foundation checkout as requested; preserve teammates' files.
- No push before user verification. No production replacement with HTML mockup.
- Maintain /api contracts; serialize frontend mutations; never auto-retry transactions.
- New UI uses Figtree, #FEE600, #b9c98b and provided consultant sprites.

## Review focus
- Failed requests must leave controls usable and chat intact; timed-out mutations must reconcile state.
- Onboarding final profile must be confirmed, not discarded or replaced by demo data.
- Full transcript must survive switching between map and advisor.
- File uploads require a session, size/type validation and no raw statement persistence.
- All seven buildings must stay reachable; hover must not permanently offset a selected building.

## Task 1: Backend agent bridge
Files: app/api/advisor.py, app/sessions.py, app/main.py, tests/test_advisor_live.py.
Consumes: app.tools.llm_tools(session_id), existing llm.run_agent and Session profile/state.
Produces: same ChatResponse with actual agent reply, session history and tool_calls; health agent_mode.
- [ ] Write tests for real agent invocation, contextual follow-up, isolated session history and failure rollback; run RED.
- [ ] Implement bridge without changing demo engine or tool semantics; run targeted tests and suite.

## Task 2: Map navigation
Files: raiffquest/scripts/frontend/city_map.gd, raiffquest/assets/raiff/city_terrain.svg, navigation test.
Consumes: authoritative institutions event counts. Produces: institution_selected(id), setup/update methods.
- [ ] Test paths to all 7 institutions and destination offsets; implement native map, pan/zoom, hover-only lift.
- [ ] Import actual artwork; extract approved terrain; test headless and visually.

## Task 3: Session, chat and main screen
Files: raiffquest/scripts/frontend/session_controller.gd, journey_screen.gd, journey_chat.gd, statement_upload.gd; new main scene; integration tests.
Consumes: existing GameApi request_finished(id,response), Task 2 navigation, Task 1 responses.
Produces: welcome -> conversational onboarding -> profile review -> map; shared transcript; real HUD and actions.
- [ ] Test successful and failed onboarding/state transitions with local backend, upload scope and chat preservation.
- [ ] Implement controller, upload, chat and screens, wire project main scene. Use 240-second agent timeout.
- [ ] Test bank action, event decision, month advance, advisor, HTTP errors; preserve controls on failure.

## Task 4: Integration review and launch
- [ ] Run backend tests, client transport tests, Godot/backend tests and headless import.
- [ ] Independent review and fix important issues; manually inspect native UI with new consultant.
- [ ] Start local backend and native app for user testing, document mode and limits; commit locally, no push.
