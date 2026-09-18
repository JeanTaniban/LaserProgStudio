# Texture Projection v41 — attach réel, pan caméra et hit-test 2D

## Problèmes corrigés

- `Attach to mesh` ne crée plus un décal superposé : la texture est attachée au vrai mesh via UV.
- Le mode décoché conserve le comportement décal/overlay séparé.
- Le pan/orbit/zoom n’est plus capturé par le filtre Qt Texture Projection lorsqu’on clique hors poignée TEX.
- Un relâchement court sur une face continue de repositionner proprement l’image.
- Le rayon de capture des poignées 2D Texture Projection est réduit pour éviter les grabs très éloignés, surtout avec caméra de côté.
- La mise à jour live en attach-to-mesh respecte le Coverage : faces couvertes = UV réels, faces non couvertes = UV de bord neutre.

## Sémantique finale

| Option | Comportement |
|---|---|
| Attach to mesh coché | Modifie le mesh réel et attache la texture à ses UV |
| Attach to mesh décoché | Crée un patch/décal visuel superposé |

Dans le mode attach-to-mesh limité par Coverage, les vertices sont séparés quand une arête est partagée entre une face couverte et une face non couverte. Cela évite que l’interpolation UV fasse baver la texture sur les faces voisines.

## Note sur Repeat

Quand le Coverage ne couvre pas tout le mesh, le mode attach-to-mesh force le sampler hors couverture vers le bord neutre. Sinon, `Repeat` ferait réapparaître la texture sur les faces non couvertes. Le mode décal reste disponible quand on veut un patch visuel indépendant.

## Validation

- 58 tests Texture Projection / export texture / UI concernés réussis.
- 1 test ignoré historique.
- Les 3 échecs observés dans le balayage caméra/sélection large sont reproduits à l’identique dans la v40 originale.

