# Texture Projection v42 — correction profonde des faux grabs 2D

## Diagnostic

Le problème n'était pas seulement un rayon de capture trop grand. Texture Projection avait deux chemins de picking :

1. le picking natif Creator API, basé sur `ctx.viewport.world_to_screen`, en coordonnées Qt ;
2. un picker manuel utilisé pour décider si un clic devait être gardé par l'outil ou laissé à la caméra.

Le picker manuel utilisait `owner._world_to_display` directement. Cette fonction retourne des coordonnées VTK, avec l'origine Y en bas de la fenêtre. Les événements souris Qt utilisent l'origine Y en haut. Résultat : un handle visible à `y = H - y_vtk` pouvait être capturé à `y = y_vtk`, donc à sa position miroir verticale. Avec une caméra de côté, ce faux positif apparaît souvent comme un grab quand la souris est largement sous le point affiché.

## Correction

- Conversion systématique VTK → Qt dans `tooling/_texture_projection_geometry.screen_pos`.
- Le picker manuel Texture Projection utilise maintenant le même repère que les événements souris.
- `pick_handle()` essaie d'abord le hit-test natif `ctx.selection.hit_test` avec une projection Qt reconstruite depuis l'owner si nécessaire.
- Le fallback manuel reste disponible pour les tests et contextes sans runtime Creator, mais il est désormais en coordonnées Qt.
- Ajout de compteurs diagnostics :
  - `texture_projection.handle_pick.native_hit`
  - `texture_projection.handle_pick.manual_hit`
  - `texture_projection.handle_pick.miss`
  - `texture_projection.handle_pick.last_distance_px`
  - `texture_projection.handle_pick.manual_best`
- Les poignées stretch U/V démarrent maintenant le drag via le callback natif, comme move/rotate/scale.

## Cas reproduit

Dans un viewport de hauteur 600 px avec un handle monde `(10, 5, 0)` projeté par VTK en `(110, 105, 0.5)` :

- position visuelle correcte en Qt : `(110, 495)` ;
- ancien picker manuel : hit possible autour de `(110, 105)` ;
- nouveau picker : `(110, 105)` est un miss, `(110, 495)` est le seul hit.

## Validation

- `tests/test_pass307_texture_projection_attach_pan_stretch.py` : 8/8 tests réussis.
- `tests/test_pass306_texture_projection_projected_drawing_migration.py` : inclus dans le sweep ciblé.
- Sweep Texture complet : 55 réussis, 1 ignoré.
- Sweep Creator interaction / caméra / native interaction ciblé : 24 réussis.
- Sweep combiné Texture + Creator interaction : 53 réussis, 1 ignoré.

## Fichiers modifiés

- `src/laserprog_studio/tooling/_texture_projection_geometry.py`
- `src/laserprog_studio/tooling/_texture_projection_projector.py`
- `tests/test_pass307_texture_projection_attach_pan_stretch.py`
- `tests/test_pass168_creator_texture_relief_refactor.py`
