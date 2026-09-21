# CDC mission — Socle commun d’intégrité géométrique

## Statut

**CDC finalisé pour implémentation — 21 septembre 2026.**

Ce document est la source de vérité de la mission sur la branche leane/geometry-integrity-foundation-cdc. Il décrit l’architecture cible, les défauts reproduits, les décisions techniques, les tests obligatoires, les budgets de performance et l’ordre de migration.

La phase d’étude est considérée comme suffisamment complète pour commencer l’implémentation. Une hypothèse peut encore être ajustée si un test reproductible la contredit, mais toute modification de contrat doit être documentée ici avant d’être généralisée.

Cette mission remplace l’approche où chaque outil implémente ses propres contrôles de mesh. Le principe retenu est un **socle géométrique commun, déclaratif et versionné**, appelé automatiquement par le runtime aux frontières où un mesh devient un résultat persistant, un opérande booléen ou un fichier de fabrication.

Le but n’est pas de rendre les outils dépendants les uns des autres. Au contraire, les outils doivent rester remplaçables, supprimables et ajoutables indépendamment.

---

## 0. Résumé exécutif

Les audits de cette mission montrent trois familles de défauts à traiter ensemble sans les confondre :

1. **Intégrité géométrique** : plusieurs outils produisent ou préparent des meshes avec des règles différentes. Des réparations locales peuvent modifier la matière, les cavités ou masquer un échec Boolean.
2. **Masque 2D** : le contour binaire actuel est quantifié sur la grille avant lissage. Cela produit des bords crénelés ; à fort lissage, des trous et détails fins peuvent disparaître. Le chemin cible est un iso-contour sub-pixel puis une extrusion planaire commune certifiée.
3. **Persistance** : les sauvegardes sérialisent trop de géométrie dupliquée, recompressent les mêmes données et le save manuel reste synchrone. L’autosave en thread réduit le blocage direct mais continue de consommer fortement CPU/GIL. La cible sépare révisions légères, blobs de géométrie, full save portable et recovery incrémental.

Les décisions structurantes sont figées :

- une frontière unique de mutation persistante : GeometryMutationGateway ;
- des rôles et profils géométriques explicites ;
- validation DIRECT avant toute adaptation ;
- aucune réparation destructive implicite ;
- ShellNestingTree comme vérité commune pour matière/cavités ;
- le masque 2D devient producteur de PlanarRegion, pas moteur d’extrusion autonome ;
- le save manuel sort du thread Qt ;
- l’autosave devient un recovery minimal ;
- les géométries persistantes sont dédupliquées par contenu ;
- le fichier utilisateur v2 reste portable et atomique ; le recovery utilise un store incrémental séparé ;
- toutes les migrations se font par jalons testables, avec observation avant enforcement lorsque le risque de régression est élevé.

La priorité produit est d’éliminer en premier les corruptions silencieuses et les blocages utilisateur, puis de généraliser le socle sans régression.

---

## 1. Objectif

Garantir qu’une même géométrie produise un diagnostic identique quel que soit l’outil qui l’a créée, et qu’aucun outil ne puisse appliquer silencieusement un solide invalide simplement parce qu’il a oublié une validation locale.

Le socle doit assurer :

- des contrôles déterministes et répétables ;
- un contrat unique de sortie des géométries ;
- une certification commune des solides ;
- un comportement cohérent entre génération, modification, Boolean, import, export et sauvegarde/rechargement ;
- une séparation stricte entre logique métier d’un outil et règles génériques d’intégrité ;
- une possibilité d’ajouter un outil sans recopier les validateurs existants ;
- une possibilité de supprimer un outil sans modifier le socle ni les autres outils.

---

## 2. Non-objectifs

Le socle commun ne doit pas :

- connaître l’interface utilisateur spécifique d’un outil ;
- décider de la forme géométrique métier attendue par un outil ;
- réparer agressivement ou supprimer silencieusement des détails ;
- forcer tous les objets à être des solides ;
- confondre plusieurs corps fermés légitimes avec de la pollution ;
- transformer une concaténation de pièces en union booléenne implicite ;
- utiliser une soudure par coordonnées comme définition universelle de la manifoldness.

---

## 3. Principe architectural

Chaque outil ne doit déclarer que son **intention géométrique**.

Le runtime commun réalise les contrôles.

Exemple conceptuel :

```python
ctx.operations.register(
    "simplify",
    self._operation,
    geometry_contract=GeometryOperationContract(
        mutation=GeometryMutation.REBUILD,
        default_output=GeometryArtifactContract(
            role=GeometryRole.SOLID,
            validation=GeometryProfile.MANUFACTURING_SOLID,
            components=ComponentPolicy.PRESERVE,
        ),
        repair=RepairPolicy.NONE,
    ),
)
```

L’outil Simplify ne contient alors aucune implémentation de :

- détection des faces dégénérées ;
- détection des sommets inutilisés ;
- analyse des composantes ;
- contrôle des arêtes frontières ;
- validation Manifold ;
- fingerprint de géométrie ;
- certification ;
- logique générique de réparation.

Il ne fait que simplifier.

Le socle commun exécute ensuite automatiquement les postconditions demandées par le contrat.

---

## 4. Nouveau vocabulaire géométrique

### 4.1 GeometryRole

Chaque mesh persistant possède un rôle explicite.

| Rôle | Signification |
|---|---|
| `UNKNOWN` | Objet legacy/importé dont le rôle n’a pas encore été qualifié |
| `SOLID` | Matière volumique fermée destinée à la fabrication et aux opérations solides |
| `SOLID_SET` | Plusieurs régions matérielles fermées légitimes dans un même WorkMesh |
| `SURFACE` | Surface volontairement ouverte |
| `VISUAL_PROXY` | Géométrie d’affichage uniquement |
| `HELPER` | Mesure, guide, gizmo ou données auxiliaires |
| `DECAL` | Géométrie ou projection visuelle non destinée aux opérations solides |

Un `VISUAL_PROXY` ou un `HELPER` ne doit jamais devenir accidentellement un opérande Boolean ou un objet de fabrication.

`ASSEMBLY` n’est finalement **pas** un rôle de WorkMesh. Une assembly est un concept de scène/groupe contenant plusieurs objets identifiés. Mettre plusieurs pièces dans un seul WorkMesh puis l’appeler assembly recréerait l’ambiguïté actuelle de Lay Flat. Le grouping doit vivre au niveau scène/projet.

### 4.2 GeometryMutation

Le contrat décrit aussi la nature de la transformation.

| Mutation | Comportement |
|---|---|
| `METADATA_ONLY` | Aucun changement de vertices/triangles |
| `AFFINE` | Translation, rotation ou scale inversible |
| `PRESERVE_TOPOLOGY` | Vertices modifiés, connectivité volontairement conservée |
| `REBUILD` | Connectivité reconstruite |
| `GENERATE` | Nouvelle géométrie |
| `BOOLEAN` | Résultat d’opération volumique |
| `REPAIR` | Modification explicitement destinée à restaurer une géométrie |

Cette information permet d’éviter de refaire des contrôles coûteux lorsqu’ils n’ont aucun intérêt.

### 4.3 Contrat AFFINE détaillé

`AFFINE` ne signifie pas « toute transformation conserve automatiquement le certificat ».

Le gateway classe la matrice 3×3 par déterminant et conditionnement :

#### Rigid / direct positive affine

Pour translation, rotation et scale inversible de déterminant strictement positif :

- connectivité indexée inchangée ;
- fermeture/topologie des shells inchangée ;
- nesting topologique conservé ;
- certificat structurel/topologique réutilisable ;
- métriques géométriques, fingerprint, bounds, volume et local feature size sont recalculés ;
- un scale non uniforme peut modifier les contraintes métier d’épaisseur, même s’il préserve la topologie.

Test box `20×10×6` :

- source : `1200 mm³` ;
- translation + rotation 33° : `1200 mm³`, DIRECT_CERTIFIED ;
- scale `(2, 0.5, 1.5)`, det `1.5` : `1800 mm³`, DIRECT_CERTIFIED.

#### Orientation-reversing affine

Si `det(A) < 0` :

- la connectivité reste valide ;
- la sémantique d’orientation est inversée globalement ;
- le certificat d’orientation/volume signé est invalidé ;
- le candidat passe par `GLOBAL_WINDING_FLIP` si son rôle exige un solide matériel positif.

Test mirror X : Manifold direct `NoError`, volume `-1200 mm³`, puis `+1200 mm³` après flip global.

#### Affine quasi singulière / singulière

Un kernel peut accepter une géométrie numériquement presque aplatie.

Test scale X `1e-12` :

- Manifold direct `NoError` ;
- volume seulement `1.2e-9 mm³`.

Scale X `0` :

- status Manifold peut encore être `NoError` ;
- mais résultat vide/invalide, volume `0`, 8 triangles de surface nulle dans le WorkMesh source transformé.

Le profil `MANUFACTURING_SOLID` doit donc imposer indépendamment du kernel :

- déterminant/conditionnement minimal de la transformation lorsqu’il est connu ;
- volume matériel minimal relatif/absolu ;
- surface/triangle non dégénéré ;
- dimensions locales minimales cohérentes avec les tolérances numériques.

Le statut `NoError` n’est jamais suffisant pour accepter un solide presque singulier.

---

## 5. Profils de validation communs

Le socle expose des profils stables et versionnés.

### BASIC_MESH

Contrôles peu coûteux :

- indices valides ;
- nombres finis ;
- triangles avec trois indices distincts ;
- surface non nulle ;
- sommets référencés ;
- absence de triangles strictement dupliqués.

### SURFACE

Ajoute les invariants utiles aux surfaces sans exiger de fermeture.

### MANUFACTURING_SOLID

Pour `SOLID` et `SOLID_SET` :

- BASIC_MESH ;
- arêtes indexées cohérentes ;
- fermeture des coques attendues ;
- sémantique d’orientation cohérente avec la matière et les cavités ;
- volume matériel fini et strictement positif ;
- absence de composante parasite selon le contrat de l’opération ;
- certification par le kernel Manifold sur la représentation retenue.

Important : plusieurs coques de triangles ne signifient pas plusieurs corps matériels. Un solide creux possède typiquement une coque extérieure et une coque intérieure orientée en sens opposé. Le validateur ne doit donc jamais « corriger » chaque coque indépendamment vers un volume positif.

### BOOLEAN_INPUT

Profil strict exécuté juste avant une opération Boolean :

- MANUFACTURING_SOLID ;
- contrôles numériques supplémentaires utiles au moteur Boolean ;
- certification fraîche si la géométrie a changé depuis la dernière certification.

### EXPORT_SOLID

Profil appliqué avant les exports qui exigent des volumes.

Les tolérances, l’ordre des contrôles et les codes d’erreur sont définis une seule fois dans le socle et versionnés.

---

## 6. Règle Manifold

La préparation vers Manifold doit préserver la sémantique volumique avant de chercher à « nettoyer » le mesh.

Ordre obligatoire :

```text
WorkMesh original
→ BASIC_MESH
→ tentative Manifold directe, sans soudure ni réorientation globale
→ vérification status / non-vide / volume signé
→ si acceptable : STOP, conserver cette représentation
→ sinon seulement : adaptation conservatrice
→ nouveau test Manifold
→ réparation plus forte uniquement si la politique l’autorise
```

Une entrée directement acceptée par Manifold et représentant un volume matériel positif ne doit pas être retessellée, soudée ou réorientée par habitude.

Cette règle est nécessaire pour conserver les cavités. Les tests 2026-09-18 ont montré qu’un Hollow de cube a un volume brut correct d’environ `2568.51 mm³`, alors que la préparation Boolean actuelle réoriente séparément les deux coques et transforme ce volume en environ `13431.49 mm³`. La cavité est alors interprétée comme de la matière.

À l’inverse, l’Acoustic Diffuser skirt est fermé par ses indices mais possède des conflits d’orientation ; Manifold direct le refuse. Une étape d’orientation peut donc être utile **en fallback**, jamais en prétraitement universel.

La fusion de sommets par coordonnées n’est pas une définition universelle de manifoldness. Le test synthétique de deux cubes fermés en contact ponctuel est accepté directement par Manifold avec deux volumes valides, alors que `geometric_manifold_v2` le classe invalide après soudure par coordonnées. Ce diagnostic devient donc un **warning de contact/coïncidence**, pas une autorité absolue de rejet.

Une soudure ou `Mesh.merge()` n’intervient qu’après échec du chemin direct. Elle reste un best-effort du kernel, pas une preuve indépendante.

Les tests de contact ont été étendus :

- contact ponctuel : Manifold direct `NoError`, 2 corps ;
- contact par arête : Manifold direct `NoError`, 2 corps ;
- contact par face : Manifold direct `NoError`, 2 corps.

Dans les trois cas, la soudure géométrique produit des sommets/arêtes non-manifold alors que les deux solides indexés restent deux volumes valides. Le validateur welded devient donc un diagnostic de coïncidence/contact potentiel, jamais un rejet universel.

Toute adaptation produit un objet éphémère :

```python
PreparedSolid(
    source_fingerprint=...,
    manifold=...,
    strategy=...,
    source_unchanged=True,
    audit=...,
)
```

Le WorkMesh source n’est pas modifié par la préparation Boolean.

Le rapport distingue au minimum :

- `DIRECT_CERTIFIED` ;
- `ADAPTED_CERTIFIED` ;
- `REPAIR_REQUIRED` ;
- `NON_SOLID` ;
- `REJECTED`.

---

## 7. Coques, corps, cavités et pollution

Le mot « composante » est trop ambigu pour servir seul de contrat.

Le socle distingue au minimum :

1. **surface shell** : composante de triangles reliés par indices/arêtes ;
2. **material region** : région volumique positive de matière ;
3. **cavity shell** : coque fermée orientée comme un vide à l’intérieur d’une région ;
4. **disconnected material region** : deuxième pièce matérielle réellement séparée ;
5. **orphan fragment** : fragment apparu sans être autorisé par le contrat.

Exemples :

- Hollow cube : deux surface shells, mais une seule pièce creuse sémantique ;
- texte « AB » : plusieurs régions matérielles légitimes ;
- Simplify d’une pièce monobloc : une nouvelle petite île détachée est une régression ;
- deux cubes volontairement distincts : plusieurs régions peuvent être autorisées.

Le socle calcule deux inventaires :

### SurfaceTopologyReport

- shells par connectivité indexée ;
- triangles ;
- surface ;
- bbox ;
- arêtes frontière/non-manifold ;
- winding/orientation.

### SolidKernelReport

- status Manifold ;
- volume signé total ;
- surface ;
- informations de décomposition disponibles ;
- stratégie de préparation utilisée.

Le contrat d’opération indique ensuite la politique avant/après :

| Politique | Exemple |
|---|---|
| `PRESERVE_SHELL_CONNECTIVITY` | Simplify d’un solide |
| `PRESERVE_MATERIAL_REGIONS` | Simplify/fidelity |
| `ALLOW_TOPOLOGY_CHANGE` | Boolean |
| `DECLARE_OUTPUT_COUNT(n)` | Générateur déterministe |
| `ALLOW_CAVITIES` | Hollow |
| `ALLOW_SOLID_SET` | Relief texte |

Aucune logique générique ne doit faire `extract_largest()` ou supprimer automatiquement les petits fragments. La décision dépend du delta attendu par l’opération.

---

## 7.1 ShellNestingTree — topologie sémantique partagée

Le socle commun doit construire une représentation sémantique des coques fermées, réutilisée par tous les outils consommateurs.

Une liste de composantes connexes n’est pas suffisante. Le même WorkMesh peut contenir :

- une coque extérieure ;
- une coque de cavité ;
- une île de matière à l’intérieur d’une cavité ;
- une nouvelle cavité à l’intérieur de cette île ;
- plusieurs régions matérielles indépendantes.

Créer un rapport commun équivalent à :

```python
ShellNestingTree(
    shells=(
        Shell(id=0, parent=None, depth=0, semantic=MATERIAL_BOUNDARY, ...),
        Shell(id=1, parent=0, depth=1, semantic=CAVITY_BOUNDARY, ...),
        Shell(id=2, parent=1, depth=2, semantic=MATERIAL_BOUNDARY, ...),
    ),
    material_regions=(...),
)
```

Règle de parité :

- profondeur paire : frontière de matière ;
- profondeur impaire : frontière de vide/cavité.

L’orientation signée reste une information importante, mais elle ne doit pas être la seule source de vérité : un import miroir peut inverser toutes les orientations sans changer la relation matière/cavité.

Le calcul de nesting doit utiliser :

1. bbox comme filtre rapide ;
2. un point intérieur robuste par shell, pas seulement le centroïde surfacique ;
3. un test de containment commun et déterministe ;
4. le plus petit parent contenant comme parent direct ;
5. des diagnostics explicites pour les shells tangents/intersectants/ambigus.

Cette structure devient la source commune pour :

- `Cavity Volume` ;
- `Separate mesh` ;
- validation Hollow ;
- préservation des cavités dans Lay Flat ;
- normalisation de winding ;
- calcul du volume matériel ;
- validation sémantique avant/après une opération.

### Cavity Volume doit consommer le socle

Le code actuel considère la plus grosse shell comme extérieure puis additionne toutes les autres shells contenues comme des cavités.

Ce modèle échoue dès qu’une île de matière est imbriquée dans une cavité.

Fixture mesuré :

- enveloppe extérieure : `8000 mm³` ;
- vide intérieur : `4096 mm³` ;
- île de matière dans ce vide : `64 mm³`.

Valeurs physiques attendues :

- matière : `8000 - 4096 + 64 = 3968 mm³` ;
- cavité nette : `4096 - 64 = 4032 mm³`.

Résultat actuel :

- matière estimée : `3840 mm³` ;
- cavité : `4160 mm³`.

L’outil compte donc l’île de matière comme du vide.

Décision : `Cavity Volume` ne doit plus maintenir sa propre logique de nesting. Il consomme `ShellNestingTree` et applique la parité commune.

---

## 7.2 CandidateGeometry vs géométrie persistée

Le fait qu’un outil produise un candidat imparfait ne doit pas l’obliger à recopier les réparations génériques du socle.

Le runtime distingue conceptuellement :

```text
Tool output = CandidateGeometry
        ↓
GeometryMutationGateway
        ↓
audit + adaptations autorisées + semantic delta
        ↓
CertifiedGeometry / WorkMesh persistant
```

Exemple Extrude Down :

- les cas box/cylinder/sphere testés sont fermés par indices ;
- ils contiennent respectivement des conflits de winding ;
- Manifold direct les refuse ;
- le fallback de winding actuel les rend Manifold-valides.

Ce comportement générique ne doit pas être recodé dans Extrude Down.

Le contrat de l’outil autorise par exemple `CONSISTENT_WINDING`. Le gateway applique cette adaptation, recertifie, puis **persiste la représentation certifiée**, afin que l’outil suivant ne doive pas refaire exactement la même correction.

À l’inverse :

- Hollow est déjà valide directement ;
- le gateway doit donc conserver sa représentation et sa sémantique de cavité ;
- aucune adaptation plus agressive n’est autorisée « par habitude ».

Règle :

> Une adaptation générique peut corriger la représentation d’un candidat, mais la géométrie persistée après commit doit satisfaire directement son contrat enregistré.

Cela permet de centraliser les réparations sans conserver éternellement des meshes qui ne fonctionnent qu’après un hack implicite au prochain outil.

---

## 8. Architecture logicielle cible

### 8.1 Couche pure

Créer un package indépendant de Qt et des outils :

```text
src/laserprog_studio/geometry_contract/
    roles.py
    contracts.py
    profiles.py
    audit.py
    components.py
    manifold_certifier.py
    comparison.py
    preparation.py
    changeset.py
    repair.py
    fingerprint.py
    certification.py
```

Cette couche ne dépend pas de `tooling`, des controllers ou de l’UI.

Elle reçoit des objets WorkMesh-like et renvoie des rapports purs.

### 8.2 Service runtime commun

Créer :

```text
src/laserprog_studio/tool_core/app_services/geometry_integrity.py
```

Le `GeometryIntegrityService` est accessible par :

```python
ctx.geometry
```

Il orchestre :

- audit ;
- certification ;
- comparaison avant/après ;
- cache ;
- réparation explicitement autorisée ;
- génération des rapports utilisateur/développeur.

### 8.3 API publique

Exposer uniquement les contrats nécessaires aux outils via :

```text
laserprog_studio.tool_api.geometry
```

Un CreatorTool ne doit jamais importer directement le package interne de validation.

### 8.4 GeometryMutationGateway — frontière unique d’écriture

Le gate ne doit pas dépendre du bon comportement volontaire des outils.

Créer un service d’écriture unique :

```text
GeometryMutationGateway
    preview(change_set, contract)
    commit(change_set, contract)
    import_meshes(...)
    replace(...)
    add(...)
    remove(...)
```

Le gateway est la seule couche runtime autorisée à transformer une sortie géométrique en état persistant du `ModelStore`.

### Point d’insertion vérifié dans l’architecture actuelle

Le chemin Creator existant est déjà favorable :

```text
CreatorTool
→ OperationManager
→ PreviewSession.show_meshes()
→ DocumentFacade.set_preview_meshes()
→ PreviewSession.apply()
→ DocumentFacade.commit_preview()
→ ModelStore
```

`OperationManager.apply()` délègue également à `DocumentFacade.set_meshes()`.

Le premier raccord du gateway doit donc se faire **derrière DocumentFacade**, pas dans chaque CreatorTool. Cela donne immédiatement une couverture transversale aux outils Creator migrés.

Le gateway ne remplace pas `DocumentFacade` dans l’API publique : `DocumentFacade` reste l’interface document des outils et délègue en interne les mutations géométriques au gateway.

Les controllers legacy qui écrivent directement dans ModelStore restent une dette de migration séparée et doivent être recensés par un audit statique.

Chemin cible :

```text
Tool / Controller / Import
        ↓
GeometryChangeSet
        ↓
GeometryMutationGateway
        ↓
GeometryIntegrityService
        ↓
audit / certification / contract
        ↓
ModelStore
```

`ModelStore` reste volontairement un conteneur de données et d’historique. Il ne doit pas importer Manifold ni connaître les profils de fabrication.

`OperationManager`, `DocumentFacade`, `PreviewSession`, les contrôleurs de transform et les workflows spécialisés délèguent leurs écritures au même gateway.

Pendant la migration, les chemins legacy qui écrivent encore directement dans `ModelStore` sont :

1. recensés par un audit statique ;
2. journalisés comme bypass ;
3. migrés progressivement ;
4. finalement interdits par le quality gate.

Les seules écritures directes tolérées à terme sont des chemins d’hydratation bas niveau explicitement approuvés, par exemple le chargement d’un fichier projet déjà sérialisé. Ces chemins doivent déclencher une qualification après hydratation avant tout usage Boolean/export.

Cette architecture donne la garantie recherchée : ajouter un outil ne nécessite pas de connaître tous les anciens outils, et oublier un appel local de validation ne permet pas de contourner le contrat.

### 8.5 État réel des bypass — audit 2026-09-18

L’audit AST dédié mesure actuellement :

- **54** appels aux primitives de mutation `set_meshes/push_meshes/set_preview_meshes/commit_preview` ;
- **50** appels runtime hors des chemins bas niveau explicitement autorisés ;
- répartition des appels store : `application=15`, `tool_core=15`, `controllers=8`, `fabrication=6`, `tooling=6` ;
- **39** affectations directes à `.vertices/.triangles` ;
- **10** affectations persistantes à haut risque dans `application/controllers/tool_core` ;
- 9 de ces 10 affectations à haut risque sont dans les transforms.

Les écritures locales dans `geometry_ops`, Folding, Cloth picking, etc. restent légitimes lorsqu’elles construisent un **CandidateGeometry non persistant**.

La distinction importante est donc :

```text
mutation d’un candidat local        → autorisée
mutation d’un WorkMesh de scène     → interdite à terme hors gateway
```

### 8.6 Mutation persistante en place

`ModelStore.meshes` et `committed_meshes` exposent aujourd’hui les objets WorkMesh réels. Un contrôleur peut donc faire :

```python
meshes[i].vertices = ...
```

sans appeler `set_meshes()`.

Cela contourne :

- le futur Solid Commit Gate ;
- l’historique s’il n’est pas géré séparément ;
- l’invalidation de certification ;
- les notifications centralisées.

Cible progressive :

#### Phase 1 — protection par fingerprint

Aucun certificat chargé depuis metadata n’est cru sans recalculer le fingerprint courant aux frontières sensibles :

- Boolean ;
- export ;
- commit ;
- Repair ;
- analyses de fabrication.

Une mutation clandestine ne peut donc pas conserver frauduleusement un ancien certificat.

#### Phase 2 — migration des writers persistants

Les controllers et services ne modifient plus `vertices/triangles` d’un mesh commité.

Ils produisent un mesh candidat ou un `GeometryChangeSet.replace(mesh_id, candidate)`, puis passent par le gateway.

Pour le Transform live :

1. le drag travaille sur l’acteur de rendu / un buffer temporaire non certifié ;
2. le WorkMesh commité reste intact pendant le mouvement ;
3. au mouse release, un candidat est construit ;
4. le gateway applique le contrat `AFFINE` ;
5. réussite → replace + undo ;
6. échec → l’acteur revient exactement au snapshot initial.

#### Phase 3 — quality gate strict

`scripts/audit_geometry_mutation_bypasses.py` devient bloquant :

- allowlist bas niveau minimale ;
- zéro appel runtime direct au store hors `GeometryMutationGateway` ;
- zéro affectation persistante `.vertices/.triangles` dans controllers/application/tool_core.

Une éventuelle future valeur `MeshGeometry` immuable peut renforcer encore cette règle, mais elle n’est **pas nécessaire comme première étape** et ne doit pas imposer une refonte massive des producteurs actuels.

---

## 9. Intégration avec OperationManager et GeometryChangeSet

### Unifier le contrat de résultat avant d’ajouter le ChangeSet

L’audit du code montre aujourd’hui deux types homonymes :

- `tool_core.app_services.operations.OperationResult` : contrat Creator/public, avec `ok`, tuple de meshes, report, warnings, errors et metadata ;
- `geometry_ops.result.OperationResult` : résultat interne des opérations géométriques, avec liste de meshes, warnings et errors.

Les outils Creator actuels font explicitement l’adaptation entre les deux. Ce fonctionnement est valide mais le nom identique masque la frontière.

La migration ne doit pas créer un troisième `OperationResult`.

Cible :

- le contrat public reste `tool_api.application.OperationResult` ;
- le résultat interne de géométrie est renommé sémantiquement, par exemple `GeometryOpResult` ;
- `GeometryChangeSet` devient un champ structuré du résultat public / de la transaction, pas un nouveau type concurrent de résultat ;
- les adaptateurs Creator peuvent être supprimés progressivement lorsque les opérations internes publient directement leur ChangeSet.



`OperationManager.register()` accepte un `geometry_contract`.

En interne, la registry conserve :

- la fonction de l’opération ;
- son contrat géométrique.

La nouvelle frontière standard est un `GeometryChangeSet` :

```python
GeometryChangeSet(
    added=(
        GeometryAddition(
            mesh=new_mesh,
            contract=GeometryArtifactContract(
                role=GeometryRole.SOLID,
                validation=GeometryProfile.MANUFACTURING_SOLID,
            ),
        ),
    ),
    replaced=(
        GeometryReplacement(
            mesh_id=source_id,
            mesh=new_mesh,
            contract=GeometryArtifactContract(...),
        ),
    ),
    removed=(mesh_id, ...),
)
```

Le but est de ne **jamais rescanner toute la scène** simplement parce qu’un outil modifie un objet.

### Contrat par artefact de sortie

Le contrat de l’opération décrit la mutation commune et peut fournir un `default_output`, mais **chaque ajout/remplacement peut surcharger son propre `GeometryArtifactContract`**.

C’est obligatoire pour les opérations hétérogènes.

Exemple Cloth Apply :

```python
GeometryChangeSet(
    added=(
        GeometryAddition(
            mesh=folded,
            contract=GeometryArtifactContract(
                role=GeometryRole.SOLID,
                validation=GeometryProfile.MANUFACTURING_SOLID,
            ),
        ),
        GeometryAddition(
            mesh=flat_pattern,
            contract=GeometryArtifactContract(
                role=GeometryRole.SURFACE,
                validation=GeometryProfile.SURFACE,
            ),
        ),
    ),
)
```

Ainsi :

- le folded est certifié comme volume ;
- le flat pattern reste volontairement ouvert ;
- aucune exception `if tool_id == "cloth"` n’entre dans le socle ;
- un futur outil peut produire plusieurs rôles sans modifier l’architecture centrale.

Pour un outil simple comme Simplify, le `default_output` évite de répéter le même contrat sur chaque replacement.

Le Solid Commit Gate certifie uniquement :

- les meshes ajoutés ;
- les meshes remplacés ;
- les géométries dont le fingerprint a réellement changé.

Les meshes inchangés conservent leur certification.

Pendant la migration, les anciens `OperationResult(meshes=scene_complete)` restent acceptés. Un adaptateur compare `mesh_id + geometry_fingerprint` pour déduire le ChangeSet. Les nouveaux outils doivent produire directement un changement explicite.

Après exécution, `OperationManager` appelle automatiquement le socle pour produire un `GeometryAuditReport` et attacher les certificats aux changements.

L’outil ne recode aucune validation générique.

Pour `METADATA_ONLY`, la certification géométrique est conservée. Pour `AFFINE`, la certification topologique peut être conservée, tandis que les propriétés métriques/fingerprint sont actualisées de manière déterministe.

---

## 10. Solid Commit Gate

La sécurité réelle doit être située au niveau du commit et non uniquement dans les outils.

Le **Solid Commit Gate** est le dernier contrôle avant qu’une nouvelle géométrie devienne persistante.

Il est utilisé par :

- `PreviewSession.apply()` ;
- `OperationManager.apply()` ;
- les chemins d’import ;
- les sorties spéciales qui ne passent pas par OperationManager ;
- les exports solides ;
- Boolean avant consommation des opérandes.

Un outil ne doit pas pouvoir contourner ce gate simplement en oubliant un appel local.

### Preview

Un preview peut être temporairement non certifié.

Le preview exécute :

- BASIC_MESH immédiatement ;
- les validations lourdes en fonction du contrat et du coût.

### Apply

Un résultat déclaré `SOLID` ou `SOLID_SET` ne peut pas être commité sans satisfaire son profil. Le gate travaille sur le `GeometryChangeSet`, pas sur toute la scène.

En cas d’échec :

- aucun commit ;
- le mesh original reste intact ;
- diagnostic structuré ;
- aucune suppression silencieuse.

---

## 11. Certification et cache

Chaque certification est liée à une empreinte déterministe de la géométrie.

Le socle calcule une signature stable à partir de :

- vertices ;
- triangles ;
- paramètres du profil ;
- version du validateur ;
- version du profil ;
- kernel et version exacte du kernel.

Un certificat contient au minimum :

```json
{
  "schema_version": 1,
  "validator_version": 1,
  "profile_version": 1,
  "kernel": "manifold3d",
  "kernel_version": "...",
  "role": "solid",
  "profile": "manufacturing_solid",
  "status": "certified",
  "geometry_fingerprint": "...",
  "component_count": 1
}
```

Le certificat peut être persisté dans `mesh.metadata`, mais il n’est jamais cru aveuglément : le fingerprint doit correspondre.

Cela évite qu’une certification ancienne reste valable après modification du mesh.

Les transformations affines peuvent conserver une information de topologie, mais une certification Boolean fraîche peut être recalculée à la demande.

---

## 12. Réparation commune

La réparation doit être centrale, déterministe et **sémantiquement conservatrice**.

Elle ne s’exécute jamais implicitement pour masquer une erreur.

Le test `Hollow → repair_work_mesh(optional_backends=False)` démontre un défaut critique actuel : le rapport de réparation indique 0 face supprimée, 0 sommet supprimé et un mesh fermé avant/après, mais le volume matière passe de ~`2568.51` à ~`13431.49 mm³`. La seule cause est la normalisation de winding par composante.

Conséquence : une réparation ne peut jamais être déclarée « conservative » uniquement parce que le nombre de vertices/triangles est inchangé. Elle doit vérifier la sémantique volumique avant/après.

`RepairPolicy` :

- `NONE` : aucun changement automatique ;
- `CONSERVATIVE` : uniquement corrections démontrées sans changement de forme métier ;
- `EXPLICIT_TOOL` : réservé à Repair Mesh.

Le pipeline de réparation doit produire un diff mesurable :

- vertices avant/après ;
- triangles avant/après ;
- composantes avant/après ;
- volume avant/après ;
- surface avant/après ;
- codes des corrections appliquées ;
- volume matériel signé avant/après ;
- shells/régions/cavités avant/après ;
- stratégie exacte de winding utilisée.

Une réparation qui modifie fortement la forme doit échouer ou demander une action explicite, pas continuer silencieusement.

Règles obligatoires :

- si le mesh est déjà DIRECT_CERTIFIED, `RepairPolicy.CONSERVATIVE` ne change pas son winding ;
- un flip d’orientation global peut être appliqué si l’objet entier est cohérent mais globalement inversé ;
- l’orientation indépendante de chaque shell est interdite pour les solides pouvant contenir des cavités ;
- une réparation dont le delta volumique dépasse la tolérance du profil est rejetée.

---

## 13. Responsabilité des outils

Les outils conservent leur logique métier.

Exemples :

### Simplify

Responsable de :

- demander un objectif de simplification ;
- choisir ou proposer un backend de simplification.

Le socle contrôle :

- fermeture ;
- création/disparition de shells ;
- création/disparition de régions matérielles ;
- certification kernel ;
- volume ;
- dérive géométrique ;
- objectif réellement atteint.

Les tests ont reproduit le défaut actuel sur une pièce « haltère » valide : avec `preserve_topology=False`, PyVista retourne sans erreur des résultats avec jusqu’à 17 arêtes ouvertes et 3 îlots. Avec `preserve_topology=True`, le même cas reste valide mais peut ne presque plus se simplifier.

Le backend `Manifold.simplify(tolerance)` est un candidat intéressant parce qu’il conserve un Manifold valide, mais il ne remplace pas le contrat : à `1 mm` de tolérance, le test a supprimé le pont de l’haltère et transformé une région connectée en deux volumes fermés. Le gate de fidélité reste donc obligatoire quel que soit le backend.

Stratégie cible :

1. produire un candidat ;
2. certifier le candidat ;
3. comparer source/candidat ;
4. si le contrat topologique ou la dérive est dépassé, réduire l’agressivité ;
5. accepter le meilleur candidat sûr ;
6. sinon conserver la source et signaler que la réduction demandée n’est pas atteignable avec le profil choisi.

Le preset `viewport_proxy` doit produire un `VISUAL_PROXY` séparé et ne doit jamais remplacer le solide maître.

### Hollow

Responsable du calcul de coque.

Le socle certifie la sortie **sans perdre la relation extérieur/cavité**.

Une préparation Boolean ne doit jamais réorienter toutes les shells vers un volume positif. Le test de référence `hollow_box` devient un test de sémantique volumique : volume avant préparation, volume du PreparedSolid et résultat Boolean doivent représenter la même quantité de matière à tolérance définie.

### Extrude Down

Les probes sur box, cylinder et sphere montrent un pattern stable :

- sortie indexée fermée ;
- zéro arête frontière ;
- mais conflits d’orientation ;
- Manifold direct : `NotManifold` ;
- préparation actuelle après propagation de winding : `NoError`.

Le problème appartient donc au contrat commun de représentation, pas à une raison pour ajouter un validateur privé supplémentaire dans Extrude Down.

Décision cible :

- Extrude Down déclare `GeometryMutation.REBUILD` + sortie `SOLID` ;
- son profil autorise `CONSISTENT_WINDING` ;
- le gateway certifie et canonicalise avant commit ;
- le WorkMesh persistant doit ensuite être DIRECT_CERTIFIED ;
- les trous des sections extrudées restent des trous : la triangulation contrainte déjà utilisée doit être verrouillée par tests.

### Split

Responsable du plan de coupe et des morceaux.

Le socle refuse un morceau déclaré `SOLID` s’il reste ouvert.

### Folding

Responsable de la déformation.

Le socle certifie les sorties destinées à rester solides.

Pour un `SOLID`, le plan de dessin/face sélectionnée ne doit pas être confondu implicitement avec l’axe neutre physique de la matière. Le contrat de déformation doit distinguer :

- authoring plane ;
- neutral surface/axis ;
- épaisseur locale ;
- conservation de matière ;
- self-contact / self-intersection.

Un résultat fermé et accepté par Manifold n’est pas suffisant pour Folding.

### Relief

Responsable de la création des glyphes.

Le contrat peut déclarer `SOLID_SET`.

### Lay Flat

Lorsqu’il regroupe des pièces sans union volumique, il doit conserver plusieurs WorkMesh et créer un **groupe de scène**.

Il est interdit de concaténer plusieurs pièces dans un WorkMesh et de présenter cette concaténation comme une fusion.

Une vraie fusion volumique doit passer par le pipeline Boolean et produire une sortie certifiée.

### Mechanical Motion

Un échec de Boolean ne doit plus être remplacé silencieusement par une concaténation prétendant être une pièce fusionnée.

### Cloth

Cloth démontre pourquoi le rôle géométrique doit piloter le gate :

- la sortie folded 3D du fixture rectangle est un `SOLID` fermé, 12 triangles, 1 corps, Manifold direct `NoError`, volume `120 mm³` ;
- la sortie flat pattern est volontairement une `SURFACE` de 2 triangles avec 4 boundary edges et Manifold `NotManifold`.

Le flat pattern ne doit donc jamais être « réparé » ou refusé par un profil solide.

La solidification Cloth écrit actuellement `_lps_skip_boolean_merge=True` en attribut runtime afin d’éviter qu’un merge spatial reconnecte des Cut boundaries distinctes. Comme les attributs `_lps_*` ne survivent pas au project Save/Load, cette exception est une dette similaire à Image Relief.

Décision cible : Cloth déclare son contrat via le socle public. Le préparateur commun doit pouvoir reconnaître/certifier la topologie directement sans dépendre d’un attribut runtime privé.

---

## 14. Données auxiliaires

Les données de mesure ou de rendu ne doivent plus polluer `WorkMesh.vertices`.

Exemple actuel à corriger :

- Vent Generator ajoute des vertices non référencés pour mesurer une bouche.

Ces informations doivent aller dans :

- metadata structurée ;
- helper geometry ;
- measurement anchors ;
- acteurs de preview.

Un `SOLID` doit contenir uniquement la géométrie appartenant au solide.

---

## 15. Persistance

Les contrats géométriques et informations indispensables doivent être enregistrés dans `mesh.metadata`.

Le corpus runtime montre que la persistance géométrique brute est saine sur le Hollow de référence :

- `.lpsproj` Save → Reload conserve exactement 16 vertices, 24 triangles et ~`2568.509979 mm³` ;
- export 3MF → réimport conserve 16 vertices, 24 triangles et ~`2568.509880 mm³`, l’écart étant celui de la sérialisation décimale ;
- dans les deux cas, la cavité reste correctement orientée avant passage dans la préparation Boolean.

Conclusion : la corruption Hollow observée n’est pas introduite par le format projet ou le 3MF sur ce cas. Elle est introduite par les étapes de normalisation postérieures.

Les attributs runtime privés de type `_lps_*` ne peuvent pas être la seule source d’une règle qui doit survivre à Save/Load.

Le rechargement d’un projet doit donner exactement le même rôle géométrique et les mêmes règles applicables.

Une certification chargée est réutilisable uniquement si son fingerprint correspond.

---

## 16. Diagnostics

Tous les validateurs renvoient des problèmes structurés.

Exemple :

```python
GeometryIssue(
    code="UNUSED_VERTICES",
    severity="error",
    count=8,
    message="8 vertices are not referenced by any triangle.",
)
```

Les codes sont stables.

L’UI transforme ces rapports en texte mais ne contient aucune logique de validation.

Cela permet :

- tests faciles ;
- logs exploitables ;
- diagnostics identiques entre outils ;
- futures statistiques de télémétrie locale si souhaité.

---

## 17. Priorités de correction issues des reproductions

### P0 — corruption silencieuse de la matière

À corriger avant d’élargir le socle à tous les outils :

1. orientation multi-shell dans `boolean_ops._orient_triangles_for_manifold` ;
2. réutilisation de cette orientation dans `mesh_repair` ;
3. préparation Boolean des Hollow/cavités ;
4. Lay Flat `repair_triangle_winding` sur les solides creux.

Critère P0 : aucune opération qui reçoit un solide DIRECT_CERTIFIED ne peut changer son volume matériel uniquement pour « normaliser » les normales.

### P1 — sorties faussement valides

1. Simplify qui ouvre/déconnecte silencieusement une pièce ;
2. Mechanical compound qui remplace un échec Boolean par une concaténation ;
3. Lay Flat qui présente une concaténation chevauchante comme une fusion ;
4. `Separate mesh` qui transforme une cavity shell en seconde pièce ;
5. sorties Boolean chaînées converties en `to_mesh()` qui peuvent introduire des triangles dégénérés ;
6. Folding qui peut conserver un statut Manifold malgré dérive matière ou auto-recouvrement ;
7. Vent qui stocke des anchors de mesure dans les vertices du solide.

### P2 — interopérabilité / persistance

1. conversion des unités 3MF ;
2. transformations miroir 3MF et winding global ;
3. suppression progressive des flags runtime `_lps_*` au profit des contrats persistants ;
4. qualification après Save/Load/import.

### P3 — durcissement

1. reconstruction robuste du fallback Split ouvert désormais reproduit ;
2. Hollow : self-intersections, local feature size et changements de connectivité de cavité ;
3. corpus legacy réel ;
4. performance et cache du GeometryChangeSet.

---

## 18. Migration des outils existants

Ordre de migration recommandé :

1. créer le package `geometry_contract` et sa suite de tests ;
2. créer `GeometryIntegrityService` et `ctx.geometry` ;
3. intégrer le contrat dans `OperationManager` ;
4. créer `GeometryMutationGateway` et faire déléguer PreviewSession/DocumentFacade ;
5. conserver l’audit des 54 écritures store et 39 mutations géométriques comme baseline ;
6. migrer d’abord les 10 mutations persistantes en place, en particulier Transform ;
7. migrer ensuite les 50 appels runtime store vers le gateway, par couche ;
8. migrer Boolean et Import ;
9. migrer Simplify, Split, Hollow et Repair ;
10. corriger Vent Generator ;
11. corriger Lay Flat et Mechanical compound ;
12. migrer Folding, Acoustic Diffuser et Relief ;
13. harmoniser Plan Tracer, Joint Builder et Cloth avec le socle ;
14. supprimer les validateurs génériques dupliqués devenus inutiles ;
15. rendre l’audit des bypass strict dans le quality gate.

La migration doit rester progressive : un outil peut continuer à fonctionner pendant que les autres sont migrés.

---

## 19. Cas actuellement identifiés à corriger

### Simplify

- aucune validation topologique finale ;
- pollution par composantes possible ;
- tests limités principalement au nombre de triangles ;
- `viewport_proxy` peut remplacer un solide de production.

### Vent Generator

- vertices volontairement non référencés ;
- incompatibilité directe avec Hollow ;
- contrôle final insuffisant ;
- état/preflight actuellement non déterministe sur un test ciblé : une configuration attendue `rectangular fill block` ressort `round pipe`.

### Lay Flat

- concaténation de meshes appelée fusion ;
- pièces interpénétrées possibles ;
- réorientation positive de chaque shell qui détruit les cavités ;
- regroupement par bounds qui ne prouve pas une union matérielle.

Test mesuré : deux cubes de 20 mm se chevauchant de 10 mm sont concaténés en un WorkMesh Manifold-valide de `16000 mm³`, alors que leur union géométrique réelle vaut `12000 mm³`.

### Mechanical compound

- fallback de Boolean vers concaténation ;
- résultat présenté comme pièce rigide fusionnée.

Test forcé du fallback sur le même compound :

- vraie union Boolean : 1 shell/région connectée, volume ~`23716.26 mm³` ;
- fallback concaténé : 3 shells/corps, volume ~`25989.87 mm³` ;
- le fallback reste pourtant Manifold `NoError`.

L’écart (~`2273.61 mm³`) correspond notamment aux volumes d’intersection comptés plusieurs fois. Le flag `mechanical_compound_union_fallback` ne suffit donc pas : un résultat qui prétend être une pièce rigide unique doit échouer si l’union volumique échoue, ou rester explicitement une assembly de scène.

### Split

- fallback `clip()` produit effectivement des surfaces ouvertes ;
- aucune postcondition commune ne bloque encore automatiquement ce fallback.

Reproduction directe du chemin de secours sur un cube fermé :

- source : 12 triangles, 0 boundary edge, Manifold `NoError` ;
- `poly.clip(...).triangulate().clean()` : 14 triangles ;
- **8 boundary edges** ;
- Manifold direct et après merge : `NotManifold`.

Ce fallback ne doit plus être committable comme `SOLID`. Il peut éventuellement servir de preview de diagnostic, mais Apply doit soit reconstruire/capper correctement, soit échouer sans modifier la scène.

Tests mesurés positifs à conserver comme non-régression :

- Hollow cube, coupe centrale : 2 solides fermés de ~`1284.255 mm³` chacun ;
- Hollow cube, coupe oblique/off-center : ~`1407.149 + 1161.361 = 2568.510 mm³`, soit conservation du volume source.

Le chemin normal de Split est donc sain sur ces cas ; le risque se concentre sur le fallback et les géométries pathologiques.

### Separate mesh

L’action Boolean `Separate mesh` appelle actuellement `split_disconnected_mesh()`, qui sépare les triangles par connectivité d’indices.

Cette définition est incorrecte pour un solide creux : la coque extérieure et la coque de cavité sont volontairement déconnectées par indices, mais appartiennent à **la même pièce matérielle**.

Reproduction sur le Hollow cube :

- entrée : 1 WorkMesh, volume matière ~`2568.51 mm³` ;
- sortie actuelle : 2 WorkMesh ;
- partie 1 : coque extérieure, `+8000 mm³` ;
- partie 2 : coque intérieure, `-5431.49 mm³` avant normalisation, ensuite `+5431.49 mm³` via la préparation courante.

L’action détruit donc la sémantique « cavité » et transforme le vide intérieur en une seconde pièce.

La future séparation doit opérer sur des **material regions** certifiées, pas sur les surface shells brutes. Une cavity shell ne doit jamais devenir une pièce autonome par défaut.

### Hollow

- offset de normales pouvant s’auto-intersecter ;
- absence de certification finale ;
- la préparation Boolean actuelle inverse la sémantique de la coque de cavité ;
- une différence avec un cutter entièrement situé dans le vide intérieur modifie pourtant la pièce et produit 4 shells, avec triangles dupliqués après soudure ;
- le même défaut est reproduit sur une forme concave « haltère » : volume direct ~`2827.14 mm³`, préparation Boolean actuelle ~`29180.06 mm³` ;
- la limite d’épaisseur repose aujourd’hui sur la bbox globale et ne détecte pas les cols/features localement plus fins.

Le fixture haltère contient un col carré de `0.6 × 0.6 mm`. Une cavité avec une paroi strictement supérieure à `0.3 mm` ne peut plus traverser ce col. Pourtant les épaisseurs `0.50`, `1.0`, `2.0` et `4.0 mm` sont acceptées et conservent une seule inner shell connectée.

La préflight Hollow cible doit donc inclure une estimation de **local feature size / local clearance**, puis vérifier après génération que la topologie de cavité est compatible avec l’épaisseur demandée.

### Repair Mesh

Repair Mesh contient à la fois une capacité utile et une normalisation dangereuse.

Cas positif mesuré :

- cube avec 2 triangles retirés ;
- entrée : 10 triangles, 4 boundary edges, Manifold `NotManifold` ;
- `repair_work_mesh(fill_holes=True)` : 12 triangles, 0 boundary edge, Manifold `NoError`, volume `8000 mm³`.

Cette capacité de fermeture doit être conservée.

Cas destructif mesuré :

- `repair_work_mesh()` réutilise actuellement le même helper d’orientation que Boolean ;
- un Hollow parfaitement fermé et sans face dégénérée est transformé de ~`2568.51` à ~`13431.49 mm³` même avec `fill_holes=False`, `remove_tiny_faces=False` et backends optionnels désactivés ;
- le rapport actuel ne détecte pas cette altération car il mesure essentiellement fermeture/compteurs, pas la sémantique volumique.

Décision : Repair doit construire plusieurs `RepairCandidate`, mesurer leur delta sémantique, puis accepter uniquement un candidat qui améliore les défauts ciblés sans violer le contrat matière/cavité. Un mesh déjà DIRECT_CERTIFIED ne doit jamais être « réparé » par défaut.

### Folding

- déformation sans postcondition solide commune ;
- le mode living-hinge accepte jusqu’à ±720° ;
- un plan neutre placé sur la face d’un solide introduit une forte dérive de volume ;
- Manifold direct peut accepter une géométrie qui se recouvre elle-même sur plusieurs tours.

Corpus fermé `20 × 4 × 1 mm`, volume source `80 mm³` :

- plan sur la face, 90° → ~`76.80 mm³` ;
- 180° → ~`73.62 mm³` ;
- 450° → ~`64.22 mm³` ;
- 720° → ~`54.82 mm³`.

Avec le plan placé au milieu de l’épaisseur, le même déformeur reste autour de `79.89–79.94 mm³`.

À 720° avec plan médian, le résultat reste `Manifold NoError` mais le diagnostic spatial après weld trouve 17 faces dupliquées, 610 arêtes non-manifold et 1208 sommets non-manifold, signature d’un auto-recouvrement exact.

### Text Relief

- triangulation à harmoniser avec le chemin contraint utilisé ailleurs.

### Image Relief

Le test binaire produit une géométrie fermée mais Manifold direct la refuse à cause de conflits d’orientation ; le fallback d’orientation actuel la rend valide. Le chemin grayscale est directement valide.

Le grayscale ne persiste pas `boolean_skip_merge` dans metadata alors que le binaire le fait.

Décision cible : ne pas institutionnaliser ces marqueurs spécifiques par outil. Le nouveau préparateur commun doit d’abord essayer DIRECT, puis ses candidats d’adaptation. Les flags `_lps_skip_boolean_merge` / `boolean_skip_merge` deviennent une dette de migration et doivent pouvoir disparaître lorsque le nouveau pipeline couvre correctement ces cas.


#### Masque 2D binaire — refonte du pipeline contour

Le pipeline actuel transforme d’abord chaque pixel actif en rectangle, fusionne ces rectangles avec Shapely, puis tente de lisser le polygone en escalier.

Cette architecture explique directement les bords dentés :

```text
pixels binaires
→ rectangles axis-aligned
→ unary_union
→ contour déjà quantifié sur la grille
→ simplify/buffer
→ extrusion 3D privée
```

Une fois l’information sub-pixel perdue au moment de la binarisation/union de cases, le lissage ne peut que deviner une courbe plus douce à partir d’un contour déjà crénelé.

Le chemin cible est :

```text
RGBA source
→ activité continue 0..255
→ seuil Levels
→ iso-contour sub-pixel
→ validation topologique 2D
→ lissage 2D contrôlé
→ PlanarRegion commun
→ extrude_planar_regions_boolean_ready()
→ GeometryIntegrityService
→ SOLID certifié
```

##### Contour sub-pixel

Utiliser un marching-squares déterministe sur le champ d’activité continu, avec interpolation linéaire au niveau du seuil.

Le contour est donc calculé entre les centres de pixels et non sur les bords de rectangles entiers.

Bénéfices attendus :

- diagonales réellement diagonales ;
- cercles/ellipses beaucoup moins crénelés ;
- exploitation de l’anti-aliasing du PNG/JPG ;
- seuil `Levels` déplaçant continûment le contour au lieu de seulement ajouter/enlever des blocs ;
- moins de sommets inutiles avant simplification.

Le marching-squares doit gérer explicitement les cas ambigus 5/10 avec un decider scalaire déterministe afin d’éviter que la topologie dépende de l’ordre de parcours.

##### Le lissage reste strictement 2D

Le slider `Smooth` ne modifie jamais un WorkMesh.

Il construit un `SmoothedPlanarFootprintCandidate` à partir du contour source, puis compare avant/après :

- nombre de composantes ;
- nombre de trous ;
- relation d’imbrication ;
- aire ;
- périmètre ;
- Hausdorff distance ;
- déplacement maximal ;
- minimum clearance ;
- validité Shapely ;
- absence de nouveaux contacts zéro-clearance.

Le candidat est rejeté si le lissage :

- ferme un trou ;
- fusionne deux îlots ;
- coupe un isthme ;
- supprime une branche fine ;
- crée une self-intersection ;
- déplace le contour au-delà du budget.

La règle `valid_candidate()` actuelle basée essentiellement sur l’aire globale/symmetric-difference est insuffisante.

##### Smooth adaptatif

Le niveau utilisateur 0..100 ne doit pas correspondre directement à un rayon morphologique fixe.

Il contrôle une enveloppe de qualité :

- `0` : iso-contour brut sub-pixel ;
- faible : réduction du bruit haute fréquence seulement ;
- moyen : simplification + arrondi léger ;
- élevé : courbe visuellement adoucie, mais toujours dans le budget topologique/géométrique.

Si un niveau demandé serait destructif, le système doit revenir au meilleur candidat sûr inférieur au lieu de produire un solide faux.

Le résultat peut donc être moins lissé que demandé, mais jamais topologiquement cassé.

##### Une seule extrusion 2D → 3D

`image_mask_relief_vector.py` ne doit plus maintenir son propre moteur :

- constrained triangulation des caps ;
- création des walls ;
- orientation des trous ;
- déduplication de vertices ;
- règles Manifold spécifiques.

Le masque convertit uniquement son footprint vers `PlanarRegion`.

L’extrusion est déléguée à :

`geometry_ops.planar_boolean_solid.extrude_planar_regions_boolean_ready()`

déjà utilisé comme frontière robuste par Plan Tracer.

Cela centralise :

- normalisation Shapely ;
- précision ;
- contacts zéro-clearance ;
- Manifold CrossSection ;
- fallback indexé ;
- certification du solide.

Le masque 2D devient alors un **producteur de footprint**, pas un second moteur CAD.

##### Preview WYSIWYG

Le preview et le mesh final utilisent exactement le même `PlanarFootprint` calculé.

Il est interdit d’avoir :

```text
preview rasterisé par une logique
+
mesh final vectorisé par une autre
```

Le preview peut rasteriser le footprint commun pour l’affichage, mais ne recalcule pas le contour.

##### Résolution et dimensions physiques

`max_grid_size` est une limite d’échantillonnage, pas une instruction de redimensionnement physique.

Si une image source `Ws × Hs` est ramenée à une grille `Wg × Hg`, la taille physique doit rester indépendante de cette réduction.

Pour un `source_pixel_size_mm` :

```text
physical_width  = Ws * source_pixel_size_mm
physical_height = Hs * source_pixel_size_mm
grid_step_x     = physical_width / Wg
grid_step_y     = physical_height / Hg
```

Le code actuel utilise encore `pixel_size_mm` directement après downsampling, ce qui doit être testé/corrigé.

La résolution de vectorisation peut ensuite être augmentée sans changer la taille de la pièce.

##### Résolution cible

La limite historique de 512 venait notamment du coût du pipeline basé sur des milliers de rectangles Shapely.

Avec marching squares, le coût devient linéaire sur le raster puis proportionnel au contour.

Le plafond doit être rebenchmarké. La cible est de privilégier :

- 1024/2048 pour les masques détaillés si le temps reste acceptable ;
- résolution adaptative selon taille source et complexité ;
- aucune perte arbitraire de détail simplement pour protéger l’ancien union-of-boxes.

##### Contrat de sortie

Le masque binaire déclare :

```text
GeometryRole.SOLID
GeometryMutation.GENERATE
GeometryProfile.MANUFACTURING_SOLID
source = IMAGE_MASK_2D
```

Le commit n’a lieu que si l’extrusion commune est certifiée.

Les flags `boolean_skip_merge` spécifiques au masque doivent disparaître après migration vers ce chemin commun.

##### Tests obligatoires masque

Corpus minimal :

- cercle anti-aliasé ;
- ellipse ;
- rectangle arrondi ;
- diagonale ;
- étoile concave ;
- anneau ;
- multiples trous ;
- composantes proches mais séparées ;
- isthme de 1–2 pixels ;
- stroke fin ;
- contact diagonal ;
- PNG transparent ;
- JPEG bruité ;
- image > 512 px ;
- image > 2048 px.

Pour `Smooth = 0, 15, 35, 50, 75, 100` :

- génération sans exception ;
- footprint Shapely valide ;
- même nombre de composantes/trous sauf transformation explicitement autorisée ;
- aucune self-intersection ;
- déplacement maximal borné ;
- sortie 3D fermée ;
- Manifold direct/certifié ;
- Boolean simple ;
- deuxième Boolean chaînée.

Qualité sur cercle/ellipse :

- mesurer fraction de segments strictement horizontaux/verticaux ;
- erreur radiale RMS/max ;
- Hausdorff au contour analytique ;
- nombre de vertices.

Les seuils d’acceptation définitifs sont fixés à partir du corpus réel, pas choisis arbitrairement avant mesure.


##### Résultats mesurés — masque 2D

Le probe dédié a été exécuté avec succès sur Linux et Windows.

**Cercle anti-aliasé 160×160, rayon nominal 60 px**

Pipeline actuel :

- `Smooth=0` : fraction de périmètre strictement horizontal/vertical = **100 %** ;
- erreur radiale RMS ≈ **0,438 px** ;
- erreur radiale max ≈ **0,959 px** ;
- périmètre polygonal ≈ **480 px** au lieu d’environ `2πr = 377 px`.

À `Smooth=35`, valeur par défaut de l’UI :

- encore **70,3 %** du périmètre axis-aligned ;
- erreur RMS ≈ **0,454 px** ;
- `879` vertices de ring.

Le lissage actuel réduit donc partiellement l’aspect en escalier, mais il part d’un contour déjà quantifié et conserve beaucoup de marches.

Prototype marching-squares sub-pixel sur la même source :

- axis-aligned ≈ **2,64 %** ;
- erreur radiale RMS ≈ **0,170 px** ;
- erreur max ≈ **0,375 px** ;
- périmètre ≈ **378,68 px**, très proche du cercle analytique.

Cela valide expérimentalement la refonte sub-pixel.

**Lissage destructif reproduit**

Fixture `thin` contenant traits fins + anneau/trous :

- `Smooth=0` : 1 composante, **4 trous**, aire `812` ;
- `Smooth=50` : 1 composante, 4 trous, aire `823,74` ;
- `Smooth=75` : 1 composante, **3 trous**, aire `1221,5` ;
- `Smooth=100` : même résultat destructif.

Le lissage supprime donc réellement un trou et augmente l’aire d’environ **50 %**.

Le garde-fou actuel est insuffisant parce qu’il autorise une symmetric-difference très importante et ne compare pas explicitement la signature topologique.

**Sortie 3D actuelle**

Sur tout le corpus cercle/anneau/étoile/traits fins/trous/diagonale :

- mesh indexé fermé ;
- `geometrically_manifold=True` selon le diagnostic welded actuel ;
- mais construction Manifold directe : **NotManifold**.

Cela confirme que l’extrudeur privé du masque ne doit plus être la frontière finale. La sortie doit passer par le constructeur planar commun puis être DIRECT_CERTIFIED/canonicalisée avant commit.

**Downsampling et taille physique**

Fixture source `2048×1024`, `pixel_size_mm=1`, `max_grid_size=512` :

- grille de travail : `512×256` ;
- `downsampled=True` ;
- largeur logique de grille actuelle : **512 mm** au lieu des **2048 mm** correspondant au contrat 1 mm/source-pixel.

Le downsampling modifie donc aujourd’hui simultanément la résolution **et** l’échelle physique. Ces deux notions doivent être découplées.

### Import 3MF

- ne doit pas confondre validité 3MF indexée et résultat d’une soudure par coordonnées ;
- doit convertir systématiquement l’unité source vers le millimètre interne.

Test mesuré : un 3MF déclaré `unit="inch"` contenant une géométrie de taille 1 est actuellement importé avec une étendue de `1.0 mm` au lieu de `25.4 mm`. Le lecteur ignore donc aujourd’hui l’unité du modèle.

Le reader cible normalise tous les formats Core 3MF vers l’unité interne millimètre :

| unité 3MF | facteur vers mm |
|---|---:|
| `micron` | 0.001 |
| `millimeter` | 1 |
| `centimeter` | 10 |
| `inch` | 25.4 |
| `foot` | 304.8 |
| `meter` | 1000 |

L’absence d’attribut `unit` utilise le défaut 3MF : millimètre.

---

## 20. Tests du socle

Le socle doit avoir sa propre suite de tests, indépendante des outils.

Elle doit couvrir au minimum :

- cube fermé valide ;
- plusieurs volumes fermés légitimes ;
- triangle dégénéré ;
- triangle dupliqué ;
- sommet inutilisé ;
- face flottante ;
- composante parasite ;
- surface ouverte ;
- arête non-manifold indexée ;
- sommets de coordonnées identiques mais topologiquement distincts ;
- mesh accepté directement par Manifold ;
- mesh refusé directement mais réparable en mode explicite ;
- stabilité du fingerprint ;
- invalidation du certificat après modification ;
- persistance Save/Load ;
- résultats identiques sur plusieurs exécutions.

---

## 20.1 Matrice de couverture des outils intégrés

La mission ne peut pas être déclarée terminée sur la seule base de quelques outils critiques. Chaque outil intégré est classé par rôle et doit posséder une preuve adaptée à son contrat.

| Outil | Nature géométrique | Contrat cible | Preuve runtime actuelle |
|---|---|---|---|
| Primitives | producteur de solides | `SOLID / GENERATE` | box/cylinder/cone/sphere audités |
| Box Generator | 6 solides + groupe scène | 6 × `SOLID`, assembly hors WorkMesh | 6 panneaux DIRECT_CERTIFIED sur Linux/Windows |
| Plan Tracer | producteur de solide extrudé | `SOLID / GENERATE` | fixture avec trou DIRECT_CERTIFIED, 3300 mm³ |
| Joint Builder | modifie 2+ solides | `SOLID / BOOLEAN` | male/female réels DIRECT_CERTIFIED |
| Vent Generator | producteur de solide | `SOLID / GENERATE` | mesh fermé mais 8 vertices auxiliaires ; Vent→Hollow casse |
| Mechanical Motion | plusieurs solides/compound | `SOLID` ou groupe scène selon intention | engrenage valide ; compound Boolean vs concat documenté |
| Folding | déformation de solide | `SOLID / PRESERVE_TOPOLOGY` + fidélité matière | volume drift et self-overlap reproduits |
| Cloth folded | solide mince | `SOLID / GENERATE` | rectangle 30×20 DIRECT_CERTIFIED, 120 mm³ |
| Cloth flat | patron ouvert volontaire | `SURFACE` | 2 triangles, 4 boundary edges : ouvert par conception |
| Acoustic Diffuser | producteur de solides | `SOLID / GENERATE` | core direct ; skirt nécessite winding fallback |
| Relief texte | producteur multi-corps | `SOLID_SET / GENERATE` | AB8 : 3 régions solides légitimes |
| Relief image | producteur de solide | `SOLID / GENERATE` | grayscale direct ; binary nécessite winding fallback |
| Simplify | reconstruction | rôle hérité + `REBUILD` | pollution ouverte reproduite ; Manifold.simplify peut changer connectivité |
| Repair Mesh | réparation | rôle hérité + `REPAIR` | corruption de cavité Hollow reproduite |
| Extrude Down | reconstruction | `SOLID / REBUILD` | fermé mais winding incohérent ; fallback commun requis |
| Hollow | reconstruction avec cavité | `SOLID / REBUILD + ALLOW_CAVITIES` | cavité valide brute ; préparation actuelle la détruit |
| Split | 1→N solides | `SOLID / REBUILD` | coupes centrale/oblique saines ; fallback à tester strictement |
| Lay Flat | transformation/grouping | géométrie des pièces préservée ; grouping scène | cavité détruite par orientation et pseudo-union reproduite |
| Cavity Volume | consommateur analytique | consomme `ShellNestingTree` | erreur de parité sur nesting profondeur 3 reproduite |
| Material / Engraving | metadata | `METADATA_ONLY` | ne doit pas invalider certification géométrique |
| Texture Projection | metadata/decal | `DECAL/METADATA_ONLY` | exclu du gate solide |
| Selection API test | diagnostic | aucun solide produit | hors contrat de fabrication |

### Règle de couverture

Un outil producteur ou modificateur de géométrie n’est considéré migré que si :

1. son rôle de sortie est déclaré ;
2. au moins un cas nominal passe dans le probe commun ;
3. ses cas limites métier ont des tests dédiés ;
4. sa sortie persistée satisfait directement le profil demandé, ou le gateway canonicalise explicitement le candidat avant commit ;
5. Linux et Windows satisfont les mêmes invariants, même si un backend autorisé n’est pas byte-identical.

Les outils purement metadata ne doivent pas déclencher de recertification topologique.

### Baseline ciblée actuelle

Le workflow géométrique exécute actuellement 59 tests ciblés sur Linux et Windows :

- 58 réussis ;
- 1 échec identique sur les deux OS : Vent Generator retourne `round pipe` alors que le test demande `rectangular fill block` ;
- 0 erreur de collecte ;
- 0 test skipped dans cette sélection.

Cette baseline reste séparée de la dette générale de la suite complète.

---

## 21. Tests inter-outils obligatoires

Ajouter des chaînes de non-régression :

```text
Import → Simplify → Boolean
Plan Tracer → Joint Builder → Boolean
Vent → Hollow
Split → Boolean
Folding → Boolean
Relief → Boolean
Save → Reload → Boolean
Repair → Boolean
```

L’objectif est de tester les contrats entre outils, sans rendre les outils dépendants dans le code.

---

## 22. Résultats d’audit runtime — 2026-09-18

Les mesures suivantes ont été exécutées sur GitHub Actions avec Python 3.12 et la dépendance `manifold3d` résolue en version 3.5.3.

### Tests ciblés existants

51 tests géométriques ciblés exécutés :

- 50 réussis ;
- 1 échec actuel dans Vent Generator : le preflight attend `rectangular fill block` mais reçoit `round pipe`.

Cet échec est classé **contrat/état de l’outil**, distinct d’une erreur topologique.

### Simplify reproduit

Source « haltère » :

- 44 triangles ;
- 1 shell ;
- Manifold `NoError`.

PyVista `preserve_topology=False` :

- réduction 50 % → 22 triangles, 6 arêtes ouvertes, 2 îlots, `NotManifold` ;
- réduction 75 % → 11 triangles, 17 arêtes ouvertes, 3 îlots, `NotManifold` ;
- réduction 90 % → 4 triangles, ouvert, `NotManifold`.

L’opération retourne pourtant actuellement un succès.

PyVista `preserve_topology=True` conserve le mesh valide mais reste à 44 triangles sur ce cas.

`Manifold.simplify()` conserve la validité kernel mais à forte tolérance peut supprimer un pont et changer la connectivité. Conclusion : **kernel-valid n’est pas équivalent à faithful-to-source**.

### Hollow

Le cube Hollow de test produit :

- 2 shells indexées ;
- 24 triangles ;
- Manifold direct valide ;
- volume signé ≈ `2568.51 mm³`.

La préparation Boolean actuelle produit encore un Manifold valide, mais volume ≈ `13431.49 mm³`.

C’est une altération sémantique majeure causée par la réorientation indépendante des shells.

Un test Boolean supplémentaire place un cube de 4 mm entièrement **dans la cavité vide** et lance une différence. L’opération devrait être géométriquement neutre. Elle modifie pourtant le résultat :

- 48 triangles ;
- 4 shells ;
- volume ≈ `13303.49 mm³` ;
- 12 triangles dupliqués après soudure géométrique.

Le nouveau pipeline doit donc certifier DIRECT avant toute orientation et verrouiller la conservation de la sémantique volumique.

### Hollow — épaisseur locale

Un fixture concave possède deux volumes de 20 mm reliés par un col carré de `0.6 mm`.

Résultats Hollow :

- `0.25 mm` : accepté, cavity shell connectée ; ce passage est encore géométriquement possible ;
- `0.50 mm` : accepté, cavity shell toujours connectée ;
- `1.00 mm` : accepté, cavity shell toujours connectée ;
- `2.00 mm` : accepté, cavity shell toujours connectée ;
- `4.00 mm` : accepté, cavity shell toujours connectée.

À partir de `0.30 mm`, un offset intérieur uniforme ne peut plus laisser un canal traversant dans un col de `0.60 mm`. Le fait que l’algorithme conserve la connectivité d’origine montre que l’offset par normales de sommets ne respecte plus la sémantique d’épaisseur locale.

Le contrôle `thickness < 0.45 * min(bbox_dimensions)` n’est donc pas suffisant.

### Acoustic Diffuser

Le skirt :

- fermé par indices ;
- zéro arête frontière ;
- `geometric_manifold_v2=True` ;
- 188 conflits d’orientation ;
- Manifold direct : `NotManifold`.

La préparation d’orientation actuelle le rend ensuite Manifold `NoError`.

Conclusion : le validateur commun doit mesurer explicitement l’orientation ; fermeture + weld ne suffisent pas.

Le core Acoustic Diffuser est directement valide.

### Contact ponctuel

Deux cubes fermés partageant seulement une position de sommet, avec indices distincts :

- topologie indexée fermée ;
- Manifold direct : `NoError` ;
- 2 volumes ;
- `geometric_manifold_v2=False` après soudure par coordonnées.

Conclusion : la soudure géométrique ne peut pas être une autorité de rejet universelle.

### Vent → Hollow

Le Vent flared de test :

- 944 triangles fermés ;
- Manifold direct valide ;
- 8 sommets inutilisés ajoutés uniquement pour les mesures.

`Hollow` le rejette précisément pour ces 8 sommets.

Conclusion : les anchors de mesure doivent sortir du payload solide.

### Split

Un cube plein coupé par le plan central produit deux morceaux fermés et Manifold-valides.

Sur Hollow cube :

- coupe centrale : `1284.254989 + 1284.254989 ≈ 2568.509979 mm³` ;
- coupe oblique/off-center : `1407.149389 + 1161.360590 ≈ 2568.509979 mm³`.

La conservation de volume est exacte à l’arrondi du probe. Le chemin `clip_closed_surface()` fonctionne donc correctement sur ces cas. Le fallback `clip()` reste non certifié.

### Repair

`repair_work_mesh()` sur le Hollow cube, avec tolérance `1e-6`, sans remplissage de trous, sans suppression de tiny faces et sans backends optionnels :

- entrée : 16 vertices, 24 triangles, fermée, volume ~`2568.509979 mm³` ;
- sortie : 16 vertices, 24 triangles, fermée, aucun élément supprimé ;
- volume sortie : ~`13431.490021 mm³`.

Le rapport de réparation actuel paraît donc « sans changement structurel » alors que la matière est profondément modifiée.

### Separate mesh

Le Hollow cube est séparé par l’action actuelle en deux shells autonomes :

- extérieure : 8 vertices, 12 triangles, volume `+8000 mm³` ;
- intérieure : 8 vertices, 12 triangles, volume signé `-5431.490021 mm³`.

La préparation Boolean de la seconde shell la retourne ensuite en `+5431.490021 mm³`. Le problème est donc double : séparation sémantiquement incorrecte puis normalisation qui transforme le vide en matière.

### Persistance Hollow

- projet `.lpsproj` : volume direct avant/après exactement ~`2568.509979 mm³` ;
- roundtrip 3MF : volume direct ~`2568.509880 mm³` ;
- nombre de shells, vertices et triangles conservé.

Ces frontières ne sont pas la source de la corruption P0 observée.

### Lay Flat

Le test `Hollow → Lay Flat` confirme une perte de cavité :

- source Hollow : ≈ `2568.51 mm³` ;
- après Lay Flat : ≈ `13431.49 mm³`.

La fonction de réparation de winding du Lay Flat force actuellement chaque composante fermée vers un volume positif. Elle ne peut pas être utilisée comme normalisation universelle.

Deux cubes qui se chevauchent et sont regroupés par Lay Flat donnent en outre un WorkMesh accepté par Manifold avec `16000 mm³`, alors que l’union réelle des volumes vaut `12000 mm³`. Cela prouve que `KernelCompatibility` ne valide pas la sémantique « union ».

### 3MF

Un fixture 3MF synthétique en pouces a été chargé avec une étendue `1.0` au lieu de `25.4`. La conversion d’unité est absente du reader utilisé par `ModelStore.load_3mf()`.

Un second fixture applique une transformation miroir X via la matrice 3MF. Le reader applique correctement les coordonnées transformées mais conserve le winding source :

- topologie indexée fermée ;
- zéro conflit local d’orientation ;
- Manifold direct `NoError` ;
- volume signé `-1/6`.

La préparation actuelle retourne ensuite `+1/6` parce qu’elle réoriente le mesh. La cible devient plus stricte : l’import doit conserver la transformation géométrique, le qualificatif commun détecte le volume global négatif, puis `GLOBAL_WINDING_FLIP` fournit la représentation solide positive sans casser les cavités.

### Relief

Cas mesurés :

- texte VTK `AB8` : 3 shells légitimes, directement Manifold-valides ;
- image grayscale : directement valide, mais son flag skip-merge n’est que runtime ;
- image binaire : fermée par indices mais 36 conflits d’orientation ; Manifold direct refuse, puis la préparation actuelle réussit après réorientation.

Ce dernier cas justifie un pipeline multi-candidats, mais pas un prétraitement systématique.

### Boolean chaîné et précision de conversion

Le compound mécanique a permis d’isoler un défaut de conversion intermédiaire.

Union des trois Manifolds conservée entièrement dans le kernel puis convertie une seule fois :

- `to_mesh()` final : 3648 triangles, 0 triangle de surface nulle ;
- `to_mesh64()` final : 3648 triangles, 0 triangle de surface nulle.

Chaînage qui reproduit l’architecture LaserProg actuelle, avec conversion/reconstruction entre les unions :

- intermédiaire `to_mesh()` : première union propre, puis résultat final 3968 triangles dont **112 triangles de surface nulle** ;
- intermédiaire `to_mesh64()` : résultat final 3648 triangles, **0 triangle dégénéré**, geometric contract valide.

La cause n’est donc pas l’opération Manifold elle-même mais la perte de précision de l’intermédiaire 32 bits réinjecté dans l’union suivante.

Décision cible :

- utiliser `to_mesh64()` lorsqu’il est disponible pour les sorties canoniques destinées à être réutilisées géométriquement ;
- pour les opérations Boolean multi-opérandes, préférer conserver l’accumulation dans Manifold et ne convertir qu’une seule fois en sortie ;
- n’utiliser `to_mesh()` 32 bits que pour un besoin explicitement compatible avec cette perte de précision ;
- verrouiller le cas des 112 triangles dégénérés par une régression.

### Mechanical compound

Le fallback concaténé a été forcé en faisant échouer `boolean_union` :

- union réelle : 3968 triangles, 1 composante indexée, 1 Manifold, ~`23716.2607 mm³` ;
- concat fallback : 4704 triangles, 3 composantes indexées, 3 Manifolds, ~`25989.8716 mm³` ;
- les deux sont `Manifold NoError`.

La validité kernel ne peut donc pas prouver qu’un résultat respecte l’intention « rigid fused part ».

### Reproductibilité Linux / Windows

Le même probe a été exécuté avec :

- Python `3.12.10` sur les deux OS ;
- `manifold3d 3.5.3` ;
- `numpy 2.0.1` ;
- `pyvista 0.46.5` ;
- `vtk 9.4.2` ;
- `shapely 2.1.2`.

Les invariants Manifold et la majorité des générateurs sont équivalents à la précision numérique attendue.

En revanche, VTK/PyVista `decimate_pro` produit des maillages différents selon l’OS pour la même sphère :

- réduction 90 % : volume Linux ~`3900.3124`, Windows ~`3879.2543 mm³` ;
- réduction 95 % : volume Linux ~`3562.8022`, Windows ~`3606.3610 mm³`.

La divergence persiste avec la même version exacte de Python. Le backend VTK de Simplify n’est donc pas un générateur de géométrie cross-platform byte/deterministic.

Conclusion : les tests cross-platform doivent vérifier les **contrats et tolérances de fidélité**, pas exiger des vertices identiques pour un backend non déterministe. Si une géométrie persistante doit être exactement reproductible, elle doit utiliser un backend déterministe validé ou être générée sur l’environnement Windows de référence.

### Folding — solide fermé

Un pavé fermé `20 × 4 × 1 mm` a été déformé avec un living hinge de 10 mm.

Avec le plan d’authoring situé sur la face inférieure, tous les résultats restent fermés et Manifold `NoError`, mais le volume décroît fortement :

- 90° : ~`76.799 mm³` ;
- 180° : ~`73.621 mm³` ;
- 270° : ~`70.488 mm³` ;
- 450° : ~`64.225 mm³` ;
- 720° : ~`54.825 mm³`.

Avec le même plan translaté au milieu de l’épaisseur :

- 90° : ~`79.936 mm³` ;
- 180° : ~`79.886 mm³` ;
- 270° : ~`79.886 mm³` ;
- 450° : ~`79.889 mm³` ;
- 720° : ~`79.886 mm³`.

La dérive de volume est donc principalement liée à la position du neutral surface, pas à une simple erreur d’intégration numérique.

Le cas 720° médian révèle toutefois un second défaut : le maillage indexé et Manifold direct restent valides, alors qu’une analyse de coïncidences spatiales détecte :

- 17 triangles dupliqués après weld ;
- 610 arêtes non-manifold après weld ;
- 1208 sommets non-manifold après weld.

Le contrat Folding doit donc inclure une détection de self-contact/self-intersection indépendante du simple statut Manifold.

### Baseline suite complète

Le quality gate statique atteint pytest, mais la suite complète actuelle n’est pas verte :

- `1896 passed` ;
- `81 failed` ;
- `5 skipped` ;
- `96 warnings`.

Une grande partie des échecs concerne UI/architecture/Cloth/Plan Tracer et n’est pas causée par cette branche documentaire. Les tests géométriques de cette mission doivent donc avoir leur propre baseline stricte et reproductible pendant que la dette générale est traitée séparément.

---

## 23. Autorités et niveaux de vérité

Le système ne doit plus avoir un booléen unique `is_valid`.

Les niveaux sont :

1. **StructuralValidity** — données numériques/indexées exploitables ;
2. **SurfaceTopologyValidity** — fermeture, edges, winding, shells ;
3. **SemanticValidity** — rôle, cavités, régions, fidélité avant/après ;
4. **KernelCompatibility** — représentation acceptée par Manifold ;
5. **OperationContractValidity** — postconditions propres au type de mutation.

Une couche peut être valide alors qu’une autre ne l’est pas.

Exemples réels :

- Acoustic skirt : surface fermée mais kernel direct invalide ;
- cubes en contact : diagnostic welded invalide mais kernel direct valide ;
- Manifold-simplified dumbbell : kernel valide mais contrat de connectivité Simplify invalide ;
- Hollow préparé actuellement : kernel valide mais sémantique volumique invalide.

---

## 24. Reproductibilité des backends

La version de `manifold3d` ne doit plus rester non bornée.

Après validation du corpus Windows + CI, la version retenue doit être figée dans les dépendances de production.

Toute certification persistée contient :

- nom du kernel ;
- version ;
- version du profil ;
- version du schéma.

Un certificat produit avec une version de kernel différente est requalifié paresseusement avant un usage sensible.

### Deux niveaux de reproductibilité

**Déterminisme strict** : même entrée + mêmes paramètres + même environnement de référence ⇒ même topologie et même géométrie dans les tolérances numériques du backend.

**Équivalence contractuelle cross-platform** : Linux/Windows peuvent produire des triangulations différentes pour certains algorithmes natifs, mais doivent respecter les mêmes invariants :

- rôle ;
- fermeture ;
- nombre de régions autorisées ;
- conservation de volume dans la tolérance du profil ;
- Hausdorff/fidélité dans la tolérance ;
- absence de nouveaux fragments ;
- compatibilité kernel.

Les fingerprints de géométrie ne sont comparés à l’identique que pour un output réellement déterministe. Ils servent toujours à détecter qu’un mesh local a changé, mais ne constituent pas une promesse d’identité cross-platform.

### Environnement de référence

La release Windows est l’environnement de fabrication de référence.

La CI Linux reste obligatoire pour les contrats purs et l’architecture, mais ne doit pas définir seule la géométrie attendue d’un backend VTK non déterministe.

Le workflow d’audit exécute donc le corpus géométrique sur Windows et Linux avec les mêmes versions de dépendances.

---

## 25. GeometryChangeSet et performance

Le contrôle global doit être **central**, mais pas global en coût.

Chaque opération publie les objets réellement touchés.

Le gate :

- ignore les meshes inchangés ;
- ne recalcule pas Manifold pour un simple changement de matériau ;
- réutilise les certificats compatibles ;
- réalise le fingerprint complet seulement sur les géométries modifiées ;
- peut différer les diagnostics lourds pendant le preview ;
- impose la certification finale uniquement avant commit/Boolean/export.

Le modèle cible évite ainsi qu’un outil local provoque un audit O(toute la scène).

---

## 26. Pipeline Boolean cible

```text
source WorkMesh
  ↓
structural audit
  ↓
kernel direct, représentation source préservée
  ├─ valide + sémantique correcte → PreparedSolid DIRECT
  └─ échec / orientation globale négative
          ↓
     adaptation non destructive
          ↓
     kernel retry
          ├─ valide → PreparedSolid ADAPTED
          └─ échec → réparation autorisée ou rejet
  ↓
Boolean Manifold
  ↓
canonical output
  ↓
post-audit + certification
```

Une adaptation d’orientation multi-shell doit respecter l’imbrication extérieur/cavité. Elle ne peut pas simplement rendre chaque shell positive.

Les candidats d’adaptation sont évalués par coût croissant, sans modifier la source :

1. `DIRECT` — aucune modification ;
2. `GLOBAL_WINDING_FLIP` — inversion de tous les triangles lorsque la topologie est cohérente mais que le volume matériel global est signé négatif ;
3. `CONSISTENT_WINDING` — propagation locale du winding partagé, sans forcer chaque shell positive ;
4. `MANIFOLD_MERGE` — best-effort du kernel ;
5. `CONSISTENT_WINDING + MANIFOLD_MERGE` ;
6. nettoyage conservateur sans déplacement significatif ;
7. réparation explicite/reconstruction.

`GLOBAL_WINDING_FLIP` préserve les relations extérieur/cavité parce que toutes les shells sont inversées ensemble. Il est adapté aux imports transformés par une matrice de déterminant négatif. Il ne doit pas être remplacé par « rendre chaque shell positive ».

Dès qu’un candidat satisfait **à la fois** KernelCompatibility et SemanticValidity, le pipeline s’arrête.

Le PreparedSolid est éphémère et ne remplace pas le WorkMesh de l’utilisateur avant réussite de l’opération.

### Conversion canonique de sortie

Le résultat du kernel reste en double précision aussi longtemps que possible.

Règle cible :

```text
Manifold operation(s)
→ validate kernel result
→ to_mesh64() si disponible
→ WorkMesh canonical
→ post-audit
```

Pour un Boolean à plusieurs opérandes, les unions/différences sont accumulées dans le kernel avant la conversion finale lorsqu’il n’existe pas de nécessité métier de matérialiser un intermédiaire.

Un WorkMesh canonique réutilisé comme opérande doit pouvoir être reconstruit sans créer de nouvelles faces dégénérées.

---

## 27. Critères de validation

La mission est validée seulement si :

- un seul moteur commun réalise les contrôles génériques ;
- aucun outil migré ne recode son propre test de manifoldness générique ;
- chaque sortie géométrique persistante possède un `GeometryArtifactContract` explicite ou un default d’opération hérité de manière déterministe ;
- une même opération peut produire simultanément des rôles différents sans branche spécifique dans le socle ;
- les solides passent par le Solid Commit Gate ;
- aucun Tool/Controller runtime ne peut écrire une nouvelle géométrie dans ModelStore en contournant GeometryMutationGateway ;
- les outils Creator existants sont couverts sans appel de validation local grâce à l’intégration DocumentFacade/PreviewSession ;
- les deux contrats OperationResult actuels sont désambiguïsés avant l’introduction définitive de GeometryChangeSet ;
- Boolean applique le même profil à tous ses opérandes, quelle que soit leur provenance ;
- un mesh directement certifiable n’est pas modifié inutilement par la préparation ;
- une transformation affine réutilise uniquement les couches de certificat mathématiquement invariantes ;
- les transformations quasi singulières sont rejetées par le profil manufacturing même si Manifold retourne `NoError` ;
- le fallback Split ouvert ne peut jamais être commité comme `SOLID` ;
- le volume/sémantique de cavité d’un Hollow reste invariant à travers la préparation Boolean ;
- Hollow refuse ou reconstruit proprement les épaisseurs incompatibles avec la local feature size, au lieu de conserver artificiellement une cavité traversante ;
- une Boolean avec un cutter entièrement contenu dans une cavité reste neutre ;
- un Boolean chaîné ne crée pas de triangles dégénérés à cause d’une conversion intermédiaire de précision insuffisante ;
- `Separate mesh` préserve les cavity shells à l’intérieur de leur material region ;
- Cavity Volume utilise la même ShellNestingTree que Separate/Hollow et respecte la parité matière-vide sur des imbrications de profondeur >= 3 ;
- Extrude Down ne persiste plus une sortie NotManifold qui dépend d’un futur prétraitement implicite ;
- Lay Flat préserve la sémantique volumique des pièces et ne transforme jamais une assembly en pseudo-union ;
- les unités 3MF sont normalisées en millimètres avant création des WorkMesh ;
- Import et Save/Load conservent le contrat ;
- Simplify ne peut plus introduire silencieusement de faces/composantes parasites ;
- les données de mesure Vent ne sont plus dans le mesh solide ;
- Lay Flat ne présente plus une concaténation comme une union ;
- Mechanical ne masque plus un échec Boolean par une concaténation ;
- les tests géométriques ciblés passent sur Windows et Linux avec les mêmes versions de dépendances ;
- les backends non déterministes sont contrôlés par des métriques de fidélité, pas par une identité arbitraire de vertices ;
- Folding utilise une neutral surface explicitement définie pour les solides et respecte la tolérance de conservation matière ;
- Folding rejette ou signale les auto-recouvrements/self-intersections même si Manifold.status() reste NoError ;
- les régressions reproduites `Simplify dumbbell`, `Vent → Hollow`, `touching cubes point/edge/face`, `Acoustic skirt`, `Hollow cavity`, `Hollow → Lay Flat`, `Lay Flat overlap`, `3MF inch` et `3MF mirrored instance` sont verrouillées par des tests ;
- tous les tests unitaires du socle passent ;
- les chaînes inter-outils ciblées passent ;
- `scripts/quality_gate.py` reste vert ;
- les audits Creator existants restent verts.

---

## 28. Risques de régression

Les principaux risques sont :

- bloquer des fichiers existants valides avec un contrat trop strict ;
- augmenter le temps d’Apply sur de très gros meshes ;
- conserver des certificats obsolètes ;
- modifier involontairement des workflows qui utilisent des surfaces ouvertes ;
- confondre `SOLID_SET` et pollution ;
- introduire une réparation automatique trop agressive.

Mesures prévues :

- migration progressive ;
- rôles explicites ;
- profiles distincts ;
- cache/fingerprint ;
- diagnostics non bloquants avant activation complète ;
- corpus de fichiers legacy ;
- aucune réparation destructive implicite.

---

## 29. Décision architecturale

La règle projet devient :

> **Un outil fabrique ou transforme une géométrie. Le socle géométrique commun décide si cette géométrie satisfait le contrat déclaré.**

Les outils ne se connaissent pas entre eux.

Ils dépendent uniquement du contrat public `tool_api.geometry`.

Le socle ne connaît aucun outil particulier.

Cette séparation permet d’ajouter, modifier ou supprimer un outil sans modifier les autres et sans dupliquer les règles d’intégrité.

---

## 30. Cycle de vie de sauvegarde et compaction du projet

La robustesse géométrique doit aussi s’appliquer à la persistance. Un objet supprimé de la scène courante ne doit pas continuer à coûter du temps ou de l’espace **sans raison explicite**.

### 30.1 Diagnostic du format actuel

Le format `.lpsproj` actuel est une archive ZIP reconstruite en mode `"w"` à chaque sauvegarde.

Conséquence importante :

- le writer **n’ajoute pas** de nouveaux fichiers à l’ancienne archive ;
- un fichier supprimé de toutes les structures persistantes n’est pas physiquement conservé par accident dans le nouveau ZIP ;
- la lenteur résiduelle vient donc de données qui sont encore **référencées** ou copiées pendant la sauvegarde, pas d’anciens membres ZIP orphelins laissés par append.

Deux mécanismes sont actuellement particulièrement coûteux.

#### Historique sémantique persistant

`SceneDocument.record_modification(..., capture_snapshot=True)` stocke un snapshot complet de la scène.

Le writer sérialise ensuite pour chaque scène :

```text
current meshes
+
scene.snapshots[snapshot_1] -> tous les meshes
+
scene.snapshots[snapshot_2] -> tous les meshes
+
...
```

Le `history_limit` vaut actuellement 50 entrées par scène.

Ainsi, supprimer un objet de la scène courante ne supprime pas nécessairement sa géométrie du fichier : un ancien restore point peut encore la référencer volontairement.

Ce n’est pas un blob ZIP orphelin ; c’est une **rétention cachée par l’historique restaurable**.

#### Undo/redo RAM et autosave

Le Ctrl+Z technique de `ModelStore` reste en RAM et n’est pas directement sérialisé dans le `.lpsproj`.

Mais l’autosave fait actuellement :

```python
project_snapshot = copy.deepcopy(project)
save_project_atomic(project_snapshot, ...)
```

Le deepcopy copie donc aussi les états techniques `_history` / `_redo_history`, même si le writer ne les écrit jamais ensuite.

Une scène qui a contenu beaucoup de géométrie puis a été vidée peut donc produire :

- un fichier recovery relativement petit ;
- mais une phase `deepcopy(project)` toujours très coûteuse.

### 30.2 Troisième coût : double compression du save manuel

Le save manuel écrit actuellement chaque mesh avec :

```text
np.savez_compressed(...)
→ bytes NPZ déjà DEFLATE
→ ZipFile(..., ZIP_DEFLATED)
→ writestr(npz_bytes)
```

Le payload NPZ déjà compressé est donc repassé dans DEFLATE au niveau du `.lpsproj`.

Cette double compression ajoute du CPU pour un gain de taille généralement faible.

Le format cible doit compresser une seule fois :

- soit `.npz` compressé + membre ZIP externe `ZIP_STORED` ;
- soit arrays non compressés + compression au niveau archive.

Le choix final doit être benchmarké sur Windows, environnement de release.

### 30.3 Trois historiques distincts

Le projet doit distinguer explicitement :

#### UndoHistory — transient

- Ctrl+Z / Ctrl+Y ;
- RAM uniquement ;
- durée de vie session ;
- jamais sérialisé ;
- jamais copié dans un recovery snapshot.

#### RestoreHistory — persistent et borné

- opérations sémantiques significatives ;
- restaurable après fermeture/réouverture ;
- persistant dans le save manuel ;
- borné par politique de rétention ;
- dédupliqué par contenu.

#### PinnedCheckpoint — persistant explicite

- checkpoint que l’utilisateur veut conserver ;
- n’est pas supprimé par la politique automatique ;
- doit afficher son coût de stockage si significatif.

Un autosave de récupération n’a pas besoin de conserver l’historique restaurable complet.

### 30.4 Modes de persistance

Créer une couche dédiée :

```text
ProjectPersistenceService
    build_snapshot(project, mode)
    save(snapshot, path)
    load(path)
    analyze_storage(project_or_file)
    compact(...)
```

avec au minimum :

#### FULL_SAVE

Contient :

- scènes courantes ;
- metadata persistante ;
- RestoreHistory retenu ;
- PinnedCheckpoints ;
- contrats/certificats persistants valides.

N’inclut jamais :

- undo/redo technique ;
- preview ;
- caches de rendu ;
- helpers temporaires ;
- visual proxies reconstruisibles ;
- buffers clipboard ;
- état de drag.

#### RECOVERY_SAVE

Contient seulement ce qui est requis pour récupérer le travail courant :

- scènes courantes commitées ;
- metadata nécessaire ;
- références de fichiers/projet nécessaires ;
- éventuellement le minimum d’état applicatif validé pour reprendre le document.

N’inclut pas :

- RestoreHistory complet ;
- UndoHistory ;
- anciennes versions des meshes ;
- artefacts dérivés reconstruisibles.

Cela doit rendre l’autosave proportionnel à **l’état courant**, et non à tout ce que le projet a contenu pendant la session.

### 30.5 Snapshot de persistance dédié

L’autosave ne doit plus appeler `copy.deepcopy(project)`.

Créer un type explicite, UI-neutral :

```python
ProjectPersistenceSnapshot(
    project_id=...,
    active_scene_id=...,
    scenes=(...),
    restore_history=(...),  # FULL_SAVE seulement
    pinned_checkpoints=(...),
)
```

Le builder copie uniquement les données autorisées par le mode.

À court terme, ce snapshot peut encore copier les vertices/triangles nécessaires.

À moyen terme, l’architecture `GeometryMutationGateway` permettra aux géométries certifiées d’être représentées par des payloads immuables/révisionnés, ce qui rendra la capture d’un snapshot de sauvegarde beaucoup moins coûteuse et évitera de lire un mesh pendant qu’un contrôleur le modifie.

### 30.6 Stockage content-addressed des géométries

Le format projet cible ne doit plus écrire une copie NPZ complète du même mesh dans chaque restore point.

Créer un blob store interne :

```text
geometry/
  <geometry_hash_1>.npz
  <geometry_hash_2>.npz
```

Les scènes et snapshots stockent des références :

```json
{
  "mesh_id": "...",
  "geometry_hash": "sha256:...",
  "name": "...",
  "material": {}
}
```

Deux snapshots contenant le même mesh réutilisent donc le même blob.

Le hash de stockage doit être défini indépendamment du `mesh_id` et inclure au minimum les données géométriques persistantes qui déterminent le payload binaire.

Les metadata d’instance restent séparées afin qu’un changement de nom/couleur ne force pas la duplication des vertices/triangles.

### 30.7 Garbage collection mark-and-sweep

Avant l’écriture d’un FULL_SAVE :

1. construire les manifests des scènes courantes ;
2. appliquer la politique de rétention de RestoreHistory ;
3. collecter les références des PinnedCheckpoints ;
4. construire l’ensemble des `geometry_hash` accessibles ;
5. écrire **uniquement** ces blobs.

Un blob qui n’est référencé ni par l’état courant, ni par un restore point conservé, ni par un checkpoint épinglé disparaît du nouveau fichier.

La règle devient :

> supprimé de la scène courante + absent de l’historique retenu = absent du fichier sauvegardé.

Si un objet supprimé est encore conservé uniquement parce qu’un restore point le référence, ce coût doit être explicable par le diagnostic de stockage.

### 30.8 Politique de rétention basée sur le coût

Une limite de 50 snapshots n’est pas suffisante : 50 snapshots de petits objets et 50 snapshots d’assemblages lourds n’ont rien à voir.

`RestoreHistoryPolicy` doit combiner :

- nombre maximum d’entrées ;
- budget de stockage estimé ;
- checkpoints épinglés non supprimables automatiquement ;
- conservation préférentielle des entrées récentes.

La valeur du budget par défaut doit être choisie après benchmark sur des projets réels, pas codée arbitrairement dans le socle.

Le prune doit fonctionner sur les **références** ; le blob réellement libéré est déterminé par le mark-and-sweep.

### 30.9 Diagnostic utilisateur et instrumentation

Ajouter un rapport de sauvegarde structuré :

```python
ProjectStorageReport(
    current_scene_bytes=...,
    restore_history_bytes=...,
    pinned_checkpoint_bytes=...,
    unique_geometry_bytes=...,
    deduplicated_reference_bytes=...,
    transient_undo_bytes_estimate=...,
    unique_blob_count=...,
    referenced_blob_count=...,
)
```

La télémétrie locale de performance doit séparer :

- capture du persistence snapshot ;
- encodage arrays ;
- compression ;
- écriture archive ;
- fsync/replace atomique ;
- taille finale ;
- nombre de meshes courants ;
- nombre de restore points ;
- nombre de blobs uniques ;
- ratio de déduplication.

Une sauvegarde lente doit donc être attribuable à une phase précise.

### 30.10 Compact Project

Prévoir une opération explicite de maintenance :

`Compact project`

Elle doit :

- appliquer la politique de rétention ;
- supprimer les restore points non épinglés que l’utilisateur autorise à perdre ;
- garbage-collecter les blobs devenus inaccessibles ;
- réécrire atomiquement le projet ;
- afficher taille avant/après.

Elle ne doit jamais modifier la scène courante.

La sauvegarde normale effectue déjà le GC des blobs **inaccessibles**. Compact Project sert surtout à libérer les blobs encore accessibles uniquement via de vieux restore points.

### 30.11 Tests obligatoires de persistance

Ajouter au corpus :

1. ajouter un gros mesh → supprimer → save sans historique : fichier revient à une taille proche du projet vide ;
2. ajouter un gros mesh → snapshot sémantique → supprimer : le FULL_SAVE conserve la géométrie tant que le restore point la référence ;
3. prune du restore point → save : le blob supprimé disparaît ;
4. suppression complète d’une scène : aucun blob propre à cette scène ne reste accessible ;
5. 20 snapshots sans changement de géométrie : un seul blob géométrique ;
6. changement d’un seul mesh parmi N : seuls les blobs réellement nouveaux sont ajoutés ;
7. RECOVERY_SAVE d’un projet avec un gros undo stack : taille et temps indépendants de cet undo stack ;
8. FULL_SAVE puis save sans changement : aucune recompression géométrique inutile si le cache/reuse de blobs est disponible ;
9. corruption volontaire d’un blob : erreur de chargement explicite/hash mismatch ;
10. Linux/Windows : même graphe de références et mêmes invariants de taille logique.

### 30.11.1 Intégrité du commit atomique

Le writer atomique actuel présente une faiblesse de transaction :

```python
save_project(project, tmp_path, mark_clean=True)
os.replace(tmp_path, out_path)
```

Or `save_project(..., mark_clean=True)` modifie immédiatement :

- `project.project_path` vers le fichier temporaire ;
- `project.dirty=False`.

Si `os.replace()` échoue ensuite, le projet en mémoire peut donc être déclaré propre alors que la sauvegarde finale n’a pas été commitée.

Décision cible :

```text
serialize/write temp
→ flush/fsync selon politique
→ atomic replace
→ seulement après succès : update project_path + mark_clean
```

Le serializer bas niveau doit être sans effet de bord sur `ProjectStore`.

`ProjectPersistenceService.save(...)` renvoie un résultat transactionnel ; le contrôleur ne modifie l’état du document qu’après confirmation du commit final.

Test obligatoire : injecter un échec de `os.replace()` et vérifier que :

- `project.dirty` reste `True` ;
- `project.project_path` reste l’ancien chemin ;
- l’ancien fichier cible n’est pas considéré remplacé ;
- aucun fichier temporaire résiduel ne reste.

### 30.12 Critères d’acceptation persistence

La mission persistence est validée si :

- un mesh supprimé et non référencé par un historique/checkpoint n’est plus présent dans le fichier suivant ;
- un objet conservé pour RestoreHistory est identifiable comme tel ;
- l’autosave n’effectue plus de `deepcopy(project)` incluant undo/redo ;
- RECOVERY_SAVE n’embarque pas l’historique restaurable complet ;
- les snapshots ne dupliquent plus N fois les mêmes payloads géométriques ;
- le save manuel ne double-compresse plus les NPZ ;
- la suppression d’une scène élimine toutes ses données non partagées au prochain save ;
- le temps d’autosave dépend principalement de l’état courant ;
- la croissance du fichier est explicable par `ProjectStorageReport` ;
- save/load conserve exactement l’état courant et les restore points retenus ;
- toutes les écritures restent atomiques ;
- un échec avant le replace final ne peut jamais marquer le projet clean ni modifier son chemin canonique.

### 30.13 Résultats mesurés — rétention après suppression

Un probe dédié a été exécuté sur Linux et Windows avec un mesh synthétique lourd déterministe.

#### Suppression sans historique sémantique

Après ajout puis suppression du mesh, sans restore point persistant :

- Linux : fichier `749 bytes`, `0` NPZ, save ~`2.95 ms` ;
- Windows : fichier `753 bytes`, `0` NPZ, save ~`7.29 ms`.

Conclusion : le writer ZIP ne conserve pas de blob ancien par append. Un mesh réellement non référencé disparaît bien du fichier suivant.

#### Suppression avec RestoreHistory

Même scénario, mais un snapshot sémantique est créé avant la suppression :

- scène courante : vide ;
- 2 entrées d’historique ;
- 2 snapshots logiques, dont 1 contient encore le gros mesh ;
- archive : 1 NPZ sous `/snapshots/`.

Résultats :

- Linux : `933243 bytes`, save ~`315.95 ms` ;
- Windows : `933243 bytes`, save ~`337.31 ms`.

Le fichier est environ **1240× plus gros** que le projet vide uniquement parce que l’ancien restore point garde la géométrie supprimée.

Ce comportement est aujourd’hui fonctionnellement intentionnel — le restore point doit pouvoir restaurer l’objet — mais son coût est caché et le stockage est très inefficace car chaque snapshot sérialise des WorkMesh complets.

#### Prune de l’historique

Après limitation de l’historique à la seule entrée post-delete et `prune_history()` :

- Linux : `918 bytes`, aucun NPZ ;
- Windows : `916 bytes`, aucun NPZ.

Le gros mesh disparaît donc immédiatement du fichier lorsqu’aucun restore point retenu ne le référence.

Cela valide la future stratégie mark-and-sweep.

#### Suppression complète d’une scène

Une scène lourde avec snapshot est créée puis supprimée du `ProjectStore`.

Sauvegarde suivante :

- Linux : `750 bytes` ;
- Windows : `753 bytes` ;
- aucun NPZ de l’ancienne scène.

La suppression d’une scène entière est donc déjà correctement garbage-collectée par la reconstruction complète du ZIP.

#### Undo RAM et autosave

Scénario avec 6 états techniques d’undo lourds, scène courante vide.

Le fichier sauvegardé reste petit :

- Linux : `752 bytes` ;
- Windows : `751 bytes`.

Mais `copy.deepcopy(project)` coûte :

- Linux avec undo : ~`672.53 ms` ;
- Linux sans undo : ~`0.082 ms` ;
- Windows avec undo : ~`612.16 ms` ;
- Windows sans undo : ~`0.089 ms`.

Soit un facteur supérieur à **6900×** sur ce fixture.

Conclusion : l’undo technique n’alourdit pas le fichier final, mais il peut alourdir massivement la phase de capture de l’autosave actuel.

Le changement `RECOVERY_SAVE + ProjectPersistenceSnapshot` est donc un besoin mesuré, pas seulement une optimisation théorique.

### 30.13.1 Benchmark de compression

Fixture : `36000` vertices et `72000` triangles.

Stratégie actuelle :

```text
np.savez_compressed
+
outer ZIP_DEFLATED level 6
```

Résultats :

- Linux : ~`243.15 ms`, `1,415,992 bytes` ;
- Windows : ~`280.44 ms`, `1,415,992 bytes`.

NPZ compressé + outer `ZIP_STORED` :

- Linux : ~`208.12 ms`, `1,425,240 bytes` ;
- Windows : ~`227.36 ms`, `1,425,240 bytes`.

Gain Windows : environ **19 % de temps** sur ce fixture, pour environ **0,65 % de taille supplémentaire**.

NPZ non compressé + outer ZIP unique :

- Linux : ~`207.59 ms`, `1,425,662 bytes` ;
- Windows : ~`233.41 ms`, `1,425,662 bytes`.

Les deux stratégies à compression unique sont nettement meilleures que la double compression actuelle.

Décision cible retenue pour le format content-addressed :

```text
geometry/<hash>.npz
= NPZ compressé une fois
= membre externe ZIP_STORED
```

Raisons :

- performances meilleures que le chemin actuel ;
- taille pratiquement équivalente ;
- le blob NPZ est autonome ;
- un blob inchangé peut être recopié byte-for-byte depuis l’ancienne archive vers la nouvelle sans réencoder les arrays ;
- le hash porte sur le payload logique/canonique, avec vérification du contenu à l’écriture/lecture.

### 30.13.2 Échec transactionnel reproduit

Le probe injecte volontairement un échec dans `os.replace(tmp_path, target_path)`.

Résultat actuel :

- exception : `OSError: synthetic replace failure` ;
- fichier cible final : absent ;
- `project.dirty` après l’échec : **False** ;
- `project.project_path` après l’échec : chemin du **fichier temporaire** ;
- ce fichier temporaire est ensuite supprimé par le `finally`.

Le projet en mémoire affirme donc être sauvegardé vers un fichier qui n’existe plus.

Correction obligatoire :

- le serializer temporaire est toujours appelé avec un mode sans effet de bord ;
- `project_path` et `dirty` ne changent qu’après le succès du replace final ;
- l’état pré-save est restauré automatiquement sur toute exception.

Ce bug est classé **P0-Persistence Safety**.

### 30.14 Priorités persistence

#### P0-Persistence Safety — garantir le commit

1. rendre le serializer bas niveau sans effet de bord ;
2. marquer le projet clean uniquement après `os.replace()` réussi ;
3. ajouter un test injectant un replace en échec ;
4. garantir la restauration exacte de `dirty` et `project_path` sur erreur.

#### P0-Persistence Performance — corriger le coût caché

1. remplacer `copy.deepcopy(project)` de l’autosave par `ProjectPersistenceSnapshot(mode=RECOVERY_SAVE)` ;
2. exclure explicitement undo/redo, restore history, previews et caches du recovery ;
3. ajouter un diagnostic de taille RestoreHistory dans l’UI/log ;
4. empêcher une sauvegarde de recomprimer inutilement plusieurs copies identiques d’un même mesh.

#### P1-Persistence — format dédupliqué

1. introduire le blob store content-addressed ;
2. snapshots = manifests/références, pas copies complètes ;
3. mark-and-sweep à chaque FULL_SAVE ;
4. politique RestoreHistory bornée par stockage ;
5. checkpoints épinglés explicites.

#### P2-Persistence — performances

1. supprimer la double compression NPZ + outer ZIP ;
2. benchmarker les stratégies de compression sur Windows ;
3. réutiliser les blobs inchangés lorsqu’un format/version le permet ;
4. ajouter des métriques de phase et un test de performance de non-régression.

### 30.15 Objectif de performance et architecture de sauvegarde non bloquante

L’objectif produit est désormais explicite :

- **aucun freeze UI perceptible** pendant autosave ou save manuel ;
- lancement d’un save depuis le thread UI : budget cible **< 20 ms** ;
- aucune tranche de travail de sauvegarde exécutée sur le thread UI au-delà de **16 ms** ;
- save/autosave courant : cible **< 1 s** ;
- save lourd : cible **< 2 s** dans l’enveloppe projet supportée et avec cache chaud ;
- au-delà, l’UI reste entièrement interactive et affiche une progression réelle ;
- un autosave ne doit pas bloquer les opérations géométriques en arrière-plan.

Le budget de 1–2 s porte sur une sauvegarde incrémentale normale. Un premier Save As d’un projet exceptionnellement volumineux peut être limité par le débit disque physique ; dans ce cas la contrainte absolue reste **zéro blocage UI** et une instrumentation claire.

#### Pourquoi le thread actuel rame malgré l’arrière-plan

Le code actuel exécute dans le worker :

```python
project_snapshot = copy.deepcopy(project)
save_project_atomic(project_snapshot, ...)
```

Le deepcopy traverse de nombreuses listes/objets Python. Un thread Python séparé partage le GIL avec Qt ; déplacer ce travail dans `ThreadPoolExecutor` ne le rend donc pas gratuit pour le thread UI.

Le probe a mesuré plus de 600 ms de deepcopy pour seulement 6 gros états Undo. Sur un projet utilisateur contenant de nombreuses scènes, historiques et gros meshes, plusieurs secondes voire dizaines de secondes sont cohérentes avec cette architecture.

La cible n’est donc pas « ajouter davantage de threads », mais **supprimer presque tout le travail Python du chemin chaud de sauvegarde**.

### 30.16 ProjectRevision — snapshot O(nombre d’objets), pas O(nombre de vertices)

Le runtime maintient une révision monotone :

```python
ProjectRevision(
    revision_id: int,
    scenes: tuple[SceneRevision, ...],
    geometry_refs: tuple[GeometryBlobRef, ...],
    metadata_refs: ...,
)
```

Une géométrie persistante certifiée reçoit un `geometry_hash` et une référence immuable vers son blob/cache.

Créer la révision de sauvegarde ne copie **jamais** les tableaux de vertices/triangles.

Le snapshot consiste seulement à copier :

- IDs ;
- références de blobs ;
- metadata légères ;
- graphe des scènes ;
- références des restore points retenus.

Budget attendu : millisecondes, indépendamment du nombre total de triangles inchangés.

### 30.17 Blob encoding hors chemin Save

Le coût d’encodage d’un mesh doit être payé lorsqu’une nouvelle géométrie apparaît, pas à chaque sauvegarde.

Après commit via `GeometryMutationGateway` :

```text
new CertifiedGeometry
    ↓
geometry_hash
    ↓
BlobCache.lookup(hash)
    ├─ hit  → rien à encoder
    └─ miss → encode NPZ compressé en tâche persistence dédiée
```

Le blob cache peut être sur disque dans un répertoire applicatif temporaire/cache, indexé par hash.

Le save normal devient ensuite essentiellement :

```text
freeze ProjectRevision légère
→ écrire manifests JSON
→ recopier les blobs déjà encodés et référencés
→ atomic replace
```

Aucun recalcul Manifold, aucune conversion vertices Python→NumPy et aucune recompression des blobs inchangés pendant Save.

Un projet non modifié géométriquement doit donc avoir un coût de sauvegarde proche du coût de copie disque des blobs + quelques manifests.

### 30.18 PersistenceExecutor dédié

Les sauvegardes ne doivent plus utiliser le même `BackgroundTaskManager(max_workers=1)` que les tâches géométriques.

Créer :

```text
PersistenceExecutor
    manual-save priority
    autosave coalescing
    one writer per target path
```

Règles :

- executor dédié à la persistance ;
- un Boolean/Hollow/Simplify ne doit jamais attendre qu’un autosave termine ;
- plusieurs autosaves en attente sont coalescés : seule la dernière révision utile est écrite ;
- un save manuel est prioritaire sur un autosave non commencé ;
- si un autosave est déjà dans son replace final, le save manuel attend ce court commit au lieu de lancer deux writers concurrents ;
- deux écritures ne modifient jamais simultanément le même fichier cible.

### 30.19 Save manuel asynchrone et sémantique des révisions

Le save manuel ne doit plus appeler `save_project_atomic()` directement depuis le thread Qt.

Chemin cible :

```text
UI thread
  ↓ <20 ms
resolve path / capture revision N / schedule
  ↓
PersistenceExecutor
  ↓
write revision N
  ↓
Qt callback
```

Pendant l’écriture, l’utilisateur peut continuer à travailler.

Si le projet change pendant le save :

```text
save_started_revision = N
current_revision = N + 1
```

à la fin :

- le fichier contient correctement N ;
- `project_path` peut être mis à jour si le commit a réussi ;
- **dirty reste True**, car N+1 n’a pas encore été sauvegardée.

Le projet n’est marqué clean que si :

```text
saved_revision_id == current_revision_id
```

Cette règle évite de perdre silencieusement l’indicateur « modifications non sauvegardées » lorsqu’on édite pendant un save asynchrone.

### 30.20 Autosave = journal de récupération minimal

L’autosave n’a pas besoin de reconstruire un FULL_SAVE complet à chaque tick.

Le mode recovery cible est incrémental :

```text
recovery manifest current revision
+
new/changed blobs since previous recovery
```

Les blobs inchangés sont déjà présents dans le cache/recovery store et ne sont ni copiés ni recompressés à nouveau.

Deux implémentations compatibles sont admises :

#### Option A — recovery directory/store

Un dossier interne de recovery contient :

```text
manifest.json
geometry/<hash>.npz
```

Les updates sont atomiques au niveau manifest. C’est le chemin le plus rapide.

#### Option B — SQLite/WAL recovery store

Un fichier recovery SQLite contient manifests + blobs content-addressed, avec WAL et transactions courtes.

Cette option est intéressante si le filesystem store devient difficile à gérer, mais ne doit être retenue qu’après benchmark et test de corruption.

Le fichier utilisateur `.lpsproj` peut rester une archive portable ; le recovery interne n’a pas besoin d’utiliser exactement le même conteneur.

### 30.21 Save manuel incrémental d’un fichier portable

Un ZIP monolithique impose de recopier les membres vers un nouveau fichier pour conserver un replace atomique et éliminer les données mortes.

Avec des blobs déjà compressés `ZIP_STORED`, cette copie est essentiellement I/O séquentielle et ne consomme presque pas de CPU.

Optimisation supplémentaire :

- si la plateforme/filesystem permet un format de package incrémental sûr, il peut être évalué ;
- sinon on garde le ZIP réécrit atomiquement pour la simplicité et la robustesse.

Le système ne doit **pas** revenir à l’append ZIP permanent, qui recréerait précisément les blobs morts signalés par l’utilisateur.

### 30.22 Cache des blobs et mémoire

Le cache ne doit pas doubler indéfiniment la RAM.

Règles :

- cache principal sur disque ;
- RAM seulement pour petits manifests et blobs récemment produits ;
- LRU/budget configurable ;
- hash → chemin/cache entry ;
- validation taille/hash à la lecture ;
- nettoyage des blobs cache non référencés selon une politique indépendante du projet.

Un WorkMesh peut conserver son `geometry_hash`, mais pas nécessairement les bytes NPZ complets en mémoire.

### 30.23 Performance tests obligatoires

Ajouter une suite dédiée `persistence-performance` avec au moins :

1. projet courant de 1 gros mesh, cache chaud ;
2. 50 meshes inchangés ;
3. modification d’un seul mesh parmi 50 ;
4. suppression de 49 meshes ;
5. 50 restore points référençant majoritairement les mêmes blobs ;
6. gros undo stack technique ;
7. save manuel pendant édition continue ;
8. autosave pendant une opération géométrique background ;
9. Save As initial avec cache froid ;
10. save répété sans modification ;
11. recovery après crash simulé ;
12. panne disque/replace simulée.

Métriques :

- UI scheduling latency ;
- revision capture ms ;
- changed blob encode ms ;
- bytes réellement écrits ;
- reused blob count ;
- manifest write ms ;
- atomic replace ms ;
- end-to-end ms ;
- max main-thread stall ;
- CPU process ;
- peak RSS ;
- compression ratio.

### 30.24 Budgets d’acceptation

Pour l’enveloppe projet de référence définie par les benchmarks de release Windows :

#### Autosave chaud

- main-thread stall p95 < **16 ms** ;
- scheduling < **20 ms** ;
- aucun `deepcopy(ProjectStore)` ;
- aucune recompression d’un blob inchangé ;
- worker p95 < **1 s** ;
- p99 < **2 s**.

#### Save manuel chaud

- dialogue/path exclus : scheduling < **20 ms** ;
- fenêtre toujours interactive ;
- worker p95 < **1 s** ;
- p99 < **2 s** ;
- save sans changement réencode **0 blob**.

#### Save avec une géométrie modifiée

- seule la géométrie modifiée est encodée ;
- les autres blobs sont réutilisés ;
- le coût doit être proportionnel au delta, pas à la taille historique du projet.

#### Première sauvegarde / cache froid

- zéro blocage UI ;
- progression ;
- aucune duplication de blobs ;
- objectif < **2 s** pour l’enveloppe projet standard ;
- les cas dépassant le débit physique du support sont tolérés uniquement si l’UI reste fluide.

Ces budgets deviennent des critères de release, mesurés sous Windows avec le build distribué.

### 30.25 Mesures complémentaires — croissance avec RestoreHistory

Fixture : un seul mesh d’environ `0.695 MB` dans le fichier courant. La géométrie courante reste identique ; seul le nombre de restore points augmente.

Windows :

- 0 snapshot : `~247 ms`, `0.695 MB` ;
- 2 snapshots : `~722 ms`, `2.08 MB` ;
- 5 snapshots : `~1453 ms`, `4.17 MB` ;
- 10 snapshots : `~2667 ms`, `7.64 MB`.

Linux :

- 0 snapshot : `~149 ms` ;
- 2 snapshots : `~567 ms` ;
- 5 snapshots : `~911 ms` ;
- 10 snapshots : `~1615 ms`.

Le coût est donc approximativement proportionnel au nombre de copies de géométrie conservées.

Conclusion :

> changer uniquement le niveau de compression ne peut pas résoudre les saves de 20–30 s lorsque le fichier contient de nombreux snapshots complets.

La déduplication content-addressed et la séparation RestoreHistory / état courant sont obligatoires.

### 30.26 Benchmark Zstandard

Le codec DEFLATE utilisé par `np.savez_compressed()` est lui-même coûteux.

Fixture :

- `36000` vertices ;
- `72000` triangles ;
- payload NPZ non compressé : `2,592,520 bytes`.

Windows :

- `np.savez_compressed` : ~`205 ms`, `1,425,126 bytes` ;
- Zstandard level 1 sur le NPZ brut : ~`5.5 ms`, `1,262,831 bytes` ;
- Zstandard level 3 : ~`11.8 ms`, `1,384,606 bytes` ;
- Zstandard level 6 : ~`25.2 ms`, `1,384,540 bytes`.

Linux :

- `np.savez_compressed` : ~`209 ms` ;
- Zstd level 1 : ~`6.4 ms` ;
- Zstd level 3 : ~`14.5 ms` ;
- Zstd level 6 : ~`27.1 ms`.

Sur ce corpus, Zstd niveau 1 est à la fois :

- environ **25–35× plus rapide** ;
- environ **11 % plus petit** que le NPZ/DEFLATE actuel.

Décision cible :

- le format v2 ne doit plus dépendre de `np.savez_compressed` pour les gros blobs ;
- benchmarker/valider Zstandard niveau 1 comme codec par défaut ;
- garder le codec versionné dans le header du blob afin de permettre une évolution future ;
- stocker un payload canonique simple (arrays + header) compressé une seule fois ;
- loader v2 doit vérifier checksum/hash après décompression.

La dépendance Zstandard doit être pinée et incluse explicitement dans le packaging Windows si retenue après validation finale.

### 30.27 Conclusion performance intermédiaire

Les lenteurs actuelles ont plusieurs causes cumulatives :

1. duplication intégrale des meshes dans RestoreHistory ;
2. `copy.deepcopy(ProjectStore)` de l’autosave, y compris l’Undo RAM ;
3. conversion répétée Python lists → NumPy arrays ;
4. recompression de chaque mesh à chaque save ;
5. codec DEFLATE lent ;
6. double compression NPZ + ZIP ;
7. save manuel synchrone sur le thread Qt ;
8. autosave partageant un executor mono-worker avec d’autres tâches lourdes.

Aucune optimisation isolée ne suffira.

Le plan cible combine donc :

- modèle de révision immuable ;
- blobs content-addressed ;
- compression Zstd rapide lors de la création/modification du blob ;
- save incrémental ;
- executor persistence dédié ;
- manual save asynchrone ;
- recovery store minimal ;
- RestoreHistory dédupliqué et borné.

### 30.28 Plan de correction persistence en deux niveaux

Le projet ne doit pas attendre le format v2 complet pour supprimer les freezes actuels.

#### Phase A — corrections immédiates, format v1 conservé

Objectif : rendre le comportement actuel beaucoup moins mauvais sans changer encore le format utilisateur.

1. **Save manuel hors thread Qt**
   - résolution du chemin dans l’UI ;
   - lancement du writer dans un executor persistence dédié ;
   - indicateur non modal `Saving…` ;
   - callback transactionnel ;
   - `dirty=False` uniquement si la révision sauvegardée est toujours courante.

2. **Autosave en vrai mode RECOVERY**
   - ne pas sérialiser `SceneDocument.snapshots` ;
   - ne pas sérialiser l’historique sémantique complet ;
   - ne jamais copier `ModelStore._history` / `_redo_history` ;
   - ne pas embarquer previews/caches/transient state.

3. **Supprimer les deepcopies redondants du writer**
   - le writer actuel appelle `scene.snapshot()`, qui deep-copy les meshes courants ;
   - il deep-copy ensuite encore chaque `snapshot_meshes` avant `_write_mesh_collection()` ;
   - ces copies doivent disparaître du writer.
   
4. **Compression autosave minimale**
   - recovery privilégie latence/CPU à la taille ;
   - aucun double DEFLATE ;
   - utiliser temporairement un encodage rapide/non compressé si nécessaire jusqu’au blob codec v2.

5. **Executor dédié**
   - autosave ne partage plus le mono-worker avec Boolean/Simplify/Hollow ;
   - coalescing des autosaves ;
   - save manuel prioritaire.

6. **Instrumentation**
   - revision capture ;
   - encode ;
   - compression ;
   - bytes ;
   - write ;
   - replace ;
   - max main-thread stall.

Cette phase doit déjà supprimer l’essentiel du lag visible actuel.

#### Phase B — persistence v2 incrémentale

Objectif : garantir la performance indépendamment du nombre historique de scènes/objets.

- ProjectRevision immuable ;
- geometry blobs content-addressed ;
- Zstandard rapide ;
- transaction incrémentale ;
- RestoreHistory = références de blobs ;
- GC par références ;
- autosave recovery incrémental ;
- save normal proportionnel au delta.

### 30.29 Cohérence concurrente des autosaves

Le code actuel fait `copy.deepcopy(project)` **dans le worker** pendant que l’UI peut redevenir active.

Après le démarrage de l’autosave, l’utilisateur peut créer une nouvelle modification pendant que le worker traverse encore :

- `project.scenes` ;
- `SceneDocument.history` ;
- `ModelStore._committed_meshes` ;
- les listes vertices/triangles mutables.

Le snapshot courant n’est donc pas une vraie frontière transactionnelle.

La cible interdit à un worker de parcourir l’objet applicatif vivant.

Règle :

```text
Qt thread:
  capture immutable/light revision references
  ↓
worker:
  serialize only that frozen revision
```

Le worker ne lit jamais directement un `ProjectStore` qui continue d’être modifié.

Cette règle est nécessaire à la fois pour :

- la performance ;
- la cohérence de l’autosave ;
- l’absence de races entre mutation et sérialisation.

### 30.30 Critères d’acceptation Phase A

Avant même le format v2 :

- save manuel : aucun travail lourd sur le thread UI ;
- autosave : aucun `copy.deepcopy(project)` ;
- autosave : aucun restore snapshot ancien ;
- autosave : aucun undo/redo technique ;
- aucune tâche de géométrie bloquée derrière un autosave ;
- save atomique transactionnel corrigé ;
- 0 deepcopy redondant de snapshot dans le writer ;
- sur le corpus CI de référence, autosave doit rester < 2 s ;
- l’UI doit rester interactive pendant toute écriture ;
- une édition effectuée pendant le save laisse le projet dirty à la fin si elle est plus récente que la révision sauvegardée.

### 30.31 Benchmark conteneur à 96 MiB

Un benchmark de conteneur pur a été exécuté avec :

- `96` blobs ;
- `1 MiB` chacun ;
- `96 MiB` logiques ;
- blobs considérés déjà encodés/compressés ;
- aucune géométrie recalculée pendant la mesure.

#### ZIP v2 style — full rewrite, blobs ZIP_STORED

Windows :

- écriture initiale : ~`77.94 ms` ;
- save sans changement : ~`82.36 ms` ;
- un seul blob changé : ~`82.44 ms`.

Linux :

- initial : ~`55.50 ms` ;
- sans changement : ~`72.23 ms` ;
- un blob changé : ~`73.07 ms`.

Le coût est proportionnel à la taille totale du package, mais l’I/O séquentielle de blobs déjà compressés est très rapide.

#### SQLite/WAL — transaction incrémentale

Windows :

- insertion initiale 96 MiB : ~`2915.6 ms` ;
- save sans changement : ~`0.12 ms` ;
- un blob de 1 MiB changé : ~`31.3 ms` ;
- suppression GC d’un blob : ~`7.8 ms`.

Linux :

- initial : ~`502.8 ms` ;
- sans changement : ~`0.10 ms` ;
- un blob changé : ~`2.0 ms` ;
- suppression : ~`1.9 ms`.

Conclusion :

- SQLite est excellent pour les écritures fréquentes et incrémentales ;
- son premier remplissage lourd peut être plus cher, notamment sous Windows avec durabilité `FULL` ;
- le ZIP v2 reste très efficace pour une sauvegarde utilisateur portable si les blobs sont **déjà encodés** et ne sont pas recompressés.

### 30.32 Décision de format — architecture hybride

Au vu des benchmarks, la cible retenue est :

#### Fichier utilisateur `.lpsproj` v2

Reste un package portable atomique, afin de conserver :

- un seul fichier facilement copiable ;
- inspection/récupération simple ;
- garbage collection complète à chaque full save ;
- absence de données mortes après réécriture.

Structure cible :

```text
manifest.json
project.json
scenes/...
history/...
geometry/<geometry_hash>.lpgz
```

où `.lpgz` représente un blob géométrique canonique compressé une seule fois en Zstandard, puis stocké dans le ZIP en `ZIP_STORED`.

Le save manuel ne compresse pas les géométries. Il ne fait que :

1. capturer `ProjectRevision N` ;
2. écrire les manifests ;
3. recopier les blobs Zstd déjà disponibles ;
4. effectuer le replace atomique ;
5. marquer N sauvegardée si aucune révision plus récente n’existe.

Cette architecture garde le full save extrêmement simple et rapide.

#### Autosave / Recovery

Utilise un store interne **SQLite/WAL** séparé du fichier utilisateur.

Raisons :

- pas de full rewrite toutes les quelques minutes ;
- transaction no-op quasi gratuite ;
- écriture proportionnelle au delta ;
- bonne base pour coalescing et crash recovery ;
- le recovery n’a pas besoin d’être un package portable.

Schéma minimal :

```sql
project_revision(...)
scene_state(...)
geometry_blobs(hash PRIMARY KEY, codec, payload)
current_refs(...)
```

Le recovery store ne contient ni UndoHistory, ni RestoreHistory complet.

#### Pourquoi ne pas utiliser SQLite comme format utilisateur immédiatement

Le benchmark Windows montre que le premier remplissage de 96 MiB avec `synchronous=FULL` peut atteindre ~`2.9 s`, alors que le ZIP de blobs préencodés est très rapide.

SQLite reste excellent pour le workload fréquent/incrémental de l’autosave, mais n’apporte pas ici d’avantage décisif au premier Save As portable.

Le format utilisateur pourra être reconsidéré uniquement si les benchmarks sur de très gros projets montrent que la réécriture séquentielle ZIP dépasse régulièrement le budget.

### 30.33 Objectif final de performance

La stratégie retenue pour atteindre 1–2 s n’est pas « compression plus rapide » seule.

Elle combine :

```text
GeometryMutationGateway
→ geometry_hash
→ encode Zstd blob once
→ BlobCache
→ lightweight ProjectRevision
```

Puis :

```text
AUTOSAVE:
ProjectRevision delta
→ SQLite/WAL
→ quelques ms à quelques dizaines de ms
```

et :

```text
MANUAL SAVE:
ProjectRevision
→ write manifests
→ sequential copy of pre-encoded blobs
→ atomic replace
```

Cibles Windows :

- autosave courant : idéalement < `250 ms`, plafond release `1 s` p95 ;
- save manuel courant : < `1 s` p95 ;
- save manuel lourd : < `2 s` p99 dans l’enveloppe projet supportée ;
- main-thread stall : < `16 ms` p95 ;
- 0 recompression de blob inchangé ;
- 0 deepcopy global du projet ;
- 0 sérialisation de RestoreHistory dans l’autosave.

Si un full save dépasse 2 s à cause du débit physique d’un projet hors enveloppe, l’UI reste néanmoins totalement interactive et la progression est affichée.

---

## 31. Plan d’implémentation final

L’implémentation doit être séquencée. Un jalon ne passe pas au suivant tant que ses critères de sortie ne sont pas satisfaits.

### J0 — Baseline et garde-fous

Conserver verts les quality gates, audits Creator, geometry_integrity_probe, project_save_lifecycle_probe, mask_2d_quality_probe et les workflows CI associés.

Actions :

- archiver les métriques Windows/Linux de référence ;
- distinguer les tests globaux déjà rouges avant mission ;
- créer une fixture minimale pour chaque bug reproduit ;
- ne jamais valider une correction uniquement visuellement.

Critère de sortie : tous les défauts P0/P1 ciblés sont reproductibles par test ou probe automatisé.

### J1 — Persistence Phase A : supprimer les freezes actuels

Implémenter sans attendre le format v2 complet :

- save manuel hors thread Qt ;
- PersistenceExecutor dédié ;
- snapshot de persistence léger et cohérent ;
- autosave RECOVERY sans RestoreHistory ni UndoHistory ;
- suppression des deepcopy globaux/redondants ;
- compression unique et rapide sur le chemin recovery ;
- coalescing des autosaves ;
- gestion correcte du dirty par révision ;
- instrumentation détaillée.

Critères de sortie :

- UI interactive pendant save/autosave ;
- aucun deepcopy global de ProjectStore dans l’autosave ;
- aucun save manuel lourd sur le thread Qt ;
- autosave du corpus CI inférieur à 2 s ;
- aucune tâche géométrique bloquée derrière un autosave ;
- panne d’écriture ou de replace sans corruption du dernier fichier valide.

### J2 — Noyau geometry_contract pur

Implémenter sans dépendance Qt :

- rôles, profils et contrats ;
- fingerprint ;
- BASIC_MESH ;
- rapports de topologie ;
- certification Manifold directe ;
- préparation conservatrice ;
- ShellNestingTree ;
- comparaison sémantique avant/après ;
- codes d’erreur stables.

Le socle démarre en **mode observation** : il mesure et rapporte sans bloquer les workflows legacy non encore migrés.

Critère de sortie : les fixtures Hollow, touching cubes, Acoustic skirt, affine miroir/quasi-singulière et nesting profondeur >= 3 donnent les résultats attendus de ce CDC.

### J3 — GeometryMutationGateway et frontière d’écriture

Raccorder le gateway derrière DocumentFacade et les chemins communs de commit.

Ordre :

1. observation/audit ;
2. warning sur contrat violé ;
3. enforcement uniquement pour les chemins migrés ;
4. suppression progressive des bypass.

Aucune nouvelle écriture géométrique ne doit être ajoutée directement dans ModelStore.

Critères de sortie :

- CreatorTools migrés couverts sans validateur générique local ;
- mutation persistante en place détectée et certificat invalidé correctement ;
- preview non persistante clairement séparée du commit ;
- aucune double application d’une réparation.

### J4 — Migration des opérations à risque élevé

Ordre recommandé :

1. Boolean ;
2. Hollow ;
3. Simplify ;
4. Extrude Down ;
5. Separate mesh ;
6. Lay Flat ;
7. Repair Mesh ;
8. Folding ;
9. générateurs multi-corps / Mechanical.

Pour chaque outil :

- déclarer le contrat ;
- retirer les validations génériques locales devenues redondantes ;
- conserver seulement les règles métier propres à l’outil ;
- tester entrée, preview, Apply, undo/redo, save/load et réutilisation par un autre outil.

Critère de sortie : toutes les chaînes inter-outils de la section 21 passent sans dépendre de flags privés spécifiques à l’outil.

### J5 — Refonte Masque 2D

Implémenter :

- champ d’activité continu ;
- marching squares sub-pixel déterministe ;
- gestion explicite des cas ambigus ;
- signature topologique du footprint ;
- lissage 2D adaptatif et borné ;
- même footprint pour preview et Apply ;
- dimensions physiques indépendantes du downsampling ;
- extrusion via extrude_planar_regions_boolean_ready ;
- commit via le socle géométrique.

Supprimer ensuite l’extrusion privée et les flags de contournement devenus inutiles.

Critères de sortie :

- corpus masque complet vert ;
- aucun trou ou composante supprimé par Smooth sans autorisation explicite ;
- cercle/ellipse nettement moins axis-aligned que le pipeline actuel ;
- sortie 3D certifiée et réutilisable dans deux Boolean chaînées ;
- downsampling sans changement d’échelle physique.

### J6 — Persistence v2 content-addressed

Après stabilisation de l’identité/fingerprint géométrique :

- ProjectRevision immuable ;
- GeometryBlobRef ;
- cache disque content-addressed ;
- codec Zstandard versionné ;
- fichier lpsproj v2 avec blobs préencodés et membres ZIP_STORED ;
- RestoreHistory par références ;
- GC mark-and-sweep ;
- recovery SQLite/WAL incrémental ;
- loader v1 conservé ;
- migration v1 vers v2 testée.

Critères de sortie :

- save sans changement : 0 blob réencodé ;
- modifier 1 mesh parmi 50 : 1 blob réencodé ;
- géométrie supprimée et non référencée absente après full save/compaction ;
- autosave courant p95 < 1 s ;
- save manuel courant p95 < 1 s ;
- save lourd p99 < 2 s dans l’enveloppe de release Windows ;
- stall UI p95 < 16 ms.

### J7 — Imports, exports et legacy

Migrer les frontières restantes : Import 3MF et unités, imports maillage, exports fabrication, loaders legacy, contrôleurs hors Creator et mutations en place historiques.

Toute donnée legacy non qualifiée entre avec un rôle UNKNOWN et suit une politique explicite ; elle ne devient pas automatiquement SOLID.

Critère de sortie : l’audit des bypass ne trouve plus de chemin persistant non classé.

### J8 — Enforcement global et nettoyage

Seulement après les jalons précédents :

- activer le Solid Commit Gate globalement ;
- supprimer les anciens helpers de validation devenus morts ;
- supprimer les flags _lps_skip_boolean_merge / boolean_skip_merge devenus inutiles ;
- réduire les fallbacks legacy ;
- documenter les exceptions restantes avec propriétaire et date de retrait ;
- lancer la suite complète Windows/Linux et les benchmarks release.

Critère de sortie : aucun comportement critique ne dépend d’un bypass non documenté.

---

## 32. Règles de développement de la mission

Chaque changement suit obligatoirement :

~~~text
reproduction
→ contrat/test attendu
→ implémentation minimale
→ test ciblé
→ test d’intégration
→ quality gate
→ benchmark si chemin chaud
→ commit
~~~

Règles :

- une seule brique indépendante par changement cohérent ;
- pas de refactor hors périmètre pendant une correction ;
- aucun résultat déclaré valide sans test reproductible ;
- toute adaptation géométrique doit être observable dans un rapport ;
- toute donnée persistante nouvelle doit avoir version, ownership et politique de compatibilité ;
- toute optimisation doit préserver le résultat fonctionnel avant d’être acceptée ;
- les benchmarks utilisent des fixtures stables et comparent avant/après ;
- les seuils Windows de release priment pour les budgets UX du produit distribué.

---

## 33. Matrice de priorité finale

| Priorité | Sujet | Risque utilisateur | Dépendance |
|---|---|---|---|
| P0 | Corruption matière/cavités/Boolean silencieuse | pièce fabriquée incorrecte | J2 → J4 |
| P0 | Save manuel bloquant / autosave qui fait ramer | perte de fluidité | J1 |
| P0 | Lissage masque 2D destructif | géométrie différente de l’image | J5 |
| P1 | Bords dentés masque 2D / échelle liée au downsampling | qualité géométrique insuffisante | J5 |
| P1 | RestoreHistory dupliqué et save proportionnel à l’historique | fichiers lourds et saves très longs | J6 |
| P1 | Bypass de mutation persistante | validation contournable | J3 → J7 |
| P2 | Nettoyage flags/fallbacks legacy | dette technique | J8 |
| P2 | Optimisations supplémentaires hors budgets | performance marginale | après validation fonctionnelle |

La priorité ne permet pas de contourner les dépendances : le Masque 2D peut être prototypé tôt, mais son commit final doit passer par la frontière géométrique commune.

---

## 34. Définition de terminé

La mission complète est terminée uniquement lorsque toutes les conditions suivantes sont satisfaites.

### Architecture

- GeometryMutationGateway est la frontière normale de mutation persistante ;
- geometry_contract ne dépend ni de Qt ni d’un outil particulier ;
- les rôles/profils publics sont documentés et versionnés ;
- ShellNestingTree est partagé par les consommateurs de cavités ;
- aucune nouvelle validation générique n’est dupliquée dans un outil.

### Géométrie

- les régressions P0/P1 documentées sont verrouillées par tests ;
- les solides persistants des chemins migrés satisfont directement leur contrat ;
- les préparations Boolean ne modifient jamais silencieusement la sémantique matière/cavité ;
- les transformations singulières ou quasi singulières sont rejetées selon le profil ;
- les opérations multi-corps utilisent un contrat explicite.

### Masque 2D

- contour sub-pixel en production ;
- Smooth topologiquement sûr ;
- preview et Apply partagent le même footprint ;
- dimensions physiques invariantes au downsampling ;
- extrusion 3D commune ;
- Boolean chaînée validée.

### Persistance

- save manuel non bloquant ;
- autosave recovery incrémental ;
- aucun deepcopy global du projet ;
- RestoreHistory dédupliqué ;
- format v2 content-addressed ou architecture équivalente démontrant les mêmes propriétés ;
- suppression réelle des blobs non référencés lors du full save/compaction ;
- récupération après crash testée ;
- compatibilité lecture v1 maintenue.

### Performance

- budgets section 30 respectés sur Windows release ;
- absence de stall UI majeur pendant save/autosave ;
- coût du save chaud proportionnel au delta ;
- 0 recompression d’une géométrie inchangée.

### Validation projet

- tests ciblés verts ;
- chaînes inter-outils vertes ;
- quality_gate vert ;
- audits Creator verts ;
- workflows CI dédiés verts ;
- suite complète analysée, avec toute panne préexistante distinguée d’une régression de mission ;
- documentation d’architecture mise à jour ;
- aucune limitation connue critique masquée.

À ce point seulement, le CDC peut passer de **finalisé pour implémentation** à **implémenté et validé**.

