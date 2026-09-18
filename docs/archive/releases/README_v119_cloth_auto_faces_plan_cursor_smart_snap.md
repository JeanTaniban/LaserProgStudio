# LaserProg v119 — Cloth automatic faces, Plan Tracer cursor and smart snap

## Objectif

Rendre Cloth aussi direct qu’un outil de tracé : dessiner des frontières 3D, voir les faces apparaître sans étape manuelle, retrouver exactement les curseurs de Plan Tracer 2D et garder une interaction fluide sur les documents plus grands.

## Création automatique des faces

- Line, Polyline et Arc déclenchent une recherche topologique après validation.
- La plus petite boucle sûre contenant la nouvelle courbe est matérialisée immédiatement.
- Une boucle non plane utilise le service existant de triangulation en panneaux plans et génère ses plis internes.
- Une arête peut être partagée pour créer un panneau voisin, mais les faces superposées ambiguës ne sont pas créées silencieusement.
- Le bouton **Face repair** reste disponible comme solution explicite pour les anciens documents ou les boucles ambiguës.

## Curseur commun avec Plan Tracer 2D

Cloth n’utilise plus son propre dessin de curseur. Il passe par l’API publique `tool_api.plan2d` :

- mêmes symboles de sommet, arête, milieu, intersection et centre ;
- mêmes libellés ;
- même synchronisation d’acteur et même chemin rapide de déplacement ;
- aucune dépendance directe de Cloth au renderer interne de Plan Tracer.

## Smart snap enrichi

- sommets et arêtes Cloth ;
- sommets, arêtes et surfaces des meshes de scène ;
- milieux d’arêtes ;
- intersections locales ;
- centres d’arcs ;
- axes monde X, Y et Z ;
- prolongement du segment précédent ;
- direction perpendiculaire dans le plan caméra.

La tolérance par défaut est ramenée à 12 px afin de réduire les accrochages trop collants. Les guides de construction peuvent être désactivés dans l’inspecteur.

## Performances

- cache des cibles de snap par révision du document ;
- préfiltrage spatial des cibles proches du curseur ;
- calcul sémantique borné à 96 cibles locales ;
- cache du mesh de surface par révision ;
- aucun rebuild du mesh pendant un simple mouvement de souris ;
- mise à jour incrémentale du curseur et du rubber-band ;
- géométrie statique resynchronisée uniquement lors d’un changement réel.

## Validation

- 46 tests Cloth ciblés réussis ;
- création automatique depuis lignes indépendantes, arc + ligne et boucle 3D non plane testée ;
- curseur Plan 2D et style de snap vérifiés ;
- test garantissant l’absence de reconstruction de surface pendant 25 mouvements de curseur ;
- 18 tests représentatifs Plan Tracer 2D réussis ;
- quality gate strict, audits API, migration et qualité produit réussis.
