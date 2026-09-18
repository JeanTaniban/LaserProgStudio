# Migration Texture Projection vers l'API Gizmo 2D publique — v53

## Objectif

Texture Projection était déjà rendu avec `ctx.projected_drawing`, mais son runtime interactif gardait encore quelques dépendances directes à `laserprog_studio.tool_core` :

- enums `ProjectedInteraction`, `ProjectedHandleShape`, `ProjectedDragConstraint` ;
- calcul caméra → rayon monde via `tool_core.gizmos.camera_scale.plotter_pixel_radius_to_world` ;
- enums d'événements souris dans le creator tool.

La v53 termine cette étape pour Texture Projection : le tool ne doit plus importer `tool_core` directement. Les détails bas niveau restent encapsulés derrière `laserprog_studio.tool_api`.

## Changements

- `_texture_projection_projector.py` importe maintenant les enums Projected Drawing depuis `laserprog_studio.tool_api.projected_drawing`.
- `texture_projection_creator_tool.py` importe `MouseButton` et `ToolEventType` depuis `laserprog_studio.tool_api.core`.
- Ajout de `tool_api.projected_drawing.world_radius_for_screen_pixels(...)` pour exposer un calcul simple de taille écran → taille monde aux tools Creator.
- Le runtime Texture Projection utilise maintenant `draw2d.world_radius_for_screen_pixels(...)` pour garder les poignées/rings lisibles et stables à l'écran.

## Contrat conservé

- Les poignées texture restent déclaratives : move, rotate, scale, stretch U-/U+/V-/V+.
- Le picking natif passe toujours par `ctx.selection.hit_test(...)`.
- Le fallback manuel reste présent pour les contextes de tests headless.
- Le fast path de drag conserve la logique actuelle : mise à jour légère pendant le mouvement, rebuild plus cher à la fin.

## Garde-fous

Le test `test_pass1052_tool_gizmo2d_migration.py` vérifie maintenant aussi que Texture Projection :

1. n'importe plus directement `laserprog_studio.tool_core` ;
2. utilise le helper public `draw2d.world_radius_for_screen_pixels(...)` ;
3. conserve un fallback numérique stable en contexte headless.
