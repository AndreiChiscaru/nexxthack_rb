# Romanian / English localization plan

Goal: localize the active Godot journey and its API content without changing financial rules or player data.
Architecture: a dedicated game locale service (the pre-existing I18n belongs to the starter template), reviewed text catalogs, request-scoped API locale and agent language instructions. Default Romanian, persisted explicit choice, selector at the bottom. No currency conversion or translation of IDs/user input. Earlier free-form conversation remains as originally written; future agent replies use the selected language.

- [x] Integrate origin/main preserving local restart and greeting.
- [x] Add catalogs and locale service; render-only translation, preserve source text, support formatted strings.
- [x] Add bottom selector, persist choice, re-render without resetting session or typed amounts.
- [x] Send Accept-Language on JSON and native/web multipart requests; request-scoped language for all agents.
- [x] Translate static missions, banking products, errors and financial summary labels; leave IDs, enums, values untouched.
- [x] Test RO/EN round trips, no profile mutation, concurrent locale isolation, upload language headers, English UI layout and fresh sessions.
- [x] Restart live backend and app, verify real English agent response.
