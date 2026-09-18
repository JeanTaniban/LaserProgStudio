# Joint builder and A/B selection hotfix

This patch fixes two regressions introduced during the source refactor.

- Restored dataclass constructors for `PlankBasis` and `PlanarFace`. Without them, the joint builder raised `PlankBasis() takes no arguments`.
- Restored the joint selection UX: in Joint mode, clicking an already selected board removes it from the A/B selection without requiring Shift.

The transform multi-selection workflow remains unchanged outside the Joint tool.
