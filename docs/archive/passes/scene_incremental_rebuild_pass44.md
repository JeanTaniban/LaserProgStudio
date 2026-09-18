# Pass 44 — scène 3D incrémentale

## Problème

Quand le projet contenait beaucoup d'objets, une suppression, un ajout ou une opération relançait `rebuild_scene()` en mode destructif :

1. suppression de toute la scène PyVista ;
2. conversion de tous les `WorkMesh` en `PolyData` ;
3. recréation de tous les acteurs ;
4. reconstruction de toutes les textures/styles ;
5. rendu final.

Sur les scènes chargées, le coût était payé même quand un seul objet changeait.

## Solution

Le rebuild scène est maintenant optimisé par `laserprog_studio.rendering.incremental_scene`.

La scène garde une signature de rendu par objet : nom, couleur, matériau, géométrie, triangles, UV et projections de texture. À chaque rebuild avec caméra conservée, le renderer compare la nouvelle liste à l'ancienne et :

- réutilise les acteurs inchangés ;
- ajoute uniquement les nouveaux acteurs ;
- supprime uniquement les acteurs disparus ;
- gère les changements d'index après suppression/insertion ;
- ne fait un rebuild complet que pour les vrais resets de scène ou le premier affichage.

## Effet attendu

- Ajouter un objet ne reconstruit plus toute la scène.
- Supprimer un objet au milieu ne reconstruit plus tous les objets suivants.
- Les opérations qui ne modifient qu'une partie de la scène gardent les acteurs inchangés.
- La liste des pièces, la sélection, les gizmos, les styles et les textures restent synchronisés.

Le log `[3D] Scene OK` indique maintenant le mode utilisé, par exemple :

```text
mode=incremental reused=42 added=1 removed=0 shifted=0
```

ou :

```text
mode=full
```
