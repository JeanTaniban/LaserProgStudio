# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from .ids import (
    TOOL_BOX,
    TOOL_ENGRAVING,
    TOOL_JOINT,
    TOOL_LAYFLAT,
    TOOL_MATERIAL,
    TOOL_MOD_EXTRUDE_DOWN,
    TOOL_MOD_HOLLOW,
    TOOL_MOD_RELIEF,
    TOOL_MOD_REPAIR,
    TOOL_MOD_SIMPLIFY,
    TOOL_MOD_SPLIT,
    TOOL_PLAN_TRACE,
    TOOL_PRIMITIVE,
    TOOL_TEXTURE_PROJECTION,
    TOOL_VENT_GENERATOR,
    TOOL_MECHANICAL_MOTION,
    TOOL_FOLDING,
    TOOL_CLOTH,
    TOOL_VOLUME_MEASURE,
    TOOL_ACOUSTIC_DIFFUSER,
    TOOL_SMART_SURFACE_SELECTION_TEST,
)


@dataclass(frozen=True)
class ToolHelpDocument:
    """Short user-facing documentation for one tool or modifier.

    The text is intentionally stored outside the Qt panels: adding or changing
    documentation must not require editing UI construction code.  The body is a
    compact Markdown document shown by ``ToolHelpController``.
    """

    tool_id: str
    title: str
    summary: str
    body: str

    def as_markdown(self) -> str:
        return f"# {self.title}\n\n{self.summary.strip()}\n\n{self.body.strip()}\n"


_TOOL_HELP_DOCS: dict[str, ToolHelpDocument] = {
    TOOL_PRIMITIVE: ToolHelpDocument(
        TOOL_PRIMITIVE,
        "Primitives",
        "Create simple parametric solids and stage them as a preview before adding them to the scene.",
        """
## When to use it
Use this tool to quickly add boxes, cylinders, spheres, cones, pyramids, triangular prisms or hexagonal prisms.

## Parameters
- **Type** selects the primitive shape.
- **Custom shape** is used by the custom primitive mode.
- **Size X/Y/Z** defines the final dimensions in millimetres. For cylinders, cones and hex prisms, X/Y are used as the diameter and Z as height.
- **Segments** controls the polygon count of circular shapes. Lower values create low-poly parts; higher values make smoother geometry.
- **Position X/Y/Z** places the primitive center in the scene.
- **Color** accepts a hexadecimal value such as `#B8B8B8`.

## Workflow
Choose a shape, adjust size and position, then click **Add to preview**. Use **Apply** to commit it to the model or **Cancel** to discard it. Shortcuts: **Delete** removes the selected part, **Ctrl+C** copies, **Ctrl+V** pastes, and **Ctrl+D** duplicates.
""",
    ),
    TOOL_BOX: ToolHelpDocument(
        TOOL_BOX,
        "Box generator",
        "Generate a laser-cut box layout with configurable dimensions, wall thickness and joint styles.",
        """
## When to use it
Use this tool when you need a box-like enclosure generated from numeric dimensions.

## Parameters
- **Width X**, **Depth Y**, **Height Z** define the outside dimensions.
- **Thickness** is the material thickness used by the joint computation.
- **Vertical corners** controls the joint style on vertical edges.
- **Top/Bottom <-> Front/Back** controls joints between horizontal faces and front/back faces.
- **Top/Bottom <-> Left/Right** controls joints between horizontal faces and side faces.

## Workflow
Set dimensions and joints, then click **Generate preview**. Inspect the generated parts, then use **Apply** to keep the result or **Cancel** to restore the previous model.
""",
    ),
    TOOL_LAYFLAT: ToolHelpDocument(
        TOOL_LAYFLAT,
        "Lay flat",
        "Flatten and pack selected parts for laser preparation while keeping a configurable spacing and packing area.",
        """
## When to use it
Use this tool to prepare 3D pieces as flat laser-cut layouts.

## Parameters
- **Spacing** is the distance between laid-flat parts.
- **Overlap** and **Contact tolerance** control when adjacent outlines are considered mergeable or touching.
- **Max X** and **Max Y** define the packing area limits.
- **Merging** controls whether overlapping or touching outlines are merged.
- **Packing constraint** chooses whether packing prioritizes X, Y, or no fixed constraint.
- **Allow XY 90 deg rotation** lets the tool rotate pieces to improve packing.

## Workflow
Adjust the constraints, click **Preview lay flat**, then validate with **Apply** or reject with **Cancel**.
""",
    ),
    TOOL_JOINT: ToolHelpDocument(
        TOOL_JOINT,
        "Joint builder",
        "Create joints between two touching parts by selecting part A then part B directly in the 3D view.",
        """
## When to use it
Use this tool to add mechanical joints between two parts that touch or nearly touch.

## Parameters
- **Contact tolerance** defines how far two surfaces may be and still be considered in contact.
- **Clearance** controls fit. Positive values create looser slots; negative values create tighter interference fits.
- **Size** defines the size of each joint feature.
- **Count** is the number of joints distributed along the contact edge.
- **Edge margin** keeps joints away from the ends of the edge.
- **Compute depth only once** is faster and usually sufficient.
- **Detailed debug log** writes more diagnostics to the log panel.

## Workflow
Click the first part, then the second part. Click **Add joint to preview**, then use **Apply** or **Cancel**.
""",
    ),
    TOOL_ENGRAVING: ToolHelpDocument(
        TOOL_ENGRAVING,
        "Engraving roles",
        "Assign laser export roles to parts so the 2D engraving export knows what to cut, fill, or ignore.",
        """
## When to use it
Use this tool before generating laser engraving/cutting exports.

## Parameters
- **Role** selects the export role applied to clicked parts.
- **Outline contour** marks a part for black outline export.
- **Fill engraving** marks a part for filled black engraving.
- **Ignore / preview only** keeps the part visible in Studio but ignored by black/white laser export.

## Workflow
Select a role, then click parts in the 3D view. Changes are staged as preview changes. Use **Apply** to keep the role assignments or **Cancel** to discard them.
""",
    ),
    TOOL_MATERIAL: ToolHelpDocument(
        TOOL_MATERIAL,
        "Materials",
        "Assign visual materials and colors to selected or clicked pieces.",
        """
## When to use it
Use this tool to make parts easier to identify, preview material appearance, or prepare role/color conventions.

## Parameters
The panel exposes material/color controls for the current target. Exact controls depend on the selected material workflow.

## Workflow
Open the tool, select or click a target part, adjust material settings, then validate the staged result with **Apply**. Use **Cancel** to return to the previous material state.

## Notes
Material changes are visual and organizational; they do not replace geometric operations such as boolean union or subtraction.
""",
    ),
    TOOL_TEXTURE_PROJECTION: ToolHelpDocument(
        TOOL_TEXTURE_PROJECTION,
        "Texture projection",
        "Project an image texture onto a mesh or create an independent decal for engraving/visual layout.",
        """
## When to use it
Use this tool to place an image on a face or mesh before export or engraving preparation.

## Parameters
- **Image file** loads the source texture.
- **Projection mode** controls how UVs are generated, such as planar or object-based projection.
- **Repeat** allows UV coordinates outside the 0..1 range for repeated texture patterns.
- **Attach to mesh** embeds the texture into the selected mesh; when disabled, a separate decal is created.
- **Preserve aspect** prevents image stretching by keeping the original image ratio.
- **Rotation / move gizmo** lets you rotate or move the projected texture directly in the viewport.

## Workflow
Load an image, choose projection options, click or select the target, adjust placement with the TEX gizmo, then use **Apply** or **Cancel**.
""",
    ),
    TOOL_PLAN_TRACE: ToolHelpDocument(
        TOOL_PLAN_TRACE,
        "Plan tracer",
        "Draw a locked 2D polygon in the current view plane, then extrude it into a 3D part.",
        """
## When to use it
Use this tool when you want to sketch a custom flat profile directly in the 3D view and turn it into a solid.

## Modes
- **ADD** places polygon points in order. Hold the click to preview the moving point; release to place it. Double-click closes the polygon.
- **MOD** selects the nearest point for precise editing. Its coordinates appear in the Transform fields.
- **SUPP** deletes the nearest point.
- **RST** clears the draft and starts again.

## Parameters
- **Depth** is the extrusion thickness in millimetres.
- **Grid snap** and **Smart snap** help place points on useful positions.

## Workflow
Open the tool, let Studio lock the closest orthographic view, place at least three points, double-click to close the profile, set the depth, then click **Apply**.
""",
    ),
    TOOL_FOLDING: ToolHelpDocument(
        TOOL_FOLDING,
        "Folding",
        "Fold a mesh around a living-hinge band while both outer regions remain rigid.",
        """
## When to use it
Use Folding to preview laser-cut living hinges, flexure strips and similar bendable zones. The two limits bound the flexible band. One outer region stays fixed and the other moves as a rigid body.

## Parameters
- **Fold angle** controls the final rotation from -720° to 720°. Angles above 180° can self-intersect.
- **Fixed part** chooses which outer region remains stationary.
- **Hinge width** is the neutral-line length between the two limits.
- **Shape handles** chooses 1, 3, 5 or 7 purple controls for the curvature distribution.

## Geometry
The flexible band's neutral line follows an editable smooth profile whose length always equals the original hinge width. Zero shape offsets reproduce the previous circular arc. Moving the purple controls redistributes the local tangent angle, allowing progressive bends, concentrated bends and S-curves. Cross-sections are transported along that centerline. Geometry outside the band is transformed rigidly, so its proportions and pairwise distances are preserved. A sufficiently tessellated hinge band gives the smoothest preview.

## Workflow
1. Click the mesh.
2. Click the face containing the hinge.
3. Place the first and second limits across the flexible band.
4. Drag the purple shape handles to design the curve and use the blue handle or Angle field for the terminal direction.
5. Pause briefly for the 3D preview, then use **Apply**.

Curve overlays update immediately; the expensive mesh preview is rebuilt only after a short idle delay or immediately when Apply is pressed. Older free-curve Folding results remain editable in legacy mode.
""",
    ),
    TOOL_CLOTH: ToolHelpDocument(
        TOOL_CLOTH,
        "Cloth",
        "Create textile quickly from logical mesh surfaces, connect panels intelligently, assign textile functions and regenerate a linked flat pattern.",
        """
## When to use it
Use Cloth to design the flexible parts of a hybrid object directly around the rigid meshes already present in the scene. The tool remains geometric and deterministic: it creates editable textile panels and a linked flat pattern, not a gravity or stretch simulation.

## Main workspace
- **Draw textile** creates geometry through **Add mesh faces**, **Join faces** or **Draw polyline**.
- **Textile properties** selects finished panels and assigns **Textile**, **Pattern** or **Junction** functions.

## Add mesh faces
Hover a rigid mesh to preview the complete logical surface recognized by the shared smart-selection API. Click replaces the selection; Shift+click adds logical surfaces, including surfaces on another mesh. Use **Create textile** to turn the selected regions into editable panels. A quick double-click in empty space clears the source selection.

## Join faces
Select at least two existing textile faces. Cloth analyzes their closed boundaries, chooses a minimal set of connections, aligns the corresponding rails and previews one or more ruled panels. Review alternatives with Previous/Next, then use **Create junction**. Coplanar panels are connected through their closest compatible boundary edges; panels separated through their normal direction can receive a complete side strip.

## Draw polyline
Draw a manual 3D boundary with the same Smart Snap infrastructure used by Plan Tracer. Closing the loop creates a textile face. Use **Finish open** when an open boundary is intentionally required.

## Textile properties and layers
Selected faces can be assigned one of three functions:
- **Textile**: normal material face;
- **Pattern**: decorative, engraved or cut-pattern carrier;
- **Junction**: functional connection to wood or another textile layer.

The inspector assigns the panel name, layer identifier, material name and nominal layer thickness. Entering a new layer identifier creates it. Multiple panels can share one layer; different layers prepare lining, reinforcement and stacked textile workflows. In this version, nominal layer thickness is manufacturing metadata; the closed 3D boolean output still uses the global Material thickness in Output.

## Output
- **Flat preview** validates and displays the current pattern.
- **Apply** commits the folded and flat outputs but keeps Cloth open for further editing.
- **Finish** commits and closes the tool.
- **Cancel** restores the last committed source when editing an existing Cloth.

The folded output remains a topology-safe thin solid for boolean cuts. Reopening that output restores the editable Cloth source, including face functions, layers, materials and join provenance.
""",
    ),
    TOOL_MECHANICAL_MOTION: ToolHelpDocument(
        TOOL_MECHANICAL_MOTION,
        "Mechanical motion",
        "Create editable gears, compound gear trains and rack mechanisms, then test how motion propagates.",
        """
## When to use it
Use this tool to place individual gears, generate multi-stage gear trains, connect racks or scene parts, and validate their motion before committing the assembly. The construction plane comes from a selected face, while the camera remains free to orbit.

## Parameters
- **Gear geometry** controls module, tooth count, thickness, bore, pressure angle and backlash.
- **Chain ratio** and **Distribution** define how a requested transmission ratio is shared across intermediate shafts.
- **Curve handles** route a generated chain between its start and end shafts.
- **Driver** assigns the single rotary input and its speed.
- **Attach** binds selected scene parts to a rotary or linear motion source.
- **Rack settings** control its dimensions, clearance and engagement with a selected pinion.

## Workflow
1. Select a planar face or click an existing MEC assembly to edit it.
2. Place a gear, a chain or a rack and adjust its parameters.
3. Use smart snap or explicit connections to create the mechanical graph.
4. Select a mesh as **Driver**, then use **Attach** for additional scene parts.
5. Enter **Test** to scrub or animate the mechanism.
6. Use **Apply** to keep the editable assembly. **Cancel** leaves a selectable red recoverable draft.

Applied and draft assemblies preserve their source parameters, links and undeformed scene attachments, so reopening the tool edits the existing mechanism instead of duplicating it.
""",
    ),
    TOOL_VENT_GENERATOR: ToolHelpDocument(
        TOOL_VENT_GENERATOR,
        "Vent generator",
        "Draw a rectangular/square audio port path with a lightweight footprint preview, point-based curve sliders, smart/grid snap, and final mesh generation.",
        """
## When to use it
Use this tool to design rectangular or square speaker vents/ports while monitoring path length, extrusion height, wall thickness and a first-pass box tuning estimate.

## Modes
- **ADD** places normal waypoints. New segments are straight by default.
- **MOD** selects and moves waypoints. The selected waypoint exposes the curve controls for its associated segment in the toolbox.
- **SUPP** removes the nearest waypoint.
- **RST** clears the path.

## Parameters
- **Inner width / Inner height** define the rectangular airway. Inner height is also the vent extrusion height.
- **Wall thickness** is the material kept around the air passage.
- **Target length** shows the difference between the drawn length and the desired acoustic length.
- **Box volume** drives the Helmholtz-style tuning estimate shown in the toolbox.
- **Curve radius** and **Curve force** are sliders for the segment associated with the selected waypoint in MOD.
- **Fill area** fills the global rectangular stock footprint and carves only the inner airway.
- **Flare side** selects inlet, outlet, both, or no flared opening.
- **Flare factor** controls how much the selected opening is enlarged.

## Workflow
Place the centerline in ADD, switch to MOD to select a point and tune its segment curve with the sliders, use the red cursor feedback to avoid centerline crossings, check the length report, then use **Apply** to generate the final mesh. The preview displays the actual outer and inner footprints instead of fragile separate offset lines, so tight bends stay readable.
""",
    ),
    TOOL_VOLUME_MEASURE: ToolHelpDocument(
        TOOL_VOLUME_MEASURE,
        "Cavity volume",
        "Measures the closed internal empty volume of a fused part or selected closed assembly, and reports it in liters.",
        """
## When to use it
Use this tool after a fusion/boolean operation when one selected part contains a closed internal cavity, or when several selected parts together form one closed volume/cavity.

## Parameters
There are no shape parameters. The tool uses the currently selected mesh and reports:
- cavity volume in litres;
- approximate outer envelope volume;
- estimated solid material volume;
- detected closed shells and cavity count.

## Workflow
Select one fused part, or select all pieces that together form the closed volume, open **VOL / Cavity volume**, then click **Measure selected cavity**. Open pockets, vents and through-holes are not counted as closed cavities. If the selection is not watertight, run **Repair mesh** first.
""",
    ),

    TOOL_ACOUSTIC_DIFFUSER: ToolHelpDocument(
        TOOL_ACOUSTIC_DIFFUSER,
        "Acoustic diffuser",
        "Generate a native speaker diffuser and skirt without OpenSCAD or BOSL dependencies.",
        """
## When to use it
Use this tool to create a first-pass acoustic diffuser/skirt geometry for a speaker outlet. It is inspired by the previous OpenSCAD prototype, but it is fully generated by LaserProg Studio.

## Parameters
- **Target** sets the acoustic tuning target in hertz.
- **Outer Ø** is the outside diameter of the skirt.
- **Speaker Ø** is used for fit warnings.
- **Wall** defines the radial skirt thickness.
- **Vents** chooses holes, slots, or no side vents.
- **Resolution** controls mesh density. Use **Low** while iterating for better performance, then **High** only when a smoother final export is needed.
- **Count** controls how many repeated vents are distributed around the skirt.
- **Size** controls the hole diameter or slot height. Slot width is chosen automatically.

## Generated geometry
The tool creates two native meshes: the annular skirt and the diffuser core. The skirt vents are not SCAD booleans; they are built directly in the cylindrical mesh, so the result stays independent from OpenSCAD.

## Report
The report gives a simple cavity volume, Helmholtz estimate, exit gap and air-conductance split between the ring outlet and vents. These values are useful for design direction, not a replacement for a full loudspeaker simulation.

## Workflow
Adjust the compact controls, click **Generate preview**, then use **Apply** to commit the generated meshes or **Cancel** to discard them.
""",
    ),
    TOOL_MOD_SPLIT: ToolHelpDocument(
        TOOL_MOD_SPLIT,
        "Split modifier",
        "Cut selected meshes with an editable split plane.",
        """
## When to use it
Use this modifier to divide one or more parts along a plane.

## Parameters
- **Plane position / orientation** is controlled through the split handle in the viewport and any numeric controls exposed by the panel.
- **Preview** shows the result before committing.

## Workflow
Select the target mesh or meshes, open the modifier, position the split plane, preview the result, then click **Apply**. Use **Cancel** to keep the original parts.
""",
    ),
    TOOL_MOD_SIMPLIFY: ToolHelpDocument(
        TOOL_MOD_SIMPLIFY,
        "Simplify modifier",
        "Reduce mesh complexity while trying to preserve the visible shape.",
        """
## When to use it
Use this modifier on heavy meshes that slow down editing or are too detailed for the intended fabrication process.

## Parameters
- **Reduction / target controls** define how aggressively the mesh is simplified.
- **Preserve topology** tries to avoid changing the mesh connectivity too aggressively.

## Workflow
Select one or more meshes, adjust simplification settings, generate a preview, then use **Apply** when the result keeps enough detail.
""",
    ),
    TOOL_MOD_RELIEF: ToolHelpDocument(
        TOOL_MOD_RELIEF,
        "Relief modifier",
        "Create raised or engraved relief geometry from an image mask or text source.",
        """
## When to use it
Use this modifier to turn graphics or text into shallow 3D relief suitable for decorative or engraving workflows.

## Parameters
- **Source image/text** defines the relief pattern.
- **Height/depth** controls how far the relief is raised or engraved.
- **Resolution / smoothing controls** affect detail and mesh density.

## Workflow
Select the target mesh, configure the relief source and strength, preview the result, then validate with **Apply**.
""",
    ),
    TOOL_MOD_EXTRUDE_DOWN: ToolHelpDocument(
        TOOL_MOD_EXTRUDE_DOWN,
        "Extrude down modifier",
        "Extend selected geometry downward from a chosen reference area or handle.",
        """
## When to use it
Use this modifier to add downward thickness, create support material, or extend a shape to a lower reference level.

## Parameters
- **Depth / target controls** define how far the extrusion is applied.
- **Viewport handle** lets you adjust the extrusion interactively.

## Workflow
Select a mesh, open the modifier, adjust the extrusion handle or numeric controls, inspect the preview, then use **Apply** or **Cancel**.
""",
    ),
    TOOL_MOD_HOLLOW: ToolHelpDocument(
        TOOL_MOD_HOLLOW,
        "Hollow modifier",
        "Shell selected meshes by removing interior material while keeping a controlled wall thickness.",
        """
## When to use it
Use this modifier to reduce material usage or create hollow parts with a predictable wall.

## Parameters
- **Wall thickness** controls the target shell thickness.
- **Openings / options** depend on the current hollow workflow and define how the shell is generated.

## Workflow
Select the mesh, set the wall thickness, generate a preview, inspect thin or complex areas, then click **Apply** when the shell is acceptable.
""",
    ),
    TOOL_MOD_REPAIR: ToolHelpDocument(
        TOOL_MOD_REPAIR,
        "Repair mesh modifier",
        "Clean selected meshes before export or further operations.",
        """
## When to use it
Use this modifier when a mesh has holes, inconsistent normals, duplicate geometry, non-manifold regions, or export problems.

## Parameters
The repair panel exposes cleanup options depending on the detected mesh issues.

## Workflow
Select one or more problematic meshes, open the modifier, run the preview repair, inspect the result, then use **Apply** to replace the original meshes.

## Notes
Repair can change topology. Keep a backup or use **Cancel** if the result removes important detail.
""",
    ),
    TOOL_SMART_SURFACE_SELECTION_TEST: ToolHelpDocument(
        TOOL_SMART_SURFACE_SELECTION_TEST,
        "Selection API test",
        "Test the shared intelligent surface-selection engine on arbitrary triangular meshes before production integration.",
        """
## When to use it
Use this diagnostic tool to evaluate how LaserProg groups mesh triangles into one logical face, including slightly curved surfaces.

## Parameters
- **Hover Auto** searches for a stable semantic proposal and sets the calculated continuity value.
- **Continuity** ranges from 0 to 1. Low values stay close to the seed triangle; high values accept broader smooth curvature.
- **Profile** switches between the future Cloth-support behaviour and a stricter exact-face behaviour.
- **Show hover proposal** previews the predicted region before clicking.
- **Show logical boundary** displays the detected external contour.
- **Reuse learned logical regions** is optional and disabled by default; exact seed and accessibility caches remain active.
- The result panel reports the exact canonical face and any `cell → face` remapping; no viewport hit marker is drawn.
- **Capture performance diagnostics** buffers detailed hover, click, picking, remapping, solver and overlay timings without writing to disk on every mouse move.
- **Reset / Export** clears the trace or writes the JSONL, JSON and Markdown reports under `diagnostics/`.
- **Last hover / Last click** expose the latest end-to-end interaction latency.

## Workflow
Hover a visible mesh face and inspect the green logical proposal. Click to replace the blue selection with that complete logical region. Use **Shift+click** to add another complete logical region. Clicking empty space leaves the selection unchanged. Double-clicking a surface has no special action; double-clicking empty space clears the selection. Camera drags are filtered by the shared pointer state machine. Test exact picking with logical reuse disabled first, then enable it to evaluate conservative cross-seed reuse.
""",
    ),
}


def iter_tool_help_documents() -> tuple[ToolHelpDocument, ...]:
    return tuple(_TOOL_HELP_DOCS.values())


def get_tool_help_document(tool_id: str | None) -> ToolHelpDocument | None:
    if tool_id is None:
        return None
    return _TOOL_HELP_DOCS.get(str(tool_id))


def render_tool_help_markdown(tool_id: str | None) -> str:
    doc = get_tool_help_document(tool_id)
    if doc is None:
        return (
            "# Tool help\n\n"
            "No dedicated documentation is available for this tool yet.\n\n"
            "This usually means the tool is experimental or provided by an extension."
        )
    return doc.as_markdown()
