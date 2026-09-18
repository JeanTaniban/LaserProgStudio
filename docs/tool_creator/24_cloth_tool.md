# Cloth — traceur textile 3D et patron aplati

## État d’implémentation — v119

Cloth est intégré comme un véritable outil Creator de LaserProg. La v119 transforme le traceur 3D libre en outil de production rapide : les faces apparaissent dès qu’une frontière sûre se ferme, le curseur utilise directement l’API publique Plan 2D de Plan Tracer, et les snaps sont évalués localement autour de la souris.

Fonctions livrées :

- barre d’outils compacte dans le viewport ;
- modes Point, Line, Polyline, Arc, Modify, Face, Mesh trace et Fold / Cut ;
- premier clic utilisable immédiatement, sans sélectionner de face ou de plan ;
- smart snap sur les sommets, arêtes et surfaces des objets visibles de la scène ;
- snaps Cloth sur sommet, arête, milieu, intersection et centre d’arc ;
- guides X/Y/Z, prolongement du segment précédent et perpendiculaire ;
- curseur, symbole et libellé provenant de la même API Plan 2D que Plan Tracer 2D ;
- utilisation directe de la profondeur d’une surface située sous le curseur ;
- placement dans le vide sur un plan de profondeur temporaire orienté caméra ;
- création automatique d’une face dès qu’une polyligne ou un réseau de lignes/arcs ferme une boucle sûre ;
- mode **Face repair** conservé uniquement pour les boucles ambiguës ou historiques ;
- conversion d’une boucle 3D non plane en panneaux triangulaires plans ;
- plis droits entre panneaux voisins ;
- preview du patron plat ;
- Apply transactionnel vers la scène 3D et une scène de patron liée ;
- réédition par survol jaune et clic sur une ancienne sortie Cloth ;
- Cancel non destructif.

Cloth génère toujours des **surfaces sans épaisseur**. Il ne génère jamais de volume fermé.

## 1. Finalité

Cloth sert à dessiner dans l’espace :

- l’encombrement d’un textile ;
- ses faces ou panneaux ;
- ses bords libres ;
- ses pliures ;
- le patron aplati correspondant.

La V1 n’est pas un simulateur physique. Elle ne calcule pas la gravité, l’élasticité, le frottement ou les collisions. L’utilisateur décrit directement la géométrie voulue.

## 2. Modèle géométrique

### 2.1 Surface globale 3D, faces locales planes

Le document peut être globalement tridimensionnel. Chaque panneau reste toutefois plan afin de permettre un patron exact sans étirement.

Une boucle fermée :

- coplanaire devient un panneau unique ;
- non plane est triangulée en plusieurs panneaux plans ;
- les diagonales internes deviennent des plis neutres ;
- les points 3D placés par l’utilisateur sont conservés.

Cette représentation permet de dessiner une surface courbée ou cassée dans l’espace tout en conservant un dépliage rigide.

### 2.2 Courbes V1

- Point de construction ;
- segment ;
- polyligne ouverte ;
- polyligne fermée ;
- arc circulaire à trois points.

Limites V1 :

- pas de spline ;
- pas de cercle ou rectangle paramétrique ;
- pas de trous dans un panneau ;
- pas de pliure courbe continue ;
- pas de solveur de tissu.

## 3. Résolution d’un clic dans l’espace

Un curseur 2D ne définit pas à lui seul une profondeur 3D. Cloth utilise donc une règle déterministe :

1. smart snap sur un point ou une arête Cloth ;
2. smart snap sur un sommet ou une arête de mesh visible ;
3. point exact sur la surface de mesh située sous le curseur ;
4. dans le vide, intersection avec un plan temporaire orienté caméra et passant par le dernier point ;
5. pour le premier point dans le vide, même principe autour de la cible caméra.

Ce plan temporaire :

- n’apparaît pas comme une étape UX ;
- ne verrouille pas le document ;
- n’est pas sérialisé ;
- sert seulement à résoudre la profondeur du clic.

L’utilisateur peut orbiter entre deux clics pour changer la direction du prochain segment.

## 4. Interface utilisateur

### 4.1 Barre de commandes

La barre du viewport reprend le ruban compact de Plan Tracer :

- **Select** : Modify ;
- **Draw** : Point, Line, Polyline, Arc ;
- **Build** : Face repair, Fold ;
- **Output** : Flat preview, Apply ;
- **Session** : Reset, Close.

Elle contient seulement deux informations textuelles :

- le mode actif ;
- un statut court.

Les longues explications, compteurs et états internes ne sont plus empilés dans la fenêtre flottante.

### 4.2 Inspecteur

L’inspecteur contient uniquement des réglages persistants :

- Smart snap ;
- tolérance de snap ;
- guides d’axe, prolongement et perpendiculaire ;
- angle et rayon nominal du pli sélectionné ;
- espacement entre les composants découpés du patron ;
- nom des sorties.

Le réglage de pli est caché tant que Fold n’est pas actif. La tolérance est cachée lorsque Smart snap est désactivé.

### 4.3 Contrat souris

- clic court : action Cloth ;
- léger tremblement inférieur au seuil : reste un clic ;
- glisser dans le vide : orbit/pan caméra ;
- glisser un point libre en Modify : édition locale ;
- Escape : annule d’abord la primitive ou le drag actif.

## 5. Machine d’état

### 5.1 Workflow global

```text
OPENING
  ├─ clic ancien Cloth ─────> EDITING / réédition
  ├─ clic dans la scène ────> EDITING / premier point
  ├─ choix d’un outil ──────> EDITING
  └─ Close ─────────────────> CANCELLED

EDITING
  ├─ dessin / modification / face / pli
  ├─ Flat preview ──────────> FLAT_PREVIEW
  ├─ Apply ─────────────────> APPLY_READY -> APPLIED
  └─ Close ─────────────────> CANCELLED

FLAT_PREVIEW
  ├─ Back / nouveau mode ───> EDITING
  ├─ Apply ─────────────────> APPLIED
  └─ Close ─────────────────> CANCELLED
```

Phases de domaine :

- `OPENING` ;
- `EDITING` ;
- `VALIDATION_BLOCKED` ;
- `FLAT_PREVIEW` ;
- `APPLY_READY` ;
- `APPLIED` ;
- `CANCELLED`.

L’ancien état `PICK_PLANE` reste seulement dans l’énumération pour la compatibilité des anciennes sessions et macros. Les nouvelles sessions ne l’utilisent jamais.

### 5.2 Machine de primitive

La machine partagée `TraceDraftMachine` gère seulement la séquence de points :

- Point : 1 clic ;
- Line : 2 clics ;
- Arc : départ, arrivée, contrôle ;
- Polyline : clics successifs ;
- Enter/double-clic : terminer ouverte ;
- clic sur le premier point ou **Close face** : fermer et créer une face ;
- Escape : annuler la primitive courante.

Elle ne connaît ni Qt, ni VTK, ni le document Cloth.

## 6. Création des faces

### 6.1 Création automatique

La fermeture d’une frontière déclenche immédiatement la recherche de la plus petite boucle sûre contenant la dernière courbe. Cela fonctionne pour une polyligne fermée, mais aussi pour des lignes ou arcs indépendants qui se rejoignent. Une boucle déjà matérialisée n’est pas dupliquée et une arête déjà utilisée par deux panneaux est exclue.

Une frontière contenant au moins trois points produit :

- boucle plane : un panneau ;
- boucle non plane : triangulation en panneaux plans ;
- création automatique des plis internes partagés.

### 6.2 Réparation manuelle

Le mode **Face repair** permet de sélectionner une boucle connectée lorsque la création automatique refuse volontairement une situation ambiguë.

Pour une boucle de lignes :

- les lignes sont ordonnées topologiquement ;
- une boucle non plane utilise le même service de triangulation que la polyligne fermée ;
- aucun plan caché n’est réintroduit.

Les boucles contenant des arcs restent localement planes en V1.

## 7. Pliures et découpes de patron

Le sous-outil **Fold** ouvre un overlay contextuel dédié. Une arête partagée par deux panneaux peut recevoir l’un des rôles suivants :

- **Fold** : les panneaux restent reliés dans le graphe de dépliage ; l’arête droite possède un angle signé entre -180° et 180° et un rayon nominal ;
- **Cut** : les panneaux restent joints dans la surface 3D, mais sont séparés dans le patron aplati.

La modification est prévisualisée immédiatement, mais reste transactionnelle jusqu’à **Apply edge**. **Clear**, Escape ou un changement d’outil restaure l’état précédent. **Done** retourne dans Modify.

Le bouton **Fix cycles** analyse le graphe des panneaux et transforme uniquement les plis qui ferment des cycles en découpes. Un cube peut ainsi conserver un volume 3D fermé tout en produisant un patron dépliable. Les arêtes courbes peuvent être découpées, mais ne peuvent pas servir de charnière rigide dans le modèle actuel.

Les sommets partagés par plusieurs panneaux sont verrouillés en Modify. Leur déplacement nécessiterait un solveur multi-plan et ne doit pas rendre la topologie incohérente silencieusement.

## 8. Patron aplati et Apply

Apply réalise une transaction liée :

1. validation topologique ;
2. génération du mesh de surface 3D ;
3. sérialisation du document Cloth dans ses métadonnées ;
4. dépliage rigide des panneaux ;
5. création ou mise à jour de la scène `Cloth · Flat pattern` ;
6. génération du mesh plat ;
7. liaison des deux sorties ;
8. rollback des deux sorties en cas d’échec.

Le mesh 3D et le mesh plat :

- sont composés uniquement de triangles de surface ;
- possèdent la même topologie ;
- conservent les longueurs de bord ;
- ne contiennent aucune face latérale ni épaisseur.

## 9. Validation

Apply est bloqué pour :

- aucun panneau ;
- boucle ouverte ou dégénérée ;
- auto-intersection ;
- arc dégénéré ;
- trou non pris en charge ;
- bord non manifold ;
- pli invalide ;
- cycle fermé de plis non pris en charge ;
- triangulation ou dépliage impossible.

Le premier message bloquant est affiché dans la barre de statut sous une forme raccourcie ; le message complet reste disponible dans le statut de l’outil.

## 10. Performances interactives

- le mesh de surface est mis en cache par révision du document ;
- un mouvement de curseur ne reconstruit ni les panneaux ni la triangulation ;
- les courbes et faces statiques ne sont resynchronisées que lorsqu’elles changent ;
- le curseur suit le chemin rapide `position_only` de l’API Plan 2D ;
- les cibles Cloth sont mises en cache puis filtrées spatialement autour du pointeur avant les calculs de milieu et d’intersection ;
- le nombre de cibles sémantiques traitées pendant un mouvement est borné.

## 11. Architecture

```text
laserprog_studio/tool_core/tracing/
    modes.py
    draft.py
    curves.py
    planes.py

laserprog_studio/tooling/cloth/
    models.py
    topology.py
    validation.py
    flattening.py
    mesh_builder.py
    serialization.py
    output.py
    state_machine.py
    interaction.py
    free_space.py
    surface_creation.py
    auto_faces.py
    drawing.py
    fold_ops.py
    picking.py
    rendering.py
    point_edit.py
    panel.py
    workflow_overlay.py
```

Responsabilités :

- `free_space.py` : profondeur, surface et smart snap ;
- `surface_creation.py` : planification d’une boucle fermée 3D ;
- `auto_faces.py` : découverte topologique des boucles nouvellement fermées ;
- `drawing.py` : matérialisation des primitives et déclenchement des faces automatiques ;
- `models.py` et `topology.py` : document sans dépendance UI ;
- `flattening.py` : patron rigide ;
- `rendering.py` : overlays incrémentaux et curseur public Plan 2D ;
- `cloth_tool.py` : cycle Creator et routage, sans algorithmes géométriques.

Le noyau de tracé partagé reste neutre. Cloth consomme les APIs publiques `tool_api.tracing`, `tool_api.snap` et `tool_api.plan2d`. Aucun fichier source de Plan Tracer 2D n’a été modifié dans la v119.

## 12. Tests v119

Couverture dédiée :

- ouverture sans plan et Polyline actif par défaut ;
- Line, Polyline et Arc dans le viewport ;
- face automatique après fermeture de trois lignes indépendantes ;
- face automatique après fermeture d’une boucle arc + ligne ;
- boucle 3D non plane transformée en panneaux plans avec plis internes ;
- milieu, intersection, centre d’arc et guides de construction ;
- curseur officiel Plan 2D et style sémantique ;
- absence de reconstruction du mesh pendant les mouvements du curseur ;
- command deck compact et Face repair secondaire ;
- hover/réédition, preview et Apply multi-scène ;
- validation, sérialisation et caches.

Résultats : **46 tests Cloth ciblés réussis**. Un groupe représentatif de **18 tests Plan Tracer 2D réussit intégralement**, et le diff de ses fichiers source est vide.

## 13. Limites et suites possibles

- splines 3D ;
- cercles et rectangles ;
- détection automatique de toutes les faces d’un graphe arbitraire ;
- trous ;
- coutures et marges ;
- crans et direction du fil ;
- pliures courbes ;
- détection des recouvrements du patron ;
- export 2D ;
- simulation physique séparée du patron exact.
