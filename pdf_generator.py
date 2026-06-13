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
        """Invalide le cache des profils de mise en page (appeler apres sauvegarde JSON)."""
        for model in ("bracelet", "vertus"):
            attr = f"_layout_cache_{model}"
            if hasattr(self, attr):
                delattr(self, attr)

    def _get_action_layout(self, model: str) -> dict:
        """Retourne le profil de mise en page en cache (charge depuis JSON si necessaire)."""
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
        c.drawString(cursor_x, cursor_y, f"Ref: {payload['reference'] or '-'}")
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
            pdf.setFont("Helvetica", 12)
            pdf.drawCentredString(page_w / 2, page_h / 2, "Aucune position remplie.")

        pdf.showPage()
        pdf.save()

    def export_action_a4_selection_pdf(
        self,
        items: list[dict[str, Any]],
        output_path: str,
    ) -> None:
        page_w, page_h = A4
        margin_x_pt = mm_to_pt(layout_profiles.SHEET_MARGIN_X_MM)
        margin_y_pt = mm_to_pt(layout_profiles.SHEET_MARGIN_Y_MM)
        cell_w = mm_to_pt(layout_profiles.CELL_W_MM)
        cell_h = mm_to_pt(layout_profiles.CELL_H_MM)

        pdf = canvas.Canvas(output_path, pagesize=A4)

        for item in items:
            pos = item["pos"]
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
        page_w, page_h = A4
        margin_x_pt = mm_to_pt(layout_profiles.SHEET_MARGIN_X_MM)
        margin_y_pt = mm_to_pt(layout_profiles.SHEET_MARGIN_Y_MM)
        cell_w = mm_to_pt(layout_profiles.CELL_W_MM)
        cell_h = mm_to_pt(layout_profiles.CELL_H_MM)

        col = (position - 1) % 3
        row = (position - 1) // 3

        x = margin_x_pt + col * cell_w
        y = page_h - margin_y_pt - (row + 1) * cell_h

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

    def draw_label_action_70x37(self, c: canvas.Canvas, bracelet: dict[str, Any