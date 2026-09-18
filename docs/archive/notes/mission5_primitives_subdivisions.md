# Mission 5 - Primitives personnalisables

Ajout d'un réglage simple du niveau de détail dans le générateur de primitives.

## Inclus

- Ajout de `Personnalisé` en dernier dans le menu des primitives.
- Conservation des primitives existantes dans le menu.
- Ajout d'un choix de forme personnalisée : cylindre, sphère ou cône.
- Renommage des contrôles de subdivisions côté UI :
  - `Nb. côtés` pour cylindre/cône.
  - `Segments H` et `Segments V` pour la sphère.
- Les réglages restent mémorisés tant que le panneau existe, donc plusieurs créations successives conservent les dernières valeurs.
- Ajout d'une estimation du nombre de triangles avant création.
- Ajout d'un calcul d'estimation côté moteur de primitives pour rester testable hors UI.

## Notes

- Un cylindre avec 6 côtés produit un prisme hexagonal.
- Un cône avec 4 côtés produit une pyramide carrée.
- `Personnalisé` évite d'ajouter trop d'entrées au menu tout en donnant un contrôle fin sur les subdivisions.
