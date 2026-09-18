# Plan Tracer — Apply / Cancel Recovery (v176)

## Symptôme

Sur certains sketches fortement modifiés, **Apply** ne validait pas le volume. Après **Cancel**, la réouverture du draft devenait progressivement très lente.

## Cause 1 — Apply

Le sketch peut contenir une micro-face produite par les intersections de courbes/lignes. Dans le cas observé, son aire était d'environ `0.000515 mm²`. Après union des faces, cette configuration donnait un trou tangent au contour extérieur en un point.

La première régularisation de `build_valid_planar_footprint()` utilisait `buffer(-d).buffer(+d)`. Pour un contact polygonal exact sur un segment droit, cette opération peut recréer exactement le même point tangent. L'extrusion indexée forme alors une arête verticale partagée par quatre triangles : `nonmanifold_edges=1`, `nonmanifold_vertices=2`.

### Correction

Après la régularisation symétrique, le générateur contrôle de nouveau les contacts à dégagement nul. S'il en reste un, il conserve une érosion nette microscopique, proportionnelle à l'échelle du dessin. La variation dimensionnelle est très inférieure à la précision utile du modèle mais le contour devient réellement manifold.

## Cause 2 — lenteur après Cancel / réouverture

`deserialize_sketch()` appelait `SketchDocument.compile()` sans options. Les options par défaut du kernel autorisent le découpage des intersections de courbes et le split aux sommets. Une simple réouverture pouvait donc fragmenter arcs, lignes et points ; Cancel resauvegardait ensuite cette nouvelle topologie et la réouverture suivante recommençait.

### Correction

La désérialisation est maintenant pure et ne compile plus. Les chemins qui ont besoin de faces recompilent explicitement avec la politique Plan Tracer non destructive :

- `split_curve_intersections=False`
- `split_curves_at_vertices=False`
- `solve_faces=True`

## Validation

Le projet utilisateur reproduisant le défaut contient deux drafts similaires. Avant correction, les deux échouent à l'extrusion avec une arête non-manifold. Après correction :

- draft 1 : `36` régions, résultat manifold ;
- draft 2 : `39` régions, résultat manifold ;
- `welded_nonmanifold_edges=0` ;
- `welded_nonmanifold_vertices=0`.

Un test minimal supplémentaire couvre un trou triangulaire tangent par un sommet à un bord extérieur droit. Un test de round-trip vérifie également que la désérialisation ne fragmente plus un arc authored.
