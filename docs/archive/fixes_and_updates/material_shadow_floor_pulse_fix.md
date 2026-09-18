# Material shadow floor-pulse fix

The previous visible **Sol de rendu** workaround fixed VTK shadow maps because it forced this exact sequence:

1. enable real shadows with an opaque receiver present;
2. render once;
3. remove the receiver;
4. disable and re-enable the VTK shadow pass;
5. render the final scene without the receiver.

A simple temporary receiver was not enough: the shadow pass must be rebuilt after the receiver is removed. The material renderer now performs this internal floor-pulse sequence automatically inside `prime_vtk_shadow_maps()`.

The final scene remains piece-only: no visible ground/floor actor and no persistent ground shadow receiver.

Diagnostic log signature:

```text
[MATERIAL_RENDER] vtk shadow maps floor-pulse piece-only enabled=True details=...
```
