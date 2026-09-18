# EVT Pass 36 — preview propre + ADD/MOD simplifié

## Objectif

Cette passe retire la logique de poignées visibles qui compliquait l'édition EVT et remet une interaction plus simple :

- **ADD** pose des waypoints et affiche une polyline simple.
- **MOD** sélectionne/déplace uniquement des waypoints.
- Le waypoint sélectionné expose dans la boîte à outils les réglages du segment associé.
- Les courbes sont pilotées par sliders `Curve radius` et `Curve force`.
- Aucun handle de courbe n'est dessiné dans la scène.

## Preview extérieur

Le tracé des deux bords extérieurs a été remplacé par un offset polyline stable :

1. offset par segment ;
2. jonction par intersection des lignes offset ;
3. fallback bevel si le miter devient trop long.

Cela évite les bords qui se croisent ou partent en boucle dans les virages serrés.

## Courbes

Les nouveaux segments restent droits par défaut. Une courbe est appliquée seulement après sélection d'un waypoint en **MOD**. Le segment édité est :

- le segment entrant du point sélectionné ;
- pour le premier point, le premier segment sortant.

## Validation

La suite de tests couvre :

- grille EVT relative au premier waypoint ;
- smart snap sur centreline et bords ;
- preview offset sans spikes sur virage serré ;
- Fill area global bounding box ;
- mesh final généré uniquement à l'Apply pour EVT.
