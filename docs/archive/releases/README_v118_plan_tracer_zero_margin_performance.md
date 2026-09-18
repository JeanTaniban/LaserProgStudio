# LaserProg v118 — Plan Tracer zero-margin performance fix

## Problème corrigé

Dans l’outil Pattern de Plan Tracer 2D, mettre **Edge margin** à `0` activait le découpage au bord pour tous les types de motifs. L’ancien chemin exécutait alors une intersection GEOS complète entre la face et chaque cellule candidate.

Sur une face arrondie composée de centaines ou milliers de segments, plusieurs milliers d’intersections complexes étaient effectuées sur le thread de l’interface. L’application pouvait sembler gelée avant même la synchronisation du preview.

## Nouvelle stratégie

Le contour de la face est maintenant préparé une seule fois avec les prédicats spatiaux Shapely :

1. rejet immédiat des cellules dont les boîtes englobantes sont disjointes ;
2. acceptation directe des cellules entièrement couvertes par la face ;
3. rejet direct des cellules extérieures ;
4. intersection géométrique uniquement pour les cellules traversant réellement le bord.

La géométrie finale à marge nulle reste identique : les cellules de bord sont toujours découpées exactement contre le contour.

Pour une sélection contenant une seule face, les ouvertures déjà découpées ne sont plus intersectées une seconde fois pendant la redistribution par face.

## Résultat mesuré

Fixture de régression : rectangle arrondi de `400 × 250 mm`, contour de `4096` points, motif carré de pas `4 mm`, angle `13°`, marge `0`.

- ancien chemin de clipping : environ `7,5 s` pour la génération seule ;
- nouveau chemin : environ `1,2 s` dans le même environnement ;
- résultat : `6144` ouvertures, environ `27800` segments.

Le gain intervient avant la reconstruction des acteurs et évite le blocage principal du thread UI.

## Validation

- 2 nouveaux tests de régression dédiés ;
- 78 tests Pattern / motif / presets / union réussis ;
- contours et ouvertures à marge nulle toujours bornés par la face ;
- quality gate strict réussi pour les 20 outils Creator ;
- aucun changement du comportement ou de l’API de Cloth et Folding.
