"""pages/niimbot.py — Éditeur d'étiquettes NIIMBOT nouvelle génération.
WYSIWYG, disposition libre des éléments, comme le logiciel NIIMBOT officiel.
"""
from __future__ import annotations

import io
import time
import tkinter.messagebox as mb
from tkinter import filedialog
from typing import Any

from PIL import Image
import customtkinter as ctk

import theme
from niimbot_services import (
    generate_qr_image,
    generate_csv,
    get_default_fields,
    get_fields_for_format,
    load_templates,
    save_template,
    delete_template,
)
from phase1c_services import load_ctk_image

# ── Constantes de rendu WYSIWYG ──────────────────────────────────────

LABEL_SIZES = {
    "50x30": (50, 30),
    "50x80": (50, 80),
}
RULER_SIZE = 30          # px pour largeur/hauteur des règles
NIIMBOT_MARGIN_MM = 2   # marge imprimante NIIMBOT en mm
GRID_STEPS = [1, 2, 5]  # pas de grille configurables en mm
CALIBRATION_X_MM = 0.0  # correction X imprimante (mm)
CALIBRATION_Y_MM = 0.0  # correction Y imprimante (mm)


class NiimbotPage(ctk.CTkFrame):
    def __init__(self, parent, db=None, **kwargs) -> None:
        super().__init__(parent, fg_color=theme.BG_MAIN, **kwargs)
        self.db = db
        self._all_bracelets: list[dict] = []
        self._selected_ids: set[str] = set()
        self._checkboxes: dict[str, ctk.CTkCheckBox] = {}
        self._checkbox_vars: dict[str, ctk.BooleanVar] = {}
        self._format: str = "50x30"
        self._fields: dict[str, bool] = {}
        self._templates: dict[str, dict] = {}
        self._search_var = ctk.StringVar()
        self._search_after_id: str | None = None
        self._search_debounce_ms = 250

        # État de l'éditeur
        self._selected_elem: str | None = None
        self._element_props: dict[str, dict] = {}
        self._drag_key: str | None = None
        self._drag_start: tuple[float, float] = (0.0, 0.0)
        self._drag_orig: tuple[float, float] = (0.0, 0.0)

        # État WYSIWYG
        self._grid_step: int = 5
        self._mm_to_px: float = 7.0
        self._ox: float = 0.0
        self._oy: float = 0.0

        # Calibration + orientation
        self._calib_x: float = CALIBRATION_X_MM
        self._calib_y: float = CALIBRATION_Y_MM
        self._real_preview: bool = False
        self._portrait: bool = False

        self._build()
        self._load_bracelets()

    # ── Construction ─────────────────────────────────────────────────

    def _build(self) -> None:
        # Header
        header = ctk.CTkFrame(self, fg_color=theme.BG_SIDEBAR, corner_radius=0, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)
        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=24)
        ctk.CTkLabel(
            inner, text="🏷️  NIIMBOT  ",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme.ACCENT_TURQUOISE,
        ).pack(side="left")
        ctk.CTkLabel(
            inner, text="Éditeur d'étiquettes professionnel",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        ).pack(side="left", padx=(8, 0))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(12, 16))
        body.grid_columnconfigure(0, weight=0, minsize=280)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, weight=0, minsize=240)
        body.grid_rowconfigure(0, weight=1)

        self._build_left(body)
        self._build_center(body)
        self._build_right(body)

    # ── Left panel : bracelet list ───────────────────────────────────

    def _build_left(self, parent: ctk.CTkFrame) -> None:
        left = ctk.CTkFrame(parent, fg_color=theme.BG_SIDEBAR, corner_radius=16)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ctk.CTkLabel(
            left, text="Bracelets",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=14, pady=(14, 2))

        search_entry = ctk.CTkEntry(
            left,
            placeholder_text="Rechercher...",
            height=32, corner_radius=10,
            fg_color=theme.BG_INPUT, border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
        )
        search_entry.pack(fill="x", padx=10, pady=(0, 6))
        self._search_var.trace_add("write", lambda *_: self._schedule_filter())
        search_entry.configure(textvariable=self._search_var)

        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 6))
        ctk.CTkButton(
            btn_row, text="Tout", font=ctk.CTkFont(size=11),
            height=26, corner_radius=8,
            fg_color=theme.BG_CARD, text_color=theme.ACCENT_TURQUOISE,
            hover_color=theme.BG_CARD_HOVER,
            command=self._select_all,
        ).pack(side="left", padx=(0, 3), expand=True, fill="x")
        ctk.CTkButton(
            btn_row, text="Aucun", font=ctk.CTkFont(size=11),
            height=26, corner_radius=8,
            fg_color=theme.BG_CARD, text_color=theme.TEXT_SECONDARY,
            hover_color=theme.BG_CARD_HOVER,
            command=self._deselect_all,
        ).pack(side="left", padx=(3, 0), expand=True, fill="x")

        self._count_label = ctk.CTkLabel(
            left, text="0 sélectionné",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY,
        )
        self._count_label.pack(anchor="w", padx=14, pady=(0, 4))

        self._list_scroll = ctk.CTkScrollableFrame(
            left, fg_color="transparent",
            scrollbar_button_color=theme.BORDER,
        )
        self._list_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 10))

    # ── Center : canvas éditeur WYSIWYG ─────────────────────────────

    def _build_center(self, parent: ctk.CTkFrame) -> None:
        center = ctk.CTkFrame(parent, fg_color=theme.BG_CARD, corner_radius=16)
        center.grid(row=0, column=1, sticky="nsew", padx=(0, 10))

        # Toolbar (haut)
        toolbar = ctk.CTkFrame(center, fg_color="transparent")
        toolbar.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            toolbar, text="Aperçu WYSIWYG",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        # Sélecteur de grille
        ctk.CTkLabel(
            toolbar, text="  Grille :",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY,
        ).pack(side="left", padx=(12, 2))
        self._grid_var = ctk.StringVar(value="5")
        for step in GRID_STEPS:
            ctk.CTkRadioButton(
                toolbar, text=f"{step}mm", variable=self._grid_var, value=str(step),
                font=ctk.CTkFont(size=10), text_color=theme.TEXT_PRIMARY,
                fg_color=theme.ACCENT_TURQUOISE,
                command=self._on_grid_change,
            ).pack(side="left", padx=2)

        # Coordonnées temps réel
        self._coords_label = ctk.CTkLabel(
            toolbar, text="",
            font=ctk.CTkFont(size=10, family="Consolas"),
            text_color=theme.TEXT_SECONDARY,
        )
        self._coords_label.pack(side="right")

        # Canvas
        canvas_frame = ctk.CTkFrame(
            center, fg_color=theme.BG_INPUT, corner_radius=12,
        )
        canvas_frame.pack(fill="both", expand=True, padx=16, pady=(4, 16))

        self._canvas = ctk.CTkCanvas(
            canvas_frame,
            bg="#f5f5f5",
            highlightthickness=0,
        )
        self._canvas.pack(fill="both", expand=True, padx=10, pady=10)

        self._canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self._canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_canvas_release)

    # ── Right panel : contrôles éléments ────────────────────────────

    def _build_right(self, parent: ctk.CTkFrame) -> None:
        right = ctk.CTkScrollableFrame(
            parent, fg_color=theme.BG_CARD, corner_radius=16,
            scrollbar_button_color=theme.BORDER,
        )
        right.grid(row=0, column=2, sticky="nsew")
        pad = 16

        # ── Format ────────────────────────────────────────────────
        ctk.CTkLabel(
            right, text="Format",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=pad, pady=(14, 4))

        fmt_row = ctk.CTkFrame(right, fg_color="transparent")
        fmt_row.pack(anchor="w", padx=pad, pady=(0, 2))
        self._fmt_var = ctk.StringVar(value="50x30")
        for val, lbl in [("50x30", "50×30 mm"), ("50x80", "50×80 mm")]:
            ctk.CTkRadioButton(
                fmt_row, text=lbl, variable=self._fmt_var, value=val,
                font=ctk.CTkFont(size=12), text_color=theme.TEXT_PRIMARY,
                fg_color=theme.ACCENT_TURQUOISE,
                command=self._on_format_change,
            ).pack(anchor="w", padx=(0, 4), pady=2)

        # Orientation toggle
        orient_row = ctk.CTkFrame(right, fg_color="transparent")
        orient_row.pack(anchor="w", padx=pad, pady=(0, 8))
        self._portrait_var = ctk.BooleanVar(value=False)
        self._portrait_cb = ctk.CTkCheckBox(
            orient_row, text="Mode portrait ⟳",
            variable=self._portrait_var,
            font=ctk.CTkFont(size=11), text_color=theme.TEXT_PRIMARY,
            fg_color=theme.ACCENT_TURQUOISE,
            command=self._on_orientation_toggle,
        )
        self._portrait_cb.pack(side="left")
        self._orient_label = ctk.CTkLabel(
            orient_row, text="",
            font=ctk.CTkFont(size=10),
            text_color=theme.TEXT_SECONDARY,
        )
        self._orient_label.pack(side="left", padx=(8, 0))

        ctk.CTkFrame(right, height=1, fg_color=theme.BORDER).pack(
            fill="x", padx=pad, pady=(0, 6))

        # ── Champs ─────────────────────────────────────────────────
        ctk.CTkLabel(
            right, text="Champs",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=pad, pady=(6, 4))

        self._fields_container = ctk.CTkFrame(right, fg_color="transparent")
        self._fields_container.pack(fill="x", padx=pad, pady=(0, 6))
        self._rebuild_fields()

        ctk.CTkFrame(right, height=1, fg_color=theme.BORDER).pack(
            fill="x", padx=pad, pady=(0, 6))

        # ── Propriétés élément sélectionné ─────────────────────────
        ctk.CTkLabel(
            right, text="Propriétés",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=pad, pady=(6, 4))

        self._props_frame = ctk.CTkFrame(right, fg_color="transparent")
        self._props_frame.pack(fill="x", padx=pad, pady=(0, 10))

        # Police size (slider avec mise à jour immédiate)
        size_row = ctk.CTkFrame(self._props_frame, fg_color="transparent")
        size_row.pack(fill="x", pady=3)
        ctk.CTkLabel(size_row, text="Taille police",
                      text_color=theme.TEXT_PRIMARY,
                      font=ctk.CTkFont(size=11), width=90, anchor="w").pack(side="left")
        self._font_size_var = ctk.IntVar(value=12)
        self._font_size_slider = ctk.CTkSlider(
            size_row, from_=4, to=64, number_of_steps=60,
            variable=self._font_size_var,
            command=self._on_font_size_slider,
            width=80, height=16,
            fg_color=theme.BG_INPUT,
            progress_color=theme.ACCENT_TURQUOISE,
            button_color=theme.ACCENT_TURQUOISE,
        )
        self._font_size_slider.pack(side="left", padx=(0, 4))
        self._font_size_label = ctk.CTkLabel(
            size_row, text="12",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.ACCENT_TURQUOISE, width=28,
        )
        self._font_size_label.pack(side="left")

        # Gras
        self._bold_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self._props_frame, text="Gras",
            variable=self._bold_var,
            font=ctk.CTkFont(size=11), text_color=theme.TEXT_PRIMARY,
            fg_color=theme.ACCENT_TURQUOISE,
            command=self._apply_bold,
        ).pack(anchor="w", pady=3)

        # Alignement
        align_row = ctk.CTkFrame(self._props_frame, fg_color="transparent")
        align_row.pack(fill="x", pady=3)
        ctk.CTkLabel(align_row, text="Alignement",
                      text_color=theme.TEXT_PRIMARY,
                      font=ctk.CTkFont(size=11), width=90, anchor="w").pack(side="left")
        self._align_var = ctk.StringVar(value="left")
        for val, lbl in [("left", "◁"), ("center", "↔"), ("right", "▷")]:
            ctk.CTkRadioButton(
                align_row, text=lbl, variable=self._align_var, value=val,
                font=ctk.CTkFont(size=14), text_color=theme.TEXT_PRIMARY,
                fg_color=theme.ACCENT_TURQUOISE,
                command=self._apply_align,
            ).pack(side="left", padx=(0, 6))

        # Position X / Y
        pos_row = ctk.CTkFrame(self._props_frame, fg_color="transparent")
        pos_row.pack(fill="x", pady=3)
        ctk.CTkLabel(pos_row, text="Position X",
                      text_color=theme.TEXT_PRIMARY,
                      font=ctk.CTkFont(size=11), width=90, anchor="w").pack(side="left")
        self._pos_x_var = ctk.StringVar(value="0")
        ctk.CTkEntry(
            pos_row, textvariable=self._pos_x_var,
            width=60, height=28, corner_radius=6,
            fg_color=theme.BG_INPUT, border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        pos_row2 = ctk.CTkFrame(self._props_frame, fg_color="transparent")
        pos_row2.pack(fill="x", pady=3)
        ctk.CTkLabel(pos_row2, text="Position Y",
                      text_color=theme.TEXT_PRIMARY,
                      font=ctk.CTkFont(size=11), width=90, anchor="w").pack(side="left")
        self._pos_y_var = ctk.StringVar(value="0")
        ctk.CTkEntry(
            pos_row2, textvariable=self._pos_y_var,
            width=60, height=28, corner_radius=6,
            fg_color=theme.BG_INPUT, border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkButton(
            pos_row2, text="Appliquer", font=ctk.CTkFont(size=10),
            height=28, corner_radius=6,
            fg_color=theme.BG_CARD, text_color=theme.ACCENT_TURQUOISE,
            hover_color=theme.BG_CARD_HOVER,
            command=self._apply_position,
            width=60,
        ).pack(side="left", padx=(6, 0))

        # Éléments visibles
        visibility_frame = ctk.CTkFrame(right, fg_color="transparent")
        visibility_frame.pack(fill="x", padx=pad, pady=(6, 0))

        ctk.CTkLabel(
            visibility_frame, text="Éléments de l'étiquette",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(0, 4))

        self._element_list = ctk.CTkFrame(visibility_frame, fg_color="transparent")
        self._element_list.pack(fill="x")

        ctk.CTkFrame(right, height=1, fg_color=theme.BORDER).pack(
            fill="x", padx=pad, pady=(10, 6))

        # ── Modèles ────────────────────────────────────────────────
        ctk.CTkLabel(
            right, text="Modèles",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=pad, pady=(6, 4))

        t_row = ctk.CTkFrame(right, fg_color="transparent")
        t_row.pack(fill="x", padx=pad, pady=(0, 6))
        self._tmpl_combo = ctk.CTkOptionMenu(
            t_row, values=[],
            font=ctk.CTkFont(size=11),
            fg_color=theme.BG_INPUT, button_color=theme.ACCENT_TURQUOISE,
            dropdown_fg_color=theme.BG_CARD,
            text_color=theme.TEXT_PRIMARY,
            command=self._on_load_template,
        )
        self._tmpl_combo.pack(side="left", padx=(0, 4), fill="x", expand=True)
        ctk.CTkButton(
            t_row, text="💾", font=ctk.CTkFont(size=13),
            width=32, height=28, corner_radius=6,
            fg_color=theme.BG_CARD, text_color=theme.ACCENT_TURQUOISE,
            hover_color=theme.BG_CARD_HOVER,
            command=self._on_save_template,
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            t_row, text="🗑", font=ctk.CTkFont(size=13),
            width=32, height=28, corner_radius=6,
            fg_color=theme.BG_CARD, text_color=theme.DANGER,
            hover_color=theme.BG_CARD_HOVER,
            command=self._on_delete_template,
        ).pack(side="left", padx=2)

        ctk.CTkFrame(right, height=1, fg_color=theme.BORDER).pack(
            fill="x", padx=pad, pady=(6, 6))

        # ── Calibration ────────────────────────────────────────────
        ctk.CTkLabel(
            right, text="Calibration",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=pad, pady=(6, 2))

        cal_row = ctk.CTkFrame(right, fg_color="transparent")
        cal_row.pack(fill="x", padx=pad, pady=(0, 2))
        ctk.CTkLabel(cal_row, text="Correction X", text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(size=11), width=80, anchor="w").pack(side="left")
        self._calib_x_var = ctk.StringVar(value=str(self._calib_x))
        ctk.CTkEntry(cal_row, textvariable=self._calib_x_var,
                     width=60, height=28, corner_radius=6,
                     fg_color=theme.BG_INPUT, border_color=theme.BORDER,
                     text_color=theme.TEXT_PRIMARY).pack(side="left", padx=(0, 2))
        ctk.CTkLabel(cal_row, text="mm", text_color=theme.TEXT_SECONDARY,
                     font=ctk.CTkFont(size=10)).pack(side="left")

        cal_row2 = ctk.CTkFrame(right, fg_color="transparent")
        cal_row2.pack(fill="x", padx=pad, pady=(0, 2))
        ctk.CTkLabel(cal_row2, text="Correction Y", text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(size=11), width=80, anchor="w").pack(side="left")
        self._calib_y_var = ctk.StringVar(value=str(self._calib_y))
        ctk.CTkEntry(cal_row2, textvariable=self._calib_y_var,
                     width=60, height=28, corner_radius=6,
                     fg_color=theme.BG_INPUT, border_color=theme.BORDER,
                     text_color=theme.TEXT_PRIMARY).pack(side="left", padx=(0, 2))
        ctk.CTkLabel(cal_row2, text="mm", text_color=theme.TEXT_SECONDARY,
                     font=ctk.CTkFont(size=10)).pack(side="left")

        cal_btn_row = ctk.CTkFrame(right, fg_color="transparent")
        cal_btn_row.pack(fill="x", padx=pad, pady=(4, 0))
        ctk.CTkButton(
            cal_btn_row, text="Appliquer calibration",
            font=ctk.CTkFont(size=10), height=26, corner_radius=6,
            fg_color=theme.BG_CARD, text_color=theme.ACCENT_TURQUOISE,
            hover_color=theme.BG_CARD_HOVER,
            command=self._on_calib_apply,
        ).pack(side="left", padx=(0, 4), expand=True, fill="x")

        # Mode aperçu réel
        self._real_preview_var = ctk.BooleanVar(value=self._real_preview)
        ctk.CTkCheckBox(
            cal_btn_row, text="Réel",
            variable=self._real_preview_var,
            font=ctk.CTkFont(size=10), text_color=theme.TEXT_PRIMARY,
            fg_color=theme.ACCENT_TURQUOISE,
            command=self._on_real_preview_toggle,
        ).pack(side="right")

        # ── Export ─────────────────────────────────────────────────
        self._export_btn = ctk.CTkButton(
            right,
            text="📥  Exporter CSV NIIMBOT",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40, corner_radius=10,
            fg_color=theme.ACCENT_TURQUOISE, text_color="#ffffff",
            hover_color=theme.BG_CARD_HOVER,
            command=self._on_export,
        )
        self._export_btn.pack(fill="x", padx=pad, pady=(0, 4))

        self._perf_label = ctk.CTkLabel(
            right, text="",
            font=ctk.CTkFont(size=10),
            text_color=theme.TEXT_SECONDARY,
        )
        self._perf_label.pack(anchor="w", padx=pad, pady=(0, 16))

    # ── Data loading ───────────────────────────────────────────────

    def _load_bracelets(self) -> None:
        self._all_bracelets = sorted(
            self.db.bracelets,
            key=lambda b: str(b.get("nom", "")).lower(),
        ) if self.db else []
        self._fields = dict(get_default_fields(self._format))
        self._templates = load_templates(self.db)
        self._refresh_templates()
        self._apply_filter()

        # Charger calibration
        cal = (self.db.settings.get("niimbot_calibration", {}) if self.db else {})
        self._calib_x = float(cal.get("x", CALIBRATION_X_MM))
        self._calib_y = float(cal.get("y", CALIBRATION_Y_MM))
        self._update_orient_label()

    def _refresh_templates(self) -> None:
        names = list(self._templates.keys())
        self._tmpl_combo.configure(values=names)
        if names:
            self._tmpl_combo.set(names[0])

    # ── List rendering ─────────────────────────────────────────────

    def _schedule_filter(self) -> None:
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(self._search_debounce_ms, self._apply_filter)

    def _apply_filter(self) -> None:
        q = self._search_var.get().strip().lower()
        candidates = self._all_bracelets
        if q:
            candidates = [
                b for b in candidates
                if q in b.get("nom", "").lower() or q in b.get("reference", "").lower()
            ]
        self._render_list(candidates)

    def _render_list(self, bracelets: list[dict]) -> None:
        for w in self._list_scroll.winfo_children():
            w.destroy()
        self._checkboxes.clear()

        for b in bracelets:
            bid = str(b.get("id", ""))
            ref = b.get("reference", "—")
            nom = b.get("nom", "Sans nom")
            var = ctk.BooleanVar(value=bid in self._selected_ids)

            cb = ctk.CTkCheckBox(
                self._list_scroll,
                text=f"  {ref}  —  {nom}",
                variable=var,
                font=ctk.CTkFont(size=11),
                text_color=theme.TEXT_PRIMARY,
                fg_color=theme.ACCENT_TURQUOISE,
                hover_color=theme.BG_CARD,
                corner_radius=6,
                command=lambda rid=bid, v=var: self._on_checkbox_toggle(rid, v),
            )
            cb.pack(fill="x", padx=6, pady=2)
            self._checkboxes[bid] = cb
            self._checkbox_vars[bid] = var

            if bid in self._selected_ids:
                cb.select()

        if not bracelets:
            ctk.CTkLabel(
                self._list_scroll,
                text="Aucun bracelet",
                text_color=theme.TEXT_SECONDARY,
            ).pack(pady=20)

        self._update_count()

    def _on_checkbox_toggle(self, bid: str, var: ctk.BooleanVar) -> None:
        if var.get():
            self._selected_ids.add(bid)
        else:
            self._selected_ids.discard(bid)
        self._update_count()
        self._redraw()

    def _select_all(self) -> None:
        self._selected_ids = {str(b.get("id", "")) for b in self._all_bracelets}
        for bid, var in self._checkbox_vars.items():
            if bid in self._selected_ids:
                var.set(True)
        self._update_count()
        self._redraw()

    def _deselect_all(self) -> None:
        self._selected_ids.clear()
        for var in self._checkbox_vars.values():
            var.set(False)
        self._update_count()
        self._redraw()

    def _update_count(self) -> None:
        n = len(self._selected_ids)
        self._count_label.configure(text=f"{n} sélectionné{'s' if n != 1 else ''}")

    # ── Format / Fields ────────────────────────────────────────────

    def _on_format_change(self) -> None:
        new_fmt = self._fmt_var.get()
        if new_fmt == self._format:
            return
        self._format = new_fmt
        self._portrait = False
        self._portrait_var.set(False)
        self._update_orient_label()
        self._fields = get_default_fields(new_fmt)
        self._element_props = {}
        self._selected_elem = None
        self._rebuild_fields()
        self._redraw()

    def _on_orientation_toggle(self) -> None:
        self._portrait = self._portrait_var.get()
        self._update_orient_label()
        self._redraw()

    def _update_orient_label(self) -> None:
        lw, lh = LABEL_SIZES[self._format]
        if self._portrait:
            lw, lh = lh, lw
        orient_text = "Paysage" if lw >= lh else "Portrait"
        self._orient_label.configure(text=f"{lw}×{lh}mm ({orient_text})")

    def _rebuild_fields(self) -> None:
        for w in self._fields_container.winfo_children():
            w.destroy()

        field_labels = {
            "nom": "Nom", "prix": "Prix", "reference": "Réf.",
            "pierres": "Pierres", "composition": "Composition",
            "chakras": "Chakras", "vertus": "Vertus",
            "qr_code": "QR", "photo": "Photo",
        }

        row = ctk.CTkFrame(self._fields_container, fg_color="transparent")
        row.pack(fill="x")
        col = 0
        for fld in get_fields_for_format(self._format):
            if col == 3:
                row = ctk.CTkFrame(self._fields_container, fg_color="transparent")
                row.pack(fill="x", pady=(2, 0))
                col = 0
            var = ctk.BooleanVar(value=self._fields.get(fld, False))
            cb = ctk.CTkCheckBox(
                row, text=field_labels.get(fld, fld),
                variable=var, font=ctk.CTkFont(size=11),
                text_color=theme.TEXT_PRIMARY,
                fg_color=theme.ACCENT_TURQUOISE,
                hover_color=theme.BG_CARD, corner_radius=6,
                command=lambda f=fld, v=var: self._on_field_change(f, v),
            )
            cb.pack(side="left", padx=(0, 8))
            if fld == "nom":
                cb.configure(state="disabled")
            col += 1

    def _on_field_change(self, field: str, var: ctk.BooleanVar) -> None:
        self._fields[field] = var.get()
        self._rebuild_element_props()
        self._redraw()

    # ── Propriétés des éléments ─────────────────────────────────────

    def _build_element_props(self, bracelet: dict | None) -> None:
        """Construit les propriétés par défaut pour chaque champ actif."""
        self._element_props = {}
        if not bracelet:
            return

        label_w, label_h = LABEL_SIZES[self._format]
        margin = 0
        active_fields = [f for f in get_fields_for_format(self._format) if self._fields.get(f)]

        if self._format == "50x30":
            self._build_layout_50x30(active_fields, label_w, label_h, margin)
        else:
            self._build_layout_50x80(active_fields, label_w, label_h, margin)

    def _build_layout_50x30(self, active_fields: list[str], _lw: int, _lh: int, margin: int) -> None:
        """Disposition 2 colonnes pour le format paysage 50×30."""
        mid_x = 26  # séparation des colonnes
        y_left = margin
        y_right = margin
        for fld in active_fields:
            if fld == "nom":
                self._element_props[fld] = {"x": margin, "y": y_left, "size": 12, "bold": True, "align": "left", "visible": True}
                y_left += 5.5
            elif fld == "prix":
                self._element_props[fld] = {"x": margin, "y": y_left, "size": 11, "bold": True, "align": "left", "visible": True}
                y_left += 5
            elif fld == "reference":
                self._element_props[fld] = {"x": margin, "y": y_left, "size": 7, "bold": False, "align": "left", "visible": True}
                y_left += 3.5
            elif fld == "pierres":
                self._element_props[fld] = {"x": margin, "y": y_left, "size": 7, "bold": False, "align": "left", "visible": True}
                y_left += 3.5
            elif fld == "composition":
                self._element_props[fld] = {"x": mid_x, "y": y_right, "size": 7, "bold": False, "align": "left", "visible": True}
                y_right += 12
            elif fld == "chakras":
                self._element_props[fld] = {"x": mid_x, "y": y_right, "size": 7, "bold": False, "align": "left", "visible": True}
                y_right += 3.5
            elif fld == "vertus":
                self._element_props[fld] = {"x": mid_x, "y": y_right, "size": 7, "bold": False, "align": "left", "visible": True}
                y_right += 3.5
            elif fld == "qr_code":
                self._element_props[fld] = {"x": 37, "y": 17, "size": 10, "bold": False, "align": "left", "visible": True}
            elif fld == "photo":
                self._element_props[fld] = {"x": mid_x, "y": margin, "size": 10, "bold": False, "align": "left", "visible": True}

    def _build_layout_50x80(self, active_fields: list[str], label_w: int, label_h: int, margin: int) -> None:
        """Disposition 1 colonne pour le format portrait 50×80."""
        y = margin
        for fld in active_fields:
            if fld == "nom":
                self._element_props[fld] = {"x": margin, "y": y, "size": 14, "bold": True, "align": "left", "visible": True}
                y += 6
            elif fld == "prix":
                self._element_props[fld] = {"x": margin, "y": y, "size": 13, "bold": True, "align": "left", "visible": True}
                y += 5.5
            elif fld in ("reference",):
                self._element_props[fld] = {"x": margin, "y": y, "size": 8, "bold": False, "align": "left", "visible": True}
                y += 4
            elif fld in ("pierres", "composition"):
                self._element_props[fld] = {"x": margin, "y": y, "size": 9, "bold": False, "align": "left", "visible": True}
                y += 5
            elif fld in ("chakras", "vertus"):
                self._element_props[fld] = {"x": margin, "y": y, "size": 8, "bold": False, "align": "left", "visible": True}
                y += 4.5
            elif fld == "qr_code":
                self._element_props[fld] = {"x": label_w - 14, "y": label_h - 14, "size": 12, "bold": False, "align": "left", "visible": True}
            elif fld == "photo":
                self._element_props[fld] = {"x": label_w - 14, "y": margin, "size": 12, "bold": False, "align": "left", "visible": True}

    def _rebuild_element_props(self) -> None:
        """Recrée les props si un nouveau bracelet est sélectionné."""
        b = self._first_selected()
        if b:
            self._build_element_props(b)
            self._refresh_element_list()
            self._refresh_props_ui()

    def _first_selected(self) -> dict | None:
        for b in self._all_bracelets:
            if str(b.get("id", "")) in self._selected_ids:
                return b
        return None

    def _refresh_element_list(self) -> None:
        for w in self._element_list.winfo_children():
            w.destroy()
        field_labels = {
            "nom": "Nom", "prix": "Prix", "reference": "Réf.",
            "pierres": "Pierres", "composition": "Composition",
            "chakras": "Chakras", "vertus": "Vertus",
            "qr_code": "QR Code", "photo": "Photo",
        }
        for key, props in self._element_props.items():
            is_sel = key == self._selected_elem
            btn = ctk.CTkButton(
                self._element_list,
                text=f"  {field_labels.get(key, key)}  {'✓' if props.get('visible', True) else '✗'}",
                anchor="w", height=26, corner_radius=6,
                fg_color=theme.ACCENT_TURQUOISE if is_sel else "transparent",
                text_color="#ffffff" if is_sel else theme.TEXT_PRIMARY,
                hover_color=theme.BG_CARD_HOVER,
                font=ctk.CTkFont(size=11),
                command=lambda k=key: self._select_element(k),
            )
            btn.pack(fill="x", pady=1)

    def _select_element(self, key: str) -> None:
        self._selected_elem = key
        self._refresh_props_ui()
        self._refresh_element_list()
        self._redraw()

    def _refresh_props_ui(self) -> None:
        key = self._selected_elem
        if not key or key not in self._element_props:
            self._font_size_var.set(12)
            self._font_size_label.configure(text="12")
            self._bold_var.set(False)
            self._align_var.set("left")
            self._pos_x_var.set("")
            self._pos_y_var.set("")
            return
        p = self._element_props[key]
        sz = p.get("size", 12)
        self._font_size_var.set(sz)
        self._font_size_label.configure(text=str(sz))
        self._bold_var.set(p.get("bold", False))
        self._align_var.set(p.get("align", "left"))
        self._pos_x_var.set(str(p.get("x", 0)))
        self._pos_y_var.set(str(p.get("y", 0)))

    # ── Apply property changes ──────────────────────────────────────

    def _on_font_size_slider(self, val: float) -> None:
        sz = int(round(val))
        self._font_size_label.configure(text=str(sz))
        key = self._selected_elem
        if key and key in self._element_props:
            self._element_props[key]["size"] = sz
            self._redraw()

    def _apply_bold(self) -> None:
        key = self._selected_elem
        if not key or key not in self._element_props:
            return
        self._element_props[key]["bold"] = self._bold_var.get()
        self._redraw()

    def _apply_align(self) -> None:
        key = self._selected_elem
        if not key or key not in self._element_props:
            return
        self._element_props[key]["align"] = self._align_var.get()
        self._redraw()

    def _apply_position(self) -> None:
        key = self._selected_elem
        if not key or key not in self._element_props:
            return
        try:
            self._element_props[key]["x"] = max(0, float(self._pos_x_var.get()))
            self._element_props[key]["y"] = max(0, float(self._pos_y_var.get()))
            self._redraw()
        except ValueError:
            pass

    # ── Canvas rendering WYSIWYG ─────────────────────────────────

    def _compute_layout(self) -> tuple[int, int]:
        cw = max(self._canvas.winfo_width(), 200)
        ch = max(self._canvas.winfo_height(), 200)
        lw_mm, lh_mm = LABEL_SIZES[self._format]

        # Swap dimensions en mode portrait
        if self._portrait:
            lw_mm, lh_mm = lh_mm, lw_mm

        avail_w = cw - RULER_SIZE - 20
        avail_h = ch - RULER_SIZE - 20

        self._mm_to_px = min(avail_w / lw_mm, avail_h / lh_mm)

        lw_px = lw_mm * self._mm_to_px
        lh_px = lh_mm * self._mm_to_px
        self._ox = RULER_SIZE + (avail_w - lw_px) / 2 + 10
        self._oy = RULER_SIZE + (avail_h - lh_px) / 2 + 10
        return lw_mm, lh_mm

    def _mm_to_canvas(self, x_mm: float, y_mm: float) -> tuple[float, float]:
        """Convertit des coordonnées mm (label) en coordonnées canvas, avec calibration."""
        return (self._ox + (x_mm + self._calib_x) * self._mm_to_px,
                self._oy + (y_mm + self._calib_y) * self._mm_to_px)

    def _canvas_to_mm(self, cx: float, cy: float) -> tuple[float, float]:
        """Convertit des coordonnées canvas en coordonnées mm (label), avec calibration."""
        return ((cx - self._ox) / self._mm_to_px - self._calib_x,
                (cy - self._oy) / self._mm_to_px - self._calib_y)

    def _draw_rulers(self, lw_mm: int, lh_mm: int) -> None:
        ox, oy = self._ox, self._oy
        s = self._mm_to_px

        # Règle horizontale (au-dessus du label)
        for mm in range(0, lw_mm + 1, 10):
            x = ox + mm * s
            self._canvas.create_line(x, oy - 8, x, oy, fill="#555555", width=1)
            self._canvas.create_text(
                x, oy - 12, text=str(mm), anchor="s",
                font=("Segoe UI", 8), fill="#555555",
            )
        for mm in range(0, lw_mm + 1, 5):
            if mm % 10 != 0:
                x = ox + mm * s
                self._canvas.create_line(x, oy - 4, x, oy, fill="#888888", width=1)
        for mm in range(0, lw_mm + 1):
            if mm % 5 != 0:
                x = ox + mm * s
                self._canvas.create_line(x, oy - 2, x, oy, fill="#aaaaaa", width=1)

        # Règle verticale (à gauche du label)
        for mm in range(0, lh_mm + 1, 10):
            y = oy + mm * s
            self._canvas.create_line(ox - 8, y, ox, y, fill="#555555", width=1)
            self._canvas.create_text(
                ox - 12, y, text=str(mm), anchor="e",
                font=("Segoe UI", 8), fill="#555555",
            )
        for mm in range(0, lh_mm + 1, 5):
            if mm % 10 != 0:
                y = oy + mm * s
                self._canvas.create_line(ox - 4, y, ox, y, fill="#888888", width=1)
        for mm in range(0, lh_mm + 1):
            if mm % 5 != 0:
                y = oy + mm * s
                self._canvas.create_line(ox - 2, y, ox, y, fill="#aaaaaa", width=1)

    def _draw_grid(self, lw_mm: int, lh_mm: int) -> None:
        ox, oy = self._ox, self._oy
        s = self._mm_to_px
        step = self._grid_step
        for mm in range(0, lw_mm + 1, step):
            x = ox + mm * s
            self._canvas.create_line(x, oy, x, oy + lh_mm * s,
                                    fill="#e8e8e8", width=1)
        for mm in range(0, lh_mm + 1, step):
            y = oy + mm * s
            self._canvas.create_line(ox, y, ox + lw_mm * s, y,
                                    fill="#e8e8e8", width=1)

    def _draw_printable_zone(self, lw_mm: int, lh_mm: int) -> None:
        ox, oy = self._ox, self._oy
        s = self._mm_to_px
        m = NIIMBOT_MARGIN_MM * s
        self._canvas.create_rectangle(
            ox + m, oy + m,
            ox + lw_mm * s - m,
            oy + lh_mm * s - m,
            outline="#4fc3f7", width=1, dash=(4, 4),
        )

    def _on_grid_change(self) -> None:
        try:
            self._grid_step = int(self._grid_var.get())
        except ValueError:
            self._grid_step = 5
        self._redraw()

    def _update_coords(self, key: str | None) -> None:
        if not key or key not in self._element_props:
            self._coords_label.configure(text="")
            return
        p = self._element_props[key]
        x = p.get("x", 0)
        y = p.get("y", 0)
        sz = p.get("size", 10)
        self._coords_label.configure(
            text=f"X={x:.1f}mm  Y={y:.1f}mm  police={sz}",
        )

    def _redraw(self) -> None:
        self._canvas.delete("all")
        b = self._first_selected()
        if not b:
            self._draw_empty_state()
            return

        # Calcul dynamique du layout
        lw_mm, lh_mm = self._compute_layout()
        lw_px = lw_mm * self._mm_to_px
        lh_px = lh_mm * self._mm_to_px
        ox, oy, s = self._ox, self._oy, self._mm_to_px

        # Règles (masquées en mode aperçu réel)
        if not self._real_preview:
            self._draw_rulers(lw_mm, lh_mm)

        # Fond du label
        self._canvas.create_rectangle(
            ox, oy, ox + lw_px, oy + lh_px,
            fill="#fefefe", outline="#888888", width=1,
        )

        # Zone imprimable NIIMBOT (masquée en mode aperçu réel)
        if not self._real_preview:
            self._draw_printable_zone(lw_mm, lh_mm)

        # Grille (masquée en mode aperçu réel)
        if not self._real_preview:
            self._draw_grid(lw_mm, lh_mm)

        # Initialiser les props si nécessaire
        if not self._element_props:
            self._build_element_props(b)
        if not self._element_props:
            return

        # Dessiner chaque champ
        for key, props in self._element_props.items():
            if not props.get("visible", True):
                continue
            is_selected = (key == self._selected_elem)
            x_mm = props.get("x", 0)
            y_mm = props.get("y", 0)
            font_size = props.get("size", 10)
            bold = props.get("bold", False)
            align = props.get("align", "left")

            cx = ox + x_mm * s
            cy = oy + y_mm * s

            disp_size = max(6, int(font_size * s * 0.4))

            text = self._get_field_text(b, key)
            if not text:
                continue

            anchor_map = {"left": "nw", "center": "n", "right": "ne"}
            anchor = anchor_map.get(align, "nw")
            if align == "center":
                cx = ox + lw_px / 2
            elif align == "right":
                cx = ox + lw_px - 2 * s

            font_spec = ("Segoe UI", disp_size, "bold" if bold else "normal")
            color = "#1a1a1a"

            self._canvas.create_text(
                cx, cy, anchor=anchor,
                text=text, font=font_spec, fill=color,
                tags=(f"elem_{key}",),
            )

            # Hitbox invisible
            bb = self._canvas.bbox(f"elem_{key}")
            if bb:
                hm = 5
                self._canvas.create_rectangle(
                    bb[0] - hm, bb[1] - hm,
                    bb[2] + hm, bb[3] + hm,
                    outline="", fill="", tags=(f"elem_{key}",),
                )

            # Bordure de sélection
            if is_selected:
                bb = self._canvas.bbox(f"elem_{key}")
                if bb:
                    ms = 3
                    self._canvas.create_rectangle(
                        bb[0] - ms, bb[1] - ms,
                        bb[2] + ms, bb[3] + ms,
                        outline=theme.ACCENT_TURQUOISE, width=2,
                        dash=(4, 2),
                    )

        # QR Code
        if self._fields.get("qr_code") and "qr_code" in self._element_props:
            p = self._element_props["qr_code"]
            qr_img = generate_qr_image(b, size=60)
            if qr_img:
                qr_size = int(12 * s)
                qr_x = ox + p.get("x", lw_mm - 14) * s
                qr_y = oy + p.get("y", lh_mm - 14) * s
                buf = io.BytesIO()
                qr_img.save(buf, format="PNG")
                buf.seek(0)
                pil_img = Image.open(buf)
                self._qr_ctk = ctk.CTkImage(pil_img, size=(qr_size, qr_size))
                self._canvas.create_image(
                    qr_x, qr_y, anchor="nw",
                    image=self._qr_ctk,
                )

        # Photo
        if self._fields.get("photo") and "photo" in self._element_props:
            p = self._element_props["photo"]
            photo_img = load_ctk_image(self.db, b, size=(40, 40), use_thumb=True)
            if photo_img:
                ph_size = int(12 * s)
                ph_x = ox + p.get("x", lw_mm - 14) * s
                ph_y = oy + p.get("y", 2) * s
                self._canvas.create_image(
                    ph_x, ph_y, anchor="nw",
                    image=photo_img,
                )

        # Coordonnées temps réel
        self._update_coords(self._selected_elem)

    def _get_field_text(self, b: dict, field: str) -> str:
        if field == "nom":
            return b.get("nom", "") or "Bracelet"
        if field == "prix":
            pv = float(b.get("prix_vente", 0) or 0)
            return f"{pv:.2f} €".replace(".", ",")
        if field == "reference":
            return b.get("reference", "") or ""
        if field == "pierres":
            pierres = [
                c.get("composant", "")
                for c in b.get("composition", [])
                if c.get("categorie", "") == "Pierre"
            ]
            return " • ".join(pierres[:3]) if pierres else ""
        if field == "composition":
            parts = [
                f"{c.get('composant', '?')} x{c.get('quantite', 1)}"
                for c in b.get("composition", [])
            ]
            return "\n".join(parts[:5]) if parts else ""
        if field == "chakras":
            try:
                m = self.db.calculate_bracelet_metrics(b)
                return " / ".join(m.get("chakras", [])[:3])
            except Exception:
                return ""
        if field == "vertus":
            try:
                m = self.db.calculate_bracelet_metrics(b)
                return ", ".join(m.get("vertus", [])[:3])
            except Exception:
                return ""
        if field in ("qr_code", "photo"):
            return " "
        return ""

    def _draw_empty_state(self) -> None:
        cw = max(self._canvas.winfo_width(), 200)
        ch = max(self._canvas.winfo_height(), 200)
        self._canvas.create_text(
            cw / 2, ch / 2,
            text="Sélectionnez un bracelet",
            font=("Segoe UI", 14), fill="#999999",
        )
        self._coords_label.configure(text="")

    # ── Canvas interaction ──────────────────────────────────────────

    def _find_element_at(self, cx: float, cy: float) -> str | None:
        items = self._canvas.find_closest(cx, cy)
        if not items:
            return None
        tags = self._canvas.gettags(items[0])
        for tag in tags:
            if tag.startswith("elem_"):
                return tag[5:]
        return None

    def _on_canvas_press(self, event) -> None:
        key = self._find_element_at(event.x, event.y)
        if key:
            self._select_element(key)
            self._drag_key = key
            self._drag_start = (event.x, event.y)
            p = self._element_props.get(key, {})
            self._drag_orig = (p.get("x", 0), p.get("y", 0))

    def _on_canvas_drag(self, event) -> None:
        if not self._drag_key or self._drag_key not in self._element_props:
            return
        s = self._mm_to_px
        if s <= 0:
            return

        dx = (event.x - self._drag_start[0]) / s
        dy = (event.y - self._drag_start[1]) / s
        lw_mm, lh_mm = LABEL_SIZES[self._format]
        new_x = max(0, round(self._drag_orig[0] + dx, 1))
        new_y = max(0, round(self._drag_orig[1] + dy, 1))
        self._element_props[self._drag_key]["x"] = min(new_x, lw_mm - 2)
        self._element_props[self._drag_key]["y"] = min(new_y, lh_mm - 1)
        self._refresh_props_ui()
        self._update_coords(self._drag_key)
        self._redraw()

    def _on_canvas_release(self, event) -> None:
        self._drag_key = None

    # ── Templates ──────────────────────────────────────────────────

    def _on_save_template(self) -> None:
        from tkinter import simpledialog
        name = simpledialog.askstring("Enregistrer", "Nom du modèle :")
        if not name or not name.strip():
            return
        name = name.strip()
        config = {
            "label": name,
            "format": self._format,
            "fields": dict(self._fields),
            "element_props": {k: dict(v) for k, v in self._element_props.items()},
        }
        save_template(self.db, name, config)
        self._templates = load_templates(self.db)
        self._refresh_templates()
        self._tmpl_combo.set(name)

    def _on_load_template(self, name: str) -> None:
        tmpl = self._templates.get(name)
        if not tmpl:
            return
        self._format = tmpl.get("format", "50x30")
        self._portrait = False
        self._portrait_var.set(False)
        self._update_orient_label()
        self._fields = dict(tmpl.get("fields", {}))
        saved_props = tmpl.get("element_props")
        if saved_props:
            self._element_props = {k: dict(v) for k, v in saved_props.items()}
        else:
            self._element_props = {}
        self._fmt_var.set(self._format)
        self._rebuild_fields()
        if not saved_props:
            self._rebuild_element_props()
        # Auto-sélectionner le premier bracelet dispo
        if not self._selected_ids and self._all_bracelets:
            first = str(self._all_bracelets[0].get("id", ""))
            self._selected_ids = {first}
            self._apply_filter()
        # Auto-sélectionner le premier élément du template
        if self._element_props:
            first_key = next(iter(self._element_props))
            self._selected_elem = first_key
        else:
            self._selected_elem = None
        self._refresh_element_list()
        self._refresh_props_ui()
        self._update_coords(self._selected_elem)
        self._redraw()

    def _on_delete_template(self) -> None:
        name = self._tmpl_combo.get()
        if name in ("Minimal", "Boutique", "Lithothérapie", "Complet",
                     "Calibration 50x30", "Calibration 50x80"):
            mb.showinfo("Modèle", "Impossible de supprimer un modèle intégré.")
            return
        if not mb.askyesno("Supprimer", f"Supprimer le modèle « {name} » ?"):
            return
        delete_template(self.db, name)
        self._templates = load_templates(self.db)
        self._refresh_templates()

    # ── Calibration ─────────────────────────────────────────────────

    def _on_calib_apply(self) -> None:
        try:
            self._calib_x = float(self._calib_x_var.get())
            self._calib_y = float(self._calib_y_var.get())
            if self.db:
                cal = dict(self.db.settings.get("niimbot_calibration", {}))
                cal["x"] = self._calib_x
                cal["y"] = self._calib_y
                self.db.settings["niimbot_calibration"] = cal
                self.db.save_settings()
            self._redraw()
        except ValueError:
            pass

    def _on_real_preview_toggle(self) -> None:
        self._real_preview = self._real_preview_var.get()
        self._redraw()

    # ── Export ─────────────────────────────────────────────────────

    def _on_export(self) -> None:
        t0 = time.perf_counter()
        selected = [b for b in self._all_bracelets if str(b.get("id", "")) in self._selected_ids]
        if not selected:
            mb.showwarning("Export", "Sélectionnez au moins un bracelet.")
            return

        csv_data = generate_csv(selected, self._fields, self._format)

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV NIIMBOT", "*.csv"), ("Tous", "*.*")],
            title="Exporter CSV pour NIIMBOT",
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write(csv_data)
            ms = (time.perf_counter() - t0) * 1000
            self._perf_label.configure(
                text=f"Exporté : {len(selected)} bracelet(s) en {ms:.1f} ms",
                text_color=theme.SUCCESS,
            )
            mb.showinfo("Export", f"✅ {len(selected)} bracelet(s) exporté(s).")
        except Exception as e:
            mb.showerror("Export", f"Erreur : {e}")

    # ── Refresh ────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._load_bracelets()
