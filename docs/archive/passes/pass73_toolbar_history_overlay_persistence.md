# Pass 73 — persistance toolbar, historique compact, overlay Light UI

- La barre d’outils configurable du haut est maintenant sauvegardée immédiatement dans `settings/studio_toolbar.json`.
- Le JSON de layout existant reste alimenté pour compatibilité, mais la toolbar dispose de son propre fichier stable.
- La fermeture de l’application force la sauvegarde des préférences UI et toolbar avant la fermeture VTK.
- Le panneau `Tool > History` utilise des lignes compactes sur une seule ligne avec ellipse, au lieu de blocs multi-lignes espacés.
- L’overlay Light UI invalide explicitement la zone VTK sous l’ancien et le nouveau rectangle de l’overlay pour éviter les traces/empilements visuels avec la transparence.
