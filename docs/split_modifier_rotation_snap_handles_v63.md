# v63 — Split modifier rotation snap handles

## Pourquoi

La v62 avait bien migré Split modifier vers Projected Drawing 2D, mais les poignées de rotation étaient trop libres et donc peu lisibles. Le plan pouvait tourner correctement, mais l'utilisateur n'avait pas de sensation de cran ni de confirmation visuelle claire de l'axe modifié.

## Changements

- Les poignées de rotation Split sont maintenant des poignées à rotation crantée.
- Le drag de rotation est quantifié par défaut à 15°.
- Les poignées portent des métadonnées explicites : `rotation_mode=snapped`, `snap_degrees=15`.
- Des labels Projected Drawing indiquent l'axe et l'angle courant : `Rx`, `Ry`, `Rz`.
- Le mini overlay Split affiche maintenant le snap 15°.
- Le mini overlay et l'inspecteur exposent des orientations rapides : `XY`, `YZ`, `XZ`.
- Les boutons d'orientation remettent le plan sur les coupes courantes et resynchronisent l'inspecteur, le plan projeté et le rapport.

## Règle UX

- La flèche centrale déplace le plan.
- Les poignées de rotation modifient l'orientation par pas de 15°.
- Pour une coupe parfaitement standard, utiliser directement `XY`, `YZ` ou `XZ`.
- Chaque modification annule le preview actif, car le résultat de split n'est plus fiable après déplacement ou rotation du plan.

## Tests ajoutés / mis à jour

- Vérification des labels et métadonnées de snap.
- Vérification des boutons rapides `XY`, `YZ`, `XZ`.
- Vérification que le drag de rotation tombe sur un multiple de 15°.
- Mise à jour de l'audit qualité produit pour reconnaître les nouveaux boutons Split.
