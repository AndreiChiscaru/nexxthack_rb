# RaiffQuest — avatar masculin: sprite-uri prototip

Decupare din planșa ilustrată cu AI, nu animație desenată cadru cu cadru.

- Fiecare fișier `walk_*_sheet.png`: 4 cadre de 192 × 224 px, orizontal (total 768 × 224 px).
- Fiecare `walk_*_00.png` ... `walk_*_03.png`: cadru individual 192 × 224 px, fundal transparent.
- `idle.png`, `phone.png`, `happy.png`, `thinking.png`, `talking.png`, `sad.png`, `surprised.png`: poziții individuale 192 × 224 px.

În Godot: AnimatedSprite2D → SpriteFrames, creați `walk_down`, `walk_up`, `walk_left`, `walk_right`; importați 4 cadre/sheet, 4 coloane × 1 rând. Testați la 4–6 FPS.

**Limitări:** unele cadre sunt similare, nu au ciclu de mers perfect și pot prezenta ușoare variații din generarea AI. Sunt potrivite pentru un prim test de integrare, nu neapărat animații finale.

Înainte de commit, documentați fișierele în `raiffquest/asset-provenance.json` ca decupări din planșa OpenAI ImageGen.
