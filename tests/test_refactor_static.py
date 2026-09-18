# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


class RefactorStaticVerificationTest(unittest.TestCase):
    def test_verify_refactor_structure_script(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(root / "scripts" / "verify_refactor_structure.py")],
            cwd=str(root),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("Refactor structure OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
