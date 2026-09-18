# LaserProg v104 - Python 3.12.x launcher and MEC toolbar icon

## Python launcher compatibility

The Windows launcher, dependency installer, and dependency checker now accept
any stable Python 3.12 patch release. Python 3.11 and Python 3.13 remain rejected
because the tested Qt/PyVista/VTK runtime targets the Python 3.12 ABI.

The package versions in `requirements.txt` remain pinned exactly. Only the
Python patch-level restriction was relaxed.

## MEC toolbar icon

The Mechanical Motion tool now has a dedicated lightweight toolbar asset:
`tool_mechanical_motion.png`.

The icon follows the existing LaserProg toolbar language: transparent 128 x 128
PNG, dark navy contour, pale blue mechanical body, limited orange and green
accents, and a compact silhouette readable at toolbar size. The optimized indexed
PNG is approximately 3 KB and replaces the previous text-only `MEC` fallback.
