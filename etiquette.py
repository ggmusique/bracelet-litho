from __future__ import annotations

from typing import Any

MM_TO_PT = 2.8346456693


def mm_to_pt(mm: float) -> float:
    return mm * MM_TO_PT


def safe_join(items: list[str], sep: str = ", ") -> str:
    cleaned = [item.strip() for item in items if item and item.strip()]
    return sep.join(cleaned)


def build_label_payload(bracelet: dict[str, Any], metrics: dict[str, Any]) -> dict[str, str]:
    return {
        "nom": bracelet.get("nom", ""),
        "reference": bracelet.get("reference", ""),
        "composition": safe_join(metrics.get("composition", [])),
        "vertus": safe_join(metrics.get("vertus", [])),
        "chakras": safe_join(metrics.get("chakras", [])),
        "prix": f"{float(bracelet.get('prix_vente', 0.0) or 0.0):.2f} EUR",
    }


def split_text_for_preview(text: str, max_chars: int) -> list[str]:
    if not text:
        return [""]

    words = text.split()
    lines: list[str] = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines or [""]
