# Architecture Migration Pass 25 — Vent end flares

This pass finishes the audio vent tool with configurable anti-chuff end flares.

## User-facing changes

- The vent panel now exposes an `Évasement embouchure` selector: none, inlet, outlet, or both.
- A `Coef évasement` spin box controls how much the selected opening widens.
- The option works for round and rectangular vents.
- The option remains compatible with rectangular `Only walls` mode.

## Geometry contract

The mesh generator widens the internal section at the selected end and rebuilds
the outer section from that widened internal section plus the requested minimum
wall thickness. This preserves the minimum wall thickness instead of simply
scaling the whole mesh.

The transition length is derived automatically from the vent section and path
length. The UI therefore stays simple while avoiding an abrupt acoustic step.

## Safety

The clearance policy uses the largest effective flared internal width, so the
interactive clamp does not allow a path that would become unsafe only after mesh
generation.
