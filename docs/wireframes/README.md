# Wireframe — hartă principală RaiffQuest

- `map-wireframe.svg`: schemă conceptuală editabilă, 1440×900.
- Include 7 instituții, consultant AI stânga sus, HUD dreapta sus și personaj central.
- Nu este un fundal final și nu trebuie importat ca hartă unică în Godot.
- `world_map.gd` din arhiva inițială folosește `MAP_SIZE = Vector2(800, 560)` și 5 clădiri; implementarea noului layout necesită acord cu colegul responsabil de Godot.
- Culorile urmează `raiffquest/scripts/frontend/journey_theme.gd`.
- Elementele vor fi implementate ca noduri/asset-uri separate, astfel încât să fie interactive.
