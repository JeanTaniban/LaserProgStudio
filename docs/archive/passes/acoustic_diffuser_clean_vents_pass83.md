# Pass 83 - Acoustic diffuser clean vent holes

The acoustic diffuser skirt no longer cuts round vents by dropping coarse cells from a cylindrical grid.

Changes:

- vents are described as continuous contours in developed cylinder coordinates;
- round holes use circular contours with adaptive segment count;
- slots use rounded-rectangle contours;
- the cylindrical skirt wall is triangulated around those contours using Shapely constrained Delaunay triangulation;
- each opening receives radial tunnel faces connecting the outer and inner wall contours;
- the generator stays native Python/mesh and does not depend on OpenSCAD or BOSL;
- the acoustic conductance report uses the same effective vent contours as the mesh generator, including size clamping near pitch or top/bottom limits.

This keeps the user workflow simple while producing clean 3D binary geometry instead of pixel-like vent boundaries.
