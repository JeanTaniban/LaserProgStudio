# CDC mission — Socle commun d’intégrité géométrique

## Statut

Architecture cible proposée pour LaserProg Studio.

Cette mission remplace l’approche où chaque outil implémente ses propres contrôles de mesh. Le principe retenu est un **socle géométrique commun, déclaratif et versionné**, appelé automatiquement par le runtime aux frontières où un mesh devient un résultat persistant, un opérande booléen ou un fichier de fabrication.

Le but n’est pas de rendre les outils dépendants les uns des autres. Au contraire, les outils doivent rester remplaçables, supprimables et ajoutables indépendamment.

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
        output_role=GeometryRole.SOLID,
        validation=GeometryProfile.MANUFACTURING_SOLID,
        components=ComponentPolicy.PRESERVE,
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
    added=(...),
    replaced=((mesh_id, new_mesh), ...),
    removed=(mesh_id, ...),
)
```

Le but est de ne **jamais rescanner toute la scène** simplement parce qu’un outil modifie un objet.

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

### Split

Responsable du plan de coupe et des morceaux.

Le socle refuse un morceau déclaré `SOLID` s’il reste ouvert.

### Folding

Responsable de la déformation.

Le socle certifie les sorties destinées à rester solides.

### Relief

Responsable de la création des glyphes.

Le contrat peut déclarer `SOLID_SET`.

### Lay Flat

Lorsqu’il regroupe des pièces sans union volumique, il doit conserver plusieurs WorkMesh et créer un **groupe de scène**.

Il est interdit de concaténer plusieurs pièces dans un WorkMesh et de présenter cette concaténation comme une fusion.

Une vraie fusion volumique doit passer par le pipeline Boolean et produire une sortie certifiée.

### Mechanical Motion

Un échec de Boolean ne doit plus être remplacé silencieusement par une concaténation prétendant être une pièce fusionnée.

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
6. Vent qui stocke des anchors de mesure dans les vertices du solide.

### P2 — interopérabilité / persistance

1. conversion des unités 3MF ;
2. transformations miroir 3MF et winding global ;
3. suppression progressive des flags runtime `_lps_*` au profit des contrats persistants ;
4. qualification après Save/Load/import.

### P3 — durcissement

1. fallback Split ouvert ;
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
5. ajouter un audit des écritures directes `ModelStore` et migrer les contrôleurs legacy ;
6. migrer Boolean et Import ;
7. migrer Simplify, Split, Hollow et Repair ;
8. corriger Vent Generator ;
9. corriger Lay Flat et Mechanical compound ;
10. migrer Folding, Acoustic Diffuser et Relief ;
11. harmoniser Plan Tracer, Joint Builder et Cloth avec le socle ;
12. supprimer les validateurs génériques dupliqués devenus inutiles ;
13. rendre l’audit des bypass strict dans le quality gate.

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

- fallback `clip()` pouvant produire des surfaces ouvertes si `clip_closed_surface()` échoue ;
- aucune postcondition commune ne bloque encore automatiquement ce fallback.

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

- `repair_work_mesh()` réutilise actuellement le même helper d’orientation que Boolean ;
- un Hollow parfaitement fermé et sans face dégénérée est transformé de ~`2568.51` à ~`13431.49 mm³` même avec `fill_holes=False`, `remove_tiny_faces=False` et backends optionnels désactivés ;
- le rapport actuel ne détecte pas cette altération car il mesure essentiellement fermeture/compteurs, pas la sémantique volumique.

### Folding

- déformation sans postcondition solide commune.

### Text Relief

- triangulation à harmoniser avec le chemin contraint utilisé ailleurs.

### Image Relief

Le test binaire produit une géométrie fermée mais Manifold direct la refuse à cause de conflits d’orientation ; le fallback d’orientation actuel la rend valide. Le chemin grayscale est directement valide.

Le grayscale ne persiste pas `boolean_skip_merge` dans metadata alors que le binaire le fait.

Décision cible : ne pas institutionnaliser ces marqueurs spécifiques par outil. Le nouveau préparateur commun doit d’abord essayer DIRECT, puis ses candidats d’adaptation. Les flags `_lps_skip_boolean_merge` / `boolean_skip_merge` deviennent une dette de migration et doivent pouvoir disparaître lorsque le nouveau pipeline couvre correctement ces cas.

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
- chaque sortie géométrique persistante possède un rôle explicite ou un rôle hérité de manière déterministe ;
- les solides passent par le Solid Commit Gate ;
- aucun Tool/Controller runtime ne peut écrire une nouvelle géométrie dans ModelStore en contournant GeometryMutationGateway ;
- les outils Creator existants sont couverts sans appel de validation local grâce à l’intégration DocumentFacade/PreviewSession ;
- les deux contrats OperationResult actuels sont désambiguïsés avant l’introduction définitive de GeometryChangeSet ;
- Boolean applique le même profil à tous ses opérandes, quelle que soit leur provenance ;
- un mesh directement certifiable n’est pas modifié inutilement par la préparation ;
- le volume/sémantique de cavité d’un Hollow reste invariant à travers la préparation Boolean ;
- Hollow refuse ou reconstruit proprement les épaisseurs incompatibles avec la local feature size, au lieu de conserver artificiellement une cavité traversante ;
- une Boolean avec un cutter entièrement contenu dans une cavité reste neutre ;
- un Boolean chaîné ne crée pas de triangles dégénérés à cause d’une conversion intermédiaire de précision insuffisante ;
- `Separate mesh` préserve les cavity shells à l’intérieur de leur material region ;
- Lay Flat préserve la sémantique volumique des pièces et ne transforme jamais une assembly en pseudo-union ;
- les unités 3MF sont normalisées en millimètres avant création des WorkMesh ;
- Import et Save/Load conservent le contrat ;
- Simplify ne peut plus introduire silencieusement de faces/composantes parasites ;
- les données de mesure Vent ne sont plus dans le mesh solide ;
- Lay Flat ne présente plus une concaténation comme une union ;
- Mechanical ne masque plus un échec Boolean par une concaténation ;
- les tests géométriques ciblés passent sur Windows et Linux avec les mêmes versions de dépendances ;
- les backends non déterministes sont contrôlés par des métriques de fidélité, pas par une identité arbitraire de vertices ;
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
