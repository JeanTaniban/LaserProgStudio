# MEC v103 — Smart snap and fast gear drag

## Drag performance contract

A standalone gear drag must never regenerate mechanical geometry for every pointer event.

During drag:

- the existing VTK actor is moved with an affine matrix when the runtime supports it;
- a lightweight projected outline shows the actual tooth silhouette, pitch circle and centre;
- if actor transformation is unavailable, the actor is hidden and the projected outline remains as the fallback preview;
- no `WorkMesh`, document preview, kinematic solve or scene rebuild is performed.

On release, the actor transform is restored and the mechanical preview is rebuilt once from the committed domain state.

## Smart mesh contract

Only a unique standalone gear can initiate this drag workflow. A snap candidate requires:

- compatible modules and pressure angles;
- axial overlap on the current mechanical work plane;
- different shafts;
- a pitch-circle centre-distance error inside the capture radius.

The snap computes the exact pitch-circle centre distance and a tooth phase that preserves the target gear's current phase at the contact point. Releasing on the candidate creates a persistent `smart_mesh` gear stage. Moving the gear away removes its previous smart stage.

The projected overlay displays the dragged tooth silhouette, both pitch circles, the contact point and a persistent connection marker after release.
