# EVT pass 41 — embouchure locale et suppression de la sécurité anti-touche

## Objectif

Cette passe corrige deux comportements gênants dans l'outil EVT rectangulaire :

- la sécurité qui refusait un waypoint simplement posé sur une ligne centrale existante ;
- l'embouchure qui était propagée comme une largeur variable le long des points échantillonnés du chemin.

## Nouveau comportement des waypoints

Le candidat n'est plus refusé uniquement parce qu'il touche une centerline existante. L'outil ne déplace toujours pas le point automatiquement : il accepte le point si la géométrie finale reste valide.

Les vrais auto-croisements de centerline restent refusés, parce qu'ils produisent une empreinte ambiguë pour la génération du mesh.

## Nouveau comportement de l'embouchure

L'embouchure n'est plus calculée comme un facteur de largeur appliqué aux stations de la centerline. Ce comportement faisait visuellement glisser l'embouchure quand la courbe changeait, et pouvait donner l'impression qu'elle se plaçait sur plusieurs points.

Le nouvel algorithme fait :

1. un évent rectangulaire de largeur constante ;
2. une petite empreinte rectangulaire locale ajoutée uniquement sur le premier waypoint, le dernier waypoint, ou les deux ;
3. la même empreinte est utilisée pour le preview, le snap, le Fill area et Apply.

La profondeur de cette embouchure est volontairement courte et bornée à une fraction du premier/dernier segment. Elle ne peut donc pas consommer un segment complet ni se répandre jusqu'au waypoint suivant.

## Fichiers principaux

- `src/laserprog_studio/planar_tools/vent_constraints.py`
- `src/laserprog_studio/planar_tools/vent_preview_snap.py`
- `src/laserprog_studio/application/planar_preview_service.py`
- `src/laserprog_studio/planar_tools/mesh_generation.py`
- `tests/test_vent_flare_local_mouth_pass41.py`
