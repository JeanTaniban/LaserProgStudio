# Pass181 — Minimal dot selection feedback and frozen Creator UI runtime contract

- Selected/grabbed runtime feedback now overrides requested baseline visual states in `tool_api.styles.resolve_actor_visual(...)`.
- This fixes the `minimal` point style when a motif requested `visual_state="grabbable"`: it no longer stays blue after selection; it resolves to yellow when selected and orange while grabbed/dragged.
- The public API exports `CREATOR_UI_RUNTIME_CONTRACT = "native_non_overridable"` so docs/tests can assert the intended boundary.
- Documentation now states that external tool authors declare actors and official styles only. Hover/select/grab feedback, drag fast paths, camera orientation and FOV scaling remain native runtime responsibilities.
