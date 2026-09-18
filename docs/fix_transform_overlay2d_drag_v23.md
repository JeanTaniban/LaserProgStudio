# Correctif drag du gizmo Transform 2D — v23

Le picking et le hover du gizmo 2D fonctionnaient, mais certains événements
`MouseMove` émis par QVTK après un clic sur un `vtkActor2D` arrivaient avec
`event.buttons() == Qt.NoButton`. Le contrôleur interprétait immédiatement cet
état comme une perte du relâchement souris et annulait `_gizmo_pressed_axis`
avant que le seuil de 4 px puisse démarrer le drag.

Le contrôleur considère désormais le drag Transform comme propriétaire du
pointeur tant qu'un axe est pressé ou qu'un drag est actif **et** que le clic
initial n'a pas reçu son événement de release. La release explicite conserve le
nettoyage normal. Les autres gestes (pan, perte réelle de bouton, récupération
de focus) gardent leur mécanisme de remise à zéro.
