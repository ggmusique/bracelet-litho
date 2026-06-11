"""Services pour le module d'impression NIIMBOT (Phase 2B)."""
from __future__ import annotations
import io
import json
import csv
from typing import Any

import qrcode
from PIL import Image

# ── Helpers d'extraction ─────────────────────────────────────────

def get_pierres(bracelet: dict) -> list[str]:
    return [
        c.get("composant", "")
        for c in bracelet.get("composition", [])
        if c.get("categorie", "") == "Pierre"
    ]


def get_composition_lines(bracelet: dict) -> list[str]:
    return [
        f"{c.get('composant', '?')} x{c.get('quantite', 1)}"
        for c in bracelet.get("composition", [])
    ]


def get_chakras(bracelet: dict) -> list[str]:
    raw = bracelet.get("chakras", "")
    if isinstance(raw, str):
        return [s.strip() for s in raw.split(",") if s.strip()]
    if isinstance(raw, list):
        return raw
    return []


def get_vertus(bracelet: dict) -> str:
    raw = bracelet.get("vertus", "")
    if isinstance(raw, list):
        return ", ".join(raw)
    return str(raw)


def get_prix(bracelet: dict) -> str:
    pv = float(bracelet.get("prix_vente", 0) or 0)
    return f"{pv:.2f} €".replace(".", ",")


def get_prix_float(bracelet: dict) -> float:
    return float(bracelet.get("prix_vente", 0) or 0)


# ── Templates ────────────────────────────────────────────────────

DEFAULT_TEMPLATES: dict[str, dict] = {
    "Minimal": {
        "label": "Minimal",
        "format": "50x30",
        "fields": {"nom": True, "prix": True, "reference": False, "pierres": False, "chakras": False, "qr_code": False, "photo": False},
    },
    "Boutique": {
        "label": "Boutique",
        "format": "50x30",
        "fields": {"nom": True, "prix": True, "reference": True, "pierres": True, "chakras": False, "qr_code": False, "photo": False},
    },
    "Calibration 50x30": {
        "label": "Calibration 50x30",
        "format": "50x30",
        "fields": {"nom": True, "prix": True, "reference": True, "pierres": True, "chakras": True, "qr_code": False},
        "element_props": {
            "nom":       {"x": 0, "y": 0, "size": 12, "bold": True, "align": "left", "visible": True},
            "prix":      {"x": 45, "y": 0, "size": 8, "bold": False, "align": "right", "visible": True},
            "reference": {"x": 0, "y": 25, "size": 8, "bold": False, "align": "left", "visible": True},
            "pierres":   {"x": 45, "y": 25, "size": 7, "bold": False, "align": "right", "visible": True},
            "chakras":   {"x": 25, "y": 15, "size": 8, "bold": False, "align": "center", "visible": True},
        },
    },
    "Lithothérapie": {
        "label": "Lithothérapie",
        "format": "50x80",
        "fields": {"nom": True, "composition": False, "prix": False, "reference": False, "chakras": True, "vertus": True, "qr_code": False, "photo": False},
    },
    "Complet": {
        "label": "Complet",
        "format": "50x80",
        "fields": {"nom": True, "composition": True, "prix": True, "reference": True, "chakras": True, "vertus": False, "qr_code": True, "photo": True},
    },
    "Calibration 50x80": {
        "label": "Calibration 50x80",
        "format": "50x80",
        "fields": {"nom": True, "prix": True, "reference": True, "pierres": True, "chakras": True, "vertus": False, "qr_code": False},
        "element_props": {
            "nom":       {"x": 0, "y": 0, "size": 12, "bold": True, "align": "left", "visible": True},
            "prix":      {"x": 45, "y": 0, "size": 8, "bold": False, "align": "right", "visible": True},
            "reference": {"x": 0, "y": 75, "size": 8, "bold": False, "align": "left", "visible": True},
            "pierres":   {"x": 45, "y": 75, "size": 7, "bold": False, "align": "right", "visible": True},
            "chakras":   {"x": 25, "y": 40, "size": 8, "bold": False, "align": "center", "visible": True},
        },
    },
}

DEFAULT_50X30_FIELDS: dict[str, bool] = {
    "nom": True, "prix": True, "reference": True, "pierres": True, "chakras": False, "qr_code": False, "photo": False,
}

DEFAULT_50X80_FIELDS: dict[str, bool] = {
    "nom": True, "composition": True, "prix": True, "reference": True,
    "chakras": True, "vertus": False, "qr_code": False, "photo": False,
}

_FIELDS_50X30 = ["nom", "prix", "reference", "pierres", "chakras", "qr_code"]
_FIELDS_50X80 = ["nom", "composition", "prix", "reference", "chakras", "vertus", "qr_code", "photo"]


def get_fields_for_format(fmt: str) -> list[str]:
    return _FIELDS_50X30 if fmt == "50x30" else _FIELDS_50X80


def get_default_fields(fmt: str) -> dict[str, bool]:
    return dict(DEFAULT_50X30_FIELDS if fmt == "50x30" else DEFAULT_50X80_FIELDS)


def load_templates(db: Any) -> dict[str, dict]:
    saved = db.settings.get("niimbot_templates", {}) if db else {}
    merged = dict(DEFAULT_TEMPLATES)
    merged.update(saved)
    return merged


def save_template(db: Any, name: str, config: dict) -> None:
    templates = dict(db.settings.get("niimbot_templates", {}))
    templates[name] = config
    db.settings["niimbot_templates"] = templates
    db.save_settings()


def delete_template(db: Any, name: str) -> None:
    templates = dict(db.settings.get("niimbot_templates", {}))
    templates.pop(name, None)
    db.settings["niimbot_templates"] = templates
    db.save_settings()


# ── Rendu aperçu ─────────────────────────────────────────────────

def render_preview_lines(bracelet: dict, fields: dict[str, bool], fmt: str) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    if fields.get("nom", True):
        lines.append(("nom", bracelet.get("nom", "?").upper()))

    if fmt == "50x30":
        if fields.get("pierres"):
            pierres = get_pierres(bracelet)
            if pierres:
                lines.append(("pierres", " • ".join(pierres[:3])))
        if fields.get("chakras"):
            chakras = get_chakras(bracelet)
            if chakras:
                lines.append(("chakras", " / ".join(chakras[:2])))
        if fields.get("prix"):
            lines.append(("prix", get_prix(bracelet)))
        if fields.get("reference"):
            lines.append(("ref", bracelet.get("reference", "")))
    else:
        if fields.get("composition"):
            comp = get_composition_lines(bracelet)
            if comp:
                lines.append(("section", "Composition :"))
                for c in comp[:6]:
                    lines.append(("item", c))
        if fields.get("chakras"):
            chakras = get_chakras(bracelet)
            if chakras:
                lines.append(("section", "Chakras :"))
                for ch in chakras[:4]:
                    lines.append(("item", ch))
        if fields.get("vertus"):
            vertus = get_vertus(bracelet)
            if vertus:
                lines.append(("section", "Vertus :"))
                lines.append(("item", vertus[:120]))
        if fields.get("prix"):
            lines.append(("prix", get_prix(bracelet)))
        if fields.get("reference"):
            lines.append(("ref", bracelet.get("reference", "")))

    return lines


def generate_qr_image(bracelet: dict, size: int = 60) -> Image.Image | None:
    data = json.dumps({
        "nom": bracelet.get("nom", ""),
        "ref": bracelet.get("reference", ""),
        "prix": get_prix_float(bracelet),
        "pierres": get_pierres(bracelet),
        "vertus": get_vertus(bracelet),
        "chakras": get_chakras(bracelet),
    }, ensure_ascii=False)
    try:
        img = qrcode.make(data, box_size=3, border=1)
        return img.resize((size, size), Image.NEAREST)
    except Exception:
        return None


# ── CSV Export ────────────────────────────────────────────────────

def generate_csv(bracelets: list[dict], fields: dict[str, bool], fmt: str) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\n")

    headers: list[str] = ["reference", "nom"]
    if fmt == "50x30":
        if fields.get("pierres"):
            headers.append("pierres")
        if fields.get("prix"):
            headers.append("prix")
        if fields.get("chakras"):
            headers.append("chakras")
    else:
        if fields.get("composition"):
            headers.append("composition")
        if fields.get("prix"):
            headers.append("prix")
        if fields.get("chakras"):
            headers.append("chakras")
        if fields.get("vertus"):
            headers.append("vertus")
        if fields.get("reference"):
            headers.append("reference")
    writer.writerow(headers)

    for b in bracelets:
        row: list[str] = [str(b.get("reference", "")), str(b.get("nom", ""))]
        if fmt == "50x30":
            if "pierres" in headers:
                row.append("|".join(get_pierres(b)))
            if "prix" in headers:
                row.append(f"{get_prix_float(b):.2f}")
            if "chakras" in headers:
                row.append("|".join(get_chakras(b)))
        else:
            if "composition" in headers:
                row.append("|".join(c.get("composant", "") for c in b.get("composition", [])))
            if "prix" in headers:
                row.append(f"{get_prix_float(b):.2f}")
            if "chakras" in headers:
                row.append("|".join(get_chakras(b)))
            if "vertus" in headers:
                row.append(str(get_vertus(b)))
        writer.writerow(row)

    return output.getvalue()
