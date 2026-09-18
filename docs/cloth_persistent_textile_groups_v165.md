# Cloth persistent textile groups — v165

## Design rule

A technical Cloth patch is geometry. A textile group is user intent.

Selection, Close, Properties and rendering must use persistent group identity,
not geometric continuity, after geometry has entered the textile domain.

## Creation operations

| Operation | Persistent result |
| --- | --- |
| Take face | One group per connected selected source region |
| Close | One new independent group for the complete accepted proposal |
| Draw closed face | One independent group |
| Draw Modify separation | One new group per selected subset/original parent |
| Draw deletion | Remaining disconnected components are split into groups |

## Metadata

Each member patch stores:

- `cloth_logical_group_id`
- `cloth_group_origin`
- optional `cloth_group_parent_ids`

The document metadata registry `cloth_textile_groups_v1` stores:

- group id;
- patch ids;
- origin;
- parent provenance ids;
- label;
- creation revision.

Parent ids are diagnostic provenance. They never affect selection.

## Selection

Main menu:

- click selects the complete persistent group under the pointer;
- Shift-click adds another group;
- touching groups remain separate.

Properties:

- Face selects one technical patch;
- Group selects the complete persistent group.

Draw:

- technical faces and edges can be selected individually;
- Apply can detach selected technical faces from the original group;
- deletion normalizes disconnected remaining components.

## Compatibility

Explicit group metadata wins. Legacy fallback identity can use stable creation,
source-component, draw-region, ruled-strip or Close proposal metadata.

## Tests

`tests/test_v165_cloth_persistent_textile_groups.py` verifies:

- strict selection of touching groups;
- complete selection from any technical patch;
- independent Close output;
- Draw Modify separation;
- automatic split after deletion;
- serialization of the group registry.
