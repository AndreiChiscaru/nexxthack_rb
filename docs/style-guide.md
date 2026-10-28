# RaiffQuest — Style Guide v1.1

> Prototip de hackathon, inspirat de identitatea vizuală Raiffeisen. Acest document este ghidul de design al jocului, **nu** un manual oficial al băncii.

## 1. Direcția vizuală

**Flat vector izometric (2.5D)**: oraș financiar gamificat, cu forme geometrice simplificate, siluete recognoscibile și interfață clară. Clădirile sunt obiecte separate, nu parte integrată într-un singur fundal. Harta rămâne ușor de explorat, iar elementele financiare sunt lizibile pe laptop și desktop.

Inspirație de brand: utilizarea consecventă a galbenului, a contrastului cu neutrele și a accentelor diagonale/direcționale. Nu reproducem marca figurativă Raiffeisen sau logo-urile oficiale fără autorizarea explicită a folosirii lor în cadrul hackathonului.

## 2. Paleta cromatică

### 2.1. Culori oficiale — din `Colour-Palette-2026-10.zip` → `RBI - Palette Breakdown.pdf`

| Rol | Denumire din material | HEX |
| --- | --- | --- |
| Identitate vizuală / CTA | Primary Yellow | `#FEE600` |
| Iluminări delicate | Yellow 1 | `#FFF0A6` |
| Evidențiere caldă | Yellow 2 | `#FFD403` |
| Umbre calde / detalii | Yellow 3 | `#F9BB30` |
| Text închis / contururi | Off Black | `#2B2D33` |
| Suprafață neutră deschisă | Warm Grey | `#F1EDE6` |
| Suprafață neutră deschisă | Warm Grey 50% | `#F8F6F2` |
| Text sau suprafață albă | White | `#FFFFFF` |
| Natură / indicatori prietenoși | Green Midtone | `#67D0AB` |
| Avertismente / evenimente | Coral Midtone | `#FF8B6B` |
| Tehnologie / consultant AI | Purple Midtone | `#6A4CAD` |

Paleta pentru **ilustrații și infografice** din aceeași arhivă conține tonuri suplimentare (de exemplu albastru și turcoaz). Folosiți-le pentru apă, cer, obiecte și varietate, fără a concura cu galbenul principal.

### 2.2. Culori implementate momentan în Godot — `raiffquest/scripts/raiff/ui_kit.gd`

| Token în cod | HEX existent | Utilizare curentă |
| --- | --- | --- |
| `BG` | `#14171C` | Fundal joc/UI |
| `PANEL` | `#1F2329` | Panouri |
| `PANEL_2` | `#2A2F37` | Panouri secundare |
| `BORDER` | `#3A404A` | Borduri |
| `YELLOW` | `#FFE600` | Butoane/accent |
| `TEXT` | `#F4F4EF` | Text |
| `MUTED` | `#A9AFB8` | Text secundar |
| `GOOD` | `#62D98F` | Indicator pozitiv |
| `BAD` | `#FF6F61` | Indicator negativ |
| `INFO` | `#7BD3F7` | Indicator informativ |

**Important — diferență de păstrat vizibilă:** galbenul oficial din paleta trimisă este `#FEE600`, iar proiectul Godot folosește în prezent `#FFE600`. Nu le considerați identice. Recomandare pentru echipă: trecerea la `#FEE600` pentru noul design, **după confirmarea cu frontend-ul**, fiindcă schimbarea tokenului `YELLOW` afectează toate ecranele existente. Până atunci, asset-urile noi se pot proiecta în `#FEE600`, fără modificarea codului.

## 3. Tipografie

- În ghidul oficial Raiffeisen, fontul de brand este **Amalia**; utilizarea lui depinde de acces și licență.
- În prototipul Godot, păstrăm **Figtree**, deja integrat, ca alegere tehnică a proiectului, nu ca reprezentare a tipografiei oficiale.
- Text normal și butoane: clar și scurt; etichete de clădire randate separat în Godot (nu incluse în PNG).

## 4. Harta principală

Toate cele **7 instituții** sunt vizibile: **Acasă, Piață, Educație, Muncă, Afacere, Spital, Bancă**. Fiecare clădire are o siluetă distinctă și o zonă de interacțiune clară. Drumurile pot fi simplificate pentru un ecran comun.

- **Stânga sus:** butonul persistent al consultantului AI.
- **Dreapta sus:** HUD cu bilanț, venituri, cheltuieli, economii și progresul obiectivului.
- **Zona centrală:** personaj și trasee între instituții.
- **Evenimente:** marcaj deasupra clădirii relevante (pictogramă + text/indicator; nu exclusiv culoare).

Wireframe aprobat: `docs/wireframes/map-wireframe.*`. Dimensiunile lui reprezintă **compoziția conceptuală**, nu o obligație de rezoluție în Godot; frontend-ul adaptează afișarea la viewport.

## 5. Designul clădirilor

**Regulă comună:** perspectivă izometrică consecventă, muchii clare, 2–3 tonuri principale per obiect, umbră discretă, fără text sau logo integrat în sprite.

| Instituție | Reper vizual | Accente propuse |
| --- | --- | --- |
| Acasă | Casă cu acoperiș și grădină | gri cald + galben |
| Piață | Tarabe/coș/alimente | coral + galben |
| Educație | Facultate cu coloane/carte | crem + galben |
| Muncă | Birou modern | neutre + turcoaz |
| Afacere | Hub antreprenorial, grafic de creștere | verde + galben |
| Spital | Corp medical și cruce medicală generică | alb + coral |
| Bancă | Clădire cu intrare recognoscibilă | galben + off-black; fără logo neautorizat |

## 6. UI și feedback vizual

- Carduri întunecate, colțuri rotunjite (aprox. 8–10 px), contrast bun cu textul.
- Butoane primare: galben + text închis; butoane secundare: panou închis + bordură.
- Progres: bară galbenă și procent numeric.
- Câștig/pierdere: icon + sumă + etichetă, pe lângă culoare.
- Motive diagonale subtile, fără imitarea logo-ului proprietar.
- Consultant AI: icon original creat pentru joc; posibil accent violet secundar pentru diferențiere.

## 7. Formatul asset-urilor și integrare

- **Clădiri:** PNG individual cu transparență, preferabil master 512 × 512 px și versiuni de afișare adaptate Godot; păstrați și sursa editabilă dacă există.
- **Iconițe:** 64–128 px, PNG transparent; sursă SVG când este posibil.
- **Hartă:** separați fundalul/tileset-ul de clădiri, avatar, marcaje și HUD.
- **Locație în repository:** `raiffquest/assets/raiff/`.
- **Trasabilitate:** pentru asset-urile generate cu AI, actualizați `raiffquest/asset-provenance.json` conform structurii existente, incluzând sursa și informațiile despre drepturile de utilizare.

## 8. Materiale de referință și permisiuni

- `Home.pdf` — *Brand Guidelines Summary*, în special paginile 2 (diagonale), 4–5 (logo), 6–8 (culori) și 9 (Amalia).
- `Colour-Palette-2026-10.zip` — *RBI - Palette Breakdown.pdf*, *RBI_Data and Illustration palette.pdf*.
- `Retail Bank.zip`, `Digital Bank.zip`, `International.zip` — **variante de logo pentru referință**, nu asset-uri aprobate automat pentru distribuire.

**Regulă de utilizare:** solicităm confirmarea organizatorilor dacă putem folosi marca oficială în demo, capturi și pitch. Până atunci, utilizăm numele proiectului „RaiffQuest”, ilustrații originale și o formulare de tip „prototip pentru provocarea Raiffeisen”, fără a sugera un produs bancar oficial.
