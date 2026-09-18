# Pass 330 — Cloth architecture foundation

## Goal

Define Cloth as a professional surface-topology tool before adding viewport interactions.

## Key decision

Cloth V1 is globally 3D and locally planar. Panels are rigidly developable faces connected by straight folds. This makes flat-pattern generation deterministic and length-preserving.

## Boundaries

- `tool_core/tracing`: neutral interaction vocabulary.
- `tool_api/tracing`: public façade.
- `tooling/cloth/models.py`: domain document.
- `topology.py`: loops and local frames.
- `validation.py`: apply-time rules.
- `flattening.py`: rigid unfolding.
- `mesh_builder.py`: surface-only triangulation.
- `serialization.py`: editable metadata.
- `output.py`: transaction-neutral output plan.
- `state_machine.py`: workflow and fold creation.

## Deliberate non-goals

- no toolbar registration;
- no half-working picking;
- no direct ProjectStore/MainWindow import;
- no physical cloth simulation;
- no arbitrary non-developable surface flattening.
