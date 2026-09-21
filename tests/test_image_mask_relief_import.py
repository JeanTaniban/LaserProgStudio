# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import math
import tempfile
import unittest

from PIL import Image, ImageDraw

import _path_setup  # noqa: F401
from laserprog_studio.geometry_ops.image_mask_relief import build_mask_relief_mesh, render_mask_preview_image
from laserprog_studio.geometry_ops.image_mask_relief_contour import build_binary_mask_footprint
from laserprog_studio.boolean_ops import is_closed_triangle_mesh


class ImageMaskReliefImportTest(unittest.TestCase):
    def test_grayscale_mask_maps_black_to_full_height_and_white_to_void(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "mask.png"
            # top-left black, top-right 50%, bottom-left white, bottom-right dark gray
            img = Image.new("L", (2, 2))
            img.putdata([0, 128, 255, 64])
            img.save(path)

            result = build_mask_relief_mesh(path, max_height_mm=4.0, pixel_size_mm=2.0, max_grid_size=0)
            zs = [round(v[2], 3) for v in result.mesh.vertices]
            self.assertIn(4.0, zs)
            self.assertTrue(any(1.9 <= z <= 2.1 for z in zs))
            self.assertGreaterEqual(result.stats.active_pixels, 3)
            self.assertEqual(result.stats.width, 2)
            self.assertEqual(result.stats.height, 2)
            self.assertGreater(len(result.mesh.triangles), 0)
            self.assertEqual(is_closed_triangle_mesh(result.mesh.vertices, result.mesh.triangles), (True, 0, 0))

    def test_invert_swaps_black_and_white(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "mask.png"
            img = Image.new("L", (2, 1))
            img.putdata([0, 255])
            img.save(path)

            result = build_mask_relief_mesh(path, max_height_mm=3.0, pixel_size_mm=1.0, invert=True, max_grid_size=0)
            xs_at_top = [round(v[0], 3) for v in result.mesh.vertices if abs(v[2] - 3.0) < 1e-6]
            self.assertTrue(xs_at_top)
            self.assertEqual(result.stats.active_pixels, 1)


class ImageMaskReliefBinaryImportTest(unittest.TestCase):
    def test_binary_mask_uses_full_height_or_void_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "mask.png"
            img = Image.new("L", (4, 1))
            # Normal mapping: black/dark enough are active; light pixels are void.
            img.putdata([0, 126, 128, 255])
            img.save(path)

            result = build_mask_relief_mesh(
                path,
                max_height_mm=5.0,
                pixel_size_mm=1.0,
                binary=True,
                max_grid_size=0,
            )
            non_zero_z = sorted({round(v[2], 6) for v in result.mesh.vertices if v[2] > 0})
            self.assertEqual(non_zero_z, [5.0])
            self.assertEqual(result.stats.active_pixels, 2)
            self.assertTrue(result.stats.binary)


    def test_binary_threshold_is_user_controllable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "mask.png"
            img = Image.new("L", (4, 1))
            # reliefs after normal mapping: 1.0, 0.75, 0.5, 0.25
            img.putdata([0, 64, 128, 191])
            img.save(path)

            result = build_mask_relief_mesh(
                path,
                max_height_mm=3.0,
                pixel_size_mm=1.0,
                binary=True,
                binary_threshold=0.7,
                max_grid_size=0,
            )
            self.assertEqual(result.stats.active_pixels, 2)
            self.assertAlmostEqual(result.stats.binary_threshold, 0.7, places=6)
            non_zero_z = sorted({round(v[2], 6) for v in result.mesh.vertices if v[2] > 0})
            self.assertEqual(non_zero_z, [3.0])




    def test_mask_preview_image_reflects_levels_and_invert(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "preview_mask.png"
            img = Image.new("L", (8, 4), 255)
            draw = ImageDraw.Draw(img)
            draw.rectangle((0, 0, 2, 3), fill=0)
            draw.rectangle((4, 0, 7, 3), fill=210)
            img.save(path)

            normal = render_mask_preview_image(path, levels=50, smooth=0, max_grid_size=0, max_preview_size=(8, 4))
            inverted = render_mask_preview_image(path, invert=True, levels=50, smooth=0, max_grid_size=0, max_preview_size=(8, 4))

            normal_pixels = list(normal.convert("L").getdata())
            inverted_pixels = list(inverted.convert("L").getdata())
            self.assertNotEqual(normal_pixels, inverted_pixels)
            self.assertLess(min(normal_pixels), 80)
            self.assertGreater(max(normal_pixels), 200)

    def test_smart_levels_and_smooth_make_clean_binary_vector_shape(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ellipse_mask.png"
            img = Image.new("RGBA", (96, 96), (255, 255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw.ellipse((16, 12, 80, 84), fill=(0, 0, 0, 255))
            img.save(path)

            result = build_mask_relief_mesh(
                path,
                max_height_mm=10.0,
                pixel_size_mm=1.0,
                binary=True,
                levels=50,
                smooth=45,
                max_grid_size=0,
            )

            z_values = sorted({round(v[2], 6) for v in result.mesh.vertices})
            self.assertEqual(z_values, [0.0, 10.0])
            self.assertLess(result.stats.vertices, result.stats.active_pixels // 5)
            self.assertEqual(is_closed_triangle_mesh(result.mesh.vertices, result.mesh.triangles), (True, 0, 0))


    def test_smooth_does_not_blur_or_drop_thin_mask_edges(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "thin_stroke.png"
            img = Image.new("L", (24, 12), 255)
            draw = ImageDraw.Draw(img)
            draw.line((2, 6, 21, 6), fill=0, width=1)
            img.save(path)

            raw = build_mask_relief_mesh(
                path,
                max_height_mm=10.0,
                pixel_size_mm=1.0,
                binary=True,
                levels=50,
                smooth=0,
                max_grid_size=0,
            )
            smoothed = build_mask_relief_mesh(
                path,
                max_height_mm=10.0,
                pixel_size_mm=1.0,
                binary=True,
                levels=50,
                smooth=100,
                max_grid_size=0,
            )

            self.assertEqual(raw.stats.active_pixels, 20)
            self.assertEqual(smoothed.stats.active_pixels, raw.stats.active_pixels)
            self.assertEqual(sorted({round(v[2], 6) for v in smoothed.mesh.vertices}), [0.0, 10.0])
            self.assertEqual(is_closed_triangle_mesh(smoothed.mesh.vertices, smoothed.mesh.triangles), (True, 0, 0))

    def test_subpixel_circle_contour_is_not_pixel_staircase(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "circle_aa.png"
            scale = 4
            big = Image.new("L", (160 * scale, 160 * scale), 255)
            draw = ImageDraw.Draw(big)
            draw.ellipse((20 * scale, 20 * scale, 140 * scale, 140 * scale), fill=0)
            big.resize((160, 160), Image.Resampling.LANCZOS).save(path)

            footprint = build_binary_mask_footprint(
                path,
                pixel_size_mm=1.0,
                levels=50,
                smooth=0,
                max_grid_size=0,
            )
            poly = footprint.geometry
            self.assertEqual(poly.geom_type, "Polygon")
            coords = list(poly.exterior.coords)
            perimeter = 0.0
            axis_length = 0.0
            radial_sq = []
            max_error = 0.0
            for a, b in zip(coords, coords[1:]):
                dx = float(b[0] - a[0])
                dy = float(b[1] - a[1])
                length = math.hypot(dx, dy)
                perimeter += length
                if abs(dx) <= 1e-12 or abs(dy) <= 1e-12:
                    axis_length += length
            for x, y in coords[:-1]:
                error = abs(math.hypot(float(x), float(y)) - 60.0)
                radial_sq.append(error * error)
                max_error = max(max_error, error)
            rms = math.sqrt(sum(radial_sq) / max(len(radial_sq), 1))

            self.assertLess(axis_length / max(perimeter, 1e-12), 0.15)
            self.assertLess(rms, 0.30)
            self.assertLess(max_error, 0.60)

    def test_smooth_preserves_holes_and_thin_feature_topology(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "thin_features.png"
            img = Image.new("L", (160, 160), 255)
            draw = ImageDraw.Draw(img)
            draw.line((12, 80, 148, 80), fill=0, width=2)
            draw.line((80, 12, 80, 148), fill=0, width=2)
            draw.ellipse((55, 55, 105, 105), outline=0, width=2)
            img.save(path)

            raw = build_binary_mask_footprint(
                path,
                pixel_size_mm=1.0,
                levels=50,
                smooth=0,
                max_grid_size=0,
            )
            smoothed = build_binary_mask_footprint(
                path,
                pixel_size_mm=1.0,
                levels=50,
                smooth=100,
                max_grid_size=0,
            )

            def signature(geometry):
                polys = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)
                return len(polys), tuple(sorted(len(poly.interiors) for poly in polys))

            self.assertEqual(signature(smoothed.geometry), signature(raw.geometry))
            self.assertLess(
                abs(float(smoothed.geometry.area) - float(raw.geometry.area)),
                max(float(raw.geometry.area) * 0.08, 1.0),
            )

    def test_downsample_preserves_source_physical_extent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "large_black.png"
            Image.new("L", (512, 256), 0).save(path)

            footprint = build_binary_mask_footprint(
                path,
                pixel_size_mm=1.0,
                levels=50,
                smooth=0,
                max_grid_size=128,
            )

            self.assertTrue(footprint.downsampled)
            self.assertEqual((footprint.width, footprint.height), (128, 64))
            self.assertAlmostEqual(footprint.physical_width_mm, 512.0, places=6)
            self.assertAlmostEqual(footprint.physical_height_mm, 256.0, places=6)
            minx, miny, maxx, maxy = footprint.geometry.bounds
            self.assertLess(abs((maxx - minx) - 512.0), 0.05)
            self.assertLess(abs((maxy - miny) - 256.0), 0.05)

    def test_smoothing_report_is_persisted_and_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "smooth_report.png"
            img = Image.new("L", (120, 120), 255)
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle((12, 12, 108, 108), radius=26, fill=0)
            draw.ellipse((44, 44, 76, 76), fill=255)
            img.save(path)

            footprint = build_binary_mask_footprint(
                path,
                pixel_size_mm=1.0,
                levels=50,
                smooth=73,
                max_grid_size=0,
            )
            report = footprint.smoothing_report

            self.assertAlmostEqual(report.requested_level, 73.0, places=6)
            self.assertGreaterEqual(report.accepted_level, 0.0)
            self.assertLessEqual(report.accepted_level, report.requested_level)
            self.assertEqual(report.source_components, report.result_components)
            self.assertEqual(report.source_holes, report.result_holes)
            self.assertEqual(report.fallback_used, report.accepted_level + 1.0e-9 < report.requested_level)

            result = build_mask_relief_mesh(
                path,
                max_height_mm=6.0,
                pixel_size_mm=1.0,
                binary=True,
                levels=50,
                smooth=73,
                max_grid_size=0,
            )
            metadata = result.mesh.metadata or {}
            self.assertAlmostEqual(float(metadata["mask_smooth_requested"]), report.requested_level, places=6)
            self.assertAlmostEqual(float(metadata["mask_smooth_accepted"]), report.accepted_level, places=6)
            self.assertEqual(bool(metadata["mask_smooth_fallback"]), bool(report.fallback_used))

    def test_smart_import_treats_transparent_background_as_empty_white(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "transparent_mask.png"
            img = Image.new("RGBA", (20, 20), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            draw.rectangle((5, 5, 14, 14), fill=(0, 0, 0, 255))
            img.save(path)

            result = build_mask_relief_mesh(
                path,
                max_height_mm=10.0,
                pixel_size_mm=1.0,
                binary=True,
                levels=50,
                smooth=0,
                max_grid_size=0,
            )

            self.assertEqual(result.stats.active_pixels, 100)
            self.assertEqual(sorted({round(v[2], 6) for v in result.mesh.vertices}), [0.0, 10.0])

    def test_binary_invert_applies_threshold_after_inversion(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "mask.png"
            img = Image.new("L", (4, 1))
            img.putdata([0, 126, 128, 255])
            img.save(path)

            result = build_mask_relief_mesh(
                path,
                max_height_mm=2.5,
                pixel_size_mm=1.0,
                invert=True,
                binary=True,
                max_grid_size=0,
            )
            non_zero_z = sorted({round(v[2], 6) for v in result.mesh.vertices if v[2] > 0})
            self.assertEqual(non_zero_z, [2.5])
            self.assertEqual(result.stats.active_pixels, 2)


class ImageMaskReliefBooleanSafetyTest(unittest.TestCase):
    def test_grayscale_mask_with_diagonal_and_hole_contacts_is_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "complex_mask.png"
            img = Image.new("L", (6, 6))
            img.putdata([
                0, 255, 128, 255, 255, 64,
                128, 0, 0, 128, 192, 255,
                0, 128, 192, 128, 255, 64,
                255, 192, 192, 255, 128, 0,
                255, 0, 0, 192, 0, 255,
                192, 128, 64, 128, 0, 64,
            ])
            img.save(path)

            result = build_mask_relief_mesh(path, max_height_mm=10.0, pixel_size_mm=1.0, max_grid_size=0)

            self.assertEqual(is_closed_triangle_mesh(result.mesh.vertices, result.mesh.triangles), (True, 0, 0))

    def test_binary_diagonal_pixels_do_not_share_topology(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "diagonal_binary.png"
            img = Image.new("L", (2, 2))
            img.putdata([0, 255, 255, 0])
            img.save(path)

            result = build_mask_relief_mesh(path, max_height_mm=2.0, pixel_size_mm=1.0, binary=True, max_grid_size=0)

            self.assertEqual(is_closed_triangle_mesh(result.mesh.vertices, result.mesh.triangles), (True, 0, 0))


if __name__ == "__main__":
    unittest.main()
