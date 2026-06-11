"""pages/impression.py
Impression PDF A4 — Grille Action 3×8, Zoom, Profils.
Portage V2 complet depuis ui.py (V1 legacy).
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, filedialog
from typing import Any

import customtkinter as ctk
import layout_profiles
import theme
from pdf_generator import PDFGenerator

# ── Helpers (anciennement dans ui.py) ──────────────────────────────────


def _safe_filename(value: str) -> str:
    clean = "".join(ch for ch in value if ch.isalnum() or ch in ("-", "_", " ")).strip()
    return clean.replace(" ", "_") or "etiquette"


def _open_generated_file(file_path: str) -> None:
    try:
        if os.name == "nt":
            os.startfile(file_path)
        else:
            import webbrowser
            webbrowser.open(Path(file_path).as_uri())
    except OSError:
        pass


def _is_default_printer_selection(name: str) -> bool:
    return not name or name.strip().lower() == "imprimante par defaut"


def _refresh_printer_list() -> list[str]:
    printers = ["Imprimante par defaut"]
    if os.name == "nt":
        try:
            import win32print
            for entry in win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            ):
                pname = entry[2]
                if pname and pname not in printers:
                    printers.append(pname)
        except Exception:
            pass
    return printers


# ── Page principale ───────────────────────────────────────────────────

class ImpressionPage(ctk.CTkFrame):
    """Page d'impression A4 avec grille 3×8, zoom, export PDF."""

    def __init__(self, parent, db=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.db = db
        self.pdf = PDFGenerator(db) if db else None

        # État
        self._pos_buttons: list[ctk.CTkButton] = []
        self._selected_pos: int | None = None
        self._selected_positions: set[int] = set()
        self._list_bracelet_ids: list[str] = []

        # Variables
        self._model_var = ctk.StringVar(value="bracelet")
        self._mode_var = ctk.StringVar(value="position")
        self._printer_var = ctk.StringVar(value="Imprimante par defaut")

        self._build_ui()

    # ── Construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=16, pady=(8, 4))

        left = ctk.CTkFrame(main, fg_color="transparent")
        mid = ctk.CTkFrame(main, fg_color="transparent")
        right = ctk.CTkFrame(main, fg_color="transparent")
        left.pack(side="left", fill="y", padx=(0, 8))
        mid.pack(side="left", fill="y", padx=(0, 8))
        right.pack(side="left", fill="both", expand=True)

        self._build_bracelet_list(left)
        self._build_grid_area(mid)
        self._build_preview(right)
        self._build_footer()

        self._refresh_bracelet_list()
        self._update_grid_buttons()
        self._draw_preview()

    def _build_bracelet_list(self, parent) -> None:
        ctk.CTkLabel(
            parent, text="Bracelet à imprimer",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 6))

        self._bracelet_scroll = ctk.CTkScrollableFrame(
            parent, width=280, height=520,
            fg_color=theme.BG_CARD, corner_radius=12,
        )
        self._bracelet_scroll.pack(fill="both", expand=True)

        self._bracelet_buttons: list[ctk.CTkButton] = []
        self._selected_bracelet_idx = ctk.IntVar(value=-1)

    def _refresh_bracelet_list(self) -> None:
        if not self.db:
            return
        for w in self._bracelet_scroll.winfo_children():
            w.destroy()
        self._bracelet_buttons.clear()
        self._list_bracelet_ids.clear()
        self._selected_bracelet_idx.set(-1)

        bracelets = sorted(
            self.db.bracelets,
            key=lambda b: b.get("nom", "").lower(),
        )
        for idx, b in enumerate(bracelets):
            bid = b.get("id", "")
            self._list_bracelet_ids.append(bid)
            nom = b.get("nom", "?")
            ref = b.get("reference", "")
            pv = float(b.get("prix_vente", 0) or 0)
            label = f"{nom}"
            if ref:
                label += f"  ·  {ref}"
            label += f"  —  {pv:.2f} €"

            btn = ctk.CTkButton(
                self._bracelet_scroll,
                text=label,
                anchor="w",
                height=36,
                corner_radius=10,
                fg_color="transparent",
                hover_color=theme.BG_CARD_HOVER,
                text_color=theme.TEXT_PRIMARY,
                font=ctk.CTkFont(size=12),
                command=lambda i=idx: self._on_select_bracelet(i),
            )
            btn.pack(fill="x", pady=2)
            self._bracelet_buttons.append(btn)

    def _on_select_bracelet(self, idx: int) -> None:
        self._selected_bracelet_idx.set(idx)
        for i, btn in enumerate(self._bracelet_buttons):
            if i == idx:
                btn.configure(fg_color=theme.ACCENT_TURQUOISE, text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", text_color=theme.TEXT_PRIMARY)
        self._draw_preview()

    def _get_selected_bracelet(self) -> dict | None:
        idx = self._selected_bracelet_idx.get()
        if idx < 0 or not self.db:
            return None
        bid = self._list_bracelet_ids[idx] if idx < len(self._list_bracelet_ids) else ""
        return self.db.get_bracelet_by_id(bid) if bid else None

    def _build_grid_area(self, parent) -> None:
        # Type d'étiquette
        type_frame = ctk.CTkFrame(parent, fg_color=theme.BG_CARD, corner_radius=12)
        type_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            type_frame, text="Type d'étiquette",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=12, pady=(8, 4))

        for val, label in [("bracelet", "Bracelet (composition + prix)"),
                           ("vertus", "Vertus / Chakras")]:
            ctk.CTkRadioButton(
                type_frame, text=label, variable=self._model_var,
                value=val, command=self._on_model_change,
                fg_color=theme.ACCENT_TURQUOISE,
                text_color=theme.TEXT_PRIMARY,
            ).pack(anchor="w", padx=16, pady=2)

        ctk.CTkFrame(type_frame, height=1, fg_color=theme.BORDER).pack(
            fill="x", padx=12, pady=(6, 0))

        # Mode
        ctk.CTkLabel(
            type_frame, text="Mode",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=12, pady=(8, 4))

        for val, label in [
            ("position", "Position unique"),
            ("multi", "Sélection multiple"),
            ("feuille", "Feuille complète"),
        ]:
            ctk.CTkRadioButton(
                type_frame, text=label, variable=self._mode_var,
                value=val, command=self._on_mode_change,
                fg_color=theme.ACCENT_TURQUOISE,
                text_color=theme.TEXT_PRIMARY,
            ).pack(anchor="w", padx=16, pady=2)

        # Légende
        leg = ctk.CTkFrame(type_frame, fg_color="transparent")
        leg.pack(anchor="w", padx=12, pady=(8, 6))
        for color, txt in [
            (theme.SUCCESS, "Libre"),
            ("#f87171", "Utilisée"),
            (theme.INFO, "Sélectionnée"),
        ]:
            ctk.CTkLabel(
                leg, text="  ", width=14, fg_color=color,
                corner_radius=3,
            ).pack(side="left", padx=(0, 2))
            ctk.CTkLabel(
                leg, text=txt, text_color=theme.TEXT_SECONDARY,
                font=ctk.CTkFont(size=11),
            ).pack(side="left", padx=(0, 10))

        # Grille 3×8
        grid_wrap = ctk.CTkFrame(parent, fg_color="transparent")
        grid_wrap.pack(pady=(4, 0))

        self._pos_buttons.clear()
        for pos in range(1, 25):
            col = (pos - 1) % 3
            row = (pos - 1) // 3
            btn = ctk.CTkButton(
                grid_wrap,
                text=f"{pos:02d}",
                width=56, height=40,
                corner_radius=8,
                fg_color=theme.SUCCESS,
                text_color="#ffffff",
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda p=pos: self._select_position(p),
            )
            btn.grid(row=row, column=col, padx=3, pady=3)
            self._pos_buttons.append(btn)

        # Boutons d'action
        sep = ctk.CTkFrame(parent, height=1, fg_color=theme.BORDER)
        sep.pack(fill="x", pady=(10, 6))

        self._btn_add = ctk.CTkButton(
            parent, text="✚  Ajouter (Bracelet)",
            fg_color=theme.SUCCESS, hover_color="#059669",
            text_color="#ffffff", font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=10, command=self._action_add_to_sheet,
        )
        self._btn_add.pack(fill="x", pady=(0, 4))

        ctk.CTkButton(
            parent, text="✖  Retirer de la feuille",
            fg_color=theme.DANGER, hover_color="#dc2626",
            text_color="#ffffff", font=ctk.CTkFont(size=12),
            corner_radius=10, command=self._action_remove_from_sheet,
        ).pack(fill="x", pady=(0, 4))

        ctk.CTkButton(
            parent, text="Nouvelle feuille",
            fg_color=theme.BG_CARD, hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(size=12),
            corner_radius=10, command=self._action_new_sheet,
        ).pack(fill="x", pady=(4, 0))

    def _build_preview(self, parent) -> None:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            header, text="Aperçu feuille A4",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        preview_frame = ctk.CTkFrame(
            parent, fg_color=theme.BG_CARD, corner_radius=12,
        )
        preview_frame.pack(fill="both", expand=True)

        self._preview_canvas = ctk.CTkCanvas(
            preview_frame,
            bg="#f8fafc",
            highlightthickness=0,
        )
        self._preview_canvas.pack(fill="both", expand=True, padx=8, pady=8)

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=12, height=48)
        footer.pack(fill="x", side="bottom", pady=(4, 8), padx=16)
        footer.pack_propagate(False)

        inner = ctk.CTkFrame(footer, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12)

        ctk.CTkLabel(
            inner, text="Imprimante :",
            text_color=theme.TEXT_SECONDARY, font=ctk.CTkFont(size=12),
        ).pack(side="left")

        printers = _refresh_printer_list()
        self._printer_combo = ctk.CTkComboBox(
            inner, variable=self._printer_var,
            values=printers, width=240,
            fg_color=theme.BG_INPUT, border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
            dropdown_fg_color=theme.BG_CARD,
            dropdown_text_color=theme.TEXT_PRIMARY,
            button_color=theme.ACCENT_TURQUOISE,
            corner_radius=8,
        )
        self._printer_combo.pack(side="left", padx=(6, 12))

        ctk.CTkButton(
            inner, text="📂  Dossier PDF",
            fg_color=theme.BG_INPUT, hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(size=11),
            corner_radius=8, width=100, command=self._open_pdf_folder,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            inner, text="🔍  Zoom",
            fg_color=theme.BG_INPUT, hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(size=11),
            corner_radius=8, width=80, command=self._open_zoom_editor,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            inner, text="📄  Export feuille",
            fg_color=theme.ACCENT_TURQUOISE,
            text_color="#ffffff", font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=8, width=110, command=self._action_export_feuille,
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            inner, text="🖨️  Imprimer feuille",
            fg_color=theme.ACCENT_AMETHYSTE,
            text_color="#ffffff", font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=8, width=110, command=self._action_print_feuille,
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            inner, text="🖨️  Sélection",
            fg_color=theme.BG_INPUT, hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(size=11),
            corner_radius=8, width=90, command=self._action_print_selection,
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            inner, text="📄  Export sélection",
            fg_color=theme.BG_INPUT, hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(size=11),
            corner_radius=8, width=110, command=self._action_export_selection,
        ).pack(side="left", padx=(0, 4))

    # ── État et mise à jour ───────────────────────────────────────────

    def refresh(self) -> None:
        self._refresh_bracelet_list()
        self._update_grid_buttons()
        self._draw_preview()

    def _on_model_change(self) -> None:
        self._update_add_button_label()
        self._draw_preview()

    def _on_mode_change(self) -> None:
        self._selected_pos = None
        self._selected_positions.clear()
        self._update_add_button_label()
        self._update_grid_buttons()
        self._draw_preview()

    def _update_add_button_label(self) -> None:
        model = self._model_var.get()
        mode = self._mode_var.get()
        label = "Vertus/Chakras" if model == "vertus" else "Bracelet"
        if mode == "multi":
            self._btn_add.configure(
                text="✚  Ajouter (mode position uniquement)",
                state="disabled",
            )
        else:
            self._btn_add.configure(
                text=f"✚  Ajouter ({label})",
                state="normal",
            )

    def _select_position(self, pos: int) -> None:
        mode = self._mode_var.get()
        if mode == "multi":
            if pos in self._selected_positions:
                self._selected_positions.discard(pos)
            else:
                self._selected_positions.add(pos)
        else:
            if self._selected_pos == pos:
                self._selected_pos = None
            else:
                self._selected_pos = pos
        self._update_grid_buttons()
        self._draw_preview()

    def _update_grid_buttons(self) -> None:
        if not self._pos_buttons or not self.db:
            return
        mode = self._mode_var.get()
        positions = self.db.get_feuille_positions()
        for i, btn in enumerate(self._pos_buttons):
            p = i + 1
            pd = positions[i]
            used = pd.get("used", False)
            selected = (
                p in self._selected_positions if mode == "multi"
                else p == self._selected_pos
            )
            if selected:
                btn.configure(fg_color=theme.INFO, text_color="#ffffff", text=f"{p:02d}")
            elif used:
                mtype = "V" if pd.get("model") == "vertus" else "B"
                btn.configure(fg_color="#f87171", text_color="#ffffff", text=f"{p:02d}\n{mtype}")
            else:
                btn.configure(fg_color=theme.SUCCESS, text_color="#ffffff", text=f"{p:02d}")

    # ── Aperçu canvas ─────────────────────────────────────────────────

    def _draw_preview(self) -> None:
        cv = self._preview_canvas
        cv.delete("all")
        if not self.db:
            return

        cw = max(cv.winfo_width(), 370)
        ch = max(cv.winfo_height(), 400)

        margin = 12
        scale = min((cw - 2 * margin) / 210, (ch - 2 * margin) / 296)
        cell_w = 70 * scale
        cell_h = 37 * scale
        ox = (cw - 3 * cell_w) / 2
        oy = (ch - 8 * cell_h) / 2

        mode = self._mode_var.get()
        positions = self.db.get_feuille_positions()
        current = self._get_selected_bracelet()

        for pos in range(1, 25):
            col_i = (pos - 1) % 3
            row_i = (pos - 1) // 3
            x0 = ox + col_i * cell_w
            y0 = oy + row_i * cell_h
            x1 = x0 + cell_w
            y1 = y0 + cell_h

            pd = positions[pos - 1]
            used = pd.get("used", False)
            selected = (
                pos in self._selected_positions if mode == "multi"
                else pos == self._selected_pos
            )

            if selected:
                fill, outline, lw = "#dbeafe", "#2563eb", 2
            elif used:
                fill, outline, lw = "#fee2e2", "#dc2626", 1
            else:
                fill, outline, lw = "#f0fdf4", "#9ca3af", 1

            cv.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=lw)

            if selected and current:
                if used:
                    bracelet_db = self.db.get_bracelet_by_id(pd.get("bracelet_id", ""))
                    model = pd.get("model", "bracelet")
                    bracelet = bracelet_db or current
                else:
                    bracelet = current
                    model = self._model_var.get()
                self._draw_cell(cv, bracelet, model, x0, y0, x1, y1, scale)
                if not used:
                    fs = max(5, int(scale * 1.6))
                    cv.create_text(
                        (x0 + x1) / 2, y1 - max(3, int(scale * 1.2)),
                        text="— APERÇU —",
                        font=("Segoe UI", fs, "italic"),
                        fill="#2563eb", anchor="s",
                    )
            elif used:
                stored_id = pd.get("bracelet_id", "")
                stored_model = pd.get("model", "bracelet")
                stored_b = self.db.get_bracelet_by_id(stored_id) if stored_id else None
                if stored_b:
                    self._draw_cell(cv, stored_b, stored_model, x0, y0, x1, y1, scale)
                else:
                    nom = pd.get("bracelet_nom", "?")
                    mt = "V/C" if stored_model == "vertus" else "Brac."
                    mcolor = "#7c3aed" if stored_model == "vertus" else "#1d4ed8"
                    fs_s = max(4, int(scale * 1.6))
                    cv.create_text(x1 - 2, y0 + 2, anchor="ne", text=mt,
                                   font=("Segoe UI", fs_s, "bold"), fill=mcolor)
                    nom_short = (nom[:13] + "…") if len(nom) > 14 else nom
                    cv.create_text(x0 + 2, (y0 + y1) / 2, anchor="w",
                                   text=nom_short,
                                   font=("Segoe UI", max(5, int(scale * 1.8))),
                                   fill="#7f1d1d")
            else:
                fs = max(6, int(scale * 2.3))
                cv.create_text((x0 + x1) / 2, (y0 + y1) / 2,
                               text=f"{pos:02d}",
                               font=("Segoe UI", fs), fill="#6b7280")

    def _draw_cell(self, cv, bracelet: dict, model: str,
                   x0: float, y0: float, x1: float, y1: float,
                   scale: float) -> None:
        lyt = layout_profiles.load_layout(model, self.db.base_dir)

        def at(x_mm: float, y_mm: float) -> tuple[float, float]:
            return x0 + x_mm * scale, y0 + y_mm * scale

        def pt_size(pdf_pt: float) -> int:
            return max(4, round(pdf_pt * scale * 25.4 / 96))

        # Nom
        nc = lyt.get("nom", {})
        if isinstance(nc, dict):
            cx, cy = at(nc.get("x", 4), nc.get("y", 4))
            fs = pt_size(float(nc.get("size", 11)))
            bold = "bold" if nc.get("bold", True) else "normal"
            cv.create_text(cx, cy, anchor="nw",
                           text=bracelet.get("nom", "") or "Bracelet",
                           font=("Segoe UI", fs, bold), fill="#0f172a")

        # Séparateur
        sep_y_mm = float(lyt.get("sep_y", 7.5))
        _, sep_cy = at(4, sep_y_mm)
        cv.create_line(x0 + 4 * scale, sep_cy, x1 - 4 * scale, sep_cy,
                       fill="#aaaaaa", width=1, dash=(3, 2))

        try:
            met = self.db.calculate_bracelet_metrics(bracelet)
        except Exception:
            met = {}
        pv = float(bracelet.get("prix_vente", 0.0) or 0.0)
        pr = float(met.get("cout_revient", 0.0))

        if model == "bracelet":
            cl = lyt.get("comp_label", {})
            if isinstance(cl, dict):
                cx, cy = at(cl.get("x", 4), cl.get("y", 9.5))
                fs = pt_size(float(cl.get("size", 8)))
                cv.create_text(cx, cy, anchor="nw", text="Composition :",
                               font=("Segoe UI", fs, "bold"), fill="#374151")

            ci = lyt.get("comp_items", {})
            if isinstance(ci, dict):
                ix = float(ci.get("x", 5.5))
                iy = float(ci.get("y", 13.0))
                lead = float(ci.get("leading", 4.8))
                fs = pt_size(float(ci.get("size", 8)))
                for i, row in enumerate(bracelet.get("composition", [])):
                    qty = int(row.get("quantite", 1) or 1)
                    nom_c = str(row.get("composant", "")).strip()
                    if not nom_c:
                        continue
                    cx, cy = at(ix, iy + i * lead)
                    if cy > y1 - 2:
                        break
                    line = f"{qty}× {nom_c}" if qty > 1 else nom_c
                    cv.create_text(cx, cy, anchor="nw", text=line,
                                   font=("Segoe UI", fs), fill="#1f2937")
        else:
            vertus = met.get("vertus", [])
            chakras = met.get("chakras", [])

            vl = lyt.get("vertus_label", {})
            if isinstance(vl, dict):
                cx, cy = at(vl.get("x", 4), vl.get("y", 9.5))
                fs = pt_size(float(vl.get("size", 7)))
                cv.create_text(cx, cy, anchor="nw", text="Vertus :",
                               font=("Segoe UI", fs, "bold"), fill="#374151")

            vi = lyt.get("vertus_items", {})
            if isinstance(vi, dict):
                ix = float(vi.get("x", 5))
                iy = float(vi.get("y", 12.5))
                lead = float(vi.get("leading", 4.2))
                fs = pt_size(float(vi.get("size", 7)))
                for i, v in enumerate(vertus):
                    cx, cy = at(ix, iy + i * lead)
                    if cy > y1 - 2:
                        break
                    cv.create_text(cx, cy, anchor="nw", text=str(v),
                                   font=("Segoe UI", fs), fill="#374151")

            chl = lyt.get("chakras_label", {})
            if isinstance(chl, dict):
                cx, cy = at(chl.get("x", 4), chl.get("y", 22.5))
                fs = pt_size(float(chl.get("size", 7)))
                cv.create_text(cx, cy, anchor="nw", text="Chakras :",
                               font=("Segoe UI", fs, "bold"), fill="#374151")

            chi = lyt.get("chakras_items", {})
            if isinstance(chi, dict):
                ix = float(chi.get("x", 5))
                iy = float(chi.get("y", 26.0))
                lead = float(chi.get("leading", 4.2))
                fs = pt_size(float(chi.get("size", 7)))
                for i, ch in enumerate(chakras):
                    cx, cy = at(ix, iy + i * lead)
                    if cy > y1 - 2:
                        break
                    cv.create_text(cx, cy, anchor="nw", text=str(ch),
                                   font=("Segoe UI", fs), fill="#374151")

        # Prix
        pc = lyt.get("prix", {})
        if isinstance(pc, dict) and pc.get("visible", True):
            cx, cy = at(float(pc.get("x", 4.0)), float(pc.get("y", 34.5)))
            fs = pt_size(float(pc.get("size", 12)))
            cv.create_text(cx, cy, anchor="nw", text=f"PV : {pv:.2f} €",
                           font=("Segoe UI", fs, "bold"), fill="#166534")

        prc = lyt.get("prix_revient", {})
        if isinstance(prc, dict) and prc.get("visible", False):
            cx, cy = at(float(prc.get("x", 4.0)), float(prc.get("y", 30.0)))
            fs = pt_size(float(prc.get("size", 10)))
            cv.create_text(cx, cy, anchor="nw", text=f"PR : {pr:.2f} €",
                           font=("Segoe UI", fs), fill="#92400e")

        mg = lyt.get("marge", {})
        if isinstance(mg, dict) and mg.get("visible", False):
            cx, cy = at(float(mg.get("x", 38.0)), float(mg.get("y", 34.5)))
            fs = pt_size(float(mg.get("size", 10)))
            cv.create_text(cx, cy, anchor="nw",
                           text=f"M  : {pv - pr:.2f} €",
                           font=("Segoe UI", fs), fill="#1d4ed8")

    # ── Actions feuille ───────────────────────────────────────────────

    def _action_add_to_sheet(self) -> None:
        bracelet = self._get_selected_bracelet()
        pos = self._selected_pos
        if not bracelet:
            messagebox.showwarning("Sélection", "Sélectionnez un bracelet dans la liste.")
            return
        if pos is None:
            messagebox.showwarning("Position", "Sélectionnez une position sur la grille (1-24).")
            return
        model = self._model_var.get()
        positions = self.db.get_feuille_positions()
        pd = positions[pos - 1]
        if pd.get("used"):
            stored_model = pd.get("model", "bracelet")
            stored_nom = pd.get("bracelet_nom", "?")
            stored_label = "Vertus/Chakras" if stored_model == "vertus" else "Bracelet"
            new_label = "Vertus/Chakras" if model == "vertus" else "Bracelet"
            msg = (
                f"La position {pos:02d} est déjà occupée par :\n"
                f"  « {stored_nom} » ({stored_label})\n\n"
                f"Voulez-vous la remplacer par :\n"
                f"  « {bracelet.get('nom', '?')} » ({new_label}) ?"
            )
            if not messagebox.askyesno("Position déjà utilisée", msg):
                return
        self.db.use_feuille_position(
            pos,
            bracelet_id=bracelet.get("id", ""),
            bracelet_nom=bracelet.get("nom", ""),
            model=model,
        )
        # Auto-next
        positions = self.db.get_feuille_positions()
        next_pos = None
        for i in range(pos, 24):
            if not positions[i].get("used"):
                next_pos = i + 1
                break
        if next_pos is None:
            for i in range(0, pos - 1):
                if not positions[i].get("used"):
                    next_pos = i + 1
                    break
        self._selected_pos = next_pos
        self._update_grid_buttons()
        self._draw_preview()

    def _action_remove_from_sheet(self) -> None:
        pos = self._selected_pos
        if pos is None:
            messagebox.showwarning("Position", "Sélectionnez une position sur la grille.")
            return
        positions = self.db.get_feuille_positions()
        if not positions[pos - 1].get("used"):
            messagebox.showinfo("Déjà libre", f"La position {pos:02d} est déjà libre.")
            return
        self.db.free_feuille_position(pos)
        self._update_grid_buttons()
        self._draw_preview()

    def _action_new_sheet(self) -> None:
        if not messagebox.askyesno(
            "Nouvelle feuille",
            "Remettre les 24 positions à l'état libre ?\n\n"
            "Cette action efface la mémoire de la feuille.",
        ):
            return
        self.db.reset_feuille()
        self._selected_pos = None
        self._update_grid_buttons()
        self._draw_preview()

    # ── Validation / helpers ──────────────────────────────────────────

    def _get_print_items(self) -> list[dict] | None:
        if not self._selected_positions:
            messagebox.showwarning(
                "Sélection vide",
                "Aucune position sélectionnée.\n\n"
                "Cliquez sur les positions souhaitées dans la grille.",
            )
            return None
        positions_db = self.db.get_feuille_positions()
        bracelet_list = self._get_selected_bracelet()
        model_list = self._model_var.get()

        items: list[dict] = []
        for p in sorted(self._selected_positions):
            pd = positions_db[p - 1]
            if pd.get("used"):
                bid = pd.get("bracelet_id", "")
                bracelet = self.db.get_bracelet_by_id(bid) if bid else None
                model = pd.get("model", "bracelet")
            else:
                bracelet = bracelet_list
                model = model_list
            if bracelet:
                items.append({"pos": p, "bracelet": bracelet, "model": model})

        if not items:
            messagebox.showwarning(
                "Aucun contenu",
                "Aucune des positions sélectionnées ne peut être imprimée.\n\n"
                "Sélectionnez un bracelet dans la liste\n"
                "ou ajoutez des bracelets aux positions via « Ajouter à la feuille ».",
            )
            return None
        return items

    def _choose_path(self, title: str, ext: str,
                     types: list[tuple[str, str]],
                     suggested: str = "") -> str:
        file_path = filedialog.asksaveasfilename(
            title=title,
            defaultextension=ext,
            filetypes=types,
            initialfile=suggested,
            initialdir=self.db.settings.get("last_export_dir", str(Path.cwd())),
        )
        if file_path and self.db:
            self.db.settings["last_export_dir"] = str(Path(file_path).parent)
            self.db.save_settings()
        return file_path

    # ── Zoom Editor ───────────────────────────────────────────────────

    def _open_zoom_editor(self) -> None:
        pos = self._selected_pos
        bracelet = self._get_selected_bracelet()
        model = self._model_var.get()

        if pos is not None:
            pd = self.db.get_feuille_positions()[pos - 1]
            if pd.get("used") and pd.get("model"):
                model = pd["model"]
                if bracelet is None and pd.get("bracelet_id"):
                    bracelet = self.db.get_bracelet_by_id(pd["bracelet_id"])

        if not bracelet:
            messagebox.showwarning(
                "Bracelet requis",
                "Sélectionnez un bracelet dans la liste pour ouvrir l'éditeur de mise en page.",
            )
            return

        def _on_save() -> None:
            if self.pdf:
                self.pdf.invalidate_layout_cache()
            self._draw_preview()

        from zoom_editor import LabelZoomEditor
        editor = LabelZoomEditor(
            self, model=model, bracelet=bracelet, db=self.db, on_save=_on_save,
        )

    # ── PDF / Impression ──────────────────────────────────────────────

    def _print_pdf(self, pdf_path: str) -> None:
        if not self.db:
            return
        selected_printer = self._printer_var.get().strip()
        try:
            if _is_default_printer_selection(selected_printer):
                os.startfile(pdf_path, "print")
            else:
                try:
                    import win32print
                    previous_default = win32print.GetDefaultPrinter()
                    try:
                        win32print.SetDefaultPrinter(selected_printer)
                        os.startfile(pdf_path, "print")
                    finally:
                        win32print.SetDefaultPrinter(previous_default)
                except ImportError:
                    os.startfile(pdf_path, "print")
        except OSError as exc:
            messagebox.showerror("Impression", f"Erreur d'impression :\n{exc}")

    def _action_export_selection(self) -> None:
        items = self._get_print_items()
        if not items:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        noms = "_".join(f"{it['pos']:02d}" for it in items[:5])
        if len(items) > 5:
            noms += f"_et{len(items) - 5}autres"
        suggested = f"selection_action_{noms}_{stamp}.pdf"
        path = self._choose_path(
            "Exporter la sélection — A4", ".pdf",
            [("PDF", "*.pdf")], suggested,
        )
        if not path:
            return
        self.pdf.export_action_a4_selection_pdf(items, path)
        _open_generated_file(path)
        pos_str = ", ".join(f"{it['pos']:02d}" for it in items)
        messagebox.showinfo(
            "Export sélection",
            f"{len(items)} position(s) exportée(s) : {pos_str}.\n\nFichier :\n{path}",
        )

    def _action_print_selection(self) -> None:
        items = self._get_print_items()
        if not items:
            return
        if os.name != "nt":
            messagebox.showerror("Impression",
                                 "L'impression directe est disponible uniquement sous Windows.")
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_dir = Path(self.db.settings.get("last_export_dir", str(Path.cwd())))
        base_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = str(base_dir / f"selection_action_{stamp}.pdf")
        self.pdf.export_action_a4_selection_pdf(items, pdf_path)
        self._print_pdf(pdf_path)
        pos_str = ", ".join(f"{it['pos']:02d}" for it in items)
        messagebox.showinfo(
            "Impression sélection",
            f"Impression envoyée — {len(items)} étiquette(s) : {pos_str}.",
        )

    def _action_export_feuille(self) -> None:
        positions = self.db.get_feuille_positions()
        used = [p for p in positions if p.get("used")]
        if not used:
            messagebox.showwarning(
                "Feuille vide",
                "Aucune position n'est remplie.\n\n"
                "Ajoutez des bracelets aux positions avant d'exporter.",
            )
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        suggested = f"feuille_action_{stamp}.pdf"
        path = self._choose_path(
            "Exporter la feuille complète — A4", ".pdf",
            [("PDF", "*.pdf")], suggested,
        )
        if not path:
            return
        self.pdf.export_action_a4_sheet_pdf(positions, path)
        _open_generated_file(path)
        messagebox.showinfo(
            "Export feuille",
            f"{len(used)} position(s) exportée(s).\n\nFichier :\n{path}",
        )

    def _action_print_feuille(self) -> None:
        positions = self.db.get_feuille_positions()
        used = [p for p in positions if p.get("used")]
        if not used:
            messagebox.showwarning(
                "Feuille vide",
                "Aucune position n'est remplie. Ajoutez des bracelets avant d'imprimer.",
            )
            return
        if os.name != "nt":
            messagebox.showerror("Impression",
                                 "L'impression directe est disponible uniquement sous Windows.")
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_dir = Path(self.db.settings.get("last_export_dir", str(Path.cwd())))
        base_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = str(base_dir / f"feuille_action_{stamp}.pdf")
        self.pdf.export_action_a4_sheet_pdf(positions, pdf_path)
        self._print_pdf(pdf_path)
        messagebox.showinfo(
            "Impression feuille",
            f"Impression envoyée — {len(used)} étiquette(s).",
        )

    def _action_export_position(self) -> None:
        mode = self._mode_var.get()
        if mode == "multi":
            self._action_export_selection()
            return
        if mode == "feuille":
            self._action_export_feuille()
            return
        bracelet = self._get_selected_bracelet()
        pos = self._selected_pos
        if not bracelet:
            messagebox.showwarning("Sélection", "Sélectionnez un bracelet dans la liste.")
            return
        if pos is None:
            messagebox.showwarning("Position", "Sélectionnez une position sur la grille.")
            return
        model = self._model_var.get()
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        suggested = (
            f"action_pos{pos:02d}_"
            f"{_safe_filename(bracelet.get('nom', 'bracelet'))}_{stamp}.pdf"
        )
        path = self._choose_path(
            "Exporter étiquette Action — A4 position", ".pdf",
            [("PDF", "*.pdf")], suggested,
        )
        if not path:
            return
        self.pdf.export_action_a4_position_pdf(bracelet, path, pos, model=model)
        self.db.use_feuille_position(
            pos,
            bracelet_id=bracelet.get("id", ""),
            bracelet_nom=bracelet.get("nom", "?"),
            model=model,
        )
        self._selected_pos = None
        self._update_grid_buttons()
        self._draw_preview()
        _open_generated_file(path)
        messagebox.showinfo(
            "Export PDF",
            f"Étiquette générée à la position {pos:02d}.\n"
            f"Position marquée comme utilisée.\n\nFichier :\n{path}",
        )

    def _open_pdf_folder(self) -> None:
        folder = Path(self.db.settings.get("last_export_dir", str(Path.cwd())))
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(folder))
            else:
                import webbrowser
                webbrowser.open(folder.as_uri())
        except OSError as exc:
            messagebox.showerror("Dossier PDF", f"Impossible d'ouvrir le dossier :\n{exc}")
