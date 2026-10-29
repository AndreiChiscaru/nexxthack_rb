# Rulare

Jocul public este http://158.180.47.250:8787/demo. Adresa duce la exportul Godot de la `/joc/`. `/demo-vechi` duce tot acolo.

## Local

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Pe Windows, pip și uvicorn sunt în `.venv\Scripts\`. În `.env` se completează `ANTHROPIC_API_KEY`. Fișierul nu se commite.

Pentru OCR pe PDF-uri scanate trebuie Tesseract cu limba română (`tesseract-ocr` și `tesseract-ocr-ron`).

`http://127.0.0.1:8000/` redirecționează la `/joc/` doar dacă există exportul din `game/`. Fără export, jocul se deschide din editor: `raiffquest/project.godot` în Godot 4.7.

Testele folosite și la build-ul de pe server:

```sh
godot --headless --path raiffquest res://test/journey_boot_test.tscn
godot --headless --path raiffquest res://test/city_map_test.tscn
godot --headless --path raiffquest res://test/stat_hud_test.tscn
```

Extrasele reale și cheile nu intră în git. Pentru demo sunt extrase sintetice în `static/samples/` și `deploy/sample_statement.py`.

## Server

Aplicația stă în `/opt/extras`, pe `ubuntu@158.180.47.250`. systemd pornește un singur worker:

```text
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Sesiunile sunt în memoria procesului. Un al doilea worker, sau un restart, face sesiunile vechi invalide. După deploy, în browser se dă Ctrl+F5 și se apasă **Începe jocul**.

`.env` de pe server rămâne pe server. Nu se copiază `.env`-ul local peste el. `deploy/deploy.ps1` face asta dacă fișierul există în checkout, deci nu se rulează dintr-un folder care conține `.env`.

Deploy din ultima variantă de pe `main`, fără să atingă `.env`:

1. `git fetch origin main` și se ia un checkout curat al lui `origin/main`, fără `.env`.
2. Se copiază pe server `app`, `static`, `data`, `deploy`, `requirements.txt` și `.env.example`. Nu și `.env`.
3. Pe server, înainte de scripturi: `sed -i 's/\r$//' /opt/extras/deploy/*.sh /opt/extras/deploy/*.service /opt/extras/deploy/*.conf`
4. `bash /opt/extras/deploy/setup_server.sh` instalează dependențele, reîncarcă nginx și repornește serviciul. Dacă `.env` lipsește, scriptul copiază `.env.example`; dacă există, îl lasă.
5. `rm -rf /opt/extras/raiffquest`, apoi se copiază sursa Godot din checkout.
6. `bash /opt/extras/deploy/build_game.sh` rulează testele, exportă web-ul în `/opt/extras/game` și repornește serviciul.

Verificare:

```sh
curl -sI http://158.180.47.250:8787/demo
curl -s http://158.180.47.250:8787/api/health
```

`/demo` trebuie să răspundă `308` către `http://158.180.47.250:8787/joc/`. Health trebuie să fie `status: ok`.

nginx lasă gzip oprit pe `/api/` și pe `/joc/`: clientul web Godot nu decomprimă răspunsurile. `build_game.sh` peticește AudioWorklet, pentru că pagina e servită pe HTTP, nu pe un context securizat.

Push-ul către GitHub se face din WSL, unde e cheia `~/.ssh/id_ed25519`. SSH-ul către server, din PowerShell, folosește `C:\Users\Legion\.ssh\oracle_extras.key`.
