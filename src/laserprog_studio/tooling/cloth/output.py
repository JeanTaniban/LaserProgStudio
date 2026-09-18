"""Apply output plan for Cloth without depending on application controllers."""
from __future__ import annotations

from dataclasses import dataclass

from laserprog_studio.domain.work_model import WorkMesh

from .flattening import ClothFlatteningResult, flatten_cloth_document
from .mesh_builder import build_cloth_surface_mesh
from .models import ClothDocument
from .serialization import attach_cloth_source_in_place
from .stitching import heal_cloth_stitches
from .validation import ClothValidationReport, validate_cloth_document


@dataclass(frozen=True, slots=True)
class ClothApplyPlan:
    validation: ClothValidationReport
    flattening: ClothFlatteningResult | None = None
    folded_mesh: WorkMesh | None = None
    flat_mesh: WorkMesh | None = None
    flat_scene_name: str = "Cloth · Flat pattern"
    issues: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return (
            self.validation.can_apply
            and self.flattening is not None
            and self.flattening.success
            and self.folded_mesh is not None
            and self.flat_mesh is not None
            and not self.issues
        )


def build_cloth_apply_plan(document: ClothDocument, *, name: str = "Cloth") -> ClothApplyPlan:
    # Work on a clone so preflight remains transactional.  The healed clone is
    # the source embedded in the outputs, making microscopic historical gaps a
    # one-time migration rather than a recurring flattening defect.
    working = document.clone()
    heal_cloth_stitches(working)
    validation = validate_cloth_document(working)
    if not validation.can_apply:
        return ClothApplyPlan(validation, issues=tuple(issue.message for issue in validation.errors))
    flattening = flatten_cloth_document(working, heal_stitches=False)
    if not flattening.success:
        return ClothApplyPlan(
            validation,
            flattening=flattening,
            issues=tuple(issue.message for issue in flattening.issues if issue.error),
        )
    folded = build_cloth_surface_mesh(working, name=f"{name} · 3D", solid=True)
    flat = build_cloth_surface_mesh(working, name=f"{name} · Flat", flattened=flattening, solid=False)
    issues = tuple((*folded.issues, *flat.issues))
    if folded.mesh is not None:
        folded.mesh = attach_cloth_source_in_place(folded.mesh, document=working, output_kind="folded")
    if flat.mesh is not None:
        flat.mesh = attach_cloth_source_in_place(flat.mesh, document=working, output_kind="flat")
    return ClothApplyPlan(validation, flattening, folded.mesh, flat.mesh, f"{name} · Flat pattern", issues)


__all__ = ["ClothApplyPlan", "build_cloth_apply_plan"]
