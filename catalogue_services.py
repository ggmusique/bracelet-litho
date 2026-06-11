"""Services pour le catalogue commercial & fiches produits (Phase 2C)."""
from __future__ import annotations
import textwrap
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from phase1c_services import resolve_media_path

# ── Bibliothèque des pierres (20 pierres majeures) ───────────────

PIERRE_INFO: dict[str, dict] = {
    "amethyste": {
        "vertus": ["Apaisement", "Spiritualité", "Intuition", "Protection", "Sérénité"],
        "chakras": ["Couronne (7e)", "3e Œil (6e)"],
        "signes": ["Poissons", "Verseau", "Sagittaire"],
        "purification": "Eau déminéralisée ou fumigation",
        "rechargement": "Lune ou amas cristallin 4h",
        "description": "Pierre d'apaisement et de spiritualité, l'Améthyste calme le mental et favorise la méditation.",
        "themes": ["apaisement", "spiritualité", "intuition"],
    },
    "quartz rose": {
        "vertus": ["Amour", "Tendresse", "Compassion", "Paix intérieure", "Réconfort"],
        "chakras": ["Cœur (4e)"],
        "signes": ["Balance", "Taureau", "Lion"],
        "purification": "Eau douce ou fumigation",
        "rechargement": "Lune ou soleil doux 2h",
        "description": "Pierre de l'amour inconditionnel, le Quartz Rose ouvre le cœur et invite à la douceur.",
        "themes": ["amour", "apaisement", "compassion"],
    },
    "labradorite": {
        "vertus": ["Protection", "Intuition", "Transformation", "Clairvoyance", "Magie"],
        "chakras": ["3e Œil (6e)", "Couronne (7e)"],
        "signes": ["Scorpion", "Sagittaire", "Lion"],
        "purification": "Fumigation ou géode",
        "rechargement": "Lune 6h",
        "description": "Pierre magique aux reflets irisés, la Labradorite protège l'aura et stimule l'intuition.",
        "themes": ["protection", "intuition", "transformation"],
    },
    "citrine": {
        "vertus": ["Prospérité", "Abondance", "Joie", "Confiance", "Énergie positive"],
        "chakras": ["Plexus solaire (3e)", "Sacré (2e)"],
        "signes": ["Gémeaux", "Balance", "Bélier"],
        "purification": "Eau ou fumigation",
        "rechargement": "Soleil 2h",
        "description": "Pierre de prospérité et d'abondance, la Citrine attire la joie et la réussite.",
        "themes": ["prospérité", "joie", "confiance"],
    },
    "aventurine verte": {
        "vertus": ["Chance", "Prospérité", "Guérison", "Optimisme", "Bien-être"],
        "chakras": ["Cœur (4e)", "Plexus solaire (3e)"],
        "signes": ["Taureau", "Balance", "Bélier"],
        "purification": "Eau ou fumigation",
        "rechargement": "Soleil ou lune 3h",
        "description": "Pierre de chance et de bien-être, l'Aventurine verte attire la prospérité et apaise le cœur.",
        "themes": ["prospérité", "guérison", "chance"],
    },
    "oeil de tigre": {
        "vertus": ["Protection", "Confiance", "Ancrage", "Force intérieure", "Détermination"],
        "chakras": ["Plexus solaire (3e)", "Sacré (2e)"],
        "signes": ["Gémeaux", "Lion", "Vierge"],
        "purification": "Fumigation ou géode",
        "rechargement": "Soleil 2h",
        "description": "Pierre de protection et de confiance, l'Œil de Tigre renforce la détermination et l'ancrage.",
        "themes": ["protection", "confiance", "ancrage"],
    },
    "lapis lazuli": {
        "vertus": ["Communication", "Intuition", "Sagesse", "Vérité", "Expression personnelle"],
        "chakras": ["Gorge (5e)", "3e Œil (6e)"],
        "signes": ["Sagittaire", "Verseau", "Balance"],
        "purification": "Eau déminéralisée ou fumigation",
        "rechargement": "Lune 4h",
        "description": "Pierre de sagesse et de vérité, le Lapis-Lazuli stimule l'intellect et favorise l'expression authentique.",
        "themes": ["communication", "intuition", "sagesse"],
    },
    "cornaline": {
        "vertus": ["Créativité", "Énergie", "Vitalité", "Confiance", "Motivation"],
        "chakras": ["Sacré (2e)", "Racine (1ère)"],
        "signes": ["Vierge", "Lion", "Bélier"],
        "purification": "Eau ou fumigation",
        "rechargement": "Soleil 3h",
        "description": "Pierre de vitalité et de créativité, la Cornaline dynamise et motive.",
        "themes": ["créativité", "énergie", "confiance"],
    },
    "onyx": {
        "vertus": ["Protection", "Ancrage", "Force", "Maîtrise de soi", "Stabilité"],
        "chakras": ["Racine (1ère)"],
        "signes": ["Capricorne", "Lion", "Scorpion"],
        "purification": "Fumigation ou géode",
        "rechargement": "Soleil 2h",
        "description": "Pierre de protection et d'ancrage, l'Onyx apporte force et stabilité.",
        "themes": ["protection", "ancrage", "force"],
    },
    "onyx noir": {
        "vertus": ["Protection", "Ancrage", "Force intérieure", "Confiance", "Stabilité"],
        "chakras": ["Racine (1ère)"],
        "signes": ["Capricorne", "Scorpion"],
        "purification": "Fumigation ou géode (éviter l'eau prolongée)",
        "rechargement": "Lune ou amas de quartz 4h",
        "description": "Pierre de protection et d'ancrage par excellence, l'Onyx noir absorbe les énergies négatives et renforce la confiance en soi.",
        "themes": ["protection", "ancrage", "force"],
    },
    "amazonite": {
        "vertus": ["Communication", "Vérité", "Harmonie", "Apaisement", "Sagesse"],
        "chakras": ["Gorge (5e)", "Cœur (4e)"],
        "signes": ["Vierge", "Balance", "Verseau"],
        "purification": "Eau ou fumigation",
        "rechargement": "Lune 3h",
        "description": "Pierre de communication et d'harmonie, l'Amazonite apaise les conflits et favorise la vérité.",
        "themes": ["communication", "harmonie", "apaisement"],
    },
    "turquoise": {
        "vertus": ["Protection", "Communication", "Sagesse", "Guérison", "Amitié"],
        "chakras": ["Gorge (5e)", "Cœur (4e)"],
        "signes": ["Sagittaire", "Poissons", "Verseau"],
        "purification": "Fumigation (pas d'eau)",
        "rechargement": "Lune 4h",
        "description": "Pierre protectrice et guérisseuse, la Turquoise favorise la communication et la sagesse.",
        "themes": ["protection", "communication", "guérison"],
    },
    "fluorite": {
        "vertus": ["Clarté mentale", "Concentration", "Organisation", "Protection", "Intuition"],
        "chakras": ["3e Œil (6e)", "Cœur (4e)"],
        "signes": ["Poissons", "Capricorne", "Balance"],
        "purification": "Eau ou fumigation",
        "rechargement": "Soleil doux 2h",
        "description": "Pierre de clarté mentale, la Fluorite structure la pensée et améliore la concentration.",
        "themes": ["clarté mentale", "intuition", "protection"],
    },
    "jaspe rouge": {
        "vertus": ["Ancrage", "Vitalité", "Protection", "Force physique", "Endurance"],
        "chakras": ["Racine (1ère)"],
        "signes": ["Scorpion", "Bélier", "Lion"],
        "purification": "Eau ou fumigation",
        "rechargement": "Soleil 3h",
        "description": "Pierre d'ancrage et de vitalité, le Jaspe rouge dynamise le corps et protège.",
        "themes": ["ancrage", "énergie", "protection"],
    },
    "howlite": {
        "vertus": ["Apaisement", "Patience", "Conscience", "Sommeil", "Détente"],
        "chakras": ["Couronne (7e)"],
        "signes": ["Gémeaux", "Vierge", "Poissons"],
        "purification": "Eau ou fumigation",
        "rechargement": "Lune 4h",
        "description": "Pierre d'apaisement et de patience, l'Howlite calme le mental et facilite le sommeil.",
        "themes": ["apaisement", "sommeil", "patience"],
    },
    "sodalite": {
        "vertus": ["Communication", "Vérité", "Intuition", "Logique", "Clarté"],
        "chakras": ["Gorge (5e)", "3e Œil (6e)"],
        "signes": ["Sagittaire", "Balance", "Poissons"],
        "purification": "Eau ou fumigation",
        "rechargement": "Lune 3h",
        "description": "Pierre de communication et de vérité, la Sodalite allie logique et intuition.",
        "themes": ["communication", "intuition", "vérité"],
    },
    "hématite": {
        "vertus": ["Ancrage", "Protection", "Concentration", "Mémoire", "Stabilité"],
        "chakras": ["Racine (1ère)"],
        "signes": ["Bélier", "Scorpion", "Capricorne"],
        "purification": "Fumigation (pas d'eau)",
        "rechargement": "Soleil 2h ou géode",
        "description": "Pierre d'ancrage et de protection, l'Hématite améliore la concentration et la mémoire.",
        "themes": ["ancrage", "protection", "concentration"],
    },
    "pyrite": {
        "vertus": ["Prospérité", "Confiance", "Protection", "Force", "Abondance"],
        "chakras": ["Plexus solaire (3e)"],
        "signes": ["Lion", "Bélier", "Sagittaire"],
        "purification": "Fumigation (pas d'eau)",
        "rechargement": "Soleil 2h",
        "description": "Pierre de prospérité et de confiance, la Pyrite attire l'abondance et protège.",
        "themes": ["prospérité", "confiance", "force"],
    },
    "obsidienne noire": {
        "vertus": ["Protection", "Purification", "Ancrage", "Nettoyage", "Vérité"],
        "chakras": ["Racine (1ère)"],
        "signes": ["Scorpion", "Capricorne", "Sagittaire"],
        "purification": "Fumigation ou géode (pas d'eau)",
        "rechargement": "Soleil ou lune 4h",
        "description": "Pierre de protection puissante, l'Obsidienne noire purifie et révèle la vérité.",
        "themes": ["protection", "purification", "ancrage"],
    },
    "pierre de lune": {
        "vertus": ["Intuition", "Féminin", "Émotions", "Créativité", "Sommeil"],
        "chakras": ["Sacré (2e)", "Couronne (7e)"],
        "signes": ["Cancer", "Poissons", "Balance"],
        "purification": "Eau ou fumigation",
        "rechargement": "Lune 6h",
        "description": "Pierre de l'intuition et du féminin, la Pierre de Lune équilibre les émotions et inspire la créativité.",
        "themes": ["intuition", "créativité", "apaisement"],
    },
    "tourmaline noire": {
        "vertus": ["Protection", "Purification", "Ancrage", "Nettoyage énergétique", "Sécurité"],
        "chakras": ["Racine (1ère)"],
        "signes": ["Capricorne", "Scorpion", "Balance"],
        "purification": "Fumigation ou géode",
        "rechargement": "Soleil 2h",
        "description": "Pierre de protection par excellence, la Tourmaline noire neutralise les énergies négatives.",
        "themes": ["protection", "purification", "ancrage"],
    },
    "malachite": {
        "vertus": ["Transformation", "Protection", "Guérison", "Confiance", "Changement"],
        "chakras": ["Cœur (4e)", "Plexus solaire (3e)"],
        "signes": ["Scorpion", "Capricorne", "Lion"],
        "purification": "Fumigation (pas d'eau)",
        "rechargement": "Lune 4h ou géode",
        "description": "Pierre de transformation, la Malachite accompagne les changements et protège le cœur.",
        "themes": ["transformation", "protection", "guérison"],
    },
}

# ── Mots-clés pour générateur de noms ────────────────────────────

_THEME_WORDS: dict[str, list[str]] = {
    "communication": ["Voix", "Parole", "Dialogue", "Expression", "Message", "Verbale"],
    "intuition": ["Intuition", "Pressentiment", "Clairvoyance", "Sixième Sens"],
    "sagesse": ["Sagesse", "Connaissance", "Savoir", "Philosophie", "Lumière"],
    "vérité": ["Vérité", "Authenticité", "Sincérité", "Transparence", "Réalité"],
    "transformation": ["Transformation", "Métamorphose", "Renaissance", "Changement", "Évolution"],
    "protection": ["Protection", "Bouclier", "Sécurité", "Gardien", "Sentinel"],
    "guérison": ["Guérison", "Réparation", "Bien-être", "Harmonie", "Soin"],
    "confiance": ["Confiance", "Assurance", "Estime", "Affirmation", "Foi"],
    "amour": ["Amour", "Tendresse", "Affection", "Compassion", "Cœur"],
    "prospérité": ["Prospérité", "Abondance", "Réussite", "Fortune", "Abondance"],
    "ancrage": ["Ancrage", "Enracinement", "Stabilité", "Fondation", "Solide"],
    "apaisement": ["Apaisement", "Sérénité", "Paix", "Calme", "Douceur", "Zen"],
    "spiritualité": ["Spirituel", "Éveil", "Divin", "Cosmique", "Sacré", "Âme"],
    "créativité": ["Créativité", "Inspiration", "Artiste", "Imagination", "Muse"],
    "énergie": ["Énergie", "Vitalité", "Dynamique", "Force", "Puissance"],
    "sommeil": ["Sommeil", "Rêve", "Nuit", "Repos", "Lunaire"],
    "foi": ["Foi", "Espoir", "Confiance", "Destin", "Providence"],
    "force": ["Force", "Pouvoir", "Volonté", "Détermination", " Courage"],
    "harmonie": ["Harmonie", "Équilibre", "Union", "Paix", "Concorde"],
    "clairvoyance": ["Clairvoyance", "Vision", "Prophétie", "Oracle", "Voyance"],
}

_ADJECTIVES = [
    "Sacré", "Authentique", "Libre", "Profond", "Éclatant", "Radieux",
    "Harmonieux", "Pur", "Essentiel", "Intemporel", "Lumineux", "Céleste",
    "Sauvage", "Douce", "Forte", "Magique", "Subtile", "Élevé",
]

_THEMES_DISPLAY: dict[str, str] = {
    "communication": "💬 Communication",
    "intuition": "🔮 Intuition",
    "sagesse": "📚 Sagesse",
    "vérité": "⭐ Vérité",
    "transformation": "🦋 Transformation",
    "protection": "🛡️ Protection",
    "guérison": "💚 Guérison",
    "confiance": "💪 Confiance",
    "amour": "❤️ Amour",
    "prospérité": "💰 Prospérité",
    "ancrage": "🌳 Ancrage",
    "apaisement": "😌 Apaisement",
    "énergie": "⚡ Énergie",
    "créativité": "🎨 Créativité",
    "sommeil": "🌙 Sommeil",
    "spiritualité": "🙏 Spiritualité",
    "force": "💪 Force",
    "harmonie": "☯️ Harmonie",
    "clairvoyance": "👁️ Clairvoyance",
    "purification": "🧹 Purification",
    "concentration": "🎯 Concentration",
    "chance": "🍀 Chance",
    "clarté mentale": "💡 Clarté mentale",
}

# ── Helpers ──────────────────────────────────────────────────────

def _normalize_name(name: str) -> str:
    return name.strip().lower().replace("-", " ").replace("é", "e").replace("è", "e")


def _find_stone_info(stone_name: str) -> dict | None:
    key = _normalize_name(stone_name)
    for info_key, info in PIERRE_INFO.items():
        if _normalize_name(info_key) == key:
            return dict(info)
    return None


def get_stone_info_from_db(db: Any, stone_name: str) -> dict:
    for s in db.stones:
        if s.get("nom", "").strip().lower() == stone_name.strip().lower():
            return s
    return {}


def aggregate_vertus(bracelet: dict, db: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for comp in bracelet.get("composition", []):
        if comp.get("categorie", "") == "Pierre":
            name = comp.get("composant", "")
            info = _find_stone_info(name)
            if info:
                for v in info["vertus"]:
                    if v not in seen:
                        seen.add(v)
                        result.append(v)
            else:
                stone = get_stone_info_from_db(db, name)
                raw = stone.get("vertus", "")
                if raw:
                    for v in str(raw).split(","):
                        v = v.strip()
                        if v and v not in seen:
                            seen.add(v)
                            result.append(v)
    return result


def aggregate_chakras(bracelet: dict, db: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for comp in bracelet.get("composition", []):
        if comp.get("categorie", "") == "Pierre":
            name = comp.get("composant", "")
            info = _find_stone_info(name)
            if info:
                for c in info["chakras"]:
                    if c not in seen:
                        seen.add(c)
                        result.append(c)
            else:
                stone = get_stone_info_from_db(db, name)
                raw = stone.get("chakra", stone.get("chakras", ""))
                if raw:
                    for c in str(raw).split(","):
                        c = c.strip()
                        if c and c not in seen:
                            seen.add(c)
                            result.append(c)
    return result


def generate_short_description(bracelet: dict, db: Any) -> str:
    vertus = aggregate_vertus(bracelet, db)
    if not vertus:
        return ""
    if len(vertus) == 1:
        return f"Bracelet favorisant la {vertus[0].lower()}."
    if len(vertus) == 2:
        return f"Bracelet favorisant la {vertus[0].lower()} et la {vertus[1].lower()}."
    return f"Bracelet favorisant la {vertus[0].lower()}, la {vertus[1].lower()} et la {vertus[2].lower()}."


def generate_long_description(bracelet: dict, db: Any) -> str:
    nom = bracelet.get("nom", "Ce bracelet")
    stones = [c.get("composant", "") for c in bracelet.get("composition", []) if c.get("categorie", "") == "Pierre"]
    vertus = aggregate_vertus(bracelet, db)

    intro = f"{nom} associe les propriétés du {stones[0]}" if len(stones) == 1 else \
            f"{nom} associe les propriétés {', '.join(['du ' + s if not s.endswith('e') else 'de la ' + s for s in stones[:-1]])} et du {stones[-1]}" if len(stones) > 1 else \
            f"{nom} est un bracelet aux propriétés uniques."

    usage = ""
    if vertus:
        top = vertus[:3]
        usage = f"Il est particulièrement apprécié pour accompagner le travail de {top[0].lower()}"
        if len(top) > 1:
            usage += f", de {top[1].lower()}"
        if len(top) > 2:
            usage += f" et de {top[2].lower()}"
        usage += "."

    return f"{intro}\n\n{usage}".strip()


# ── Générateur de noms ───────────────────────────────────────────

def suggest_names(bracelet: dict, db: Any) -> list[str]:
    themes: set[str] = set()
    for comp in bracelet.get("composition", []):
        if comp.get("categorie", "") == "Pierre":
            name = comp.get("composant", "")
            info = _find_stone_info(name)
            if info:
                themes.update(info.get("themes", []))
            else:
                stone = get_stone_info_from_db(db, name)
                for t in _detect_themes_from_vertus(stone.get("vertus", "")):
                    themes.add(t)

    if not themes:
        return []

    theme_list = list(themes)
    suggestions: list[str] = []
    seen_names: set[str] = set()

    for i in range(min(3, len(theme_list))):
        theme = theme_list[i]
        words = _THEME_WORDS.get(theme, [])
        for adj in _ADJECTIVES:
            for word in words[:2]:
                if word == adj:
                    continue
                candidate = f"{word} {adj}" if word != "Douce" else f"{adj} {word}"
                if candidate not in seen_names:
                    seen_names.add(candidate)
                    suggestions.append(candidate)
                    if len(suggestions) >= 5:
                        return suggestions

    return suggestions[:5]


def _detect_themes_from_vertus(vertus_raw: str) -> list[str]:
    vertus = [v.strip().lower() for v in vertus_raw.split(",")]
    theme_map: dict[str, list[str]] = {
        "apaisement": ["apaisement", "sérénité", "calme", "paix", "zen"],
        "protection": ["protection", "bouclier", "sécurité"],
        "confiance": ["confiance", "assurance", "foi"],
        "énergie": ["énergie", "vitalité", "dynamique", "force"],
        "ancrage": ["ancrage", "stabilité", "enracinement"],
        "intuition": ["intuition", "clairvoyance", "sixième sens"],
        "communication": ["communication", "expression", "vérité"],
        "créativité": ["créativité", "inspiration", "imagination"],
        "joie": ["joie", "bonheur", "gaîté"],
        "harmonie": ["harmonie", "équilibre", "union"],
    }
    result: list[str] = []
    for theme, keywords in theme_map.items():
        for v in vertus:
            for kw in keywords:
                if kw in v:
                    result.append(theme)
                    break
            if theme in result:
                break
    return result


def suggest_themes(bracelet: dict, db: Any) -> list[str]:
    themes: set[str] = set()
    for comp in bracelet.get("composition", []):
        if comp.get("categorie", "") == "Pierre":
            name = comp.get("composant", "")
            info = _find_stone_info(name)
            if info:
                themes.update(info.get("themes", []))
            else:
                stone = get_stone_info_from_db(db, name)
                detected = _detect_themes_from_vertus(stone.get("vertus", ""))
                themes.update(detected)
    return [t for t in themes if t in _THEMES_DISPLAY]


def format_theme(text: str) -> str:
    return _THEMES_DISPLAY.get(text, text)


# ── Export PDF ────────────────────────────────────────────────────

def export_fiche_pdf(bracelet: dict, db: Any, format_type: str, output_path: str) -> bool:
    try:
        c = canvas.Canvas(output_path, pagesize=A4)
        w, h = A4
        margin = 20 * mm
        y = h - margin
        c.setFont("Helvetica-Bold", 20)
        c.drawString(margin, y, bracelet.get("nom", "?").upper())
        y -= 10 * mm

        c.setFont("Helvetica", 10)
        c.drawString(margin, y, f"Réf : {bracelet.get('reference', '—')}")
        y -= 6 * mm
        y -= 4 * mm

        if format_type in ("boutique", "marche"):
            pv = float(bracelet.get("prix_vente", 0) or 0)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(margin, y, f"{pv:.2f} €")
            y -= 8 * mm

        if format_type == "boutique":
            c.setFont("Helvetica", 11)
            desc = bracelet.get("description_courte", "") or generate_short_description(bracelet, db)
            for line in textwrap.wrap(desc, width=70):
                c.drawString(margin, y, line)
                y -= 5 * mm
            y -= 4 * mm

        if format_type in ("client", "marche"):
            c.setFont("Helvetica-Bold", 12)
            if format_type == "client":
                c.drawString(margin, y, "Composition")
                y -= 5 * mm
                c.setFont("Helvetica", 10)
                for comp in bracelet.get("composition", []):
                    c.drawString(margin + 5 * mm, y, f"{comp.get('composant', '')} x{comp.get('quantite', 1)}")
                    y -= 5 * mm
                y -= 3 * mm

                vertus = aggregate_vertus(bracelet, db)
                if vertus:
                    c.setFont("Helvetica-Bold", 12)
                    c.drawString(margin, y, "Vertus")
                    y -= 5 * mm
                    c.setFont("Helvetica", 10)
                    for v in vertus[:5]:
                        c.drawString(margin + 5 * mm, y, f"• {v}")
                        y -= 5 * mm
                    y -= 3 * mm

                chakras = aggregate_chakras(bracelet, db)
                if chakras:
                    c.setFont("Helvetica-Bold", 12)
                    c.drawString(margin, y, "Chakras")
                    y -= 5 * mm
                    c.setFont("Helvetica", 10)
                    for ch in chakras:
                        c.drawString(margin + 5 * mm, y, f"• {ch}")
                        y -= 5 * mm

            if format_type == "marche":
                vertus = aggregate_vertus(bracelet, db)
                for v in vertus[:3]:
                    c.drawString(margin + 5 * mm, y, f"✨ {v}")
                    y -= 6 * mm

        if format_type == "client":
            y -= 5 * mm
            c.setFont("Helvetica-Bold", 12)
            c.drawString(margin, y, "Conseils d'utilisation")
            y -= 5 * mm
            c.setFont("Helvetica", 10)
            tips = [
                "Porter en contact direct avec la peau.",
                "Nettoyer régulièrement à l'eau claire.",
                "Recharger à la lumière lunaire ou solaire.",
                "Éviter le contact avec produits chimiques.",
            ]
            for tip in tips:
                c.drawString(margin + 5 * mm, y, f"• {tip}")
                y -= 5 * mm

        c.showPage()
        c.save()
        return True
    except Exception:
        return False


def export_catalogue_pdf(bracelets: list[dict], db: Any, output_path: str) -> bool:
    try:
        c = canvas.Canvas(output_path, pagesize=A4)
        w, h = A4
        margin = 20 * mm

        for bracelet in bracelets:
            y = h - margin

            c.setFont("Helvetica-Bold", 22)
            c.drawString(margin, y, bracelet.get("nom", "?").upper())
            y -= 10 * mm

            c.setFont("Helvetica", 11)
            ref = bracelet.get("reference", "—")
            pv = float(bracelet.get("prix_vente", 0) or 0)
            c.drawString(margin, y, f"Réf : {ref}    |    Prix : {pv:.2f} €")
            y -= 8 * mm

            c.setFont("Helvetica-Bold", 12)
            c.drawString(margin, y, "Composition")
            y -= 6 * mm
            c.setFont("Helvetica", 10)
            for comp in bracelet.get("composition", []):
                c.drawString(margin + 5 * mm, y, f"• {comp.get('composant', '')} x{comp.get('quantite', 1)}")
                y -= 5 * mm
            y -= 3 * mm

            vertus = aggregate_vertus(bracelet, db)
            if vertus:
                c.setFont("Helvetica-Bold", 12)
                c.drawString(margin, y, "Vertus")
                y -= 6 * mm
                c.setFont("Helvetica", 10)
                for v in vertus[:4]:
                    c.drawString(margin + 5 * mm, y, f"• {v}")
                    y -= 5 * mm
                y -= 3 * mm

            chakras = aggregate_chakras(bracelet, db)
            if chakras:
                c.setFont("Helvetica-Bold", 12)
                c.drawString(margin, y, "Chakras")
                y -= 6 * mm
                c.setFont("Helvetica", 10)
                for ch in chakras[:3]:
                    c.drawString(margin + 5 * mm, y, f"• {ch}")
                    y -= 5 * mm

            c.showPage()

        c.save()
        return True
    except Exception:
        return False


# ── Export PNG ────────────────────────────────────────────────────

def export_fiche_png(bracelet: dict, db: Any, output_path: str) -> bool:
    try:
        img = Image.new("RGB", (600, 900), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        nom = bracelet.get("nom", "?").upper()
        ref = bracelet.get("reference", "—")
        pv = float(bracelet.get("prix_vente", 0) or 0)

        try:
            font_big = ImageFont.truetype("arial.ttf", 36)
            font_mid = ImageFont.truetype("arial.ttf", 24)
            font_small = ImageFont.truetype("arial.ttf", 16)
        except Exception:
            font_big = ImageFont.load_default()
            font_mid = font_big
            font_small = font_big

        draw.text((30, 30), nom, fill=(30, 30, 30), font=font_big)
        draw.text((30, 80), f"{pv:.2f} €", fill=(0, 180, 180), font=font_mid)
        draw.text((30, 120), f"Réf : {ref}", fill=(100, 100, 100), font=font_small)

        photo_path = None
        for p in [bracelet.get("photo_thumb", ""), bracelet.get("photo", "")]:
            if p:
                rp = resolve_media_path(getattr(db, "base_dir", ""), p)
                if rp and rp.exists():
                    photo_path = str(rp)
                    break

        if photo_path:
            try:
                photo = Image.open(photo_path).convert("RGB").resize((200, 200))
                img.paste(photo, (370, 30))
            except Exception:
                pass

        vertus = aggregate_vertus(bracelet, db)
        y = 180
        draw.text((30, y), "✨ Vertus", fill=(50, 50, 50), font=font_mid)
        y += 35
        for v in vertus[:5]:
            draw.text((45, y), f"• {v}", fill=(80, 80, 80), font=font_small)
            y += 25

        img.save(output_path, "PNG")
        return True
    except Exception:
        return False
