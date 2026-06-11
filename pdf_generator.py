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


class PDFGenerator:
    def __init__(self, db_manager) -> None:
        self.db = db_manager
        self.base_font = "Helvetica"

    def invalidate_layout_cache(self) -> None:
        """Invalide le cache des profils de mise en page (appeler après sauvegarde JSON)."""
        for model in ("bracelet", "vertus"):
            attr = f"_layout_cache_{model}"
            if hasattr(self, attr):
                delattr(self, attr)

    def _get_action_layout(self, model: str) -> dict:
        """Retourne le profil de mise en page en cache (chargé depuis JSON si nécessaire)."""
        attr = f"_layout_cache_{model}"
        if not hasattr(self, attr):
            setattr(self, attr, layout_profiles.load_layout(model, self.db.base_dir))
        return getattr(self, attr)

    def refresh_style_from_settings(self) -> None:
        self.base_font = self.db.settings.get("label_font", "Helvetica") or "Helvetica"

    @staticmethod
    def _safe_font(requested: str, bold: bool = False) -> str:
        family = (requested or "Helvetica").strip().lower()
        if family.startswith("times"):
            return "Times-Bold" if bold else "Times-Roman"
        if family.startswith("courier"):
            return "Courier-Bold" if bold else "Courier"
        return "Helvetica-Bold" if bold else "Helvetica"

    @staticmethod
    def _draw_field(c: canvas.Canvas, label: str, value: str, x: float, y: float, width: float, font_size: int = 8) -> float:
        c.setFont("Helvetica-Bold", font_size)
        c.drawString(x, y, f"{label}:")
        y -= font_size + 1

        c.setFont("Helvetica", font_size)
        for line in simpleSplit(value or "-", "Helvetica", font_size, width):
            c.drawString(x, y, line)
            y -= font_size + 1
        return y - 1

    def _make_qr_image(self, bracelet: dict[str, Any]) -> ImageReader | None:
        if not qrcode:
            return None

        payload = f"{bracelet.get('nom', '')}|{bracelet.get('reference', '')}|{bracelet.get('prix_vente', 0)}"
        image = qrcode.make(payload)
        stream = BytesIO()
        image.save(stream, format="PNG")
        stream.seek(0)
        return ImageReader(stream)

    def draw_single_label(self, c: canvas.Canvas, bracelet: dict[str, Any], x: float, y: float, w: float, h: float) -> None:
        self.refresh_style_from_settings()
        metrics = self.db.calculate_bracelet_metrics(bracelet)
        payload = build_label_payload(bracelet, metrics)

        margin = 8
        cursor_x = x + margin
        cursor_y = y + h - margin - 2
        usable_w = w - (margin * 2)

        c.setLineWidth(1)
        c.rect(x, y, w, h)

        logo_path = self.db.settings.get("logo_path", "")
        if logo_path and Path(logo_path).exists():
            try:
                c.drawImage(
                    logo_path,
                    x + w - 55,
                    y + h - 28,
                    45,
                    18,
                    preserveAspectRatio=True,
                    mask="auto",
                )
            except Exception:
                pass

        c.setFont(self._safe_font(self.base_font, bold=True), 11)
        c.drawString(cursor_x, cursor_y, payload["nom"] or "Bracelet")
        cursor_y -= 14

        c.setFont(self._safe_font(self.base_font), 8)
        c.drawString(cursor_x, cursor_y, f"Réf: {payload['reference'] or '-'}")
        cursor_y -= 11

        qr_enabled = bool(bracelet.get("qr_enabled"))
        qr_box_size = 44 if qr_enabled else 0
        text_w = usable_w - (qr_box_size + 6 if qr_enabled else 0)

        text_y = cursor_y
        c.setFont(self._safe_font(self.base_font, bold=True), 8)
        c.drawString(cursor_x, text_y, "Composition:")
        text_y -= 9
        c.setFont(self._safe_font(self.base_font), 8)
        for line in simpleSplit(payload["composition"] or "-", self._safe_font(self.base_font), 8, text_w):
            c.drawString(cursor_x, text_y, line)
            text_y -= 9
        text_y -= 1

        c.setFont(self._safe_font(self.base_font, bold=True), 8)
        c.drawString(cursor_x, text_y, "Vertus:")
        text_y -= 9
        c.setFont(self._safe_font(self.base_font), 8)
        for line in simpleSplit(payload["vertus"] or "-", self._safe_font(self.base_font), 8, text_w):
            c.drawString(cursor_x, text_y, line)
            text_y -= 9
        text_y -= 1

        c.setFont(self._safe_font(self.base_font, bold=True), 8)
        c.drawString(cursor_x, text_y, "Chakras:")
        text_y -= 9
        c.setFont(self._safe_font(self.base_font), 8)
        for line in simpleSplit(payload["chakras"] or "-", self._safe_font(self.base_font), 8, text_w):
            c.drawString(cursor_x, text_y, line)
            text_y -= 9

        c.setFont(self._safe_font(self.base_font, bold=True), 10)
        c.drawString(cursor_x, y + margin + 2, f"Prix: {payload['prix']}")

        if qr_enabled:
            qr_img = self._make_qr_image(bracelet)
            if qr_img:
                c.drawImage(
                    qr_img,
                    x + w - margin - qr_box_size,
                    y + margin,
                    qr_box_size,
                    qr_box_size,
                    preserveAspectRatio=True,
                    mask="auto",
                )

    def export_action_a4_sheet_pdf(
        self,
        positions: list[dict],
        output_path: str,
    ) -> None:
        """Génère un PDF A4 complet avec toutes les positions utilisées de la feuille.

        `positions` est la liste de 24 dicts renvoyée par db.get_feuille_positions().
        Chaque dict utilisé doit contenir 'bracelet_id' et 'model'.
        Le bracelet est chargé dynamiquement via self.db.get_bracelet_by_id().
        """
        page_w, page_h = A4
        margin_x_pt = mm_to_pt(layout_profiles.SHEET_MARGIN_X_MM)
        margin_y_pt = mm_to_pt(layout_profiles.SHEET_MARGIN_Y_MM)
        cell_w = mm_to_pt(layout_profiles.CELL_W_MM)
        cell_h = mm_to_pt(layout_profiles.CELL_H_MM)

        pdf = canvas.Canvas(output_path, pagesize=A4)

        has_content = False
        for i, pos_data in enumerate(positions):
            if not pos_data.get("used"):
                continue
            bracelet_id = pos_data.get("bracelet_id", "")
            bracelet = self.db.get_bracelet_by_id(bracelet_id) if bracelet_id else None
            if not bracelet:
                continue
            model = pos_data.get("model", "bracelet")
            col = i % 3
            row = i // 3
            x = margin_x_pt + col * cell_w
            y = page_h - margin_y_pt - (row + 1) * cell_h
            lyt = self._get_action_layout(model)
            self._draw_action_label(pdf, bracelet, x, y, cell_w, cell_h, model, lyt)
            has_content = True

        if not has_content:
            # Page vide avec message si aucune position n'est remplie
            pdf.setFont("Helvetica", 12)
            pdf.drawCentredString(page_w / 2, page_h / 2, "Aucune position remplie.")

        pdf.showPage()
        pdf.save()

    def export_action_a4_selection_pdf(
        self,
        items: list[dict[str, Any]],
        output_path: str,
    ) -> None:
        """Génère un PDF A4 avec les positions de la sélection multiple.

        `items` : liste de dicts {"pos": int (1-24), "bracelet": dict, "model": str}
        produite par _validate_multi_selection().  Les positions absentes de la
        liste restent vides sur la feuille.
        """
        page_w, page_h = A4
        margin_x_pt = mm_to_pt(layout_profiles.SHEET_MARGIN_X_MM)
        margin_y_pt = mm_to_pt(layout_profiles.SHEET_MARGIN_Y_MM)
        cell_w = mm_to_pt(layout_profiles.CELL_W_MM)
        cell_h = mm_to_pt(layout_profiles.CELL_H_MM)

        pdf = canvas.Canvas(output_path, pagesize=A4)

        for item in items:
            pos = item["pos"]          # 1-based
            bracelet = item["bracelet"]
            model = item["model"]
            col = (pos - 1) % 3
            row = (pos - 1) // 3
            x = margin_x_pt + col * cell_w
            y = page_h - margin_y_pt - (row + 1) * cell_h
            lyt = self._get_action_layout(model)
            self._draw_action_label(pdf, bracelet, x, y, cell_w, cell_h, model, lyt)

        if not items:
            pdf.setFont("Helvetica", 12)
            pdf.drawCentredString(page_w / 2, page_h / 2, "Aucun contenu a imprimer.")

        pdf.showPage()
        pdf.save()

    def export_action_a4_position_pdf(
        self,
        bracelet: dict[str, Any],
        output_path: str,
        position: int,
        model: str = "bracelet",
    ) -> None:
        """Génère un PDF A4 avec l'étiquette uniquement à la position donnée (1–24).

        Marge contour 2 mm, zéro écart entre étiquettes.
        Cellule : 70 mm × 37 mm.
        """
        page_w, page_h = A4
        margin_x_pt = mm_to_pt(layout_profiles.SHEET_MARGIN_X_MM)
        margin_y_pt = mm_to_pt(layout_profiles.SHEET_MARGIN_Y_MM)
        cell_w = mm_to_pt(layout_profiles.CELL_W_MM)
        cell_h = mm_to_pt(layout_profiles.CELL_H_MM)

        col = (position - 1) % 3
        row = (position - 1) // 3

        x = margin_x_pt + col * cell_w
        y = page_h - margin_y_pt - (row + 1) * cell_h  # ReportLab : y = 0 en bas

        lyt = self._get_action_layout(model)
        pdf = canvas.Canvas(output_path, pagesize=A4)
        self._draw_action_label(pdf, bracelet, x, y, cell_w, cell_h, model, lyt)
        pdf.showPage()
        pdf.save()

    def export_single_label_pdf(self, bracelet: dict[str, Any], output_path: str, label_mm: tuple[float, float] = (80, 50), format_type: str = "Complet 80x50 mm") -> None:
        if "Action" in format_type:
            cell_w = mm_to_pt(layout_profiles.CELL_W_MM)
            cell_h = mm_to_pt(layout_profiles.CELL_H_MM)
            pdf = canvas.Canvas(output_path, pagesize=(cell_w, cell_h))
            self._draw_action_label(pdf, bracelet, 0, 0, cell_w, cell_h, "bracelet", self._get_action_layout("bracelet"))
        elif "Vertus" in format_type or "Chakra" in format_type:
            cell_w = mm_to_pt(layout_profiles.CELL_W_MM)
            cell_h = mm_to_pt(layout_profiles.CELL_H_MM)
            pdf = canvas.Canvas(output_path, pagesize=(cell_w, cell_h))
            self._draw_action_label(pdf, bracelet, 0, 0, cell_w, cell_h, "vertus", self._get_action_layout("vertus"))
        else:
            w, h = mm_to_pt(label_mm[0]), mm_to_pt(label_mm[1])
            pdf = canvas.Canvas(output_path, pagesize=(w, h))
            self.draw_single_label(pdf, bracelet, 0, 0, w, h)
        pdf.showPage()
        pdf.save()

    def draw_label_action_70x37(self, c: canvas.Canvas, bracelet: dict[str, Any], x: float, y: float, w: float, h: float) -> None:
        """Format Action — Nom + Composition + Prix, positions depuis le profil JSON."""
        self._draw_action_label(c, bracelet, x, y, w, h, "bracelet", self._get_action_layout("bracelet"))

    def draw_label_vertus_chakras(self, c: canvas.Canvas, bracelet: dict[str, Any], x: float, y: float, w: float, h: float) -> None:
        """Format Action — Nom + Vertus + Chakras, positions depuis le profil JSON."""
        self._draw_action_label(c, bracelet, x, y, w, h, "vertus", self._get_action_layout("vertus"))

    def _draw_action_label(
        self,
        c: canvas.Canvas,
        bracelet: dict[str, Any],
        x: float, y: float, w: float, h: float,
        model: str,
        layout: dict[str, Any],
    ) -> None:
        """Noyau commun : dessine une étiquette Action avec les positions du profil.

        Les coordonnées JSON (x, y) représentent le COIN SUPÉRIEUR GAUCHE du texte,
        identique à l'anchor='nw' du Zoom. La conversion baseline ReportLab est
        effectuée ici via le ratio d'ascent Helvetica (0.72 × taille).
        """
        self.refresh_style_from_settings()
        fnt = self._safe_font

        def pt(mm: float) -> float:
            return mm_to_pt(mm)

        def at(ex_mm: float, ey_mm: float, size_pt: float = 0.0) -> tuple[float, float]:
            """Convertit (x_mm, y_mm) depuis le coin sup-gauche du label en coords ReportLab.

            size_pt : taille de police en points. Si > 0, ajuste la baseline pour que
                      le HAUT du glyphe soit à ey_mm (comme anchor='nw' dans le Zoom).
                      Laisser à 0 pour les éléments géométriques (lignes, contours).
            """
            # Ascent Helvetica ≈ 0.72 × taille ; déplace la baseline vers le bas
            # pour que le sommet visible du texte coïncide avec ey_mm depuis le haut.
            return x + pt(ex_mm), y + h - pt(ey_mm) - size_pt * 0.72

        # Contour du label
        c.setLineWidth(0.5)
        c.rect(x, y, w, h)

        # ── Nom ──────────────────────────────────────────────────────
        nom_cfg = layout.get("nom", {})
        if isinstance(nom_cfg, dict):
            nom_size = int(nom_cfg.get("size", 11))
            c.setFont(fnt(self.base_font, bold=bool(nom_cfg.get("bold", True))), nom_size)
            cx, cy = at(nom_cfg.get("x", 4), nom_cfg.get("y", 4), nom_size)
            c.drawString(cx, cy, bracelet.get("nom", "") or "Bracelet")

        # ── Ligne de séparation (géométrique, pas d'ajustement ascent) ───
        sep_y_mm = float(layout.get("sep_y", 7.5))
        _, sep_cy = at(4, sep_y_mm)          # size_pt=0 → y est la position exacte
        c.setLineWidth(0.3)
        c.line(x + pt(4), sep_cy, x + w - pt(4), sep_cy)

        # ── Métriques communes aux deux modèles ────────────────────────
        metrics      = self.db.calculate_bracelet_metrics(bracelet)
        prix_vente   = float(bracelet.get("prix_vente", 0.0) or 0.0)
        cout_revient = float(metrics.get("cout_revient", 0.0))

        if model == "bracelet":
            # ── Titre "Composition :" ─────────────────────────────────
            cl_cfg = layout.get("comp_label", {})
            if isinstance(cl_cfg, dict):
                cl_size = int(cl_cfg.get("size", 8))
                c.setFont(fnt(self.base_font, bold=True), cl_size)
                cx, cy = at(cl_cfg.get("x", 4), cl_cfg.get("y", 9.5), cl_size)
                c.drawString(cx, cy, "Composition :")

            # ── Items composition ─────────────────────────────────────
            ci_cfg = layout.get("comp_items", {})
            if isinstance(ci_cfg, dict):
                ix_mm      = float(ci_cfg.get("x", 5.5))
                iy_mm      = float(ci_cfg.get("y", 13.0))
                leading_mm = float(ci_cfg.get("leading", 4.8))
                item_size  = int(ci_cfg.get("size", 8))
                c.setFont(fnt(self.base_font, bold=False), item_size)
                for i, row in enumerate(bracelet.get("composition", [])):
                    qty   = int(row.get("quantite", 1) or 1)
                    nom_c = str(row.get("composant", "")).strip()
                    if not nom_c:
                        continue
                    cur_y_mm = iy_mm + i * leading_mm
                    if cur_y_mm > layout_profiles.CELL_H_MM - 1:
                        break
                    cx, cy = at(ix_mm, cur_y_mm, item_size)
                    if cy < y + pt(1.0):
                        break
                    c.drawString(cx, cy, f"{qty}\u00d7 {nom_c}" if qty > 1 else nom_c)

        elif model == "vertus":
            # ── Titre "Vertus :" ──────────────────────────────────────
            vl_cfg = layout.get("vertus_label", {})
            if isinstance(vl_cfg, dict):
                vl_size = int(vl_cfg.get("size", 7))
                c.setFont(fnt(self.base_font, bold=True), vl_size)
                cx, cy = at(vl_cfg.get("x", 4), vl_cfg.get("y", 9.5), vl_size)
                c.drawString(cx, cy, "Vertus :")

            # ── Items vertus ──────────────────────────────────────────
            vi_cfg = layout.get("vertus_items", {})
            if isinstance(vi_cfg, dict):
                ix_mm      = float(vi_cfg.get("x", 5))
                iy_mm      = float(vi_cfg.get("y", 12.5))
                leading_mm = float(vi_cfg.get("leading", 4.2))
                vi_size    = int(vi_cfg.get("size", 7))
                c.setFont(fnt(self.base_font, bold=False), vi_size)
                for i, v in enumerate(metrics.get("vertus", [])):
                    cur_y_mm = iy_mm + i * leading_mm
                    if cur_y_mm > layout_profiles.CELL_H_MM - 1:
                        break
                    cx, cy = at(ix_mm, cur_y_mm, vi_size)
                    if cy < y + pt(1.0):
                        break
                    c.drawString(cx, cy, str(v))

            # ── Titre "Chakras :" ─────────────────────────────────────
            chl_cfg = layout.get("chakras_label", {})
            if isinstance(chl_cfg, dict):
                chl_size = int(chl_cfg.get("size", 7))
                c.setFont(fnt(self.base_font, bold=True), chl_size)
                cx, cy = at(chl_cfg.get("x", 4), chl_cfg.get("y", 22.5), chl_size)
                c.drawString(cx, cy, "Chakras :")

            # ── Items chakras ─────────────────────────────────────────
            ci_cfg = layout.get("chakras_items", {})
            if isinstance(ci_cfg, dict):
                ix_mm      = float(ci_cfg.get("x", 5))
                iy_mm      = float(ci_cfg.get("y", 26.0))
                leading_mm = float(ci_cfg.get("leading", 4.2))
                ci_size    = int(ci_cfg.get("size", 7))
                c.setFont(fnt(self.base_font, bold=False), ci_size)
                for i, ch_val in enumerate(metrics.get("chakras", [])):
                    cur_y_mm = iy_mm + i * leading_mm
                    if cur_y_mm > layout_profiles.CELL_H_MM - 1:
                        break
                    cx, cy = at(ix_mm, cur_y_mm, ci_size)
                    if cy < y + pt(1.0):
                        break
                    c.drawString(cx, cy, str(ch_val))

        # ── Prix — communs aux deux modèles ────────────────────────────
        prix_cfg = layout.get("prix", {})
        if isinstance(prix_cfg, dict) and prix_cfg.get("visible", True):
            pv_size = int(prix_cfg.get("size", 12))
            c.setFont(fnt(self.base_font, bold=bool(prix_cfg.get("bold", True))), pv_size)
            cx, cy = at(float(prix_cfg.get("x", 4.0)), float(prix_cfg.get("y", 34.5)), pv_size)
            c.drawString(cx, cy, f"PV : {prix_vente:.2f} \u20ac")

        pr_cfg = layout.get("prix_revient", {})
        if isinstance(pr_cfg, dict) and pr_cfg.get("visible", False):
            pr_size = int(pr_cfg.get("size", 10))
            c.setFont(fnt(self.base_font, bold=False), pr_size)
            cx, cy = at(float(pr_cfg.get("x", 4.0)), float(pr_cfg.get("y", 30.0)), pr_size)
            c.drawString(cx, cy, f"PR : {cout_revient:.2f} \u20ac")

        mg_cfg = layout.get("marge", {})
        if isinstance(mg_cfg, dict) and mg_cfg.get("visible", False):
            mg_size = int(mg_cfg.get("size", 10))
            c.setFont(fnt(self.base_font, bold=False), mg_size)
            cx, cy = at(float(mg_cfg.get("x", 38.0)), float(mg_cfg.get("y", 34.5)), mg_size)
            c.drawString(cx, cy, f"M  : {prix_vente - cout_revient:.2f} \u20ac")

    def export_multiple_labels_pdf(
        self,
        bracelets: list[dict[str, Any]],
        output_path: str,
        layout: str = "12",
        label_mm: tuple[float, float] = (80, 50),
        orientation: str = "portrait",
        format_type: str = "Complet 80x50 mm",
    ) -> None:
        # Sélection de la méthode de dessin selon le type d'étiquette
        if "Action" in format_type:
            draw_fn = self.draw_label_action_70x37
            single_mm = (70, 37)
        elif "Vertus" in format_type or "Chakra" in format_type:
            draw_fn = self.draw_label_vertus_chakras
            single_mm = (70, 37)
        else:
            draw_fn = self.draw_single_label
            single_mm = label_mm

        single_layout_sizes = {
            "80x50": (80, 50),
            "70x40": (70, 40),
            "60x30": (60, 30),
            "50x25": (50, 25),
        }

        if layout in single_layout_sizes:
            mm_size = single_layout_sizes.get(layout, single_mm)
            w, h = mm_to_pt(mm_size[0]), mm_to_pt(mm_size[1])
            if orientation == "paysage":
                w, h = h, w
            pdf = canvas.Canvas(output_path, pagesize=(w, h))
            for bracelet in bracelets:
                draw_fn(pdf, bracelet, 0, 0, w, h)
                pdf.showPage()
            pdf.save()
            return

        if layout == "custom":
            w, h = mm_to_pt(single_mm[0]), mm_to_pt(single_mm[1])
            if orientation == "paysage":
                w, h = h, w
            pdf = canvas.Canvas(output_path, pagesize=(w, h))
            for bracelet in bracelets:
                draw_fn(pdf, bracelet, 0, 0, w, h)
                pdf.showPage()
            pdf.save()
            return

        page_size = landscape(A4) if orientation == "paysage" else A4
        page_w, page_h = page_size
        pdf = canvas.Canvas(output_path, pagesize=page_size)

        if layout == "8":
            cols, rows = 2, 4
        elif layout == "12":
            cols, rows = 3, 4
        elif layout == "21":
            cols, rows = 3, 7
        else:
            cols, rows = 3, 4

        margin_x = mm_to_pt(8)
        margin_y = mm_to_pt(8)
        gap_x = mm_to_pt(4)
        gap_y = mm_to_pt(4)

        cell_w = (page_w - 2 * margin_x - (cols - 1) * gap_x) / cols
        cell_h = (page_h - 2 * margin_y - (rows - 1) * gap_y) / rows

        per_page = cols * rows
        index = 0

        while index < len(bracelets):
            for pos in range(per_page):
                if index >= len(bracelets):
                    break

                col = pos % cols
                row = pos // cols

                x = margin_x + col * (cell_w + gap_x)
                y = page_h - margin_y - (row + 1) * cell_h - row * gap_y
                draw_fn(pdf, bracelets[index], x, y, cell_w, cell_h)
                index += 1

            pdf.showPage()

        pdf.save()

    def export_product_price_labels_pdf(
        self,
        products: list[dict[str, Any]],
        output_path: str,
        layout: str = "21",
        orientation: str = "portrait",
    ) -> None:
        page_size = landscape(A4) if orientation == "paysage" else A4
        page_w, page_h = page_size
        pdf = canvas.Canvas(output_path, pagesize=page_size)

        if layout == "8":
            cols, rows = 2, 4
        elif layout == "12":
            cols, rows = 3, 4
        else:
            cols, rows = 3, 7

        margin_x = mm_to_pt(8)
        margin_y = mm_to_pt(8)
        gap_x = mm_to_pt(4)
        gap_y = mm_to_pt(4)
        cell_w = (page_w - 2 * margin_x - (cols - 1) * gap_x) / cols
        cell_h = (page_h - 2 * margin_y - (rows - 1) * gap_y) / rows

        per_page = cols * rows
        idx = 0
        while idx < len(products):
            for pos in range(per_page):
                if idx >= len(products):
                    break
                col = pos % cols
                row = pos // cols
                x = margin_x + col * (cell_w + gap_x)
                y = page_h - margin_y - (row + 1) * cell_h - row * gap_y
                self._draw_product_price_label(pdf, products[idx], x, y, cell_w, cell_h)
                idx += 1
            pdf.showPage()

        pdf.save()

    def _draw_product_price_label(self, c: canvas.Canvas, product: dict[str, Any], x: float, y: float, w: float, h: float) -> None:
        self.refresh_style_from_settings()
        margin = 8
        c.rect(x, y, w, h)
        c.setFont(self._safe_font(self.base_font, bold=True), 11)
        c.drawString(x + margin, y + h - margin - 2, product.get("nom", "Article"))
        c.setFont(self._safe_font(self.base_font), 8)
        c.drawString(x + margin, y + h - margin - 16, f"Cat.: {product.get('categorie', '-')}")
        c.drawString(x + margin, y + h - margin - 28, f"SKU: {product.get('sku', '-')}")

        c.setFont(self._safe_font(self.base_font, bold=True), 12)
        c.drawString(x + margin, y + margin + 2, f"{float(product.get('prix_vente', 0.0) or 0.0):.2f} EUR")

    def export_fiches_creation_pdf(self, bracelets, output_path: str) -> None:
        """Genere un PDF A4 avec plusieurs petites fiches encadrees par page."""
        from datetime import datetime as _dt
        self.refresh_style_from_settings()
        fnt = self._safe_font
        font_n = fnt(self.base_font, bold=False)
        font_b = fnt(self.base_font, bold=True)

        page_w, page_h = A4
        margin = 36.0
        header_h = 30.0
        cols, rows = 2, 4
        gx, gy = 16.0, 14.0
        cw = (page_w - 2 * margin - (cols - 1) * gx) / cols
        content_top = page_h - margin - header_h
        avail_h = content_top - margin
        ch = (avail_h - (rows - 1) * gy) / rows

        c = canvas.Canvas(output_path, pagesize=A4)
        genre_map = {"homme": "Homme", "femme": "Femme", "mixte": "Mixte", "enfant": "Enfant"}
        date_txt = _dt.now().strftime("%d/%m/%Y")

        def draw_header(page_no):
            c.setFont(font_b, 14)
            c.drawString(margin, page_h - margin - 6, "Fiches bracelets")
            c.setFont(font_n, 9)
            c.drawRightString(page_w - margin, page_h - margin - 6, f"Date : {date_txt}   -   Page {page_no}")
            c.setLineWidth(1)
            c.line(margin, page_h - margin - 12, page_w - margin, page_h - margin - 12)

        def draw_card(bx, by, bracelet):
            pad = 8.0
            inner_w = cw - 2 * pad
            x = bx + pad
            bottom = by + pad
            c.setLineWidth(0.8)
            c.rect(bx, by, cw, ch, fill=0, stroke=1)

            metrics = self.db.calculate_bracelet_metrics(bracelet) if self.db else {}
            yy = by + ch - pad

            c.setFont(font_b, 10)
            nom = str(bracelet.get("nom", "") or "Bracelet")
            nlines = simpleSplit(nom, font_b, 10, inner_w)
            c.drawString(x, yy - 8, nlines[0] if nlines else nom)
            yy -= 22

            c.setFont(font_n, 7.5)
            ref = str(bracelet.get("reference", "") or "-")
            genre_raw = str(bracelet.get("genre", "") or "").strip().lower()
            genre_txt = genre_map.get(genre_raw, "-")
            stock = int(bracelet.get("stock", 0) or 0)
            c.drawString(x, yy, f"Ref: {ref}   -   {genre_txt}   -   Stock: {stock}")
            yy -= 13

            def block(title, text, max_lines, size=7.5):
                nonlocal yy
                if not text:
                    return
                if yy < bottom + 24:
                    return
                c.setFont(font_b, 7.5)
                c.drawString(x, yy, title)
                yy -= 10
                c.setFont(font_n, size)
                lines2 = simpleSplit(text, font_n, size, inner_w)
                shown = lines2[:max_lines]
                if len(lines2) > max_lines and shown:
                    shown[-1] = shown[-1][: max(0, len(shown[-1]) - 1)] + "..."
                for ln in shown:
                    if yy < bottom + 14:
                        break
                    c.drawString(x, yy, ln)
                    yy -= 10
                yy -= 3

            comp_txt = ", ".join(str(m) for m in (metrics.get("composition") or [])) or "-"
            block("Composition", comp_txt, 3)
            block("Vertus", ", ".join(metrics.get("vertus", []) or []), 2)
            block("Chakras", ", ".join(metrics.get("chakras", []) or []), 1)

            prix_vente = float(bracelet.get("prix_vente", 0.0) or 0.0)
            cout = float(metrics.get("cout_revient", 0.0) or 0.0)
            marge = prix_vente - cout
            c.setFont(font_b, 8)
            c.drawString(x, bottom + 2, f"PV {prix_vente:.2f} EUR   Cout {cout:.2f} EUR   Marge {marge:.2f} EUR")

        per_page = cols * rows
        page_no = 1
        for idx, bracelet in enumerate(bracelets):
            slot = idx % per_page
            if slot == 0:
                if idx > 0:
                    c.showPage()
                    page_no += 1
                draw_header(page_no)
            r = slot // cols
            col = slot % cols
            bx = margin + col * (cw + gx)
            by = content_top - (r + 1) * ch - r * gy
            draw_card(bx, by, bracelet)

        if not bracelets:
            draw_header(1)
            c.setFont(font_n, 11)
            c.drawString(margin, content_top - 20, "Aucun bracelet a exporter.")

        c.showPage()
        c.save()

    def export_fiche_creation_pdf(self, bracelet: dict[str, Any], output_path: str) -> None:
        """Genere une fiche de creation/fabrication A4 d'un bracelet."""
        from datetime import datetime as _dt

        self.refresh_style_from_settings()
        fnt = self._safe_font
        font_n = fnt(self.base_font, bold=False)
        font_b = fnt(self.base_font, bold=True)

        metrics = self.db.calculate_bracelet_metrics(bracelet) if self.db else {}
        composition = bracelet.get("composition", []) or []

        genre_raw = str(bracelet.get("genre", "") or "").strip().lower()
        genre_map = {"homme": "Homme", "femme": "Femme", "mixte": "Mixte", "enfant": "Enfant"}
        genre_txt = genre_map.get(genre_raw, "Non specifie")

        page_w, page_h = A4
        margin = 50.0
        x0 = margin
        x_right = page_w - margin
        c = canvas.Canvas(output_path, pagesize=A4)

        # Colonnes :  #  |  Qte  |  Composant  |  Type  |  PU achat  |  Sous-total
        col_idx = x0              # "#"  (gauche)
        col_qte = x0 + 50         # "Qte" (droite)
        col_nom = x0 + 60         # "Composant" (gauche)
        col_type = x0 + 270       # "Type" (gauche)
        col_pu = x0 + 400         # "PU achat" (droite)
        col_sub = x_right         # "Sous-total" (droite)

        def header_band(title_y):
            yy = title_y
            c.setFont(font_b, 18)
            c.drawString(x0, yy, "Fiche de creation de bracelet")
            yy -= 6
            c.setLineWidth(1)
            c.line(x0, yy, x_right, yy)
            yy -= 22
            return yy

        def table_header(yy):
            c.setFillColorRGB(0.93, 0.93, 0.93)
            c.rect(x0, yy - 4, x_right - x0, 18, fill=1, stroke=0)
            c.setFillColorRGB(0, 0, 0)
            c.setFont(font_b, 9)
            c.drawString(col_idx, yy, "#")
            c.drawRightString(col_qte, yy, "Qte")
            c.drawString(col_nom, yy, "Composant")
            c.drawString(col_type, yy, "Type")
            c.drawRightString(col_pu, yy, "PU achat")
            c.drawRightString(col_sub, yy, "Sous-total")
            return yy - 20

        y = header_band(page_h - margin)

        c.setFont(font_b, 13)
        c.drawString(x0, y, bracelet.get("nom", "") or "Bracelet")
        c.setFont(font_n, 10)
        ref = bracelet.get("reference", "") or "-"
        c.drawRightString(x_right, y, f"Ref : {ref}")
        y -= 16
        c.setFont(font_n, 10)
        c.drawString(x0, y, f"Genre : {genre_txt}")
        c.drawRightString(x_right, y, f"Date : {_dt.now().strftime('%d/%m/%Y')}")
        y -= 14
        c.drawString(x0, y, f"Stock actuel : {int(bracelet.get('stock', 0) or 0)}")
        y -= 24

        c.setFont(font_b, 12)
        c.drawString(x0, y, "Ordre de montage")
        y -= 20
        y = table_header(y)

        total_mat = 0.0
        total_pierres = 0.0
        nb_pierres = 0
        c.setFont(font_n, 9)
        for i, row in enumerate(composition, start=1):
            nom = str(row.get("composant", "")).strip() or "-"
            cat = str(row.get("categorie", "")).strip() or "-"
            qty = int(row.get("quantite", 1) or 1)
            pu = float(row.get("cout_unitaire", 0.0) or 0.0)
            sub = pu * qty
            total_mat += sub
            is_pierre = cat.lower().startswith("pierre")
            if is_pierre:
                total_pierres += sub
                nb_pierres += qty

            if y < margin + 120:
                c.showPage()
                y = header_band(page_h - margin)
                y = table_header(y)
                c.setFont(font_n, 9)

            nom_lines = simpleSplit(nom, font_n, 9, col_type - col_nom - 6)
            c.drawString(col_idx, y, str(i))
            c.drawRightString(col_qte, y, str(qty))
            c.drawString(col_nom, y, nom_lines[0] if nom_lines else nom)
            c.drawString(col_type, y, cat)
            c.drawRightString(col_pu, y, f"{pu:.2f} EUR")
            c.drawRightString(col_sub, y, f"{sub:.2f} EUR")
            y -= 14
            for extra in nom_lines[1:]:
                c.drawString(col_nom, y, extra)
                y -= 12

        if not composition:
            c.setFont(font_n, 10)
            c.drawString(x0, y, "Aucun composant defini pour ce bracelet.")
            y -= 16

        y -= 4
        c.setLineWidth(0.5)
        c.line(x0, y, x_right, y)
        y -= 18

        # Nombre de pierres (uniquement les pierres)
        c.setFont(font_b, 10)
        c.drawString(x0, y, f"Nombre de pierres : {nb_pierres}")
        y -= 20

        # Recapitulatif des couts
        prix_vente = float(bracelet.get("prix_vente", 0.0) or 0.0)
        total_autres = total_mat - total_pierres
        cout_total = total_pierres + total_autres
        marge = prix_vente - cout_total

        def total_line(lbl, val, bold=False, size=10):
            nonlocal y
            c.setFont(font_b if bold else font_n, size)
            c.drawRightString(col_pu, y, lbl)
            c.drawRightString(col_sub, y, val)
            y -= 14

        total_line("Cout pierres :", f"{total_pierres:.2f} EUR")
        total_line("Cout matieres :", f"{total_autres:.2f} EUR")
        total_line("Cout total (pierres + matieres) :", f"{cout_total:.2f} EUR", bold=True)
        y -= 3
        total_line("Prix de vente :", f"{prix_vente:.2f} EUR", bold=True, size=11)
        total_line("Marge :", f"{marge:.2f} EUR")
        y -= 22

        vertus = metrics.get("vertus", []) or []
        chakras = metrics.get("chakras", []) or []
        if vertus:
            c.setFont(font_b, 11)
            c.drawString(x0, y, "Vertus")
            y -= 15
            c.setFont(font_n, 9)
            for line in simpleSplit(", ".join(vertus), font_n, 9, x_right - x0):
                c.drawString(x0, y, line)
                y -= 12
            y -= 6
        if chakras:
            c.setFont(font_b, 11)
            c.drawString(x0, y, "Chakras")
            y -= 15
            c.setFont(font_n, 9)
            for line in simpleSplit(", ".join(chakras), font_n, 9, x_right - x0):
                c.drawString(x0, y, line)
                y -= 12

        c.setFont(font_n, 7)
        from catalogue_services import _find_stone_info
        purifs = []
        rechs = []
        seen_stones = set()
        for erow in composition:
            if not str(erow.get("categorie", "")).strip().lower().startswith("pierre"):
                continue
            snom = str(erow.get("composant", "")).strip()
            skey = snom.lower()
            if not snom or skey in seen_stones:
                continue
            seen_stones.add(skey)
            info = _find_stone_info(snom)
            if info:
                pp = info.get("purification")
                rr = info.get("rechargement")
                if pp and pp not in purifs:
                    purifs.append(pp)
                if rr and rr not in rechs:
                    rechs.append(rr)

        if y < margin + 95:
            c.showPage()
            y = page_h - margin
        y -= 6
        c.setFont(font_b, 11)
        c.drawString(x0, y, "Entretien : purification & rechargement")
        y -= 15
        c.setFont(font_n, 9)
        purif_txt = coherent_purification(purifs)
        rech_txt = coherent_rechargement(rechs)
        for _lbl, _val in (("Purification : ", purif_txt), ("Rechargement : ", rech_txt)):
            for line in simpleSplit(_lbl + _val, font_n, 9, x_right - x0):
                c.drawString(x0, y, line)
                y -= 12
        c.setFont(font_n, 8)
        for line in simpleSplit("Astuce : la fumigation et la lune conviennent a toutes les pierres ; evitez l'eau pour les pierres fragiles.", font_n, 8, x_right - x0):
            c.drawString(x0, y, line)
            y -= 11
        y -= 4

        from lunar_services import next_full_moons
        moon_based = (not rechs) or any("lune" in str(_r).lower() for _r in rechs)
        if moon_based:
            try:
                _fms = next_full_moons(4)
            except Exception:
                _fms = []
            if y < margin + 75:
                c.showPage()
                y = page_h - margin
            y -= 6
            c.setFont(font_b, 11)
            c.drawString(x0, y, "Calendrier de rechargement - prochaines pleines lunes")
            y -= 15
            c.setFont(font_n, 9)
            if _fms:
                for _d in _fms:
                    c.drawString(x0, y, "- " + _d.strftime("%d/%m/%Y a %Hh%M"))
                    y -= 12
            else:
                c.drawString(x0, y, "- Rechargez a la prochaine nuit de pleine lune.")
                y -= 12
            c.setFont(font_n, 8)
            for line in simpleSplit("Posez le bracelet sur un rebord de fenetre la nuit de pleine lune (la veille ou le lendemain conviennent aussi).", font_n, 8, x_right - x0):
                c.drawString(x0, y, line)
                y -= 11
            y -= 4
        c.drawString(x0, margin - 12, "Document interne de fabrication - prix d'achat confidentiels.")
        c.showPage()
        c.save()
