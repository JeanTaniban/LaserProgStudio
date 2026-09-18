# LaserProg v179 — Plan Tracer Performance Safety Verification

## Vérification v179

Cette passe ne modifie pas les algorithmes de production de v178. Elle ajoute des tests de non-régression ciblés pour verrouiller les optimisations de performance :

- suppression rapide d’une face générée suivie d’un Apply immédiat ;
- suppression d’une arête structurelle, recompilation, conservation stricte d’une région distante puis Apply ;
- validation `geometric_manifold_v2` des volumes obtenus ;
- vérification que le clone optimisé d’historique n’aliasse ni metadata de face ni style de dimension.

Les sorties contrôlées doivent rester fermées et avoir zéro arête frontière/non-manifold, zéro sommet non-manifold et zéro triangle effondré/dupliqué après soudure géométrique.

---

# LaserProg v178 — Plan Tracer Interaction Performance

## Performance v178

Cette version ajoute une passe de performance ciblée sur les interactions Plan Tracer qui devenaient lentes sur les grands dessins : **hover des faces** et **suppression**.

Principaux changements :

- index spatial écran pour le hit-test des faces/éléments au lieu de reprojeter toute la scène à chaque `MouseMove` ;
- indexation indépendante des trous de faces/motifs ;
- Smart Snap Modify limité aux cibles locales pendant le hover, tout en conservant le Smart Snap complet pendant le drag ;
- snapshots d'historique beaucoup moins coûteux ;
- suppression d'une face générée sans recompilation topologique inutile ;
- broad-phases spatiales dans le compilateur pour éviter les passages quadratiques point-point, ligne-ligne et ligne-point.

Mesures synthétiques représentatives :

- hit-test 10 000 faces : ~42,5 ms → ~0,08 ms après construction de l'index ;
- synchronisation visuelle du hover sur 10 000 faces : ~3,1 ms → ~0,0024 ms ;
- face avec 5 000 trous : ~14,9 ms → ~0,005 ms ;
- clone d'un sketch ~4 000 points + 4 000 lignes : ~53 ms → ~2,3 ms ;
- recompilation après suppression structurelle sur 100 rectangles : ~194 ms → ~17,5 ms.

La géométrie du nouveau compilateur a été comparée à v177 sur 30 sketches aléatoires d'intersections : **30/30 résultats identiques**. La suite ciblée v178 donne **50/50 tests réussis**.

Voir `docs/plan_tracer_interaction_performance_v178.md` pour l'analyse détaillée.

---

## Héritage v177 — Motif paramétrique

## Objectif

Cette version refond le comportement de **Pattern / Motif** dans Plan Tracer 2D.

Le principe devient strict :

> Un motif est un modificateur paramétrique attaché à une face Plan Tracer. Il ne doit jamais convertir le motif en milliers de points/lignes persistants dans le sketch maître.

Cette correction vise les symptômes suivants :

- plusieurs motifs qui s'empilent sur une même face ;
- `Back` qui laisse malgré tout un motif appliqué ;
- réouverture d'un sketch qui devient très lente ;
- accumulation de lignes `plan_trace_2d.pattern.material_boundary` ;
- ouvertures natives qui disparaissent ou deviennent des faces fermées ;
- comportement incorrect sur des faces contenant des arcs ou des cercles.

## Architecture du motif

Une face possède désormais au plus **une définition paramétrique compacte** :

- type de motif ;
- pas / `cell_size` ;
- épaisseur / `wall` ;
- marge ;
- angle ;
- aspect ;
- seed ;
- offsets X/Y.

Les polygones d'ouvertures sont un **cache dérivé**. Ils sont régénérés à partir de la face et de cette définition.

Le motif ne crée plus de géométrie d'auteur dans le sketch pendant le workflow normal :

- pas de nouveaux `SketchPoint` persistants ;
- pas de nouveaux `SketchLine` persistants ;
- pas de conversion destructrice de la face en « material boundary ».

L'ancien `keep_form=False` est conservé uniquement pour compatibilité des presets/sources, mais le résultat reste toujours attaché à la face.

## Un seul motif par face

Lorsqu'un motif existe déjà sur une face :

- l'éditeur recharge ses paramètres ;
- le nouveau `Apply` remplace l'ancienne définition ;
- aucune seconde couche de motif n'est créée ;
- les points/lignes du sketch ne grossissent pas.

Les motifs multi-faces gardent une définition de groupe compacte et restent alignés globalement.

## Correction de Back / Cancel

Le preview différé du motif utilisait un timer. Une callback ancienne pouvait encore s'exécuter après `Back` et réinjecter le motif dans le sketch restauré.

La fermeture fait désormais dans cet ordre :

1. fermeture logique de l'overlay ;
2. invalidation de la génération de preview ;
3. suppression de l'état `pending` ;
4. restauration du snapshot ;
5. nettoyage des transients.

Une callback ancienne devient donc inopérante.

## Conservation des trous natifs

Correction importante : les versions précédentes pouvaient remplacer `face.hole_polygons` entièrement par les trous du motif.

Cela pouvait fermer une ouverture qui existait déjà dans le sketch, par exemple :

- cercle intérieur ;
- anneau ;
- découpe créée avec des lignes ;
- trou dont la frontière contient un arc.

v177 distingue maintenant :

- **trous natifs** : appartenant au sketch / à la topologie de la face ;
- **trous motif** : géométrie dérivée du modificateur Pattern.

Les trous motif sont ajoutés aux trous natifs, jamais à leur place. Les `hole_boundary_entity_ids` des ouvertures natives sont conservés.

## Arcs et cercles

La correction a été vérifiée sur :

- face circulaire complète ;
- anneau avec cercle extérieur + trou circulaire natif ;
- rectangle séparé en deux faces par **un même arc partagé** ;
- motif appliqué sur une seule des deux faces partageant cet arc ;
- recompilation complète du sketch après motif ;
- génération du solide 3D final.

Les entités `SketchCircle` et `SketchArc` restent inchangées. Le motif travaille sur la représentation de face dérivée et ne transforme pas la courbe en lignework persistant.

## Contacts avec le bord

Un trou de face doit être strictement intérieur. Une cellule de motif qui touche exactement le contour extérieur peut produire une topologie 2D/3D ambiguë.

Même avec une marge utilisateur à zéro, les ouvertures face-owned reçoivent un dégagement interne microscopique de `1e-4 mm` (0,1 µm). Cette valeur est invisible à l'échelle d'usinage mais évite les anneaux partageant exactement un bord avec le contour extérieur.

## Editable source / Draft

Les sources Plan Tracer et les drafts sauvegardent maintenant la définition compacte du motif dans :

`editable_source["motifs"]`

La géométrie dérivée du motif n'est pas sérialisée sous forme de points/lignes.

À la réouverture :

1. le sketch d'origine est désérialisé ;
2. les faces sont recompilées avec la politique Plan Tracer non destructive ;
3. les assignments motif sont chargés ;
4. les ouvertures sont régénérées sur les faces correspondantes.

## Validation

Tests ciblés v177 : **95 réussis**.

Ils couvrent notamment :

- preview et overlay Motif ;
- `Back` avec preview différé ;
- remplacement d'un motif existant ;
- absence de croissance points/lignes ;
- zero-margin ;
- motifs sur faces irrégulières ;
- motifs multi-faces ;
- génération de mesh ;
- cercle complet ;
- arc partagé entre deux faces ;
- anneau avec trou circulaire natif ;
- conservation des `hole_boundary_entity_ids` ;
- contrat `geometric_manifold_v2` sur les solides courbes testés ;
- sérialisation compacte de la définition du motif.

Le premier échec rencontré dans la suite globale complète est également présent dans v176 (`test_pass1013_native_translate_gizmo_resizes_live_without_redeclaration`) et concerne le gizmo natif de transformation, sans lien avec Plan Tracer Motif.
