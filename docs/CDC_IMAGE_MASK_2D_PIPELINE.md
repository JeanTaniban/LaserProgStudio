# CDC — Pipeline Masque 2D

Statut : **en cours de validation**
Branche de travail : `leane/fix-mask-2d-subpixel`

Ce document est le CDC spécialisé du pipeline :

`Image raster → masque 2D → contour vectoriel → lissage → solide 3D`.

Il complète le CDC global d’intégrité géométrique. Le CDC global reste la source des contrats communs de solidité, Manifold, mutation et persistance.

---

## 1. Objectifs

Le masque 2D doit :

- produire un contour visuellement lisse à partir d’un PNG/JPG/BMP ;
- exploiter l’anti-aliasing de l’image au lieu de suivre les cases du raster ;
- préserver trous, îlots, traits fins et séparations ;
- ne jamais produire silencieusement un solide topologiquement différent du footprint validé ;
- produire un solide directement certifiable par le moteur Manifold ;
- conserver une taille physique indépendante de la résolution de calcul ;
- garder le preview interactif ;
- permettre une qualité supérieure lors de l’Apply sans changer la taille de la pièce.

---

## 2. Défauts reproduits

### 2.1 Contour en marches d’escalier

Ancien chemin :

```text
pixels actifs
→ rectangles axis-aligned
→ unary_union
→ contour quantifié sur les bords de pixels
→ simplify/buffer
→ mesh 3D
```

Le défaut est structurel : une fois le contour converti en cases pleines, l’information sub-pixel du bord original est perdue.

Mesure sur un cercle anti-aliasé 160×160, rayon nominal 60 px :

| pipeline | fraction axis-aligned | erreur radiale RMS | périmètre |
|---|---:|---:|---:|
| ancien brut | 100 % | ~0,438 px | ~480 px |
| nouveau brut sub-pixel | ~2,64 % | ~0,171 px | ~378,69 px |
| cercle analytique | — | 0 | ~376,99 px |

Conclusion : le problème principal n’était pas l’absence de lissage mais la mauvaise primitive de vectorisation.

### 2.2 Lissage destructif

Fixture contenant traits fins + anneau/trous :

- ancien `Smooth=0` : 4 trous, aire 812 ;
- ancien `Smooth=75/100` : 3 trous, aire ~1221,5 ;
- le lissage supprimait donc réellement une cavité.

Nouveau pipeline :

- 4 trous conservés jusqu’à `Smooth=100` ;
- sortie Shapely valide ;
- sortie 3D fermée ;
- Manifold direct `NoError`.

### 2.3 Extrudeur privé du masque

L’ancien masque binaire reconstruisait lui-même :

- cap supérieur ;
- cap inférieur ;
- walls ;
- orientation des trous ;
- déduplication des sommets ;
- exception `boolean_skip_merge`.

Cette duplication de logique divergeait du chemin Plan Tracer.

Décision : le masque 2D ne fabrique plus directement un mesh 3D. Il fournit un footprint commun au générateur planar.

### 2.4 Résolution et taille physique mélangées

L’ancien `max_grid_size` avait deux effets :

- réduction du nombre d’échantillons ;
- changement implicite de la taille physique, puisque `pixel_size_mm` était appliqué après downsampling.

Ce couplage est interdit dans l’architecture cible.

---

## 3. Architecture cible

```text
Image source RGBA
        │
        ▼
Composition fond / alpha
        │
        ▼
Champ d'activité continu 0..255
        │
        ▼
Sélection du seuil
        │
        ▼
Marching squares sub-pixel
        │
        ▼
PlanarFootprint brut
        │
        ▼
Validation topologique 2D
        │
        ▼
Lissage contrôlé
        │
        ▼
PlanarFootprint final
        │
        ├──► preview rasterisé
        │
        ▼
PlanarRegion
        │
        ▼
extrude_planar_regions_boolean_ready()
        │
        ▼
WorkMesh DIRECT_CERTIFIED
        │
        ▼
GeometryIntegrityService
        │
        ▼
Commit scène
```

Règle : le raster ne produit jamais directement des triangles 3D.

---

## 4. Contrats de données

### 4.1 RasterActivityField

Responsable de :

- dimensions source ;
- dimensions de la grille d’analyse ;
- champ scalaire matériau 0..255 ;
- seuil ;
- orientation image ;
- alpha composite ;
- ratio physique.

Il ne contient aucune géométrie 3D.

### 4.2 BinaryMaskFootprint

Doit exposer au minimum :

```python
BinaryMaskFootprint(
    geometry,
    source_size,
    width,
    height,
    active_pixels,
    downsampled,
    threshold,
    step_x_mm,
    step_y_mm,
    physical_width_mm,
    physical_height_mm,
)
```

Évolution cible :

- `source_fingerprint` ;
- `contour_contract_version` ;
- `topology_signature` ;
- `quality_level` ;
- `smoothing_report`.

### 4.3 SmoothingReport

À introduire :

```python
SmoothingReport(
    requested_level,
    accepted_level,
    source_components,
    result_components,
    source_holes,
    result_holes,
    source_area,
    result_area,
    symmetric_difference_area,
    hausdorff_distance,
    source_vertices,
    result_vertices,
    fallback_used,
)
```

L’UI pourra ainsi indiquer qu’un `Smooth=100` a été volontairement réduit pour préserver la forme.

---

## 5. Chargement image

### 5.1 Alpha

Un fond transparent doit être considéré comme vide par défaut.

Le pipeline actuel compose les RGBA sur blanc avant conversion grayscale. Cette convention est conservée.

### 5.2 Invert

`Invert=False` :

- noir = matériau ;
- blanc = vide.

`Invert=True` inverse cette relation.

### 5.3 JPG

Le JPEG introduit du bruit et des halos de compression.

Le seuil et le nettoyage doivent rester séparés :

- `Levels` décide matériau/vide ;
- `Smooth` agit sur la géométrie du contour ;
- un futur `Cleanup / Minimum feature` devra traiter le bruit et les micro-îlots.

Il est interdit d’utiliser Smooth comme filtre anti-bruit implicite.

---

## 6. Seuil Levels

### 6.1 Mode automatique

`Levels=50` utilise Otsu avec une règle déterministe de plateau.

Otsu peut produire une plage entière de seuils ayant exactement le même score,
notamment sur un masque noir/blanc pur. Il est interdit de choisir arbitrairement
le premier seuil optimal.

Règle :

- détecter le plateau optimal ;
- choisir son milieu ;
- cas noir/blanc 0/255 : index Otsu attendu ≈ 127 ;
- iso-niveau continu utilisé par le contour : **127,5**.

Otsu sépare les bins `<= t` et `> t`. Le contour continu doit donc être placé
entre les bins `t` et `t+1`, soit `t + 0,5`. Utiliser directement `t`
réintroduit un biais topologique : un damier diagonal peut se connecter alors
qu'il doit rester séparé.

### 6.2 Déplacement utilisateur

Le slider déplace le seuil autour du niveau automatique.

Le sens UX est conservé :

- valeur basse = sélection stricte ;
- valeur haute = conserve davantage de matière faible.

### 6.3 Contrat

Le seuil doit rester une valeur scalaire continue utilisée par :

- extraction du contour ;
- résolution des cellules ambiguës ;
- classification des faces polygonisées.

Une étape ne doit jamais retransformer le champ en booléens puis tenter de reconstruire les positions de bord.

---

## 7. Marching squares

### 7.1 Interpolation

Chaque intersection d’iso-contour est interpolée linéairement sur l’arête de cellule.

### 7.2 Cellules 5/10

Les cas selle 5 et 10 utilisent un **asymptotic decider bilinéaire**.

Pour :

```text
TL  TR
BL  BR
```

avec les valeurs centrées autour du seuil :

```text
Q = TL * BR - TR * BL
```

Le signe de `Q` décide la connectivité.

La moyenne arithmétique des quatre coins est interdite : elle peut donner une topologie différente de celle du champ bilinéaire réel.

### 7.3 Égalité exacte

En cas de selle exactement au seuil, les deux composantes qui se touchent seulement en un point restent séparées.

Objectif :

- éviter les bow-tie vertices ;
- éviter la création d’un pont de matière artificiel ;
- rester compatible avec le contrat Manifold.

### 7.4 Classification des faces

Après polygonisation, matériau/vide doit être déterminé en rééchantillonnant **le même champ bilinéaire continu**.

La classification par pixel le plus proche est interdite.

---

## 8. Normalisation 2D

Après extraction :

1. polygoniser les segments ;
2. sélectionner les faces matériau ;
3. unionner les faces matériau ;
4. intersecter avec le rectangle physique de l’image ;
5. `make_valid` si nécessaire ;
6. supprimer les restes non polygonaux ;
7. vérifier surface > 0.

Aucune reconstruction 3D n’intervient à ce stade.

---

## 9. Lissage

### 9.1 Principe

Smooth simplifie le footprint sub-pixel.

Il ne modifie jamais un WorkMesh.

### 9.2 Invariants obligatoires

Un candidat est refusé si l’un de ces invariants est cassé :

- géométrie Shapely valide ;
- nombre de composantes identique ;
- nombre de trous identique ;
- signature composantes/trous identique ;
- **correspondance spatiale** des composantes conservée ;
- **correspondance spatiale** des cavités conservée ;
- aire dans le budget ;
- symmetric difference dans le budget ;
- Hausdorff distance dans le budget.

La correspondance spatiale empêche un faux positif du type :

```text
1 trou avant
1 trou après
```

alors que le trou d’origine a disparu et qu’un nouveau trou est apparu ailleurs.

Chaque composante et chaque trou utilisent des representative points croisés entre référence et candidat.

### 9.3 Backoff

Le slider indique une agressivité demandée.

L’algorithme essaye :

```text
100 %
→ 75 %
→ 50 %
→ 25 %
→ footprint brut
```

et accepte le premier candidat sûr.

Un résultat moins lissé est préférable à une forme modifiée.

### 9.4 Future protection des features fines

À ajouter au profil `manufacturing` :

- minimum feature width ;
- minimum hole diameter ;
- longueur minimale de branche ;
- contrôle des cols/isthmes.

Ces critères doivent être exprimés en millimètres, pas en pixels.

---

## 10. Taille physique

### 10.1 Règle fondamentale

La **résolution d’analyse** et la **dimension physique** sont deux paramètres indépendants.

Changer :

- preview 512 → 256 ;
- Apply 512 → 1024 ;
- backend ;
- simplification ;

ne doit jamais modifier les bounds physiques de la pièce.

### 10.2 UX cible

Le dialogue doit exposer :

- `Largeur (mm)` ;
- verrouillage du ratio ;
- hauteur calculée automatiquement ;
- éventuellement `Hauteur (mm)` si ratio déverrouillé.

Le pixel count source n’est pas une unité mécanique.

### 10.3 Compatibilité

Avant activation de cette UI, ne pas figer silencieusement un nouveau contrat `1 pixel source = 1 mm` pour les grosses images.

Le comportement historique doit être documenté puis migré explicitement.

Décision de migration recommandée :

- calculer une taille physique initiale compatible avec l’ancienne importation ;
- stocker cette taille dans le document/import request ;
- ensuite permettre 512/1024/2048 échantillons sans modifier cette taille.

Comportement historique du dialogue utilisateur :

```text
legacy_scale = min(1, 512 / max(source_width_px, source_height_px))
legacy_width_mm  = source_width_px  * legacy_scale * pixel_size_mm
legacy_height_mm = source_height_px * legacy_scale * pixel_size_mm
```

avec `pixel_size_mm=1` par défaut.

Exemple historique :

- source 2048×1024 → grille 512×256 → environ **512×256 mm** ;
- la branche sub-pixel, si elle applique naïvement 1 mm au pixel source, donnerait **2048×1024 mm**.

Ce changement ×4 est incompatible avec une migration silencieuse. Le futur
`MaskPhysicalSize` doit préserver la taille historique par défaut puis laisser
l’utilisateur saisir explicitement sa largeur mécanique.

---

## 11. Résolution

Mesure sur source 2048×1024, fixture simple :

| grille max | Linux footprint | Linux solide | Windows footprint | Windows solide |
|---:|---:|---:|---:|---:|
| 256 | ~83 ms | ~86 ms | ~93 ms | ~95 ms |
| 512 | ~206 ms | ~212 ms | ~227 ms | ~246 ms |
| 1024 | ~696 ms | ~707 ms | ~751 ms | ~866 ms |

Ces chiffres sont des probes CI et non des garanties hardware client.


### 11.0.1 Corpus complexe

Fixture `2048×1024` avec une grande région, **66 trous** et de nombreux bords.

Mesures Windows avant cache exact :

| grille | footprint froid | solide froid | ring vertices | triangles | trous |
|---:|---:|---:|---:|---:|---:|
| 512 | ~422,6 ms | ~535,6 ms | 1204 | 5076 | 66 |
| 1024 | ~1677,2 ms | ~1842,1 ms | 1964 | 8116 | 66 |

Les deux sorties sont Manifold `NoError`.

Après ajout des caches activité + contour brut + footprint lissé, nouvelle mesure Windows :

| grille | footprint froid | Smooth warm différent | Apply warm exact | triangles |
|---:|---:|---:|---:|---:|
| 512 | ~836 ms | ~322 ms | **~132 ms** | 5076 |
| 1024 | ~3106 ms | ~877 ms | ~194 ms | 8116 |

Les valeurs froides varient avec la charge CI et les contrôles supplémentaires, mais le point important est le chemin utilisateur :

```text
preview calculé
→ utilisateur valide sans changer les paramètres
→ Apply réutilise le footprint exact
```

Sur un cercle simple 512 :

- footprint froid ~257 ms ;
- Smooth warm ~8 ms ;
- Apply warm exact ~6 ms.

Un JPEG bruité modéré reste une seule composante :

- 512 : ~236 ms de footprint froid ;
- 1024 : ~877 ms.

Décision : 512 offre le meilleur compromis Standard. 1024 doit rester une option de précision explicite.

### 11.1 Preview

Cible :

- grille rapide : 512 max ;
- calcul hors UI thread ;
- debounce ;
- abandon du résultat si les paramètres ont changé entre-temps.

Budget visé :

- < 250 ms sur fixture simple 2048×1024 ;
- aucun blocage prolongé de la fenêtre.

### 11.2 Apply

Décision actuelle :

- **512 = Standard**, valeur par défaut ;
- **1024 = High precision** futur et explicite ;
- 2048 non retenu sans besoin métier et benchmark complémentaire.

Le Standard privilégie :

- WYSIWYG strict avec le preview ;
- réutilisation du contour brut caché ;
- latence courte ;
- topologie identique aux tests validés.

Le mode High precision devra être asynchrone et afficher son coût estimé si la complexité est élevée.


### 11.3 Résolution mécanique

La qualité ne doit pas être décrite uniquement par `max_grid_size`.

Pour une largeur physique `W_mm` et une grille `N` :

```text
sample_step_mm = W_mm / N
```

Exemples Standard 512 :

- pièce 512 mm → ~1,0 mm / sample ;
- pièce 256 mm → ~0,5 mm / sample ;
- pièce 100 mm → ~0,195 mm / sample ;
- pièce 50 mm → ~0,098 mm / sample.

Le dialogue futur doit pouvoir afficher :

`Résolution effective : ~0,20 mm`

et avertir si une feature détectée est proche ou sous la résolution disponible.

Le mode High precision 1024 est justifié par un besoin **mécanique** de résolution, pas par la taille pixel du fichier source seule.

---

## 12. Preview

Le preview doit représenter le même **contrat géométrique** que l’Apply.

Deux niveaux sont autorisés :

### Preview rapide

- résolution inférieure ;
- même seuil ;
- même algorithme ;
- même taille physique ;
- affiché immédiatement.

### Preview final

Après debounce/idle :

- résolution de l’Apply ;
- calcul asynchrone ;
- remplace le preview rapide.

L’UI peut indiquer :

- `Aperçu rapide` ;
- puis `Aperçu haute précision`.

Ainsi, l’utilisateur ne valide pas une forme dont les petits trous apparaîtront seulement à l’Apply.

---

## 13. Cache

Le pipeline est naturellement cacheable.

Clé minimale :

```text
source fingerprint
+ invert
+ levels
+ smooth
+ target physical size
+ analysis resolution
+ contour contract version
```

Niveaux de cache :

1. image grayscale/activité ;
2. iso-contour brut ;
3. footprint lissé ;
4. solide extrudé.

Le déplacement du slider Smooth ne doit pas recharger et redécoder l’image à chaque fois.

---

## 14. Threading

### Preview

Obligatoirement hors thread UI si le calcul dépasse le budget instantané.

Pattern :

```text
UI change
→ generation_id += 1
→ debounce
→ worker computes
→ result returns with generation_id
→ discard if stale
→ render latest only
```

### Apply

L’Apply peut utiliser le framework de tâche longue existant si :

- source complexe ;
- grille ≥ 1024 ;
- génération > seuil défini.

Le commit scène reste atomique sur le thread principal.

---

## 15. Conversion footprint → solide

Le masque ne possède aucun extrudeur 3D spécifique.

Conversion :

```text
Shapely Polygon/MultiPolygon
→ PlanarRegion[]
→ extrude_planar_regions_boolean_ready()
→ WorkMesh
```

Le générateur commun gère :

- trous ;
- composants ;
- précision ;
- zéro-clearance ;
- Manifold CrossSection ;
- fallback indexé ;
- orientation ;
- canonicalisation.

---

## 16. Contrat 3D

Sortie du masque :

```text
GeometryRole.SOLID
GeometryMutation.GENERATE
GeometryProfile.MANUFACTURING_SOLID
source = IMAGE_MASK_2D
```

Postconditions :

- mesh non vide ;
- fermé ;
- aucune arête >2-use ;
- aucun bow-tie vertex ;
- aucun triangle collapsed après weld ;
- aucun triangle dupliqué ;
- Manifold direct `NoError` ;
- aucun flag privé `boolean_skip_merge`.

---

## 17. Métadonnées

À conserver :

- source tool ;
- version du contrat contour ;
- taille source ;
- taille grille ;
- pas X/Y ;
- taille physique ;
- Levels ;
- Smooth demandé ;
- Smooth réellement accepté ;
- seuil final ;
- backend extrusion ;
- fingerprint source.

Ne pas stocker l’image entière dans le WorkMesh si le projet dispose déjà d’un asset store dédié.

---

## 18. Corpus de tests

### Formes synthétiques

- cercle anti-aliasé ;
- ellipse ;
- rectangle arrondi ;
- diagonale ;
- étoile ;
- anneau ;
- plusieurs trous ;
- plusieurs îlots ;
- composants séparés d’une fraction de pixel ;
- contact diagonal ;
- isthme 1 px ;
- isthme 2 px ;
- trait fin ;
- trou fin ;
- forme touchant le bord image.

### Images

- PNG opaque ;
- PNG transparent ;
- grayscale ;
- JPG bruité ;
- JPG faible contraste ;
- petite image ;
- 512 px ;
- 1024 px ;
- 2048 px ;
- très grand ratio panoramique/portrait.

### Paramètres

Pour chaque fixture significatif :

`Smooth = 0, 15, 35, 50, 75, 100`

et plusieurs valeurs Levels autour du seuil critique.

---

## 19. Mesures de qualité

### 2D

- validité ;
- composants ;
- trous ;
- Euler characteristic ;
- aire ;
- périmètre ;
- minimum clearance ;
- symmetric difference ;
- Hausdorff ;
- nombre de sommets ;
- fraction axis-aligned.

### Formes analytiques

Pour cercle/ellipse :

- erreur radiale RMS ;
- erreur max ;
- erreur de périmètre ;
- erreur d’aire.

### 3D

- closed ;
- boundary edges ;
- non-manifold edges ;
- non-manifold vertices ;
- collapsed triangles ;
- duplicate triangles ;
- Manifold status ;
- volume.

---

## 20. Tests fonctionnels obligatoires

Chaque solide masque de référence doit supporter :

1. import ;
2. Save/Reload ;
3. Boolean Difference ;
4. deuxième Boolean Difference ;
5. Undo/Redo ;
6. duplication ;
7. export 3MF ;
8. réimport 3MF.

Le résultat ne doit pas redevenir dépendant d’un attribut runtime privé.

---

## 21. Performance

Le budget dépend de la complexité du contour, pas seulement des pixels.

Mesurer séparément :

- décodage image ;
- resize ;
- calcul histogramme/Otsu ;
- marching squares ;
- polygonize ;
- union ;
- smooth ;
- extrusion Manifold ;
- validation.

Ajouter au probe :

- temps total ;
- nombre segments marching ;
- nombre faces polygonisées ;
- nombre polygons ;
- nombre ring vertices avant/après Smooth.

Un test performance ne doit pas échouer sur une seule durée absolue CI ; il doit surtout détecter les régressions ×2/×3 sur le même runner.

---

## 22. Gestion du bruit

Le pipeline de lissage ne doit pas supprimer les micro-composants pour « nettoyer » un JPEG.

Évolution distincte :

`MaskCleanupPolicy`

avec :

- `minimum_island_area_mm2` ;
- `minimum_hole_area_mm2` ;
- éventuellement fermeture de gaps < tolérance explicitement demandée.

Le preview doit montrer ces suppressions.

Par défaut, aucune suppression ambiguë de feature métier.

---

## 23. Erreurs utilisateur

Messages attendus :

- aucune matière détectée ;
- aucune région fermée ;
- footprint invalide ;
- feature sous la résolution disponible ;
- lissage limité pour préserver la topologie ;
- solidification impossible ;
- taille physique invalide.

Les erreurs ne doivent jamais être seulement `Manifold NotManifold`.

Le diagnostic détaillé peut rester dans les logs.

---

## 24. État d’implémentation

### Déjà implémenté sur branche

- contrat de taille physique explicite et compatible legacy ;
- preview 512 hors thread Qt avec coalescing ;
- Save/Reload, Undo/Redo et 3MF validés ;
- quality gate global Ubuntu validé ;
- marching squares sub-pixel ;
- interpolation linéaire ;
- asymptotic decider bilinéaire ;
- classification bilinéaire des faces ;
- clamp au rectangle physique ;
- lissage avec backoff ;
- conservation de la signature composants/trous ;
- extrusion via Planar Solid commun ;
- suppression du vieux vectoriseur pixel-box ;
- suppression de `boolean_skip_merge` pour le masque ;
- preview basé sur le footprint ;
- tests Manifold direct ;
- tests Boolean chaînés ;
- probe qualité Linux/Windows ;
- benchmark 256/512/1024 ;
- cache activité / contour brut / footprint lissé ;
- `MaskSmoothingReport` demandé/accepté ;
- conservation spatiale des cavités pendant Smooth.

### À faire avant merge

1. figer le contrat de taille physique ;
2. empêcher la résolution de calcul de changer les dimensions ;
3. décider 512 vs 1024 pour Apply ;
4. ajouter preview asynchrone si 1024 est retenu ;
5. enrichir le corpus JPG/faible contraste/features proches ;
6. Save/Reload + export/réimport 3MF ;
7. exécuter le quality gate global ;
8. vérifier UI réelle sous Windows.

### Après merge

- cache ;
- CleanupPolicy ;
- width/height UI ;
- preview haute précision asynchrone ;
- télémétrie locale de performance si utile.

---

## 25. Critères d’acceptation

Le chantier masque 2D est terminé lorsque :

- aucun contour n’est construit depuis une union de rectangles pixel ;
- le marching squares utilise l’asymptotic decider ;
- preview et Apply utilisent le même contrat vectoriel ;
- Smooth ne change jamais la signature topologique sans action explicite ;
- le changement de résolution ne redimensionne jamais la pièce ;
- le solide final est Manifold direct ;
- aucune exception `boolean_skip_merge` n’est requise ;
- Boolean chaînée fonctionne ;
- Save/Reload ne change pas le résultat ;
- les tests Linux et Windows sont verts ;
- le corpus réel utilisateur ne reproduit plus les dents ni la casse du lissage.

---

## 26. Non-objectifs

Ce chantier ne doit pas devenir :

- un vectoriseur SVG général ;
- un éditeur d’image ;
- un système de retouche bitmap ;
- une reconstruction photo 3D ;
- une simplification générale de mesh.

Il doit rester un pipeline fiable de conversion d’un masque raster en footprint manufacturable puis en solide.

---

## 27. Décisions verrouillées

Ces choix ne doivent plus être rediscutés sans nouvelle preuve de régression.

| sujet | décision |
|---|---|
| vectorisation | iso-contour sub-pixel, jamais union de rectangles pixel |
| ambiguïtés 5/10 | asymptotic decider bilinéaire |
| classification face | rééchantillonnage bilinéaire du même champ |
| Smooth | opération 2D uniquement |
| topologie | backoff si composants/trous changent |
| extrusion | générateur planar commun |
| kernel | sortie finale directement certifiable |
| merge hack | aucun `boolean_skip_merge` spécifique au masque |
| preview | dérivé du footprint, pas d’un pipeline parallèle |
| dimension | indépendante de la résolution d’analyse |

---

## 28. Décisions encore ouvertes

### O1 — exposition UX de la taille physique

Le **contrat interne est désormais verrouillé** :

- `MaskPhysicalSize` existe ;
- une taille explicite peut être fournie par API ;
- sans taille explicite, le dialogue conserve le comportement historique basé sur un maximum de 512 px/mm ;
- la résolution d’analyse est indépendante de cette taille ;
- le mesh persiste la largeur/hauteur physiques résolues dans ses metadata.

Reste ouvert uniquement le choix UX :

- exposer `Largeur (mm)` dans le dialogue ;
- conserver le ratio par défaut ;
- éventuellement permettre de déverrouiller largeur/hauteur.

Cette évolution UI n’est pas requise pour corriger la régression actuelle, mais le contrat de données est prêt.

### O2 — haute précision optionnelle

La résolution standard est désormais fixée à **512** pour Preview et Apply.

Raisons mesurées :

- le contour sub-pixel à 512 supprime déjà l’effet pixel-box ;
- Preview et Apply utilisent exactement la même résolution et le même contour brut ;
- le cache permet à Apply de réutiliser le travail du preview ;
- sur le fixture complexe à 66 trous, Windows :
  - 512 : ~0,42 s footprint / ~0,54 s solide à froid ;
  - 1024 : ~1,68 s footprint / ~1,84 s solide à froid ;
- les deux résolutions conservent les 66 trous et produisent Manifold `NoError`.

1024 devient donc un futur mode **High precision** explicite, jamais un changement silencieux du défaut.

### O3 — nettoyage du bruit

Ne pas introduire de suppression automatique de petits îlots dans Smooth.

Le nettoyage doit devenir un paramètre métier séparé et mesuré en mm/mm².

### O4 — arrondi réel des courbes

Le Smooth actuel est principalement un simplificateur topologiquement sûr.

Si un véritable fairing/rounding est souhaité :

- en faire une étape distincte ;
- mesurer shrink/overshoot ;
- garder les mêmes gates topologiques ;
- ne pas réintroduire un buffer morphologique destructif.

---

## 29. Work packages

### WP-A — Contour robuste

Statut : **implémenté / CI verte**

- activité continue ;
- marching squares ;
- interpolation ;
- asymptotic decider ;
- bilinear face classification ;
- clamp aux bounds ;
- tests unitaires.

Gate :

- Linux + Windows ;
- damier diagonal ;
- bord image ;
- cercle anti-aliasé.

### WP-B — Smooth sûr

Statut : **implémenté, corpus en extension**

- signature composants/trous ;
- area budget ;
- symmetric difference ;
- Hausdorff ;
- backoff.

Gate :

- trou 1 px ;
- gap 1 px ;
- trait fin ;
- anneau ;
- étoile concave.

### WP-C — Solidification commune

Statut : **implémenté / CI verte**

- PlanarRegion ;
- extrusion commune ;
- Manifold direct ;
- Boolean chaînée ;
- aucun skip-merge privé.

### WP-D — Taille physique

Statut : **implémenté / CI verte**

Livrables validés :

- `MaskPhysicalSize` ;
- migration compatible avec la taille historique ;
- séparation taille physique / résolution d’analyse ;
- metadata de taille sur le mesh ;
- tests de résolution invariants.

L’exposition width/height dans l’UI reste une amélioration produit séparée.

### WP-E — Preview / threading

Statut : **implémenté pour le profil Standard**

Déjà fait :

- debounce ;
- worker dédié au dialogue ;
- résultats obsolètes ignorés ;
- tâches en attente coalescées ;
- preview 512 calculé hors thread Qt ;
- cache LRU de l’activité raster ;
- cache WKB du contour brut avant Smooth ;
- invalidation par chemin + mtime_ns + taille fichier + paramètres de calcul.

Reste hors scope du correctif principal :

- preview High precision 1024 ;
- mesure manuelle du stall UI réel sur la machine client.

### WP-F — Interopérabilité

Statut : **implémenté / CI verte**

Validé :

- Save/Reload ;
- Undo/Redo ;
- export 3MF ;
- réimport 3MF ;
- absence de dépendance à `boolean_skip_merge`.

Le fingerprint géométrique commun reste rattaché au chantier global Geometry Integrity.

### WP-G — Corpus réel

Statut : **à faire**

Inclure plusieurs masques réels :

- logos ;
- scans ;
- captures JPG ;
- lignes fines ;
- grands formats ;
- faible contraste.

---

## 30. Gates de merge

La branche masque n’est fusionnable que si tous les gates suivants sont vrais.

### Gate G1 — algorithme

- [x] plus d’union de rectangles pixel en production ;
- [x] marching squares sub-pixel ;
- [x] asymptotic decider ;
- [x] plateau Otsu stabilisé par midpoint ;
- [x] classification bilinéaire ;
- [x] footprint borné physiquement.

### Gate G2 — topologie

- [x] trou conservé sous Smooth élevé sur fixtures actuels ;
- [x] gap entre composants conservé ;
- [x] contact diagonal non soudé ;
- [x] sortie Manifold directe.

### Gate G3 — opérations

- [x] première Boolean ;
- [x] Boolean chaînée ;
- [x] Save/Reload ;
- [x] Undo/Redo ;
- [x] export/réimport 3MF.

### Gate G4 — UX

- [x] contrat taille physique interne figé et compatible ;
- [x] résolution Standard Apply = 512 figée ;
- [x] preview et Apply utilisent le même pipeline/contrat de taille ;
- [x] preview lourd déplacé hors thread Qt ;
- [x] tâches preview obsolètes coalescées ;
- [ ] test manuel Windows : absence de lag perceptible.

### Gate G5 — qualité

- [x] tests Linux ;
- [x] tests Windows ;
- [x] corpus adversarial synthétique actuel vert ;
- [ ] corpus réel utilisateur vert ;
- [x] quality gate global du projet sur Ubuntu ;
- [x] geometry-integrity-audit vert Linux/Windows ;
- [ ] test manuel Windows sur UI réelle.

---

## 31. Règle de handoff

Tout agent reprenant ce chantier doit commencer par :

1. lire ce CDC ;
2. vérifier les derniers runs `mask-2d-audit` ;
3. ne pas réintroduire l’ancien vectoriseur pixel-box ;
4. ne pas réintroduire `boolean_skip_merge` ;
5. ajouter une fixture avant toute correction d’un nouveau cas ;
6. mettre à jour la section Gates après validation.

