from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

VISIBLE_UI_FILES = [
    ROOT / "src" / "laserprog_studio" / "ui" / "preferences_dialog.py",
    ROOT / "src" / "laserprog_studio" / "ui" / "toolbar_palette.py",
    ROOT / "src" / "laserprog_studio" / "controllers" / "selection_context_menu.py",
    ROOT / "src" / "laserprog_studio" / "tooling" / "plan_trace_2d" / "overlay.py",
    ROOT / "src" / "laserprog_studio" / "tooling" / "plan_trace_2d" / "panel.py",
    ROOT / "src" / "laserprog_studio" / "tooling" / "plan_trace_2d" / "motif_overlay.py",
    ROOT / "src" / "laserprog_studio" / "tooling" / "plan_trace_2d" / "patterns.py",
    ROOT / "src" / "laserprog_studio" / "tooling" / "plan_trace_2d" / "snap.py",
    ROOT / "src" / "laserprog_studio" / "tooling" / "plan_trace_2d_tool.py",
]

FRENCH_VISIBLE_TOKENS = re.compile(
    r"\b("
    r"Ajouter|Soustraire|Annuler|Éditer|Valider|Appliquer|Aperçu|Graine|État|"
    r"Projet|Gravure|Modélisation|Planche|préférences|préférence|"
    r"épaisseur|dessin|outil|outils|sélection|sélectionne|modèle|modèles|"
    r"creusé|échec|scène|marge|paroi|Matière|Décalage|ancien|brouillon|"
    r"Nouveau dessin|Face cible|Fermer"
    r")\b",
    re.IGNORECASE,
)
ACCENTED = re.compile(r"[éèêëàâäîïôöùûüçÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]")


def _literal_strings(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            if value.startswith("plan_trace_2d.") or value.startswith("toolctx."):
                continue
            out.append(value)
    return out


def test_high_visibility_ui_strings_are_english_only() -> None:
    offenders: list[str] = []
    for path in VISIBLE_UI_FILES:
        for literal in _literal_strings(path):
            if ACCENTED.search(literal) or FRENCH_VISIBLE_TOKENS.search(literal):
                offenders.append(f"{path.relative_to(ROOT)}: {literal!r}")
    assert offenders == []
