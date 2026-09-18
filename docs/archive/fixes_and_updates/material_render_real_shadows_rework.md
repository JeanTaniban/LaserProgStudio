# Material Render Real Shadows Rework

Cette passe remplace les ombres factices par un pipeline d'ombres réelles VTK plus robuste.

## Décision technique

- Les ombres sont à nouveau basées sur les shadow maps VTK via `enable_shadows`.
- Le pipeline utilise une seule lumière directionnelle principale pour limiter le coût GPU.
- Le sol récepteur est un volume fermé très fin (`pv.Cube`), pas un plan infini. Les shadow maps VTK attendent de la géométrie opaque propre ; un slab fermé est plus stable qu'une face seule.
- Le shadow pass n'est activé/désactivé que lorsque la signature de rendu change : mode, lumière, sol, bounds, nombre de meshes.
- En mode non-matériaux, le shadow pass est désactivé explicitement et le sol récepteur est supprimé.

## Compatibilité PBR / shadows

VTK peut avoir des comportements variables avec PBR + shadow maps suivant backend/lumières. Pour fiabiliser l'éditeur :

- mode Matériaux sans ombres : interpolation PBR si disponible ;
- mode Matériaux avec ombres : interpolation Phong compatible shadow maps, avec approximation visuelle métal/rugosité par spéculaire et puissance spéculaire.

C'est volontaire : priorité à des vraies ombres propres et stables dans l'éditeur interactif.

## Logs utiles

- `[MATERIAL_RENDER] sync begin ... engine=vtk_shadow_maps`
- `[MATERIAL_RENDER] receiver floor created ...`
- `[MATERIAL_RENDER] directional key light applied ...`
- `[MATERIAL_RENDER] vtk shadows enabled ...`
- `[MATERIAL_RENDER] real shadows enabled=True ...`
- `[MATERIAL_RENDER] real shadows disabled ...`
- `[MATERIAL_RENDER] sync end material ... engine=vtk_shadow_maps`
