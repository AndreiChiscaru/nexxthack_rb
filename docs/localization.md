# Game languages

The active journey supports Romanian (default) and English. The selector is at the bottom right. Preferences are saved in `user://game_locale.cfg`; web also uses `localStorage["raiffquest.locale"]` so the loading screen follows the saved choice. `RAIFF_LOCALE=ro|en` gives deterministic native test startup.

`raiffquest/autoload/game_locale.gd` localizes presentation nodes while retaining their source text. Text inputs and player-authored chat are never translated. Agent-generated history remains in its original language. Formatting templates are matched most-specific first and numeric placeholders only match numbers. This service belongs to the active RaiffQuest journey; the older starter-template `I18n` is separate.

Edit reviewed translations in `data/localization/en.json`, then run `python tools/sync_game_localization.py`. The copied `raiffquest/localization/game_en.json` is included by the existing web export filter. `--check` and `tests/test_localization.py` detect drift and missing mission/product entries.

All JSON requests and native/browser multipart uploads send `Accept-Language`. The backend negotiates ro/en into a request-scoped ContextVar, propagated into worker threads. The shared LLM loop appends an instruction for user-facing prose and UI button names. IDs, enums, currencies, profiles and engine snapshots stay canonical; API catalog/event text is translated by the client, not rewritten in the stored data. There is no automatic currency conversion.

Checks: `pytest tests/test_localization.py -q`; run `res://test/localization_test.tscn` with `raiffquest/tools/run_backend_integration.py`. The test changes languages in one session, verifies formatted strings, bank amount persistence and unchanged state, then restores Romanian. The UI test server uses mock agents; validate English agent prose separately against an explicitly live backend with synthetic data.
