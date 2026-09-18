# Boolean Separate Tool Update

Added a third boolean action in the top toolbar:

- `SEP`: separates disconnected islands inside the selected mesh(es).

This is useful after a boolean subtraction where one resulting mesh contains
several disconnected solids. The operation replaces each selected mesh by its
connected triangle islands and selects the newly created parts.

Connectivity is based on shared triangle vertices. The tool does not run a new
boolean operation and does not require manifold3d.
