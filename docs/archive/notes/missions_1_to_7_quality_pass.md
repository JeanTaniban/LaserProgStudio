# Passe qualité — Missions 1 à 7

Cette passe vise à consolider les ajouts récents sans changer le comportement demandé par l’utilisateur.

## Points renforcés

- Centralisation de la copie des métadonnées runtime (`material`, `engraving`, `uvs`, `texture_projections`, `domain`) dans `geometry_ops/mesh_metadata.py`.
- Conservation plus fiable des métadonnées lors des opérations géométriques qui reconstruisent un mesh.
- Résultats d’opérations homogénéisés via `OperationResult.success()` / `OperationResult.failure()`.
- Import de `WorkMesh` rendu compatible avec le lancement package et le lancement script dans l’outil Relief.
- Historique de textures rendu persistable via `RecentTextureStore(storage_path=...)`, tout en restant utilisable en mémoire pour les tests ou outils simples.
- Ordre des boutons modificateurs clarifié : `SIM`, `REL`, `CUT`, `BAS`, `CRX`. Les outils liés au plan (`CUT` et `BAS`) sont regroupés.
- Ajout de tests ciblés sur les opérations récentes et le stockage de textures.

## Remarques techniques importantes

- `Creux` reste volontairement strict : il refuse les meshes ouverts ou non-manifold.
- Sans ouverture automatique, `Creux` produit une coque interne fermée. L’utilisateur peut ouvrir ensuite avec les autres outils.
- `Relief` conserve l’approche VTK VectorText pour garantir une géométrie réelle sans dépendance externe de conversion de police.
- `Extruder vers le bas` garde une construction verticale exacte jusqu’à Z=0 et reste séparé de la logique de découpe historique.
