# Pass 241 — Vent Generator viewport feedback

Vent Generator received a Creator API feedback pass focused on live user guidance.

- Added `tooling/vent_generator/feedback.py` with a serialisable route snapshot.
- Published shared preview items for centerline, waypoints, labels, selected point, pending point and snap marker.
- Added a Creator overlay toolbar for ADD/MOD/SUPP/RST plus Preview/Apply/Clear actions.
- Added a status overlay with route, selection, snap and status text.
- Added `viewport_feedback` to the declarative inspector panel.
- Added tests for preview publication and overlay button routing.

Validation target: keep the PyVista planar preview path working while making the Creator API layer useful in headless and future hosts.
