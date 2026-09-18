# Passe performance v21 — drag Transform et zoom dynamique

## Objectifs

Cette passe traite deux sources de latence dans l'application principale :

1. le déplacement d'une sélection avec le gizmo Translate ;
2. la mise à l'échelle visuelle des gizmos Transform pendant un zoom caméra.

## Translation : chemin rapide scalaire

Au début du drag, l'application construit un profil compact de la sélection à déplacer. Le calcul du Smart Snap utilise ensuite ce profil et le décalage courant au lieu de reconstruire un tableau complet de vertices à chaque événement souris.

Pendant le drag natif :

- les acteurs VTK existants reçoivent uniquement une position temporaire ;
- le gizmo suit la sélection ;
- aucun tableau de vertices transformés n'est matérialisé dans le chemin normal ;
- les vertices définitifs sont écrits une seule fois au relâchement souris.

Le seuil de micro-mouvement a aussi été abaissé afin de conserver une sensation plus continue. Lorsque le scheduler central est disponible, il devient l'unique responsable du coalescing des rendus.

## Gizmos : taille dynamique pendant le zoom

Les gizmos Transform sont constitués de lignes et de points légers. Leur géométrie peut désormais être redimensionnée en place :

- les `PolyData.points` existants sont mis à jour ;
- les actors, mappers et assemblies ne sont pas recréés ;
- le snapshot de picking et le contexte API restent synchronisés ;
- le scheduler central utilise un budget interactif d'environ 16 ms pendant une rafale de zoom.

Un rafraîchissement exact est toujours exécuté après la fin de la rafale. Les changements d'orientation caméra peuvent conserver une reconstruction complète lorsque la frame adaptative de Scale doit être recalculée.

## Diagnostics

Les compteurs suivants permettent de confirmer le chemin rapide :

- `render.central.camera_zoom_budget` ;
- `transform.drag.translate.snap_scalar_cached` ;
- `transform.gizmo.native.camera_resize` ;
- `renderer.geometry_updated` dans `diagnostics/transform_gizmo_debug.jsonl`.

## Compatibilité

Le chemin legacy de transformation mesh reste disponible comme fallback. Les API Creator génériques, notamment celles de Plan Tracer 2D, ne sont pas modifiées par cette passe.
