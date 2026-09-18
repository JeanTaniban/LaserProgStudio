# Migration tools vers Projected Drawing 2D — v52

## Objectif

Remplacer les derniers accès directs des outils intégrés à l'ancienne API viewport (`ctx.preview`, `ctx.gizmos`, `ctx.actor_registry`) par les chemins publics actuels :

- `ctx.projected_drawing.for_tool(...)` pour les primitives et poignées 2D projetées ;
- `tool_api.plan2d` pour les acteurs sémantiques Plan Tracer / Vent Generator ;
- `tool_api.actors.registry(...)` pour la façade de compatibilité Creator, sans accès direct à `ctx.actor_registry`.

`ctx.preview_session` reste autorisé : il ne correspond pas à l'ancien rendu gizmo/preview, mais au système de preview applicatif des opérations de maillage.

## Inventaire outil par outil

| Outil | Statut v52 | Notes |
|---|---|---|
| Tool Core Diagnostic | Conservé comme laboratoire de diagnostic bas niveau | Ce n'est pas un outil de production de géométrie. Les outils intégrés ne doivent pas recopier ses chemins historiques. |
| Gizmo catalog | Déjà Projected Drawing 2D | Les scènes interactives, drag arrows et tests denses passent par `ctx.projected_drawing`. |
| Primitive | OK | Utilise `preview_session` pour prévisualiser le maillage généré, aucun gizmo legacy direct. |
| Box generator | OK | `preview_session` seulement. |
| Lay flat | OK | `preview_session` seulement. |
| Joint builder | OK | `preview_session` seulement. |
| Engraving roles | OK | `preview_session` seulement. |
| Material | OK | `preview_session` seulement. |
| Texture projection | OK | Runtime déjà migré vers Projected Drawing 2D ; aucun `ctx.preview` / `ctx.gizmos`. |
| Plan Tracer 2D | Corrigé v52 | Le dernier reliquat était le preview de motifs via `ctx.preview.show_line`; il est remplacé par un `ProjectedSegmentBatch`. |
| Vent generator | OK | Route et waypoints via `tool_api.plan2d`, compatibilité cachée en Projected Drawing. |
| Volume measure | OK | Pas de gizmo legacy direct. |
| Acoustic diffuser | OK | `preview_session` seulement. |
| Relief | OK | `preview_session` seulement. |
| Repair | OK | `preview_session` seulement. |
| Simplify | OK | `preview_session` seulement. |
| Extrude down | OK | `preview_session` seulement. |
| Hollow | OK | `preview_session` seulement. |
| Split | OK | `preview_session` seulement. |

## Changement Plan Tracer v52

Avant : le preview de motif créait une ligne legacy par segment via `ctx.preview.show_line(...)`. Cela mélangeait l'ancien renderer avec la scène Plan2D actuelle, et pouvait devenir lourd sur les motifs denses.

Maintenant : le preview de motif crée une seule primitive `ProjectedSegmentBatch` nommée `plan_trace_2d.pattern.preview:segments`, avec des `item_ids` stables pour les segments. Le nettoyage supprime uniquement les primitives Projected Drawing portant le préfixe `plan_trace_2d.pattern.preview:`.

## Garde-fou ajouté

Le test `test_pass1052_tool_gizmo2d_migration.py` vérifie deux choses :

1. aucun outil intégré sous `src/laserprog_studio/tooling` n'appelle directement `ctx.preview`, `ctx.gizmos` ou `ctx.actor_registry` ;
2. le preview de motif Plan Tracer utilise bien un batch Projected Drawing et ne crée aucun élément legacy dans `ctx.preview` / `ctx.gizmos`.
