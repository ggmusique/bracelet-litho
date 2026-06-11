"""zoom_editor.py
Fenêtre d'édition visuelle du positionnement des éléments sur l'étiquette Action 70×37.

L'éditeur affiche l'étiquette à 10 px/mm.
Chaque élément est déplaçable à la souris.
Les tailles de polices sont réglables par spinbox.
"""
from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

import layout_profiles

# ── Constantes de rendu ───────────────────────────────────────────────
SCALE_PX_MM: float = 10.0          # pixels par millimètre
CELL_W_MM = layout_profiles.CELL_W_MM
CELL_H_MM = layout_profiles.CELL_H_MM

# Taille de la zone label en pixels
_LBL_W_PX = int(CELL_W_MM * SCALE_PX_MM)
_LBL_H_PX = int(CELL_H_MM * SCALE_PX_MM)

# Marges internes du canvas autour du label
_MARGIN = 12
CANVAS_W = _LBL_W_PX + 2 * _MARGIN
CANVAS_H = _LBL_H_PX + 2 * _MARGIN

# Origine (top-left) du label dans le canvas
_OX = _MARGIN
_OY = _MARGIN


def _pdf_pt_to_tk(pdf_pt: float) -> int:
    """Convertit une taille de police PDF (points) en points Tkinter affichés à 10 px/mm."""
    # 1 pt = 1/72 inch = 25.4/72 mm ≈ 0.353 mm → 3.528 px @ 10 px/mm
    # Tkinter points @ 96 dpi : 1 pt_tk → 96/72 px = 1.333 px
    # Pour afficher 3.528 px/pt_pdf → 3.528 / 1.333 ≈ 2.646 pt_tk par pt_pdf
    return max(6, round(pdf_pt * SCALE_PX_MM * 25.4 / 96))


def _elem_keys_for(model: str) -> list[tuple[str, str]]:
    """Retourne [(key, libelle_affichage), ...] pour un modèle."""
    common_prices = [
        ("prix",          "PV (prix de vente)"),
        ("prix_revient",  "PR (prix de revient)"),
        ("marge",         "Marge"),
    ]
    if model == "bracelet":
        return [
            ("nom",        "Nom"),
            ("comp_label", "Titre composition"),
            ("comp_items", "Items composition"),
        ] + common_prices
    else:
        return [
            ("nom",           "Nom"),
            ("vertus_label",  "Titre Vertus"),
            ("vertus_items",  "Items Vertus"),
            ("chakras_label", "Titre Chakras"),
            ("chakras_items", "Items Chakras"),
        ] + common_prices


# ── Classe principale ─────────────────────────────────────────────────

class LabelZoomEditor(tk.Toplevel):
    """Éditeur visuel pour la mise en page de l'étiquette Action."""

    def __init__(
        self,
        parent: tk.Widget,
        model: str,
        bracelet: dict[str, Any],
        db,
        on_save=None,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.bracelet = bracelet
        self.db = db
        self.on_save = on_save

        # Prépare les données du label
        self._sample = self._build_sample()

        # Charge et copie le profil courant
        self._working: dict[str, Any] = copy.deepcopy(
            layout_profiles.load_layout(model, db.base_dir)
        )

        # État du drag
        self._drag_key: str | None = None
        self._drag_start_x: float = 0.0
        self._drag_start_y: float = 0.0
        self._drag_orig_x: float = 0.0
        self._drag_orig_y: float = 0.0

        title = (
            "Mise en page — Bracelet 70×37"
            if model == "bracelet"
            else "Mise en page — Vertus / Chakras 70×37"
        )
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self._build_ui()
        self._redraw()

    # ── Construction de l'interface ───────────────────────────────────

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=8)
        outer.pack(fill="both", expand=True)

        # Panneau gauche : canvas
        cv_frame = ttk.LabelFrame(outer, text="Aperçu  (glisser les éléments)")
        cv_frame.pack(side="left", fill="both", expand=True)

        self.cv = tk.Canvas(
            cv_frame,
            width=CANVAS_W, height=CANVAS_H,
            bg="#f0f0f0", cursor="fleur",
            highlightthickness=1, highlightbackground="#888888",
        )
        self.cv.pack(padx=6, pady=6)
        self.cv.bind("<ButtonPress-1>",   self._on_press)
        self.cv.bind("<B1-Motion>",       self._on_drag)
        self.cv.bind("<ButtonRelease-1>", self._on_release)

        # Panneau droit : contrôles
        side = ttk.Frame(outer)
        side.pack(side="left", fill="y", padx=(12, 0))

        ttk.Label(side, text="Taille des polices", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        # Spinboxes de taille de police
        self._size_vars: dict[str, tk.IntVar] = {}
        for key, label in _elem_keys_for(self.model):
            row = ttk.Frame(side)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, width=20, anchor="w").pack(side="left")
            cfg = self._working.get(key, {})
            initial = cfg.get("size", 8) if isinstance(cfg, dict) else 8
            var = tk.IntVar(value=int(initial))
            self._size_vars[key] = var
            sp = tk.Spinbox(
                row, from_=5, to=28, textvariable=var, width=5,
                command=self._apply_sizes,
            )
            sp.pack(side="left", padx=(4, 0))
            var.trace_add("write", lambda *_: self._apply_sizes())

        ttk.Separator(side, orient="horizontal").pack(fill="x", pady=10)

        # ── Visibilité des prix ───────────────────────────────────
        ttk.Label(side, text="Affichage des prix",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 4))
        self._vis_vars: dict[str, tk.BooleanVar] = {}
        for _pk, _pl in [
            ("prix",         "Prix de vente (PV)"),
            ("prix_revient", "Prix de revient (PR)"),
            ("marge",        "Marge (M)"),
        ]:
            _cfg = self._working.get(_pk, {})
            _init = bool(_cfg.get("visible", _pk == "prix")) if isinstance(_cfg, dict) else (_pk == "prix")
            _var = tk.BooleanVar(value=_init)
            self._vis_vars[_pk] = _var
            ttk.Checkbutton(
                side, text=_pl, variable=_var,
                command=lambda k=_pk: self._on_vis_toggle(k),
            ).pack(anchor="w", padx=4, pady=1)

        ttk.Separator(side, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(side, text="Position (mm) de l'élément sélectionné",
                  font=("Segoe UI", 9)).pack(anchor="w")
        coord_row = ttk.Frame(side)
        coord_row.pack(fill="x", pady=4)
        ttk.Label(coord_row, text="X :").pack(side="left")
        self._coord_x_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(coord_row, from_=0, to=CELL_W_MM, textvariable=self._coord_x_var,
                    increment=0.5, width=7, format="%.1f",
                    command=self._apply_coords).pack(side="left", padx=(2, 8))
        ttk.Label(coord_row, text="Y :").pack(side="left")
        self._coord_y_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(coord_row, from_=0, to=CELL_H_MM, textvariable=self._coord_y_var,
                    increment=0.5, width=7, format="%.1f",
                    command=self._apply_coords).pack(side="left", padx=(2, 0))
        self._coord_x_var.trace_add("write", lambda *_: self._apply_coords())
        self._coord_y_var.trace_add("write", lambda *_: self._apply_coords())
        self._updating_coords = False

        ttk.Separator(side, orient="horizontal").pack(fill="x", pady=10)

        ttk.Button(side, text="Enregistrer",   command=self._on_save).pack(fill="x", pady=2)
        ttk.Button(side, text="Réinitialiser", command=self._on_reset).pack(fill="x", pady=2)
        ttk.Button(side, text="Annuler",       command=self._on_cancel).pack(fill="x", pady=2)

        ttk.Separator(side, orient="horizontal").pack(fill="x", pady=8)
        hint = (
            "• Glisser un texte pour le déplacer\n"
            "• Cliquer pour sélectionner\n"
            "• Ajuster X/Y ou la taille de police\n"
            f"• Zone: {CELL_W_MM:.1f} × {CELL_H_MM:.1f} mm"
        )
        ttk.Label(side, text=hint, foreground="#666666", justify="left",
                  font=("Segoe UI", 8)).pack(anchor="w")

    # ── Données de prévisualisation ───────────────────────────────────

    def _build_sample(self) -> dict[str, Any]:
        """Construit les données à afficher selon le modèle."""
        b = self.bracelet
        nom = str(b.get("nom", "") or "Bracelet sans nom")
        pv = float(b.get("prix_vente", 0) or 0)
        try:
            m = self.db.calculate_bracelet_metrics(b)
            cout_revient = float(m.get("cout_revient", 0.0))
        except Exception:
            cout_revient = 0.0
        marge_val = pv - cout_revient
        comp = b.get("composition") or []
        comp_lines: list[str] = []
        for row in comp[:6]:
            qty = int(row.get("quantite", 1) or 1)
            nc = str(row.get("composant", "")).strip()
            if nc:
                comp_lines.append(f"{qty}× {nc}" if qty > 1 else nc)
        if not comp_lines:
            comp_lines = ["Aventurine", "Lapis-lazuli", "Obsidienne"]

        vertus: list[str] = []
        chakras: list[str] = []
        if self.model == "vertus":
            try:
                m2 = self.db.calculate_bracelet_metrics(b)
                vertus = list(m2.get("vertus", []))[:5]
                chakras = list(m2.get("chakras", []))[:4]
            except Exception:
                pass
            if not vertus:
                vertus = ["Communication", "Sérénité", "Confiance"]
            if not chakras:
                chakras = ["Gorge", "3e Œil"]

        return {
            "nom": nom,
            "prix":         f"PV : {pv:.2f} €",
            "prix_revient": f"PR : {cout_revient:.2f} €",
            "marge":        f"M  : {marge_val:.2f} €",
            "comp_lines": comp_lines,
            "vertus": vertus, "chakras": chakras,
        }

    # ── Rendu du canvas ───────────────────────────────────────────────

    def _redraw(self) -> None:
        self.cv.delete("all")

        # Fond et contour du label
        self.cv.create_rectangle(
            _OX, _OY, _OX + _LBL_W_PX, _OY + _LBL_H_PX,
            fill="white", outline="#222222", width=2,
        )

        if self.model == "bracelet":
            self._draw_bracelet()
        else:
            self._draw_vertus()

    def _mm_to_px(self, x_mm: float, y_mm: float) -> tuple[float, float]:
        return _OX + x_mm * SCALE_PX_MM, _OY + y_mm * SCALE_PX_MM

    def _px_to_mm(self, cx: float, cy: float) -> tuple[float, float]:
        return (cx - _OX) / SCALE_PX_MM, (cy - _OY) / SCALE_PX_MM

    def _draw_separator(self) -> None:
        sep_y_mm = float(self._working.get("sep_y", 7.5))
        _, sep_cy = self._mm_to_px(0, sep_y_mm)
        self.cv.create_line(
            _OX + 15, sep_cy, _OX + _LBL_W_PX - 15, sep_cy,
            fill="#999999", width=1, dash=(4, 3),
        )

    def _draw_text_elem(
        self, key: str, text: str,
        extra_tags: tuple[str, ...] = (),
        fill: str = "#1e293b",
    ) -> None:
        """Dessine un élément texte déplaçable."""
        cfg = self._working.get(key, {})
        if not isinstance(cfg, dict):
            return
        cx, cy = self._mm_to_px(cfg.get("x", 4), cfg.get("y", 4))
        pdf_size = float(cfg.get("size", 8))
        tk_size  = _pdf_pt_to_tk(pdf_size)
        bold     = "bold" if cfg.get("bold", False) else "normal"
        font     = ("Segoe UI", tk_size, bold)
        tags     = (f"el_{key}", "draggable") + extra_tags

        # Ombre légère pour rendre le texte plus lisible sur fond blanc
        self.cv.create_text(
            cx + 1, cy + 1, anchor="nw", text=text, font=font, fill="#cccccc",
        )
        self.cv.create_text(
            cx, cy, anchor="nw", text=text, font=font,
            fill=fill, tags=tags,
        )

        # Contour de sélection si l'élément est le dernier dragué
        if self._drag_key == key:
            bb = self.cv.bbox(f"el_{key}")
            if bb:
                self.cv.create_rectangle(
                    bb[0] - 2, bb[1] - 2, bb[2] + 2, bb[3] + 2,
                    outline="#2563eb", fill="", width=1, dash=(3, 2),
                )

    def _draw_items_list(
        self, key: str, lines: list[str],
    ) -> None:
        """Dessine une liste d'items (composition, vertus, chakras)."""
        cfg = self._working.get(key, {})
        if not isinstance(cfg, dict):
            return
        x_mm = float(cfg.get("x", 5))
        y_mm = float(cfg.get("y", 13))
        leading_mm = float(cfg.get("leading", 4.5))
        pdf_size = float(cfg.get("size", 7))
        tk_size  = _pdf_pt_to_tk(pdf_size)
        font = ("Segoe UI", tk_size, "normal")

        for i, line in enumerate(lines):
            cx, cy = self._mm_to_px(x_mm, y_mm + i * leading_mm)
            # Seul le premier item est le handle draggable
            tags = (f"el_{key}", "draggable") if i == 0 else ()
            self.cv.create_text(cx, cy, anchor="nw", text=line, font=font,
                                fill="#374151", tags=tags)

        if self._drag_key == key and lines:
            cx0, cy0 = self._mm_to_px(x_mm, y_mm)
            cx_last, cy_last = self._mm_to_px(x_mm, y_mm + (len(lines) - 1) * leading_mm)
            # largeur approximative
            self.cv.create_rectangle(
                cx0 - 2, cy0 - 2, cx0 + 120, cy_last + tk_size + 2,
                outline="#2563eb", fill="", width=1, dash=(3, 2),
            )

    def _draw_bracelet(self) -> None:
        s = self._sample
        self._draw_separator()
        self._draw_text_elem("nom", s["nom"])
        self._draw_text_elem("comp_label", "Composition :")
        self._draw_items_list("comp_items", s["comp_lines"])
        self._draw_price_elems()

    def _draw_vertus(self) -> None:
        s = self._sample
        self._draw_separator()
        self._draw_text_elem("nom", s["nom"])
        self._draw_text_elem("vertus_label", "Vertus :")
        self._draw_items_list("vertus_items", s["vertus"])
        self._draw_text_elem("chakras_label", "Chakras :")
        self._draw_items_list("chakras_items", s["chakras"])
        self._draw_price_elems()

    def _draw_price_elems(self) -> None:
        """Dessine les 3 éléments prix. Grisé si visible=False (positionnement possible même caché)."""
        s = self._sample
        for key, sample_text in [
            ("prix",         s["prix"]),
            ("prix_revient", s["prix_revient"]),
            ("marge",        s["marge"]),
        ]:
            cfg = self._working.get(key, {})
            visible = bool(cfg.get("visible", key == "prix")) if isinstance(cfg, dict) else (key == "prix")
            color = "#166534" if visible else "#bbbbbb"
            text = sample_text if visible else f"({sample_text})"
            self._draw_text_elem(key, text, fill=color)

    def _on_vis_toggle(self, key: str) -> None:
        """Active/désactive la visibilité d'un champ prix et redessine."""
        var = self._vis_vars.get(key)
        if var is None:
            return
        cfg = self._working.get(key, {})
        if isinstance(cfg, dict):
            cfg["visible"] = var.get()
        self._redraw()

    # ── Gestion du drag ───────────────────────────────────────────────

    def _find_drag_key(self, cx: float, cy: float) -> str | None:
        """Trouve la clé d'élément draggable le plus proche du clic."""
        items = self.cv.find_closest(cx, cy)
        if not items:
            return None
        tags = set(self.cv.gettags(items[0]))
        if "draggable" not in tags:
            return None
        for tag in tags:
            if tag.startswith("el_"):
                return tag[3:]  # supprime "el_"
        return None

    def _on_press(self, event: tk.Event) -> None:
        key = self._find_drag_key(event.x, event.y)
        if key is None:
            return
        self._drag_key = key
        self._drag_start_x = float(event.x)
        self._drag_start_y = float(event.y)
        cfg = self._working.get(key, {})
        if isinstance(cfg, dict):
            self._drag_orig_x = float(cfg.get("x", 0))
            self._drag_orig_y = float(cfg.get("y", 0))
        # Mettre à jour les spinboxes de coordonnées
        self._refresh_coord_spinboxes(key)
        self._redraw()

    def _on_drag(self, event: tk.Event) -> None:
        if self._drag_key is None:
            return
        dx_mm = (event.x - self._drag_start_x) / SCALE_PX_MM
        dy_mm = (event.y - self._drag_start_y) / SCALE_PX_MM
        new_x = max(0.0, min(CELL_W_MM - 2, round(self._drag_orig_x + dx_mm, 1)))
        new_y = max(0.0, min(CELL_H_MM - 1, round(self._drag_orig_y + dy_mm, 1)))
        cfg = self._working.get(self._drag_key, {})
        if isinstance(cfg, dict):
            cfg["x"] = new_x
            cfg["y"] = new_y
        self._refresh_coord_spinboxes(self._drag_key)
        self._redraw()

    def _on_release(self, event: tk.Event) -> None:
        # Ne réinitialise pas _drag_key pour garder la sélection visible
        pass

    # ── Spinboxes ─────────────────────────────────────────────────────

    def _apply_sizes(self, *_) -> None:
        """Applique les tailles de police depuis les spinboxes."""
        for key, var in self._size_vars.items():
            try:
                val = int(var.get())
                cfg = self._working.get(key, {})
                if isinstance(cfg, dict):
                    cfg["size"] = val
            except (tk.TclError, ValueError):
                pass
        self._redraw()

    def _refresh_coord_spinboxes(self, key: str) -> None:
        """Met à jour les spinboxes X/Y avec les valeurs de l'élément sélectionné."""
        self._updating_coords = True
        try:
            cfg = self._working.get(key, {})
            if isinstance(cfg, dict):
                self._coord_x_var.set(round(float(cfg.get("x", 0)), 1))
                self._coord_y_var.set(round(float(cfg.get("y", 0)), 1))
        except Exception:
            pass
        finally:
            self._updating_coords = False

    def _apply_coords(self, *_) -> None:
        """Applique les coordonnées X/Y à l'élément sélectionné."""
        if self._updating_coords or self._drag_key is None:
            return
        try:
            x = max(0.0, min(CELL_W_MM - 2, float(self._coord_x_var.get())))
            y = max(0.0, min(CELL_H_MM - 1, float(self._coord_y_var.get())))
            cfg = self._working.get(self._drag_key, {})
            if isinstance(cfg, dict):
                cfg["x"] = round(x, 1)
                cfg["y"] = round(y, 1)
            self._redraw()
        except (tk.TclError, ValueError):
            pass

    # ── Boutons ───────────────────────────────────────────────────────

    def _on_save(self) -> None:
        layout_profiles.save_layout(self.model, self._working, self.db.base_dir)
        fname = layout_profiles.filename_for(self.model)
        messagebox.showinfo(
            "Enregistré",
            f"Mise en page sauvegardée.\n\nFichier : {fname}",
            parent=self,
        )
        if self.on_save:
            self.on_save()
        self.destroy()

    def _on_reset(self) -> None:
        if not messagebox.askyesno(
            "Réinitialiser",
            "Réinitialiser la mise en page aux valeurs par défaut ?",
            parent=self,
        ):
            return
        self._working = layout_profiles.default_for(self.model)
        self._drag_key = None
        # Mettre à jour les spinboxes de taille de police
        for key, var in self._size_vars.items():
            cfg = self._working.get(key, {})
            if isinstance(cfg, dict):
                var.set(int(cfg.get("size", 8)))
        # Mettre à jour les checkboxes de visibilité
        for key, var in self._vis_vars.items():
            cfg = self._working.get(key, {})
            init = bool(cfg.get("visible", key == "prix")) if isinstance(cfg, dict) else (key == "prix")
            var.set(init)
        self._redraw()

    def _on_cancel(self) -> None:
        self.destroy()
