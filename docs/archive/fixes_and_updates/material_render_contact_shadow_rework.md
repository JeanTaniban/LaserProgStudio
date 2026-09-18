# Deprecated: Contact Shadow Rework

Cette note est conservée comme historique. La solution par decals/contact shadows a été retirée car elle ne répondait pas au besoin : elle créait des artefacts visuels et ce n'était pas une vraie ombre.

La version active est documentée ici :

- `docs/material_render_real_shadows_rework.md`

Le pipeline courant utilise maintenant des shadow maps VTK pilotées par une machine d'état plus stricte, avec une lumière directionnelle unique et un sol récepteur opaque en volume fin.
