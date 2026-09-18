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
| `SOLID` | Un volume fermé destiné à la fabrication et aux opérations solides |
| `SOLID_SET` | Plusieurs volumes fermés légitimes dans un même WorkMesh |
| `SURFACE` | Surface volontairement ouverte |
| `ASSEMBLY` | Groupe de pièces distinctes, sans prétendre qu’elles forment une union |
| `VISUAL_PROXY` | Géométrie d’affichage uniquement |
| `HELPER` | Mesure, guide, gizmo ou données auxiliaires |
| `DECAL` | Géométrie ou projection visuelle non destinée aux opérations solides |

Un `VISUAL_PROXY` ou un `HELPER` ne doit jamais devenir accidentellement un opérande Boolean ou un objet de fabrication.

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
- fermeture des composantes attendues ;
- orientation cohérente ;
- volume non nul ;
- absence de composante parasite selon le contrat métier ;
- construction Manifold directe réussie.

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

La règle primaire est la topologie indexée du mesh.

Le pipeline doit d’abord essayer :

```text
WorkMesh
→ contrôle structurel
→ Manifold(mesh)
```

sans `merge()` automatique.

La fusion de sommets par coordonnées n’est pas une définition universelle de la validité d’un solide et ne doit pas être utilisée comme motif absolu de rejet.

Une soudure ou un `Mesh.merge()` ne peut intervenir que comme stratégie de compatibilité ou de réparation explicite, après échec du chemin direct.

Le rapport doit distinguer :

- mesh valide directement ;
- mesh valide après adaptation conservatrice ;
- mesh non certifiable ;
- mesh volontairement non-solide.

---

## 7. Composantes et pollution

Le nombre de composantes n’est pas un critère de validité universel.

Exemples légitimes :

- plusieurs lettres d’un texte ;
- plusieurs îlots solides intentionnels ;
- un objet `SOLID_SET`.

Le socle calcule un inventaire stable des composantes :

- nombre ;
- triangles ;
- surface ;
- volume ;
- bbox ;
- fraction de taille par rapport au mesh total.

Le contrat de l’opération indique ensuite la politique attendue :

| Politique | Exemple |
|---|---|
| `PRESERVE` | Simplify |
| `ALLOW_CHANGE` | Boolean |
| `EXACT(n)` | Générateur connu |
| `DECLARED_SET` | Relief texte ou sortie multi-corps connue |

Simplify doit donc comparer avant/après au lieu de supprimer arbitrairement la plus petite composante.

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

## 9. Intégration avec OperationManager

`OperationManager.register()` doit accepter un `geometry_contract`.

En interne, la registry conserve :

- la fonction de l’opération ;
- son contrat géométrique.

Après exécution, `OperationManager` appelle automatiquement le socle pour produire un `GeometryAuditReport`.

Le résultat est enrichi d’un contrat/certificat standardisé.

L’outil ne recode aucune validation générique.

Pour les opérations qui ne changent pas la géométrie, le contrat `METADATA_ONLY` permet de conserver la certification existante.

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

Un résultat déclaré `SOLID` ou `SOLID_SET` ne peut pas être commité sans satisfaire son profil.

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
- version du validateur.

Un certificat contient au minimum :

```json
{
  "schema_version": 1,
  "validator_version": 1,
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

- choisir l’algorithme de décimation ;
- définir la réduction demandée.

Le socle contrôle :

- pollution ;
- composantes ;
- fermeture ;
- certification ;
- dérive.

Le preset `viewport_proxy` doit produire un `VISUAL_PROXY` et ne doit pas remplacer le solide maître.

### Hollow

Responsable du calcul de coque.

Le socle certifie la sortie.

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

Doit déclarer `ASSEMBLY` lorsqu’il ne fait qu’agréger des pièces.

Une vraie fusion volumique doit être une opération Boolean et être déclarée comme telle.

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

## 21. Critères de validation

La mission est validée seulement si :

- un seul moteur commun réalise les contrôles génériques ;
- aucun outil migré ne recode son propre test de manifoldness générique ;
- chaque sortie géométrique persistante possède un rôle explicite ou un rôle hérité de manière déterministe ;
- les solides passent par le Solid Commit Gate ;
- Boolean applique le même profil à tous ses opérandes, quelle que soit leur provenance ;
- Import et Save/Load conservent le contrat ;
- Simplify ne peut plus introduire silencieusement de faces/composantes parasites ;
- les données de mesure Vent ne sont plus dans le mesh solide ;
- Lay Flat ne présente plus une concaténation comme une union ;
- Mechanical ne masque plus un échec Boolean par une concaténation ;
- tous les tests unitaires du socle passent ;
- les chaînes inter-outils ciblées passent ;
- `scripts/quality_gate.py` reste vert ;
- les audits Creator existants restent verts.

---

## 22. Risques de régression

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

## 23. Décision architecturale

La règle projet devient :

> **Un outil fabrique ou transforme une géométrie. Le socle géométrique commun décide si cette géométrie satisfait le contrat déclaré.**

Les outils ne se connaissent pas entre eux.

Ils dépendent uniquement du contrat public `tool_api.geometry`.

Le socle ne connaît aucun outil particulier.

Cette séparation permet d’ajouter, modifier ou supprimer un outil sans modifier les autres et sans dupliquer les règles d’intégrité.
