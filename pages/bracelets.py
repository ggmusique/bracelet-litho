"""pages/bracelets.py
Page Bracelets - Lithotherapie Pro V2.
Phase 1C : fiche avancee, photo 300x300, KPI rentabilite et composition detaillee.
"""
from __future__ import annotations

import os
import tkinter.filedialog as fd
import tkinter.messagebox as mb
import uuid

import customtkinter as ctk

import theme
from pages.crud_editors import BraceletEditor
from phase1c_services import import_image_for_item, load_ctk_image
from phase1c_services import append_local_history, backup_before_delete
from widgets import Divider, KPICard, SectionHeader


class BraceletsPage(ctk.CTkFrame):
    def __init__(self, parent, db=None, **kwargs) -> None:
        kwargs.setdefault("fg_color", theme.BG_MAIN)
        super().__init__(parent, **kwargs)
        self.db = db
        self._selected_id: str | None = None
        self._list_buttons: dict[str, ctk.CTkButton] = {}
        self._all_bracelets: list[dict] = []
        self._search_after_id: str | None = None
        self._search_debounce_ms = 250
        self._metrics_cache: dict[tuple[str, str], dict] = {}
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._schedule_filter())
        self._genre_filter_var = ctk.StringVar(value="Tous")
        self._stock_filter_var = ctk.StringVar(value="Tous")
        self._sort_var = ctk.StringVar(value="Nom A-Z")
        for _v in (self._genre_filter_var, self._stock_filter_var, self._sort_var):
            _v.trace_add("write", lambda *_: self._apply_list_filter())
        self._photo_img = None
        self._build()
        self._load_list()

    def _build(self) -> None:
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=32, pady=(28, 0))
        SectionHeader(top, title="📿  Bracelets", subtitle="Fiches avancees et rentabilite").pack(
            side="left", fill="x", expand=True
        )

        Divider(self).pack(fill="x", padx=32, pady=20)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        self._left = ctk.CTkFrame(body, fg_color=theme.BG_SIDEBAR, corner_radius=20, width=300)
        self._left.pack(side="left", fill="y", padx=(0, 16))
        self._left.pack_propagate(False)

        ctk.CTkEntry(
            self._left,
            textvariable=self._search_var,
            placeholder_text="Rechercher (nom, reference)",
            height=36,
            corner_radius=12,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
        ).pack(fill="x", padx=14, pady=(16, 10))
        filters = ctk.CTkFrame(self._left, fg_color="transparent")
        filters.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkOptionMenu(filters, variable=self._genre_filter_var, values=["Tous", "Homme", "Femme", "Mixte", "Enfant"], fg_color=theme.BG_INPUT, button_color=theme.BG_CARD, button_hover_color=theme.BG_CARD_HOVER).pack(fill="x", pady=2)
        ctk.CTkOptionMenu(filters, variable=self._stock_filter_var, values=["Tous", "En stock", "Rupture (0)"], fg_color=theme.BG_INPUT, button_color=theme.BG_CARD, button_hover_color=theme.BG_CARD_HOVER).pack(fill="x", pady=2)
        ctk.CTkOptionMenu(filters, variable=self._sort_var, values=["Nom A-Z", "Nom Z-A", "Prix croissant", "Prix decroissant", "Stock croissant", "Stock decroissant"], fg_color=theme.BG_INPUT, button_color=theme.BG_CARD, button_hover_color=theme.BG_CARD_HOVER).pack(fill="x", pady=2)

        actions = ctk.CTkFrame(self._left, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkButton(
            actions,
            text="+ Nouveau bracelet",
            height=30,
            corner_radius=10,
            fg_color=theme.SUCCESS,
            hover_color=theme.ACCENT_TURQUOISE,
            command=self._new_bracelet,
        ).pack(fill="x", pady=(0, 4))
        ctk.CTkButton(
            actions,
            text="✏ Modifier",
            height=30,
            corner_radius=10,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            command=self._edit_bracelet,
        ).pack(fill="x", pady=2)
        ctk.CTkButton(
            actions,
            text="📄 Dupliquer",
            height=30,
            corner_radius=10,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            command=self._duplicate_bracelet,
        ).pack(fill="x", pady=2)
        ctk.CTkButton(
            actions,
            text="🗑 Supprimer",
            height=30,
            corner_radius=10,
            fg_color=theme.DANGER,
            hover_color=theme.WARNING,
            command=self._delete_bracelet,
        ).pack(fill="x", pady=(2, 0))

        ctk.CTkFrame(self._left, height=1, fg_color=theme.BORDER).pack(fill="x", padx=14, pady=(10, 6))
        ctk.CTkButton(
            self._left,
            text="📋 Fiche vierge PDF",
            height=30,
            corner_radius=10,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            command=self._export_fiche_vierge,
        ).pack(fill="x", padx=14, pady=(0, 6))

        ctk.CTkFrame(self._left, height=1, fg_color=theme.BORDER).pack(fill="x", padx=14)

        self._list_scroll = ctk.CTkScrollableFrame(
            self._left, fg_color="transparent", scrollbar_button_color=theme.BORDER
        )
        self._list_scroll.pack(fill="both", expand=True, padx=6, pady=6)

        self._right = ctk.CTkScrollableFrame(
            body, fg_color=theme.BG_CARD, corner_radius=20, scrollbar_button_color=theme.BORDER
        )
        self._right.pack(side="left", fill="both", expand=True)
        self._show_empty_fiche()

    def _load_list(self) -> None:
        self._all_bracelets = sorted(
            self.db.bracelets if self.db else [],
            key=lambda b: str(b.get("nom", "")).lower(),
        )
        self._apply_list_filter()

    def _apply_list_filter(self) -> None:
        q = self._search_var.get().strip().lower()
        for w in self._list_scroll.winfo_children():
            w.destroy()
        self._list_buttons.clear()

        genre_f = self._genre_filter_var.get()
        stock_f = self._stock_filter_var.get()

        def _match(b):
            if q and q not in str(b.get("nom", "")).lower() and q not in str(b.get("reference", "")).lower():
                return False
            if genre_f != "Tous" and str(b.get("genre", "") or "").strip() != genre_f:
                return False
            st = int(b.get("stock", 0) or 0)
            if stock_f == "En stock" and st <= 0:
                return False
            if stock_f == "Rupture (0)" and st > 0:
                return False
            return True

        visible = [b for b in self._all_bracelets if _match(b)]

        sort_mode = self._sort_var.get()
        if sort_mode == "Nom Z-A":
            visible.sort(key=lambda b: str(b.get("nom", "")).lower(), reverse=True)
        elif sort_mode == "Prix croissant":
            visible.sort(key=lambda b: float(b.get("prix_vente", 0.0) or 0.0))
        elif sort_mode == "Prix decroissant":
            visible.sort(key=lambda b: float(b.get("prix_vente", 0.0) or 0.0), reverse=True)
        elif sort_mode == "Stock croissant":
            visible.sort(key=lambda b: int(b.get("stock", 0) or 0))
        elif sort_mode == "Stock decroissant":
            visible.sort(key=lambda b: int(b.get("stock", 0) or 0), reverse=True)
        else:
            visible.sort(key=lambda b: str(b.get("nom", "")).lower())

        if not visible:
            ctk.CTkLabel(
                self._list_scroll,
                text="Aucun resultat",
                text_color=theme.TEXT_SECONDARY,
            ).pack(pady=20)
            self._show_empty_fiche()
            return

        for b in visible:
            bid = str(b.get("id", ""))
            stock = int(b.get("stock", 0) or 0)

            row = ctk.CTkFrame(self._list_scroll, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=2)

            line2 = f"  {b.get('reference', '—')}   ·   Stock: {stock}"

            btn = ctk.CTkButton(
                row,
                text=f"  {b.get('nom', 'Sans nom')}\n{line2}",
                anchor="w",
                height=52,
                corner_radius=12,
                fg_color="transparent",
                hover_color=theme.BG_CARD,
                text_color=theme.TEXT_PRIMARY,
                font=ctk.CTkFont(size=12),
                command=lambda rid=bid: self._select_bracelet(rid),
            )
            btn.pack(fill="x")

            self._list_buttons[bid] = btn

        target = self._selected_id if self._selected_id in self._list_buttons else str(visible[0].get("id", ""))
        if target and target != self._selected_id:
            self._select_bracelet(target)
        elif target:
            for rid, btn in self._list_buttons.items():
                active = rid == target
                btn.configure(
                    fg_color=theme.BG_CARD if active else "transparent",
                    text_color=theme.ACCENT_TURQUOISE if active else theme.TEXT_PRIMARY,
                )

    def _schedule_filter(self) -> None:
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
            self._search_after_id = None
        self._search_after_id = self.after(self._search_debounce_ms, self._apply_list_filter)

    def _select_bracelet(self, bracelet_id: str, force: bool = False) -> None:
        if not self.db:
            return

        b = self.db.get_bracelet_by_id(bracelet_id)
        if not b:
            return

        if self._selected_id == bracelet_id and not force:
            return

        self._selected_id = bracelet_id
        for rid, btn in self._list_buttons.items():
            active = rid == bracelet_id
            btn.configure(
                fg_color=theme.BG_CARD if active else "transparent",
                text_color=theme.ACCENT_TURQUOISE if active else theme.TEXT_PRIMARY,
            )

        cache_key = (bracelet_id, str(b.get("updated_at", "")), str(self.db.settings.get("price_coefficient", "")))
        metrics = self._metrics_cache.get(cache_key)
        if metrics is None:
            metrics = self.db.calculate_bracelet_metrics(b)
            self._metrics_cache[cache_key] = metrics
        self._render_fiche(b, metrics)

    def _render_fiche(self, b: dict, metrics: dict) -> None:
        for w in self._right.winfo_children():
            w.destroy()

        pad = {"padx": 24}

        ctk.CTkLabel(
            self._right,
            text="FICHE BRACELET",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(20, 4), **pad)
        ctk.CTkFrame(self._right, height=1, fg_color=theme.BORDER).pack(fill="x", **pad)

        top = ctk.CTkFrame(self._right, fg_color="transparent")
        top.pack(fill="x", pady=16, **pad)

        photo_box = ctk.CTkFrame(top, width=320, height=320, fg_color=theme.BG_SIDEBAR, corner_radius=20)
        photo_box.pack(side="left", anchor="n", padx=(0, 24))
        photo_box.pack_propagate(False)

        self._photo_img = load_ctk_image(self.db, b, size=(300, 300), use_thumb=False)
        if self._photo_img is None:
            ctk.CTkLabel(photo_box, text="📷", font=ctk.CTkFont(size=54), text_color=theme.TEXT_SECONDARY).pack(pady=(100, 4))
            ctk.CTkLabel(photo_box, text="Image indisponible", text_color=theme.TEXT_SECONDARY).pack()
        else:
            ctk.CTkLabel(photo_box, text="", image=self._photo_img).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkButton(
            photo_box,
            text="Importer une image",
            height=32,
            corner_radius=10,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            command=lambda: self._import_image(b),
        ).pack(side="bottom", fill="x", padx=10, pady=10)

        info = ctk.CTkFrame(top, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)

        cout = float(metrics.get("cout_revient", 0.0) or 0.0)
        prix_vente = float(metrics.get("prix_vente", b.get("prix_vente", 0.0)) or 0.0)
        marge = float(metrics.get("marge", prix_vente - cout) or 0.0)
        rentabilite = 0.0 if cout <= 0 else (marge / cout) * 100.0

        for label, value in [
            ("Reference", b.get("reference", "—")),
            ("Nom", b.get("nom", "—")),
            ("Stock", str(int(b.get("stock", 0) or 0))),
            ("Prix de revient", self._money(cout)),
            ("Prix de vente", self._money(prix_vente)),
            ("Marge", self._money(marge)),
        ]:
            row = ctk.CTkFrame(info, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=label, width=130, anchor="w", text_color=theme.TEXT_SECONDARY).pack(side="left")
            ctk.CTkLabel(row, text=str(value), anchor="w", text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(weight="bold")).pack(side="left")

        kpi_row = ctk.CTkFrame(self._right, fg_color="transparent")
        kpi_row.pack(fill="x", pady=(4, 16), **pad)
        values = [
            ("💶", self._money(cout), "Prix de revient", theme.INFO),
            ("🏷", self._money(prix_vente), "Prix de vente", theme.ACCENT_TURQUOISE),
            ("📈", self._money(marge), "Marge", theme.SUCCESS if marge >= 0 else theme.DANGER),
            ("📊", f"{rentabilite:.1f} %".replace(".", ","), "Rentabilite", theme.WARNING if rentabilite < 20 else theme.SUCCESS),
        ]
        for c, (icon, value, label, accent) in enumerate(values):
            KPICard(kpi_row, icon=icon, value=value, label=label, accent=accent).grid(
                row=0, column=c, padx=6, sticky="nsew"
            )
        for c in range(4):
            kpi_row.columnconfigure(c, weight=1)

        ctk.CTkFrame(self._right, height=1, fg_color=theme.BORDER).pack(fill="x", **pad)
        self._render_composition_table(b, pad)

        section = ctk.CTkFrame(self._right, fg_color="transparent")
        section.pack(fill="x", pady=(10, 16), **pad)
        section.columnconfigure(0, weight=1)
        section.columnconfigure(1, weight=1)

        vertus_values = self._split_values(b.get("vertus", "")) or metrics.get("vertus", [])
        chakras_values = self._split_values(b.get("chakras", b.get("chakra", ""))) or metrics.get("chakras", [])

        self._card_list(section, 0, "✨ Vertus", vertus_values, theme.ACCENT_AMETHYSTE)
        self._card_list(section, 1, "🌈 Chakras", chakras_values, theme.ACCENT_TURQUOISE)

    def _render_composition_table(self, bracelet: dict, pad: dict) -> None:
        ctk.CTkLabel(
            self._right,
            text="🧩  Composition",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(12, 8), **pad)

        wrap = ctk.CTkFrame(self._right, fg_color=theme.BG_SIDEBAR, corner_radius=14)
        wrap.pack(fill="x", **pad)

        headers = [
            ("Composant", 230),
            ("Type", 120),
            ("Quantite", 80),
            ("Prix unitaire", 110),
            ("Cout total", 110),
        ]

        head = ctk.CTkFrame(wrap, fg_color=theme.BG_CARD, corner_radius=0)
        head.pack(fill="x")
        for idx, (title, width) in enumerate(headers):
            ctk.CTkLabel(
                head,
                text=title,
                width=width,
                anchor="w",
                text_color=theme.TEXT_SECONDARY,
                font=ctk.CTkFont(size=11, weight="bold"),
            ).pack(side="left", padx=(12 if idx == 0 else 6, 0), pady=8)

        rows = bracelet.get("composition", [])
        total = 0.0
        if rows:
            for i, row in enumerate(rows):
                qty = int(row.get("quantite", 1) or 1)
                unit = float(row.get("cout_unitaire", 0.0) or 0.0)
                line_total = qty * unit
                total += line_total

                line = ctk.CTkFrame(wrap, fg_color=theme.BG_SIDEBAR if i % 2 else theme.BG_CARD, corner_radius=0)
                line.pack(fill="x")
                values = [
                    (row.get("composant", "—"), headers[0][1]),
                    (row.get("categorie", "—"), headers[1][1]),
                    (str(qty), headers[2][1]),
                    (self._money(unit), headers[3][1]),
                    (self._money(line_total), headers[4][1]),
                ]
                for idx, (value, width) in enumerate(values):
                    ctk.CTkLabel(line, text=str(value), width=width, anchor="w", text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(size=12)).pack(
                        side="left", padx=(12 if idx == 0 else 6, 0), pady=6
                    )
        else:
            ctk.CTkLabel(
                wrap,
                text="Aucune composition renseignee.",
                text_color=theme.TEXT_SECONDARY,
            ).pack(anchor="w", padx=12, pady=10)

        ctk.CTkLabel(
            self._right,
            text=f"Cout total composants: {self._money(total)}",
            text_color=theme.SUCCESS,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(10, 0), **pad)

    def _card_list(self, parent, col: int, title: str, values: list[str], accent: str) -> None:
        card = ctk.CTkFrame(parent, fg_color=theme.BG_SIDEBAR, corner_radius=14)
        card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0))
        ctk.CTkLabel(card, text=title, text_color=accent, font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=12, pady=(10, 6))
        content = " • ".join(values) if values else "Aucune information"
        ctk.CTkLabel(card, text=content, wraplength=380, justify="left", text_color=theme.TEXT_PRIMARY).pack(anchor="w", padx=12, pady=(0, 10))

    def _import_image(self, bracelet: dict) -> None:
        source = fd.askopenfilename(
            title="Importer une image bracelet",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")],
        )
        if not source:
            return

        ok, msg = import_image_for_item(self.db, bracelet, "bracelets", source)
        if not ok:
            mb.showerror("Image", msg)
            return

        if self.db:
            self.db.save_bracelets()
        metrics = self.db.calculate_bracelet_metrics(bracelet) if self.db else {}
        self._render_fiche(bracelet, metrics)

    def _export_fiche_vierge(self) -> None:
        """Genere une fiche de creation vierge (50 lignes) au format A4 et l'ouvre."""
        from pdf_generator import PDFGenerator
        dest = fd.asksaveasfilename(
            title="Enregistrer la fiche vierge",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="fiche_vierge_bracelet.pdf",
        )
        if not dest:
            return
        try:
            gen = PDFGenerator(self.db)
            gen.export_fiche_vierge_pdf(dest, nb_lignes=50)
            mb.showinfo("Fiche vierge", f"Fiche generee :\n{dest}")
            try:
                os.startfile(dest)
            except Exception:
                pass
        except Exception as exc:
            mb.showerror("Erreur PDF", str(exc))

    def _show_empty_fiche(self) -> None:
        for w in self._right.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._right, text="📿", font=ctk.CTkFont(size=42), text_color=theme.TEXT_SECONDARY).pack(expand=True, pady=(60, 8))
        ctk.CTkLabel(self._right, text="Selectionnez un bracelet", text_color=theme.TEXT_SECONDARY).pack()

    def _new_bracelet(self) -> None:
        BraceletEditor(self, self.db, "new", None, self._on_editor_submit)

    def _edit_bracelet(self) -> None:
        bracelet = self._current_bracelet()
        if bracelet is None:
            mb.showinfo("Bracelets", "Sélectionnez un bracelet à modifier.", parent=self)
            return
        BraceletEditor(self, self.db, "edit", dict(bracelet), self._on_editor_submit)

    def _duplicate_bracelet(self) -> None:
        bracelet = self._current_bracelet()
        if bracelet is None:
            mb.showinfo("Bracelets", "Sélectionnez un bracelet à dupliquer.", parent=self)
            return
        clone = dict(bracelet)
        clone["id"] = str(uuid.uuid4())
        BraceletEditor(self, self.db, "duplicate", clone, self._on_editor_submit)

    def _delete_bracelet(self) -> None:
        bracelet = self._current_bracelet()
        if bracelet is None:
            mb.showinfo("Bracelets", "Sélectionnez un bracelet à supprimer.", parent=self)
            return
        if not mb.askyesno("Suppression", "Supprimer définitivement ce bracelet ?", parent=self):
            return

        ok_backup, msg_backup = backup_before_delete(self.db, "bracelet")
        if not ok_backup:
            mb.showerror("Sauvegarde", msg_backup, parent=self)
            return

        bid = str(bracelet.get("id", ""))
        old_len = len(self.db.bracelets) if self.db else 0
        if self.db:
            self.db.bracelets = [b for b in self.db.bracelets if str(b.get("id", "")) != bid]
            if len(self.db.bracelets) != old_len:
                self.db.save_bracelets()

        append_local_history(self.db, "bracelet", "suppression", bracelet, None)
        self._selected_id = None
        self._metrics_cache.clear()
        self._load_list()
        self._refresh_global_index()

    def _on_editor_submit(self, payload: dict) -> bool:
        if not self.db:
            return False

        bid = str(payload.get("id", "") or "")
        if not bid:
            return False

        existing = next((b for b in self.db.bracelets if str(b.get("id", "")) == bid), None)
        if existing is not None:
            self.db.bracelets = [b for b in self.db.bracelets if str(b.get("id", "")) != bid]

        self.db.bracelets.append(payload)
        self.db.save_bracelets()

        if str(payload.get("reference", "")).startswith("BRA-"):
            try:
                num = int(str(payload.get("reference", "")).split("-", 1)[1])
                current = int(self.db.settings.get("phase1c_counter_bra", 0) or 0)
                if num > current:
                    self.db.settings["phase1c_counter_bra"] = num
                    self.db.save_settings()
            except (ValueError, IndexError):
                pass

        action = "modification" if existing is not None else "creation"
        append_local_history(self.db, "bracelet", action, payload, None)

        self._selected_id = bid
        self._metrics_cache.clear()
        if hasattr(self.db, "_invalidate_caches"):
            self.db._invalidate_caches()
        self._load_list()
        self._select_bracelet(bid, force=True)
        self._refresh_global_index()
        return True

    def _current_bracelet(self) -> dict | None:
        if not self._selected_id:
            return None
        return next((b for b in self._all_bracelets if str(b.get("id", "")) == self._selected_id), None)

    def _refresh_global_index(self) -> None:
        root = self.winfo_toplevel()
        if hasattr(root, "_global_index_dirty"):
            root._global_index_dirty = True

    @staticmethod
    def _split_values(raw) -> list[str]:
        if isinstance(raw, list):
            return [str(v).strip() for v in raw if str(v).strip()]
        text = str(raw or "").replace("\n", ",")
        return [s.strip() for s in text.split(",") if s.strip()]

    def apply_external_search(self, row: dict) -> None:
        target = str(row.get("id", ""))
        if target:
            self._search_var.set("")
            self._select_bracelet(target)

    @staticmethod
    def _money(value: float) -> str:
        return f"{value:,.2f} EUR".replace(",", " ").replace(".", ",")
