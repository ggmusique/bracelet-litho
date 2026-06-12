from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

from etiquette import build_label_payload, mm_to_pt
import layout_profiles

try:
    import qrcode
except ImportError:
    qrcode = None


def coherent_purification(purifs: list) -> str:
    """Recommandation de purification coherente : si une pierre craint l'eau, fumigation seule."""
    default = "Eau (sauf pierres poreuses) ou fumigation (sauge, palo santo)"
    if not purifs:
        return default

    def _n(_x: Any) -> str:
        return str(_x).lower().replace(chr(0x2019), "'")

    if any(("pas d'eau" in _n(p)) or ("eau" not in _n(p)) for p in purifs):
        return "Fumigation uniquement (sauge ou palo santo) - eviter l'eau (pierres fragiles presentes)"
    return default


def coherent_rechargement(rechs: list) -> str:
    """Recommandation de rechargement coherente : methode universelle si divergences."""
    if not rechs:
        return "Lune (nuit de pleine lune) ou amas de quartz / geode 4h"
    uniq = {str(r).strip().lower() for r in rechs}
    if len(uniq) == 1:
        return rechs[0]
    return "Lune (pleine lune) ou amas de quartz / geode - convient a toutes les pierres"
