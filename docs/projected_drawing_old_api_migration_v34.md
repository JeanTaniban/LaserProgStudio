# Audit et couverture de migration — ancienne API gizmos vers Projected Drawing 2D (v34)

## Conclusion

La nouvelle API couvre désormais les capacités réellement nécessaires pour remplacer le couple historique `ctx.preview` + `ctx.gizmos` : primitives géométriques, texte, maillage triangulé, faces perforées, poignées interactives, manipulateurs composites et opérations de registre équivalentes.

Cette livraison **ne remplace pas encore les 244 appels de rendu ni les 65 références de couplage aux acteurs** : elle fournit l’inventaire exhaustif et ferme les manques de l’API cible afin que la migration puisse être faite outil par outil sans recréer une troisième couche de rendu.

## Méthode et périmètre

- Analyse AST de tous les fichiers Python sous `src/laserprog_studio`.
- Comptage des appels exécutables à `preview` et `gizmos`, y compris les alias locaux provenant du contexte.
- Exclusion des commentaires, chaînes de documentation et d’un faux positif PIL (`Image.thumbnail`).
- Le registre `ctx.selection` / `ctx.actor_registry` est recensé séparément comme dépendance couplée : 65 références dans 13 fichiers, dont deux fichiers absents de l’inventaire de rendu.
- Le périmètre complet représente donc 31 fichiers uniques.

## Résultats globaux

| Famille | Appels | Fichiers |
|---|---:|---:|
| `ctx.preview` | 140 | 25 |
| `ctx.gizmos` | 104 | 22 |
| **Total** | **244** | **29 fichiers uniques** |

Dix-huit fichiers utilisent les deux familles. Additionner 25 et 22 fichiers donnerait donc un total erroné de 47 ; l’union réelle est de 29 fichiers.

### Répartition par zone

| Zone | Appels |
|---|---:|
| diagnostic/catalogue | 160 |
| outil métier | 46 |
| infrastructure application | 24 |
| API Plan2D | 8 |
| infrastructure Tool Core | 6 |

La concentration dans les diagnostics et catalogues (160 appels) est utile : ces écrans peuvent servir de banc de validation après migration, mais ils ne doivent pas être migrés avant les outils métier.

## Méthodes historiques rencontrées

### `ctx.preview`

| Méthode | Appels | Remplacement |
|---|---:|---|
| `show_line` | 35 | `draw2d.line()` |
| `items` | 20 | `registry.items()` / `registry.snapshot()` |
| `clear_tool` | 18 | `registry.clear()` |
| `show_text` | 15 | `draw2d.text()` |
| `show_polyline` | 13 | `draw2d.polyline()` |
| `show_circle` | 13 | `draw2d.circle()` |
| `hide` | 9 | `registry.hide()` |
| `show_arc` | 7 | `draw2d.arc()` |
| `show_face` | 6 | `draw2d.face(..., holes=...)` |
| `clear` | 3 | `ProjectedDrawingManager.clear()` / registres propriétaires |
| `show_mesh` | 1 | `draw2d.triangle_mesh()` |

### `ctx.gizmos`

| Méthode | Appels | Remplacement |
|---|---:|---|
| `handles` | 29 | `snapshot.handles` |
| `create_handle` | 18 | `draw2d.handle()` / `draw2d.drag_arrow()` |
| `clear_tool` | 10 | `registry.clear()` |
| `begin_interactive_update` | 8 | `update_many()` / `update_positions()` (une révision) |
| `end_interactive_update` | 8 | `update_many()` / `update_positions()` (une révision) |
| `update_positions_only` | 7 | `registry.update_positions()` |
| `translate` | 3 | `draw2d.translate_gizmo()` |
| `set_visible` | 3 | `registry.hide()` / `registry.show()` |
| `radius_for_style` | 3 | `ProjectedHandleStyle.size_px` + état visuel |
| `remove` | 3 | `registry.remove()` / `registry.remove_many()` |
| `rotate` | 2 | `draw2d.rotate_gizmo()` |
| `scale` | 2 | `draw2d.scale_gizmo()` |
| `plane` | 2 | `draw2d.plane_gizmo()` |
| `box_bounds` | 2 | `draw2d.box_bounds_gizmo()` |
| `set_minimal_dot_radii` | 1 | styles de handles déclaratifs |
| `update_style_metrics` | 1 | styles de handles déclaratifs |
| `triad` | 1 | `draw2d.triad_gizmo()` |
| `update_interaction_state` | 1 | synchronisation native `sync_interaction_state()` |

## Tous les fichiers concernés

| Fichier | Preview | Gizmos | Total | Priorité |
|---|---:|---:|---:|---|
| `tool_core/diagnostic/gizmo_demo.py` | 13 | 16 | 29 | 4 — validation/catalogue |
| `tool_core/diagnostic/showcase.py` | 13 | 9 | 22 | 4 — validation/catalogue |
| `application/transform_gizmo_api.py` | 17 | — | 17 | 3 — transform isolé |
| `tooling/_texture_projection_projector.py` | 7 | 9 | 16 | 2 — outil métier |
| `tool_api/_ui_motif_actor_rows.py` | 12 | 3 | 15 | 4 — validation/catalogue |
| `tool_api/_ui_motif_showcase_rows.py` | 9 | 6 | 15 | 4 — validation/catalogue |
| `tool_core/diagnostic/runner.py` | 5 | 10 | 15 | 4 — validation/catalogue |
| `tool_api/diagnostic_lab.py` | 6 | 7 | 13 | 4 — validation/catalogue |
| `tool_api/diagnostics.py` | 3 | 9 | 12 | 4 — validation/catalogue |
| `tooling/vent_generator/feedback.py` | 10 | 1 | 11 | 2 — outil métier |
| `tooling/plan_trace_2d/snap.py` | 10 | — | 10 | 1 — Plan Tracer |
| `tool_api/_ui_motif_builder.py` | 3 | 5 | 8 | 4 — validation/catalogue |
| `tool_api/plan2d/actors.py` | 8 | — | 8 | 1 — Plan Tracer |
| `tool_api/_ui_motif_runtime.py` | 1 | 5 | 6 | 4 — validation/catalogue |
| `tool_api/_ui_motif_style_rows.py` | 6 | — | 6 | 4 — validation/catalogue |
| `tool_api/_ui_motif_visibility.py` | 1 | 4 | 5 | 4 — validation/catalogue |
| `application/_tool_core_diag_scene_painter.py` | 2 | 2 | 4 | 4 — validation/catalogue |
| `application/tool_core_diag/pointer_interaction.py` | — | 4 | 4 | 4 — validation/catalogue |
| `tool_core/context.py` | 1 | 3 | 4 | 3 — infrastructure |
| `tool_core/diagnostic/bench.py` | — | 4 | 4 | 4 — validation/catalogue |
| `application/preview_controller.py` | 3 | — | 3 | 3 — infrastructure |
| `tooling/plan_trace_2d/patterns.py` | 3 | — | 3 | 1 — Plan Tracer |
| `tooling/plan_trace_2d/sketch_sync.py` | 2 | 1 | 3 | 1 — Plan Tracer |
| `application/creator_viewport_ui.py` | 1 | 1 | 2 | 3 — infrastructure |
| `application/tool_core_diag/view_settings.py` | — | 2 | 2 | 4 — validation/catalogue |
| `controllers/interaction_gizmo_refresh.py` | 1 | 1 | 2 | 3 — infrastructure |
| `tool_core/tools.py` | 1 | 1 | 2 | 3 — infrastructure |
| `tooling/plan_trace_2d_tool.py` | 2 | — | 2 | 1 — Plan Tracer |
| `tooling/plan_trace_2d/motif_overlay.py` | — | 1 | 1 | 1 — Plan Tracer |

Les lignes exactes, appels sources et remplacements proposés sont dans [`old_gizmo_api_usage_v34.csv`](old_gizmo_api_usage_v34.csv). Les références couplées aux acteurs sont détaillées dans [`old_creator_actor_coupling_v34.csv`](old_creator_actor_coupling_v34.csv).

## Capacités ajoutées à Projected Drawing 2D

### Primitives manquantes

- `draw2d.text()` et rendu persistant par `vtkTextActor`, ancré dans le monde et reprojeté avec la caméra.
- `draw2d.triangle_mesh()` avec sommets et indices de triangles, sans exposer VTK/PyVista dans l’API créateur.
- `draw2d.face(..., holes=...)` avec triangulation des trous et hit-test qui exclut réellement les zones perforées.

### Manipulateurs composites

- `translate_gizmo`, `rotate_gizmo`, `scale_gizmo`, `plane_gizmo`, `triad_gizmo`, `box_bounds_gizmo`.
- Chaque factory retourne un `ProjectedManipulator` immuable avec ses primitives et ses identifiants de poignées stables.
- `registry.add_manipulator()` injecte tout le manipulateur en une seule opération.

### Parité de registre

- `get()`, `items()`, `update_positions()`, `hide()`, `show()`, `set_primitive_visible()` et `remove_many()`.
- Les mises à jour groupées conservent une seule révision et une seule synchronisation du renderer.
- Les primitives interactives continuent d’être reflétées automatiquement dans `SelectionManager`; un outil n’a plus besoin de maintenir séparément un preview et un `ToolActor` pour la même géométrie.

## Dépendance historique aux acteurs de sélection

L’audit séparé relève **65 références dans 13 fichiers** : 45 appels contenant `actor_registry`, 13 factories d’acteurs et 7 accès bas niveau d’enregistrement/mise à jour. Les fichiers `tool_api/actors.py` et `tooling/creator_runtime.py` ne contiennent pas directement de rendu `preview/gizmos`, ce qui porte le périmètre complet à 31 fichiers uniques.

Plusieurs outils déclarent actuellement deux fois la même entité : une fois via `ctx.actor_registry(...)` pour le hit-test, puis une fois via `ctx.preview` ou `ctx.gizmos` pour l’affichage. Projected Drawing possède déjà `interaction="fixed|selectable|grabbable"` et synchronise les acteurs sémantiques automatiquement. Lors de la migration, ces doubles déclarations doivent être supprimées ensemble, sinon des acteurs invisibles ou dupliqués resteront dans la sélection.

Les zones les plus concernées sont `tool_api/plan2d/actors.py`, `_ui_motif_*`, `diagnostic_lab.py`, `_texture_projection_projector.py`, `plan_trace_2d/motif_overlay.py`, `plan_trace_2d/sketch_sync.py` et `vent_generator/feedback.py`.

## Ordre de migration recommandé

1. **Plan Tracer 2D** : migrer d’abord les lots de points/segments/faces, puis les guides de snap, puis les poignées. C’est la zone où le gain de fluidité est le plus important.
2. **Projection de texture** et **Vent Generator** : remplacer les couples actor + preview/gizmo par une déclaration projetée interactive unique.
3. **Infrastructure Creator** (`creator_viewport_ui`, rafraîchissement, nettoyage) : basculer les consommateurs vers les snapshots projetés, puis retirer les painters historiques.
4. **Diagnostics et catalogue** : convertir en dernier et utiliser leurs scénarios pour vérifier la parité visuelle et interactive.
5. **Transform application** : garder son API isolée pendant la migration Creator; elle a un renderer et des contraintes métier spécifiques.

## Limites restantes, explicites

- `triangle_mesh()` exige des sommets et triangles indexés. Un objet PyVista opaque n’est volontairement pas accepté; son extraction doit se faire à la frontière application.
- Les motifs de lignes `dashed` / `dotted` restent déclaratifs et peuvent être rendus pleins, comme dans les painters actuels. Les couleurs, largeurs et opacités sont couvertes.
- `plane_gizmo()` reproduit le couple origine/normal de l’ancienne API. Le déplacement du normal arbitraire reste piloté par la logique de l’outil via ses métadonnées, car l’ancien manager ne fournissait pas non plus une contrainte générique d’axe arbitraire.
- Les appels historiques ne sont pas désactivés dans cette livraison. Les désactiver avant la migration des 244 sites casserait Plan Tracer, les outils métier et les diagnostics.

## Validation

- Tests ajoutés pour faces à trous, texte projeté persistant, maillage triangulé, opérations de registre et six manipulateurs composites.
- Les tests Projected Drawing, styles de gizmos, catalogue et scénarios Plan Tracer ciblés passent : **49 tests réussis**.
- La suite globale n’est pas verte sur l’archive v33 : l’exécution avec arrêt après 8 échecs a donné 400 réussites et 2 ignorés avant l’arrêt. Les 8 premiers échecs ont été reproduits à l’identique dans un worktree propre du commit v33, donc ils ne sont pas introduits par cette modification.

