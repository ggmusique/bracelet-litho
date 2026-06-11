"""pages/fabrication.py — Page de fabrication des bracelets (Phase 2A)."""
from __future__ import annotations
import time
import customtkinter as ctk
import theme
from widgets import Divider, SectionHeader
from fabrication_services import check_fabrication, simulate_fabrication, execute_fabrication
from tkinter import filedialog, messagebox
from pdf_generator import PDFGenerator

_FILTER_ALL = "Tous"
_FILTER_OK = "Fabricables"
_FILTER_KO = "Non fabricables"
_FILTERS = (_FILTER_ALL, _FILTER_OK, _FILTER_KO)

_PAGE_LABEL = "fabrication"


def _open_generated_file(file_path: str) -> None:
    """Ouvre le fichier avec l'application par defaut du systeme (sans le telecharger)."""
    import os as _os
    try:
        if _os.name == "nt":
            _os.startfile(file_path)  # type: ignore[attr-defined]
        else:
            import webbrowser
            from pathlib import Path as _P
            webbrowser.open(_P(file_path).as_uri())
    except OSError:
        pass


def _money(val: float) -> str:
    s = f"{val:,.2f} EUR"
    return s.replace(",", " ").replace(".", ",").replace(" ", ".") if " " in s else s.replace(".", ",")


class FabricationPage(ctk.CTkFrame):
    def __init__(self, parent, db=None, **kwargs) -> None:
        super().__init__(parent, fg_color=theme.BG_MAIN, **kwargs)
        self.db = db
        self._selected_id: str | None = None
        self._list_buttons: dict[str, ctk.CTkButton] = {}
        self._all_bracelets: list[dict] = []
        self._filtered_bracelets: list[dict] = []
        self._cache: dict = {}
        self._active_filter: str = _FILTER_ALL
        self._filter_buttons: dict[str, ctk.CTkButton] = {}
        self._search_var = ctk.StringVar()
        self._search_after_id: str | None = None
        self._search_debounce_ms = 250
        self._quantity_var = ctk.StringVar(value="1")
        self._qty_spin: ctk.CTkEntry | None = None
        self._simulate_btn: ctk.CTkButton | None = None
        self._fab_btn: ctk.CTkButton | None = None
        self._status_frame: ctk.CTkFrame | None = None
        self._status_label: ctk.CTkLabel | None = None
        self._simulate_results: ctk.CTkFrame | None = None
        self._photo_img = None

        self._build()
        self._load_list()

    # ── Construction ───────────────────────────────────────────────

    def _build(self) -> None:
        SectionHeader(self, title="🏭  Fabrication", subtitle="Gestion de production atelier").pack(
            fill="x", padx=24, pady=(20, 0)
        )
        Divider(self).pack(fill="x", padx=24, pady=(10, 0))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=(8, 16))

        body.grid_columnconfigure(0, weight=0, minsize=340)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_list_panel(body)
        self._build_fiche_panel(body)

    def _build_list_panel(self, parent: ctk.CTkFrame) -> None:
        left = ctk.CTkFrame(parent, fg_color=theme.BG_SIDEBAR, corner_radius=16)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        ctk.CTkLabel(
            left, text="Bracelets",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=16, pady=(16, 8))

        filter_row = ctk.CTkFrame(left, fg_color="transparent")
        filter_row.pack(fill="x", padx=8, pady=(0, 8))
        for label in _FILTERS:
            btn = ctk.CTkButton(
                filter_row,
                text=label,
                font=ctk.CTkFont(size=12),
                height=30,
                corner_radius=10,
                fg_color=theme.ACCENT_TURQUOISE if label == _FILTER_ALL else "transparent",
                text_color=theme.TEXT_PRIMARY,
                hover_color=theme.BG_CARD,
                command=lambda l=label: self._set_filter(l),
            )
            btn.pack(side="left", padx=2, expand=True, fill="x")
            self._filter_buttons[label] = btn

        search_entry = ctk.CTkEntry(
            left,
            placeholder_text="Rechercher...",
            height=34,
            corner_radius=10,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
        )
        search_entry.pack(fill="x", padx=12, pady=(0, 8))
        self._search_var.trace_add("write", lambda *_: self._schedule_filter())
        search_entry.configure(textvariable=self._search_var)

        self._list_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self._list_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 12))

    def _build_fiche_panel(self, parent: ctk.CTkFrame) -> None:
        self._right = ctk.CTkScrollableFrame(parent, fg_color=theme.BG_CARD, corner_radius=16)
        self._right.grid(row=0, column=1, sticky="nsew")
        self._show_empty_fiche()

    def _show_empty_fiche(self) -> None:
        for w in self._right.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._right,
            text="Sélectionnez un bracelet\npour voir sa fiche fabrication",
            font=ctk.CTkFont(size=14),
            text_color=theme.TEXT_SECONDARY,
        ).pack(pady=80)

    # ── Filter / Search ────────────────────────────────────────────

    def _set_filter(self, label: str) -> None:
        self._active_filter = label
        for lbl, btn in self._filter_buttons.items():
            btn.configure(fg_color=theme.ACCENT_TURQUOISE if lbl == label else "transparent")
        self._apply_list_filter()

    def _schedule_filter(self) -> None:
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(self._search_debounce_ms, self._apply_list_filter)

    def _apply_list_filter(self) -> None:
        q = self._search_var.get().strip().lower()
        if self._active_filter == _FILTER_OK:
            candidates = [b for b in self._all_bracelets if self._cache.get(b.get("id", ""), {}).get("fabricable")]
        elif self._active_filter == _FILTER_KO:
            candidates = [b for b in self._all_bracelets if not self._cache.get(b.get("id", ""), {}).get("fabricable")]
        else:
            candidates = list(self._all_bracelets)

        if q:
            candidates = [
                b for b in candidates
                if q in b.get("nom", "").lower() or q in b.get("reference", "").lower()
            ]

        self._filtered_bracelets = candidates
        self._render_list()

    # ── List rendering ─────────────────────────────────────────────

    def _load_list(self) -> None:
        self._all_bracelets = sorted(
            self.db.bracelets,
            key=lambda b: str(b.get("nom", "")).lower(),
        ) if self.db else []
        self._rebuild_cache()
        self._apply_list_filter()

    def _rebuild_cache(self) -> None:
        self._cache = {}
        if not self.db:
            return
        for b in self._all_bracelets:
            bid = b.get("id", "")
            chk = check_fabrication(b, self.db, 1)
            self._cache[bid] = chk

    def _render_list(self) -> None:
        for w in self._list_scroll.winfo_children():
            w.destroy()
        self._list_buttons.clear()

        for b in self._filtered_bracelets:
            bid = str(b.get("id", ""))
            chk = self._cache.get(bid, {})
            fabricable = chk.get("fabricable", False)
            icon = "✅" if fabricable else "❌"
            ref = b.get("reference", "—")
            nom = b.get("nom", "Sans nom")

            btn = ctk.CTkButton(
                self._list_scroll,
                text=f"  {icon}  {ref}\n       {nom}",
                anchor="w",
                height=50,
                corner_radius=12,
                fg_color="transparent",
                hover_color=theme.BG_CARD,
                text_color=theme.TEXT_PRIMARY,
                font=ctk.CTkFont(size=12),
                command=lambda rid=bid: self._select_bracelet(rid),
            )
            btn.pack(fill="x", pady=2)
            self._list_buttons[bid] = btn

        if not self._filtered_bracelets:
            ctk.CTkLabel(
                self._list_scroll,
                text="Aucun bracelet",
                text_color=theme.TEXT_SECONDARY,
            ).pack(pady=20)

        auto_select = self._selected_id if self._selected_id in self._list_buttons else (
            str(self._filtered_bracelets[0].get("id", "")) if self._filtered_bracelets else None
        )
        if auto_select:
            self._select_bracelet(auto_select)

    # ── Fiche fabrication ──────────────────────────────────────────

    def _select_bracelet(self, bracelet_id: str) -> None:
        if self._selected_id == bracelet_id and bracelet_id in self._list_buttons:
            return
        self._selected_id = bracelet_id
        for rid, btn in self._list_buttons.items():
            active = rid == bracelet_id
            btn.configure(
                fg_color=theme.BG_CARD if active else "transparent",
                text_color=theme.ACCENT_TURQUOISE if active else theme.TEXT_PRIMARY,
                font=ctk.CTkFont(size=12, weight="bold") if active else ctk.CTkFont(size=12),
            )

        b = self.db.get_bracelet_by_id(bracelet_id) if self.db else None
        if b is None:
            for bb in self._all_bracelets:
                if bb.get("id") == bracelet_id:
                    b = bb
                    break
        if b is None:
            return

        chk = self._cache.get(bracelet_id, {})
        self._render_fiche(b, chk)

    def _render_fiche(self, b: dict, chk: dict) -> None:
        t0 = time.perf_counter()
        for w in self._right.winfo_children():
            w.destroy()

        pad_inner = 24
        cont = ctk.CTkFrame(self._right, fg_color="transparent")
        cont.pack(fill="both", expand=True, padx=pad_inner, pady=pad_inner)

        # ── Status badge ───────────────────────────────────────────
        fabricable = chk.get("fabricable", False)
        max_pos = chk.get("max_possible", 0)
        self._status_frame = ctk.CTkFrame(cont, fg_color="transparent")
        self._status_frame.pack(fill="x", pady=(0, 16))

        status_text = "✅ Fabricable" if fabricable else "❌ Non fabricable"
        status_color = theme.SUCCESS if fabricable else theme.DANGER
        self._status_label = ctk.CTkLabel(
            self._status_frame,
            text=status_text,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=status_color,
        )
        self._status_label.pack(anchor="w")

        if fabricable and max_pos > 0:
            ctk.CTkLabel(
                self._status_frame,
                text=f"Quantité maximale fabricable : {max_pos}",
                font=ctk.CTkFont(size=13),
                text_color=theme.TEXT_SECONDARY,
            ).pack(anchor="w", pady=(2, 0))

        if not fabricable and chk.get("missing"):
            miss_frame = ctk.CTkFrame(self._status_frame, fg_color=theme.BG_INPUT, corner_radius=8)
            miss_frame.pack(fill="x", pady=(6, 0))
            ctk.CTkLabel(
                miss_frame,
                text="Manque :",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=theme.DANGER,
            ).pack(anchor="w", padx=12, pady=(8, 2))
            for m in chk["missing"][:5]:
                ctk.CTkLabel(
                    miss_frame,
                    text=f"• {m['manque']} {m['composant']} ({m['categorie']})",
                    font=ctk.CTkFont(size=12),
                    text_color=theme.TEXT_SECONDARY,
                ).pack(anchor="w", padx=12)

        Divider(cont).pack(fill="x", pady=(0, 16))

        # ── General info ───────────────────────────────────────────
        gen = ctk.CTkFrame(cont, fg_color=theme.BG_INPUT, corner_radius=12)
        gen.pack(fill="x", pady=(0, 12))

        row1 = ctk.CTkFrame(gen, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=12)
        row1.grid_columnconfigure(1, weight=1)

        # Photo
        from phase1c_services import load_ctk_image
        photo_frame = ctk.CTkFrame(row1, fg_color=theme.BG_CARD, corner_radius=10, width=120, height=120)
        photo_frame.grid(row=0, column=0, rowspan=3, padx=(0, 16), sticky="nw")
        photo_frame.pack_propagate(False)
        img = load_ctk_image(self.db, b, size=(110, 110), use_thumb=True) if self.db else None
        self._photo_img = img
        if img:
            ctk.CTkLabel(photo_frame, image=img, text="").pack(padx=5, pady=5)
        else:
            ctk.CTkLabel(
                photo_frame, text="📷", font=ctk.CTkFont(size=36),
                text_color=theme.TEXT_SECONDARY,
            ).pack(expand=True)

        info_grid = ctk.CTkFrame(row1, fg_color="transparent")
        info_grid.grid(row=0, column=1, sticky="ew")
        info_grid.grid_columnconfigure(1, weight=1)

        fields = [
            ("Référence", b.get("reference", "—")),
            ("Nom", b.get("nom", "—")),
            ("Stock actuel", str(b.get("stock", 0))),
        ]
        for i, (label, value) in enumerate(fields):
            ctk.CTkLabel(
                info_grid, text=f"{label} :",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=theme.TEXT_SECONDARY,
            ).grid(row=i, column=0, sticky="w", padx=(0, 8), pady=2)
            ctk.CTkLabel(
                info_grid, text=value,
                font=ctk.CTkFont(size=14),
                text_color=theme.TEXT_PRIMARY,
            ).grid(row=i, column=1, sticky="w", pady=2)

        # ── Production KPIs ────────────────────────────────────────
        kpi_frame = ctk.CTkFrame(cont, fg_color="transparent")
        kpi_frame.pack(fill="x", pady=(0, 12))

        metrics = self.db.calculate_bracelet_metrics(b) if self.db else {}
        cout_revient = metrics.get("cout_revient", 0.0)
        pv = float(b.get("prix_vente", 0) or 0)
        marge = pv - cout_revient
        renta = (marge / cout_revient * 100) if cout_revient > 0 else 0.0

        kpi_data = [
            ("💰", "Prix revient", _money(cout_revient), theme.INFO),
            ("💶", "Prix vente", _money(pv), theme.ACCENT_TURQUOISE),
            ("📈", "Marge", _money(marge), theme.SUCCESS if marge >= 0 else theme.DANGER),
            ("📊", "Rentabilité", f"{renta:.1f}%", theme.WARNING if renta < 50 else theme.SUCCESS),
        ]

        kpi_frame.grid_columnconfigure(tuple(range(4)), weight=1)
        for i, (icon, label, value, color) in enumerate(kpi_data):
            card = ctk.CTkFrame(kpi_frame, fg_color=theme.BG_INPUT, corner_radius=12)
            card.grid(row=0, column=i, sticky="ew", padx=4)
            ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=22), text_color=color).pack(anchor="w", padx=12, pady=(10, 0))
            ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=18, weight="bold"), text_color=color).pack(anchor="w", padx=12)
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=11), text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=12, pady=(0, 10))

        Divider(cont).pack(fill="x", pady=(0, 12))

        # ── Composition table ─────────────────────────────────────
        SectionHeader(cont, title="Stock requis", subtitle="Détail des composants nécessaires").pack(fill="x")
        self._render_composition_table(cont, chk)

        Divider(cont).pack(fill="x", pady=(12, 12))

        # ── Quantity + buttons ────────────────────────────────────
        action_row = ctk.CTkFrame(cont, fg_color="transparent")
        action_row.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            action_row,
            text="Quantité à fabriquer :",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 8))

        self._qty_spin = ctk.CTkEntry(
            action_row,
            textvariable=self._quantity_var,
            width=70,
            height=34,
            corner_radius=8,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
            justify="center",
        )
        self._qty_spin.pack(side="left", padx=(0, 12))

        self._simulate_btn = ctk.CTkButton(
            action_row,
            text="🔍 Simuler",
            font=ctk.CTkFont(size=13),
            height=34,
            corner_radius=10,
            fg_color=theme.BG_CARD,
            text_color=theme.ACCENT_TURQUOISE,
            hover_color=theme.BG_CARD_HOVER,
            border_width=1,
            border_color=theme.ACCENT_TURQUOISE,
            command=lambda: self._on_simulate(b, chk),
        )
        self._simulate_btn.pack(side="left", padx=4)

        self._fab_btn = ctk.CTkButton(
            action_row,
            text="⚙ Fabriquer",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=34,
            corner_radius=10,
            fg_color=theme.SUCCESS if fabricable else theme.DANGER,
            text_color="white",
            hover_color="#059669" if fabricable else "#dc2626",
            command=lambda: self._on_fabricate(b),
        )
        self._fab_btn.pack(side="left", padx=4)
        if not fabricable:
            self._fab_btn.configure(state="disabled")

        self._fiche_btn = ctk.CTkButton(
            action_row,
            text="📄 Fiche PDF",
            font=ctk.CTkFont(size=13),
            height=34,
            corner_radius=10,
            fg_color=theme.BG_CARD,
            text_color=theme.ACCENT_TURQUOISE,
            hover_color=theme.BG_CARD_HOVER,
            border_width=1,
            border_color=theme.ACCENT_TURQUOISE,
            command=lambda: self._on_export_fiche(b),
        )
        self._fiche_btn.pack(side="left", padx=4)
        self._fiches_btn = ctk.CTkButton(
            action_row,
            text="🗂 Fiches (vue)",
            font=ctk.CTkFont(size=13),
            height=34,
            corner_radius=10,
            fg_color=theme.BG_CARD,
            text_color=theme.ACCENT_AMETHYSTE,
            hover_color=theme.BG_CARD_HOVER,
            border_width=1,
            border_color=theme.ACCENT_AMETHYSTE,
            command=lambda: self._on_export_fiches_grid(),
        )
        self._fiches_btn.pack(side="left", padx=4)

        # ── Simulation results ────────────────────────────────────
        self._simulate_results = ctk.CTkFrame(cont, fg_color=theme.BG_INPUT, corner_radius=12)
        self._simulate_results.pack(fill="x")
        self._simulate_results.pack_forget()

        self._perf = time.perf_counter() - t0

    def _render_composition_table(self, parent: ctk.CTkFrame, chk: dict) -> None:
        tbl = ctk.CTkFrame(parent, fg_color="transparent")
        tbl.pack(fill="x", pady=(8, 0))

        headers = ["Composant", "Type", "Nécessaire", "Stock disp.", "Statut"]
        widths = [0, 0, 80, 100, 90]
        header_frame = ctk.CTkFrame(tbl, fg_color=theme.BG_CARD, corner_radius=8)
        header_frame.pack(fill="x", pady=(0, 4))
        for col, (hdr, w) in enumerate(zip(headers, widths)):
            ctk.CTkLabel(
                header_frame,
                text=hdr,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=theme.TEXT_SECONDARY,
                width=w,
            ).pack(side="left", padx=(12 if col == 0 else 4), pady=6)

        composants = chk.get("composants", [])
        if not composants:
            ctk.CTkLabel(
                tbl,
                text="Aucun composant dans ce bracelet.",
                text_color=theme.TEXT_SECONDARY,
            ).pack(pady=12)
            return

        for comp in composants:
            row = ctk.CTkFrame(tbl, fg_color="transparent")
            row.pack(fill="x", pady=1)

            statut = comp.get("statut", "")
            if statut == "disponible":
                color = theme.SUCCESS
                icon = "✅"
            elif statut == "faible":
                color = theme.WARNING
                icon = "⚠️"
            elif statut == "insuffisant":
                color = theme.DANGER
                icon = "❌"
            else:
                color = theme.DANGER
                icon = "❓"

            values = [
                comp.get("composant", "—"),
                comp.get("categorie", "—"),
                str(comp.get("quantite_necessaire", 0)),
                str(comp.get("stock_disponible", 0)),
                f"{icon} {statut}",
            ]
            for col, (val, w) in enumerate(zip(values, widths)):
                ctk.CTkLabel(
                    row,
                    text=val,
                    font=ctk.CTkFont(size=12),
                    text_color=color if col == 4 else theme.TEXT_PRIMARY,
                    width=w,
                ).pack(side="left", padx=(12 if col == 0 else 4), pady=3)

    # ── Actions ────────────────────────────────────────────────────

    def _parse_qty(self) -> int:
        try:
            q = int(self._quantity_var.get())
            return max(1, q)
        except (ValueError, TypeError):
            return 1

    def _on_simulate(self, b: dict, chk: dict) -> None:
        qty = self._parse_qty()
        results = simulate_fabrication(b, self.db, qty)

        if not self._simulate_results:
            return

        for w in self._simulate_results.winfo_children():
            w.destroy()
        self._simulate_results.pack(fill="x", pady=(8, 0))

        ctk.CTkLabel(
            self._simulate_results,
            text=f"📊 Simulation après fabrication (x{qty})",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.ACCENT_TURQUOISE,
        ).pack(anchor="w", padx=14, pady=(10, 4))

        for r in results:
            color = theme.SUCCESS if r["stock_apres"] >= 0 else theme.DANGER
            ctk.CTkLabel(
                self._simulate_results,
                text=f"{r['composant']} : {r['stock_actuel']} → {r['stock_apres']}",
                font=ctk.CTkFont(size=12),
                text_color=color,
            ).pack(anchor="w", padx=14, pady=1)

        ctk.CTkLabel(
            self._simulate_results,
            text="",
            font=ctk.CTkFont(size=6),
        ).pack(pady=(0, 6))

    def _on_fabricate(self, b: dict) -> None:
        qty = self._parse_qty()
        chk = check_fabrication(b, self.db, qty)
        if not chk["fabricable"]:
            import tkinter.messagebox as mb
            mb.showerror("Fabrication", "Stock insuffisant pour cette quantité.")
            return

        success, msg = execute_fabrication(b, qty, self.db)
        if success:
            import tkinter.messagebox as mb
            mb.showinfo("Fabrication", f"✅ {msg}")
            self.db.reload_all()
            self._load_list()
        else:
            import tkinter.messagebox as mb
            mb.showerror("Fabrication", f"❌ {msg}")

    # ── Refresh ────────────────────────────────────────────────────

    def _on_export_fiche(self, b: dict) -> None:
        if not self.db:
            return
        from datetime import datetime
        from pathlib import Path as _Path
        raw_nom = str(b.get("nom", "bracelet"))
        safe_nom = "".join(ch for ch in raw_nom if ch.isalnum() or ch in (" ", "-", "_")).strip().replace(" ", "_") or "bracelet"
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        suggested = f"fiche_{safe_nom}_{stamp}.pdf"
        import tempfile, os as _os
        path = _os.path.join(tempfile.gettempdir(), suggested)
        try:
            pdf = PDFGenerator(self.db)
            pdf.export_fiche_creation_pdf(b, path)
        except Exception as exc:
            messagebox.showerror("Fiche PDF", f"Erreur lors de la generation : {exc}")
            return
        _open_generated_file(path)

    def _on_export_fiches_grid(self) -> None:
        if not self.db:
            return
        from datetime import datetime
        from pathlib import Path as _Path
        bracelets = list(self._filtered_bracelets)
        if not bracelets:
            messagebox.showinfo("Fiches PDF", "Aucun bracelet dans la vue actuelle.")
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        suggested = f"fiches_bracelets_{stamp}.pdf"
        import tempfile, os as _os
        path = _os.path.join(tempfile.gettempdir(), suggested)
        try:
            pdf = PDFGenerator(self.db)
            pdf.export_fiches_creation_pdf(bracelets, path)
        except Exception as exc:
            messagebox.showerror("Fiches PDF", f"Erreur lors de la generation : {exc}")
            return
        _open_generated_file(path)

    def refresh(self) -> None:
        self._load_list()
