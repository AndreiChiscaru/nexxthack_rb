# Integrated RaiffQuest frontend design

Approved basis: user-approved onboarding-game-v9.html and map-v6.html prototypes, followed by explicit instruction to integrate all changes and test before push (2026-10-28).

Godot 4 is the production frontend. Use the team's real consultant textures and expressions. Welcome at upper left, then a large scrolling chat with per-speaker bubbles. Preserve the full in-memory conversation from onboarding into map advisor. No persistence of private chat on disk by default; server sessions are volatile. Optional statement upload uses the session-scoped endpoint, native chooser and file drop. Validate 25 MB before sending.

Map: seven spaced institutions using existing PNGs, uniform grass, detailed prototype terrain, connected paths, zoom and pan. No TU tag; avatar parks beside labels. Buildings lift on hover only. Server state drives HUD, events, monthly advance and bank actions. No local financial simulator. Profile is visibly reviewed before starting. API failures remain visible and do not silently fall back to a fake game.

Approach: native Godot screens and separate session controller, reusing existing JSON API client and prototype SVG terrain. A browser-only implementation was rejected because the shared game is Godot. Rebuilding financial logic in frontend was rejected because backend is authoritative.

Connect actual consultant LLM to app.tools read-only simulation/catalog tools; preserve offline test mode and identify real/mock mode in health/UI. No push until user tests. No live user financial documents used in testing.
