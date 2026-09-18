# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _path_setup  # noqa: F401
from laserprog_studio.domain.work_model import ModelStore, WorkMesh


class ModelStoreSmokeTest(unittest.TestCase):
    def test_preview_commit_undo_redo(self) -> None:
        a = WorkMesh("a", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])
        b = WorkMesh("b", [(0, 0, 1), (1, 0, 1), (0, 1, 1)], [(0, 1, 2)])
        store = ModelStore()
        store.set_meshes([a])
        store.set_preview_meshes([a, b])
        self.assertTrue(store.has_preview)
        self.assertEqual(len(store.meshes), 2)
        self.assertTrue(store.commit_preview())
        self.assertFalse(store.has_preview)
        self.assertEqual(len(store.meshes), 2)
        self.assertTrue(store.undo())
        self.assertEqual([m.name for m in store.meshes], ["a"])
        self.assertTrue(store.redo())
        self.assertEqual([m.name for m in store.meshes], ["a", "b"])

    def test_3mf_roundtrip_on_simple_mesh(self) -> None:
        store = ModelStore()
        mesh = WorkMesh("triangle", [(0, 0, 0), (10, 0, 0), (0, 10, 0)], [(0, 1, 2)], "#00C853")
        store.set_meshes([mesh])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "triangle.3mf"
            store.export_3mf(path)
            self.assertTrue(path.exists())
            loaded = ModelStore()
            loaded.load_3mf(path)
            self.assertEqual(len(loaded.meshes), 1)
            self.assertIn("triangle", loaded.meshes[0].name)
            self.assertEqual(len(loaded.meshes[0].vertices), 3)
            self.assertEqual(len(loaded.meshes[0].triangles), 1)


if __name__ == "__main__":
    unittest.main()
