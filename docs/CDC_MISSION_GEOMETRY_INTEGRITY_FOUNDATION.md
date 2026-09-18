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

---

## 9. Intégration avec OperationManager et GeometryChangeSet

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

La réparation doit être centrale et déterministe.

Elle ne s’exécute jamais implicitement pour masquer une erreur.

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
- codes des corrections appliquées.

Une réparation qui modifie fortement la forme doit échouer ou demander une action explicite, pas continuer silencieusement.

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

## 17. Migration des outils existants

Ordre de migration recommandé :

1. créer le package `geometry_contract` et sa suite de tests ;
2. créer `GeometryIntegrityService` et `ctx.geometry` ;
3. intégrer le contrat dans `OperationManager` ;
4. intégrer le Solid Commit Gate dans PreviewSession/Document boundary ;
5. migrer Boolean et Import ;
6. migrer Simplify, Split, Hollow et Repair ;
7. corriger Vent Generator ;
8. corriger Lay Flat et Mechanical compound ;
9. migrer Folding, Acoustic Diffuser et Relief ;
10. harmoniser Plan Tracer, Joint Builder et Cloth avec le socle ;
11. supprimer les validateurs génériques dupliqués devenus inutiles.

La migration doit rester progressive : un outil peut continuer à fonctionner pendant que les autres sont migrés.

---

## 18. Cas actuellement identifiés à corriger

### Simplify

- aucune validation topologique finale ;
- pollution par composantes possible ;
- tests limités principalement au nombre de triangles ;
- `viewport_proxy` peut remplacer un solide de production.

### Vent Generator

- vertices volontairement non référencés ;
- incompatibilité directe avec Hollow ;
- contrôle final insuffisant.

### Lay Flat

- concaténation de meshes appelée fusion ;
- pièces interpénétrées possibles.

### Mechanical compound

- fallback de Boolean vers concaténation ;
- résultat présenté comme pièce rigide fusionnée.

### Split

- fallback pouvant produire des surfaces ouvertes.

### Hollow

- offset de normales pouvant s’auto-intersecter ;
- absence de certification finale.

### Folding

- déformation sans postcondition solide commune.

### Text Relief

- triangulation à harmoniser avec le chemin contraint utilisé ailleurs.

### Image Relief grayscale

- `boolean_skip_merge` doit être persisté dans metadata comme dans le relief binaire.

### Import 3MF

- ne doit pas confondre validité 3MF indexée et résultat d’une soudure par coordonnées.

---

## 19. Tests du socle

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

## 20. Tests inter-outils obligatoires

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

## 21. Résultats d’audit runtime — 2026-09-18

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

C’est une altération sémantique majeure causée par la réorientation indépendante des shells. Le nouveau pipeline doit tenter le kernel direct avant toute orientation.

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

### Split simple

Un cube coupé par le plan central produit deux morceaux fermés et Manifold-valides. Le cas simple est sain ; il reste à couvrir les fallbacks complexes où `clip_closed_surface()` échoue.

---

## 22. Autorités et niveaux de vérité

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

## 23. Reproductibilité du kernel

La version de `manifold3d` ne doit plus rester non bornée.

Après validation du corpus Windows + CI, la version retenue doit être figée dans les dépendances de production.

Toute certification persistée contient :

- nom du kernel ;
- version ;
- version du profil ;
- version du schéma.

Un certificat produit avec une version de kernel différente est requalifié paresseusement avant un usage sensible.

---

## 24. GeometryChangeSet et performance

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

## 25. Pipeline Boolean cible

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

Le PreparedSolid est éphémère et ne remplace pas le WorkMesh de l’utilisateur avant réussite de l’opération.

---

## 26. Critères de validation

La mission est validée seulement si :

- un seul moteur commun réalise les contrôles génériques ;
- aucun outil migré ne recode son propre test de manifoldness générique ;
- chaque sortie géométrique persistante possède un rôle explicite ou un rôle hérité de manière déterministe ;
- les solides passent par le Solid Commit Gate ;
- Boolean applique le même profil à tous ses opérandes, quelle que soit leur provenance ;
- un mesh directement certifiable n’est pas modifié inutilement par la préparation ;
- le volume/sémantique de cavité d’un Hollow reste invariant à travers la préparation Boolean ;
- Import et Save/Load conservent le contrat ;
- Simplify ne peut plus introduire silencieusement de faces/composantes parasites ;
- les données de mesure Vent ne sont plus dans le mesh solide ;
- Lay Flat ne présente plus une concaténation comme une union ;
- Mechanical ne masque plus un échec Boolean par une concaténation ;
- les regressions reproduites `Simplify dumbbell`, `Vent → Hollow`, `touching cubes`, `Acoustic skirt` et `Hollow cavity` sont verrouillées par des tests ;
- tous les tests unitaires du socle passent ;
- les chaînes inter-outils ciblées passent ;
- `scripts/quality_gate.py` reste vert ;
- les audits Creator existants restent verts.

---

## 27. Risques de régression

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

## 28. Décision architecturale

La règle projet devient :

> **Un outil fabrique ou transforme une géométrie. Le socle géométrique commun décide si cette géométrie satisfait le contrat déclaré.**

Les outils ne se connaissent pas entre eux.

Ils dépendent uniquement du contrat public `tool_api.geometry`.

Le socle ne connaît aucun outil particulier.

Cette séparation permet d’ajouter, modifier ou supprimer un outil sans modifier les autres et sans dupliquer les règles d’intégrité.
