# Restauration API Gizmos / isolation Transform — v19

## Cause de la régression

Deux problèmes indépendants empêchaient Plan Tracer 2D d'afficher correctement ses gizmos :

1. Le painter générique Creator UI avait été modifié par la migration Transform. Une erreur de portée sur `color_key` interrompait le rendu des handles. Le renderer basculait alors sur son ancien fallback PyVista, qui crée des sphères/cubes lourds. C'est la source du point noir/bleu pouvant rester après la fermeture de Plan Tracer.
2. Le paquet livré contenait un fichier de préférences pollué par des tests (`grid_step=100000`, tailles de motif extrêmes, Smart Snap désactivé). Plan Tracer pouvait donc sembler inutilisable même avec une API correcte.

## Restauration

Les éléments génériques suivants ont été restaurés à l'identique depuis la copie fonctionnelle fournie :

- `application/_tool_core_diag_scene_painter.py`
- `application/_tool_core_diag_scene_state.py`
- `tool_core/gizmos/__init__.py`
- les paramètres sûrs du dossier `settings/`

L'API publique historique reste donc :

```python
ctx.gizmos
```

Elle est utilisée par Plan Tracer et les autres outils Creator sans aucune dépendance envers Transform.

## Isolation de Transform

Le gestionnaire Transform est désormais un module frère séparé :

```python
ctx.transform_gizmos
# implémentation : tool_core/transform_gizmos.py
```

Il n'est plus exporté par `tool_core.gizmos` et le renderer Transform n'appelle plus les fonctions de nettoyage du painter Creator générique. Son nettoyage de compatibilité est limité aux clés historiques connues du Transform.

## Non-régression

Les tests couvrent :

- le contrat historique de `ctx.gizmos` ;
- l'absence de `TransformGizmoManager` dans l'API générique ;
- le rendu puis la destruction d'un handle Plan Tracer sans fallback sphérique ;
- l'absence d'appel au cleanup Creator générique depuis le renderer Transform ;
- des paramètres Plan Tracer empaquetés dans une plage sûre.
