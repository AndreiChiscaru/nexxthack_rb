# Raiff Quest — nexxthack (Raiffeisen Bank: Scaling & Growth)

Joc educațional 2D în care un utilizator își definește un scop financiar, un agent AI îi construiește profilul (conversație + extras de cont opțional), iar un consultant AI îl ghidează prin luni din viața lui simulată, recomandând servicii bancare.

Planul de implementare pe roluri: [`docs/implementation-plan.md`](docs/implementation-plan.md).

## Structură

| Folder | Conținut |
|---|---|
| `app/` | Backend FastAPI: extragere text din extras (PDF → OCR Tesseract), analiză cu Claude, conversie în profil de joc |
| `static/` | Pagina web de analiză a extrasului |
| `raiffquest/` | Jocul Godot 4.7 (export web servit la `/joc/`) |
| `deploy/` | Scripturi pentru serverul Ubuntu: instalare, nginx, systemd, build Godot, tunel HTTPS |
| `docs/` | Plan, contracte API, materiale de pitch |

## Rulare locală (backend)

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt   # Windows: .venv\Scripts\pip
cp .env.example .env                        # completează ANTHROPIC_API_KEY
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Pentru OCR e nevoie de Tesseract cu limba română (`apt install tesseract-ocr tesseract-ocr-ron`).

## Joc

Deschide `raiffquest/project.godot` în Godot 4.7. Teste: `godot --headless --path raiffquest res://test/test_suite.tscn`.

## Date personale

Nu adăugați în repo extrase de cont reale, chei API sau fișiere `.env`. Pentru demo folosiți extrase sintetice (`deploy/sample_statement.py`).
