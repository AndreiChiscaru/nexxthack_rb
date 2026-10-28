# RaiffQuest — Style Guide v1.0

## Direcție vizuală
Flat vector, vedere 2D izometrică, oraș financiar gamificat. Stil modern, prietenos, coerent și ușor de citit. Fără logo-ul oficial Raiffeisen fără aprobare.

## Paletă (din `raiffquest/scripts/ui_kit.gd`)
- Fundal: `#14171C`
- Panou: `#1F2329`
- Panou secundar: `#2A2F37`
- Bordură: `#3A404A`
- Accent galben: `#FFE600`
- Text: `#F4F4EF`
- Text secundar: `#A9AFB8`
- Pozitiv: `#62D98F`
- Negativ: `#FF6F61`
- Informativ: `#7BD3F7`

## Tipografie
Figtree — font deja disponibil în proiect. Titlurile sunt bold; informațiile secundare au contrast suficient față de fundal.

## Hartă
Șapte clădiri mereu prezente: Acasă, Piață, Educație, Muncă, Afacere, Spital, Bancă. Fiecare are siluetă distinctă și etichetă lizibilă. Personajul este lângă centrul hărții. Consultant AI în stânga sus; bilanț și progresul scopului în dreapta sus.

## UI
Carduri întunecate, colțuri rotunjite (aprox. 8–10 px), contur subtil; galbenul rezervat indicatorilor importanți și acțiunilor principale. Stările pozitive/negative folosesc atât culoare, cât și icon/text, nu doar culoare.

## Asset-uri
Clădiri: PNG transparent individual, exportate la rezoluție suficientă (preferabil minimum 256–512 px pe latura mare, conform dimensiunii afișate). Iconițe: PNG transparent de 64–128 px sau SVG ca sursă editabilă înainte de export. Evitați să încorporați etichetele în imagini; randarea textului se face în Godot.

## Integrare și trasabilitate
Asset-urile livrate se păstrează în `raiffquest/assets/raiff/`. Pentru fiecare asset AI completați `raiffquest/asset-provenance.json` cu proveniența și informațiile disponibile despre drepturile de utilizare. Verificați schema existentă înainte de editare. Nu folosiți sigla oficială Raiffeisen fără permisiune.

## Referință
Machetă vizuală flat vector generată în conversație; este o referință conceptuală, nu un tileset sau un set de sprite-uri gata de folosit.
