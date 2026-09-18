# LaserProg v166 — Cloth Non-Overlapping Closure

Cette version durcit le solveur **Close** afin que les nouvelles faces textiles
se raccordent aux groupes sélectionnés sans recouvrir leurs surfaces et sans
laisser une fermeture visiblement incomplète.

## Contrat géométrique de Close

Une proposition Close est maintenant valide uniquement si :

- ses rails touchent les frontières des groupes sources ;
- l’intérieur des nouvelles cellules reste hors des faces textiles existantes ;
- aucune cellule ne traverse un panneau source ou un troisième textile ;
- les cellules ne sont ni écrasées, ni torsadées en bow-tie ;
- une fermeture entre deux boucles décalées couvre au moins 98 % des frontières
  utiles ;
- une proposition partielle ne remplace jamais silencieusement une fermeture
  complète impossible.

Le résultat reste un nouveau groupe textile indépendant, conformément au modèle
persistant introduit en v165.

## Corridor textile anti-recouvrement

Au lancement de Close, LaserProg construit un obstacle triangulé à partir de
l’ensemble du document Cloth. La construction utilise successivement :

1. le mesh Cloth canonique complet ;
2. le mesh canonique des groupes sources si un ancien panneau invalide bloque
   la construction globale ;
3. une triangulation panneau par panneau en dernier recours.

Chaque cellule candidate est contrôlée dans tout son volume utile :

- grille bilinéaire répartie sur l’ensemble du quad ;
- sections transversales près des deux extrémités ;
- connecteurs de bord ;
- diagonales du quad ;
- intersections segment–triangle non coplanaires ;
- présence de points intérieurs sur les triangles existants.

Cette vérification corrige le cas où le milieu d’une fermeture se trouvait dans
le vide, mais où une extrémité repassait au-dessus d’un panneau sélectionné.

## Couverture complète et extrémités

Pour deux groupes séparés principalement selon leur normale, l’intention est une
paroi complète entre leurs contours. Le solveur n’utilise plus une chaîne
partielle comme remplacement :

- la proposition complète doit conserver au moins 99,5 % de ses cellules
  géométriquement valides ;
- sa couverture doit atteindre au moins 98 % ;
- une correspondance qui laisse le haut ouvert est rejetée ;
- les rails sont prolongés jusqu’aux véritables sommets terminaux lorsque la
  continuité géométrique le permet ;
- un coin commun ambigu ne produit plus une cellule de largeur nulle ni une
  paroi amputée.

Pour les groupes coplanaires ou latéraux, Close conserve les stratégies de
frontières faisant face, mais celles-ci passent par le même corridor
anti-recouvrement.

## Obstacles textiles

Tous les panneaux textiles existants sont considérés comme obstacles, pas
seulement les deux groupes sélectionnés.

Si un troisième textile coupe le corridor, Close ne génère pas deux bandes
partielles autour de lui. Il ne propose rien et conserve le document intact.
Cela évite les groupes incomplets difficiles à déplier ou à fabriquer.

## Alignement et performance

Les correspondances cycliques sont classées avec la collision comme critère
prioritaire : une correspondance légèrement plus courte ne peut pas gagner si
elle traverse du textile.

Pour conserver une interaction acceptable, le solveur utilise :

- un classement géométrique peu coûteux ;
- 12 candidats de collision grossière ;
- 3 candidats de collision complète ;
- des boîtes englobantes pour limiter les triangles examinés.

Le scénario de régression composé de deux groupes en U et d’environ 50 segments
de fermeture est analysé en moyenne autour de **340 ms** dans l’environnement de
test.

## Apply et flat preview

Une proposition validée est testée jusqu’au pipeline de sortie :

- commit transactionnel ;
- validation du document ;
- construction du mesh 3D ;
- flatten ;
- génération du flat preview ;
- absence d’erreur de triangulation sur le résultat testé.

## Diagnostics

Quand les diagnostics sont activés dans les préférences, l’étape
`corridor.obstacles` enregistre :

- le mode de construction des obstacles ;
- le nombre de triangles ;
- le nombre de panneaux couverts ;
- la tolérance utilisée ;
- les difficultés de triangulation rencontrées.

Aucun recorder ni contrôle supplémentaire n’est exécuté lorsque les diagnostics
sont désactivés.

## Vérifications

- 9 tests spécifiques v166 ;
- 21 tests dédiés au solveur Close global et anti-recouvrement réussis ;
- 94 tests ciblés Cloth, sélection, booléens, pipeline, Apply et flatten réussis ;
- collection Cloth historique : 156 réussis et 5 ignorés ;
- 18 anciens tests restent en échec parce qu’ils exigent les interfaces Cloth
  retirées avant le workflow à overlay unique ;
- compilation complète réussie ;
- Quality Gate réussi ;
- audit strict des frontières API réussi, sans erreur critique ;
- audits d’architecture, de migration et de qualité produit réussis ;
- les 21 outils intégrés restent sur le runtime moderne.
