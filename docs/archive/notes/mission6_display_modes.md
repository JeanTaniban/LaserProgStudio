# Mission 6 — Modes d'affichage

Ajout d'un sélecteur global de rendu dans le panneau gauche `View`, sous les paramètres caméra.

## Modes disponibles

- `Wireframe` : conserve le comportement historique LaserProg, avec faces visibles et arêtes/triangles affichés.
- `Solide` : rendu classique basé sur la couleur de rôle gravure/découpe de la pièce.
- `Matériaux` : rendu basé sur les métadonnées `WorkMesh.material` quand elles existent.

## Arêtes

Le toggle `Afficher arêtes` reste disponible et s'applique au mode courant. Changer de mode applique les valeurs par défaut cohérentes :

- Wireframe : arêtes activées.
- Solide : arêtes désactivées par défaut.
- Matériaux : arêtes désactivées par défaut.

## Matériaux

Le rendu matériau utilise `MeshMaterial.base_color`, `opacity`, `metallic` et `roughness`. Le mode solide continue volontairement d'utiliser `WorkMesh.color`, afin de préserver l'affichage des rôles d'export laser.
