# Pass 46 — Fix disparition d'objets après suppression

## Problème

Après l'optimisation de rebuild incrémental, certains objets non sélectionnés pouvaient disparaître visuellement après une suppression puis un ajout ou une autre opération.

La cause était l'utilisation de noms PyVista basés sur l'index (`mesh_0`, `mesh_1`, etc.). PyVista utilise le paramètre `name` de `add_mesh` comme une clé de remplacement. Or, après suppression, un acteur réutilisé peut changer d'index logique tout en gardant son ancien nom interne. Un ajout ultérieur au même index pouvait donc remplacer l'acteur réutilisé et faire disparaître un autre objet.

## Correction

Les acteurs mesh ont maintenant un nom unique et immuable par instance :

```text
lp_mesh_actor_1
lp_mesh_actor_2
...
```

Les index utilisateur restent gérés uniquement par :

```text
actors_by_index
polydata_by_index
actor_key_by_vtk
actor_key_by_addr
```

Le nom PyVista n'est donc plus utilisé comme identité métier de l'objet.

## Résultat

- Supprimer un objet ne peut plus remplacer ou retirer un acteur réutilisé appartenant à un autre objet.
- Le rebuild incrémental reste actif.
- Les objets inchangés continuent d'être réutilisés pour garder une scène fluide.
- Les picks/sélections continuent d'utiliser les maps indexées reconstruites après chaque rebuild.

## Test ajouté

`tests/test_scene_incremental_actor_identity_pass46.py`

Le test simule le comportement PyVista où `add_mesh(name=...)` remplace un acteur existant avec le même nom. Il vérifie le scénario critique :

1. scène avec 5 objets ;
2. suppression d'un objet au milieu ;
3. réutilisation des acteurs décalés ;
4. ajout d'un nouvel objet ;
5. aucun acteur non sélectionné ne disparaît.
