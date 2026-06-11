"""layout_profiles.py
Gestion des profils de mise en page pour les étiquettes Action 70×37mm.

Chaque profil décrit, en millimètres depuis le coin supérieur gauche du label,
la position (x, y) de chaque élément et sa taille de police (en points PDF).
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

# ── Dimensions de la feuille Action ──────────────────────────────────
SHEET_MARGIN_MM: float = 2.0        # marge de contour (référence, conservée pour compatibilité)
SHEET_MARGIN_X_MM: float = 0.0     # décalage horizontal origine grille (0 = bord gauche feuille)
SHEET_MARGIN_Y_MM: float = 2.0     # décalage vertical origine grille (2 mm depuis le haut)
ACTION_COLS: int = 3
ACTION_ROWS: int = 8
A4_W_MM: float = 210.0
A4_H_MM: float = 297.0
# Dimensions réelles des étiquettes physiques (70×37 mm, sans espace entre elles)
# La marge de 2 mm décale uniquement l'origine de la grille (X=2 mm, Y=2 mm)
CELL_W_MM: float = 70.0
CELL_H_MM: float = 37.0

# ── Profil par défaut — Modèle Bracelet ──────────────────────────────
DEFAULT_BRACELET: dict[str, Any] = {
    "model": "bracelet",
    # Positions en mm depuis le coin supérieur gauche de l'étiquette.
    # y = distance depuis le bord supérieur (augmente vers le bas).
    "nom":         {"x": 4.0,  "y": 4.0,  "size": 11, "bold": True},
    "sep_y":       7.5,                                               # ligne de séparation
    "comp_label":  {"x": 4.0,  "y": 9.5,  "size": 8,  "bold": True},
    "comp_items":  {"x": 5.5,  "y": 13.0, "size": 8,  "bold": False, "leading": 4.8},
    # ─ Prix configurables (3 éléments indépendants, déplaçables dans le Zoom) ─
    "prix":         {"x": 4.0,  "y": 34.5, "size": 12, "bold": True,  "visible": True},
    "prix_revient": {"x": 4.0,  "y": 30.0, "size": 10, "bold": False, "visible": False},
    "marge":        {"x": 38.0, "y": 34.5, "size": 10, "bold": False, "visible": False},
}

# ── Profil par défaut — Modèle Vertus / Chakras ───────────────────────
DEFAULT_VERTUS: dict[str, Any] = {
    "model": "vertus",
    "nom":           {"x": 4.0, "y": 4.0,  "size": 10, "bold": True},
    "sep_y":         7.5,
    "vertus_label":  {"x": 4.0, "y": 9.5,  "size": 7,  "bold": True},
    "vertus_items":  {"x": 5.0, "y": 12.5, "size": 7,  "bold": False, "leading": 4.2},
    "chakras_label": {"x": 4.0, "y": 22.5, "size": 7,  "bold": True},
    "chakras_items": {"x": 5.0, "y": 26.0, "size": 7,  "bold": False, "leading": 4.2},    # ─ Prix configurables (mêmes éléments que le modèle Bracelet) ─
    "prix":         {"x": 4.0,  "y": 34.5, "size": 12, "bold": True,  "visible": True},
    "prix_revient": {"x": 4.0,  "y": 30.0, "size": 10, "bold": False, "visible": False},
    "marge":        {"x": 38.0, "y": 34.5, "size": 10, "bold": False, "visible": False},}

_FILENAMES: dict[str, str] = {
    "bracelet": "Action70x37_Bracelet.json",
    "vertus":   "Action70x37_Vertus.json",
}

_DEFAULTS: dict[str, dict[str, Any]] = {
    "bracelet": DEFAULT_BRACELET,
    "vertus":   DEFAULT_VERTUS,
}


# ── API publique ──────────────────────────────────────────────────────

def load_layout(model: str, base_dir: str | Path) -> dict[str, Any]:
    """Charge le profil JSON ou retourne le profil par défaut si absent/invalide."""
    path = Path(base_dir) / _FILENAMES.get(model, f"{model}.json")
    base = copy.deepcopy(_DEFAULTS.get(model, {}))
    if not path.exists():
        return base
    try:
        with path.open("r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        _deep_merge(base, loaded)
        return base
    except (json.JSONDecodeError, OSError):
        return base


def save_layout(model: str, layout: dict[str, Any], base_dir: str | Path) -> None:
    """Sauvegarde le profil dans le fichier JSON correspondant (écriture atomique)."""
    filename = _FILENAMES.get(model, f"{model}.json")
    path = Path(base_dir) / filename
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(layout, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def default_for(model: str) -> dict[str, Any]:
    """Retourne une copie profonde du profil par défaut."""
    return copy.deepcopy(_DEFAULTS.get(model, {}))


def filename_for(model: str) -> str:
    """Retourne le nom du fichier JSON pour un modèle."""
    return _FILENAMES.get(model, f"{model}.json")


# ── Interne ───────────────────────────────────────────────────────────

def _deep_merge(base: dict, override: dict) -> None:
    """Fusionne override dans base en profondeur (dicts imbriqués)."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
