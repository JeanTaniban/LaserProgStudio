# LaserProg v117 — Cloth Free 3D Tracer

## Objectif

Remplacer le premier workflow Cloth, trop verbeux et contraint par un choix de plan, par un véritable outil de tracé 3D inspiré de Plan Tracer 2D.

## Changements UX

- command deck compact avec Select, Draw, Build, Output et Session ;
- outils Point, Line, Polyline et Arc immédiatement visibles ;
- Polyline actif par défaut ;
- premier clic utilisable sans sélection préalable ;
- suppression de l’étape et des boutons de workplane ;
- seulement Mode et Status dans la palette ;
- inspecteur limité aux réglages de snap, pli et sortie ;
- champs de pli cachés hors du mode Fold ;
- statuts longs raccourcis dans le viewport.

## Tracé 3D libre

La profondeur d’un clic est résolue par smart snap, surface de mesh, puis plan caméra temporaire. Les plans temporaires ne sont ni visibles comme étape, ni persistants, ni contraignants.

Les sommets et arêtes des objets visibles de la scène participent au smart snap. Les points et courbes Cloth existants restent prioritaires.

## Faces 3D

- une polyligne fermée plane crée un panneau ;
- une polyligne fermée non plane est triangulée en panneaux plans ;
- une boucle non plane composée de lignes individuelles peut être convertie avec Face ;
- les plis internes sont créés automatiquement entre triangles voisins.

## Architecture

Nouveaux services séparés :

- `cloth/free_space.py` pour le picking et la profondeur ;
- `cloth/surface_creation.py` pour les boucles 3D ;
- command deck dans `cloth/workflow_overlay.py` ;
- inspecteur réglages-only dans `cloth/panel.py`.

Aucun fichier source de Plan Tracer 2D n’a été modifié.

## Validation

- 47 tests Cloth/Creator/picking réussis ;
- 6 scénarios spécifiques Free 3D réussis ;
- quality gate strict réussi ;
- comparaison Plan Tracer v116/v117 identique : 56 réussites, 11 échecs historiques dans les deux versions.
