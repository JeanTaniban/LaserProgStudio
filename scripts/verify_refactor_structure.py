# -*- coding: utf-8 -*-
"""Run the LaserProg Studio static architecture guard suite.

The implementation lives in ``scripts/refactor_checks`` so this launcher
stays readable while the individual checks remain importable by tests/CI.
"""

from __future__ import annotations

from refactor_checks.verifier import main


if __name__ == "__main__":
    raise SystemExit(main())
