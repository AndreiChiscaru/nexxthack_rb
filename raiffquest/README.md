# Raiff Quest — MVP

Joc educațional financiar 2D în limba română. Ghidează personajul fictiv Ana Ionescu de la 22 la 52 de ani prin zece decizii. Toate produsele, dobânzile și datele sunt fictive și sunt folosite exclusiv în joc.

## Rulare

1. Instalează Godot 4.7 sau o versiune compatibilă.
2. Deschide `project.godot` în Godot și apasă **F6/F5** sau rulează: `godot --path .`

## Controale

- **WASD / săgeți**: mișcare pe hartă
- **E / Enter / Spațiu**: interacțiune / confirmare
- **1–4**: alege una dintre opțiunile unei decizii
- **Esc**: meniu / închidere

## Teste

Rulează testele jocului cu:

```sh
godot --headless --path . res://test/test_suite.tscn
```

Codul principal se află în `scripts/raiff/`; conținutul deciziilor și simularea financiară sunt în `events.gd` și `finance_sim.gd`. Fonturile, imaginile și licențele asociate sunt incluse în `assets/`.

## Pornire din extrasul de cont

Pe ecranul de titlu, „Încarcă extrasul tău de cont” trimite fișierul la serverul de analiză (`POST /api/analyze`: extragere text PDF, OCR Tesseract ca rezervă, analiză Claude). Răspunsul conține `game_profile` (venit, cheltuieli, sold, economii, credite existente, stres/încredere), iar `Sim.new_state(seed, profile)` pornește simularea de la situația reală; prima decizie (bugetul) e adaptată cu `Events.personalize()`.

- Web: fișierul se trimite la `/api/analyze` pe același domeniu (jocul e servit la `/joc/`). Exportul web cere HTTPS.
- Desktop/editor: serverul implicit este `http://158.180.47.250:8787`; se poate schimba cu variabila de mediu `RAIFF_API`.

**Notă:** „Consilier AI” este o simulare locală explicabilă; nu apelează un model AI și nu se conectează la bănci sau la internet. Jocul nu oferă recomandări financiare reale.
