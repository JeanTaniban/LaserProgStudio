# Pass49 - Outil Volume cavité

Ajout d'un outil **VOL / Volume cavité** pour mesurer le volume vide interne fermé d'une pièce fusionnée sélectionnée.

## Fonctionnement

- L'utilisateur sélectionne exactement une pièce.
- L'outil analyse les coques de surface du mesh sélectionné.
- La plus grande coque fermée est considérée comme l'enveloppe extérieure.
- Les autres coques fermées dont le centroïde est contenu dans cette enveloppe sont additionnées comme cavités.
- Le résultat est affiché en litres, avec le volume externe approximatif et la matière estimée.

## Limites assumées

L'outil mesure une cavité interne fermée. Les poches ouvertes, évents ouverts, trous traversants et meshes non fermés ne sont pas comptés comme cavité. Dans ce cas, le rapport conseille de fermer/réparer le mesh.

## Fichiers principaux

- `src/laserprog_studio/geometry_ops/cavity_volume.py`
- `src/laserprog_studio/controllers/cavity_volume_tool.py`
- `src/laserprog_studio/tooling/ids.py`
- `src/laserprog_studio/tooling/registry.py`
- `src/laserprog_studio/ui/tool_panel_factory.py`
- `src/laserprog_studio/ui/tool_panel_catalog.py`
- `src/laserprog_studio/ui/toolbar_catalog.py`
- `src/laserprog_studio/tooling/help_docs.py`

## Validation

- Test géométrique avec boîte 100×100×100 mm et cavité 50×50×50 mm : 0,125 L.
- Test qui ignore un solide séparé extérieur à l'enveloppe.
- Test de registre outil/panneau/toolbar.
- Suite complète : `282 passed, 3 skipped`.
