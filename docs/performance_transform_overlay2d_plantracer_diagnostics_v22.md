# Transform overlay 2D et diagnostics Plan Tracer — v22

## Transform

Le gizmo principal de Transform n'est plus rendu comme une géométrie 3D de la
scène. Le backend normal utilise des `vtkActor2D` persistants et des
`vtkPolyDataMapper2D` :

- projection de la déclaration monde juste avant chaque frame (`StartEvent`) ;
- `vtkProperty2D.SetDisplayLocationToForeground()` ;
- lignes uniquement, sans cônes, cylindres, sphères, cubes ou tubes ;
- aucun renderer secondaire et aucune copie dans le renderer principal ;
- picking calculé sur les mêmes polylignes projetées que celles affichées ;
- inversion caméra des flèches Translate avec hystérésis ;
- direction de drag alignée sur le côté réellement affiché ;
- taille écran clampée et actualisation automatique pendant zoom/orbite/pan.

L'ancien renderer 3D léger est uniquement un fallback pour un VTK ancien ou un
hôte de test qui ne fournit pas `vtkActor2D`.

## État des diagnostics Plan Tracer avant cette passe

Les rapports existants étaient suffisants pour localiser la grande famille du
problème (`cursor.actor_sync`, `sync_actor_visuals`, `render`, construction des
cibles de snap), mais pas pour répondre précisément à la question : « est-ce le
rendu des nombreux points, la reconstruction des guides, le nombre d'acteurs,
ou le rendu VTK qui domine ? »

Le paquet `session_20260626_090932.zip` n'est pas un rapport LaserProg / Plan
Tracer : il provient d'Anny UV Lab et ne contient aucune mesure exploitable pour
ce chantier.

## Nouveaux compteurs

Le rapport `diagnostics/plan_trace_2d_timings.*` inclut maintenant les compteurs
`creator_ui.*` :

- `creator_ui.plan_trace.collect` ;
- `creator_ui.plan_trace.build_batches` ;
- `creator_ui.plan_trace.render` ;
- `creator_ui.plan_trace.total` ;
- `creator_ui.plan_trace.fast_update` ;
- `creator_ui.plan_trace.fast_update_render` ;
- `plan2d.actor_visuals.fast_drag` ;
- `plan2d.actor_visuals.full_interaction`.

Les jauges indiquent aussi :

- nombre de handles, previews et acteurs ;
- nombre de batches de points, guides et lignes ;
- nombre de points centraux ;
- nombre de disques géométriques et de vertices associés ;
- nombre de vertices de guides et de lignes ;
- nombre de points réellement touchés par le fast path ;
- nombre de misses du fast path.

## Décision A/B pour Plan Tracer

Après une session dense, les mesures permettent de choisir sans intuition :

1. `build_batches` élevé et `minimal_dot_vertices` / `guide_vertices` élevés :
   migrer les handles visuels vers un overlay 2D, tout en gardant les données et
   le snap en coordonnées monde.
2. `fast_update_misses` élevé : corriger d'abord les appels qui retombent sur un
   refresh complet O(N).
3. `render` élevé mais `build_batches` faible : optimiser le scheduler / la
   cadence VTK plutôt que changer l'API.
4. `snap` ou `scene_cache` dominant : le passage 2D des points ne résoudra pas le
   principal goulot.

L'architecture recommandée reste hybride : géométrie réelle et snapping dans le
monde, poignées UI éventuellement rendues en 2D.
