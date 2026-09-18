# Migration Plan Tracer 2D vers Projected Drawing 2D — v35

## Résultat

Plan Tracer 2D n'utilise plus directement les API historiques `ctx.preview`, `ctx.gizmos` ou `ctx.actor_registry`.
La migration remplace **35 appels directs** présents dans la v34 :

- **22** appels `ctx.preview` ;
- **12** appels `ctx.actor_registry` ;
- **1** appel `ctx.gizmos`.

L'ancienne API reste disponible pour les autres outils encore non migrés, mais elle n'est plus exécutée par le chemin runtime de Plan Tracer 2D.

## Correspondance fonctionnelle

| Élément Plan Tracer | Nouvelle déclaration |
|---|---|
| Points, curseur, ancre, poignées d'offset Motif | `ProjectedHandle` |
| Segments, polylignes, cercles et arcs | `ProjectedLine` avec `actor_kind` adapté |
| Faces simples ou perforées | `ProjectedFace` avec `holes` |
| Cotes et témoins | `ProjectedLine` + `ProjectedText` |
| Survol d'un volume éditable | `ProjectedTriangleMesh` |
| Aperçus temporaires de dessin | primitives projetées transitoires |
| Visibilité, suppression et nettoyage | `ProjectedDrawingRegistry` |

Les primitives interactives créent automatiquement leur acteur Tool Core de sélection. Les éléments purement visuels — texte, témoins auxiliaires, maillage de survol et certains aperçus temporaires — portent `projected_no_selection_actor=True` pour éviter des acteurs inutiles.

## Modifications d'architecture

### Registre unique

`tool_api/plan2d/actors.py` est désormais entièrement adossé à `ctx.projected_drawing`. Il n'existe plus de double écriture « acteur + preview/gizmo » pour Plan Tracer.

### Interaction native

`tool_api/interaction.py` détecte les outils entièrement projetés. Dans ce cas, il synchronise :

1. la position des primitives après un drag ;
2. les états hover, selected et grabbed ;
3. le rendu Projected Drawing final.

Il ne relance plus les constructeurs historiques `refresh_creator_ui_drag` et `refresh_creator_ui_interaction` lorsqu'aucun acteur legacy n'est présent.

### Performance

Le registre Projected Drawing ne reconstruit plus tous les acteurs de sélection après chaque mutation. Les opérations `add`, `update`, `patch` et `remove` utilisent une synchronisation différentielle O(nombre d'éléments modifiés). `replace_all` conserve une réconciliation complète.

Pendant un drag Plan Tracer, seuls les points et les arêtes/courbes directement connectées sont rafraîchis. Les faces et dimensions restent recompilées au relâchement, conformément au contrat de performance déjà présent en v34.

### Correctifs associés

- Les faces perforées transmettent leurs trous au hit-test Tool Core.
- Les lignes et faces projetées suivent les états normal, hover, selected, grabbed et disabled.
- La signature de compilation inclut les faces supprimées volontairement (`suppressed_face_signatures`), ce qui empêche une face supprimée de rester visible.
- Les préférences Plan Tracer livrées avec l'application ont été remises à des valeurs sûres ; la v34 contenait notamment un pas de grille de `100000.0` mm.

## Validation

- **121/121** tests ciblés de migration et de comportement Plan Tracer réussis.
- **54/54** tests Projected Drawing et interaction native réussis.
- Balayage des 80 fichiers de tests Plan Tracer : **315 réussites, 8 échecs**.
- Les 8 échecs restants ont été reproduits sur la v34 intacte. Ils concernent des attentes déjà obsolètes sur le bouton Motif, le nombre d'entrées undo et le comportement d'annulation ; ils ne sont pas introduits par cette migration.
- Un test AST garantit l'absence d'appels directs à `ctx.preview`, `ctx.gizmos` et `ctx.actor_registry` dans le périmètre runtime Plan Tracer.

## Fichiers principaux modifiés

- `src/laserprog_studio/tool_api/plan2d/actors.py`
- `src/laserprog_studio/tool_api/interaction.py`
- `src/laserprog_studio/tool_core/projected_drawing.py`
- `src/laserprog_studio/tooling/plan_trace_2d_tool.py`
- `src/laserprog_studio/tooling/plan_trace_2d/sketch_sync.py`
- `src/laserprog_studio/tooling/plan_trace_2d/snap.py`
- `src/laserprog_studio/tooling/plan_trace_2d/motif_overlay.py`
- `src/laserprog_studio/tooling/plan_trace_2d/rendering.py`

L'inventaire ligne par ligne des 35 appels remplacés se trouve dans `docs/plan_tracer_old_api_replacement_v35.csv`.
