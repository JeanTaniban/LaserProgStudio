# Cloth Close global coverage — v164

## Problem

The previous Close solver used the nearest compatible technical edge for
lateral faces. This could be geometrically valid while covering only a tiny
part of two complete logical groups.

## Contract

A complete logical group selection expresses a complete construction scope.
The solver must maximise usable boundary coverage before minimising local
width.

## Candidate ranking

- substantial facing chain on lateral groups;
- complete boundary alignment when facing coverage is insufficient or the
  groups are offset through their normals;
- multi-loop alignment for equal loop counts;
- local edge fallback only after coverage penalties.

## Safety

Invalid cells are removed individually. Runs below the minimum coverage are
rejected. Commit remains transactional through `commit_join_proposal`.

## Complexity

Boundary samples are capped at 72. Pair alignment and facing-chain discovery
are bounded by small dense loops and remain suitable for interactive preview.
