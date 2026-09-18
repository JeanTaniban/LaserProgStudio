# Correctif v25 — taille du gizmo Transform pendant le zoom

## Cause

Le filtre Qt recevait la molette avant que l'interacteur VTK ait toujours appliqué la modification de caméra. Le rafraîchissement interactif reposait sur un unique `QTimer.singleShot(0)`. Selon l'ordre de traitement Qt/VTK, ce callback relisait encore l'ancien champ de vision. Le rafraîchissement exact programmé à la fin de la rafale voyait, lui, la caméra finale : le gizmo ne changeait donc visiblement de taille qu'à l'arrêt du zoom.

## Correction

Une impulsion légère reste désormais active pendant toute la courte fenêtre de zoom :

- elle redemande une mise à jour au rythme interactif du gizmo ;
- elle utilise le redimensionnement en place des lignes et points 2D ;
- elle est coalescée par le scheduler existant ;
- chaque nouvel événement molette prolonge la fenêtre ;
- le rafraîchissement final exact est conservé.

Aucun actor, mapper ou assembly n'est recréé pendant le zoom.
