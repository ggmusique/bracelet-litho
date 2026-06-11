"""pages/produits.py
Page Produits - Lithotherapie Pro V2.
Phase 1C : liste + fiche produit avec photo et KPI de marge.
"""
from __future__ import annotations

import tkinter.filedialog as fd
import tkinter.messagebox as mb
import uuid

import customtkinter as ctk

import theme
from pages.crud_editors import ProductEditor
from phase1c_services import import_image_for_item, load_ctk_image
from phase1c_services import append_local_history, backup_before_delete
from widgets import Divider, KPICard, SectionHeader


class ProduitsPage(ctk.CTkFrame):
    def __init__(self, parent, db=None, **kwargs) -> None:
        kwargs.setdefault("fg_color", theme.BG_MAIN)
        super().__init__(parent, **kwargs)
        self.db = db
        self._all_products: list[dict] = []
        self._filtered_products: list[dict] = []
        self._selected_id: str | None = None
        self._list_buttons: dict[str, ctk.CTkButton] = {}
        self._search_after_id: str | None = None
        self._search_debounce_ms = 250
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._schedule_filter())
        self._cat_var = ctk.StringVar(value="Toutes")
        self._photo_img = None
        self._build()
        self._load_data()

    def _build(self) -> None:
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=32, pady=(28, 0))
        SectionHeader(
            top,
            title="🛍  Produits",
            subtitle="Catalogue, marges et fiches produits",
        ).pack(side="left", fill="x", expand=True)

        Divider(self).pack(fill="x", padx=32, pady=20)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        self._left = ctk.CTkFrame(body, fg_color=theme.BG_SIDEBAR, corner_radius=20, width=330)
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
        ).pack(fill="x", padx=14, pady=(14, 8))

        actions = ctk.CTkFrame(self._left, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkButton(
            actions,
            text="+ Nouveau produit",
            height=30,
            corner_radius=10,
            fg_color=theme.SUCCESS,
            hover_color=theme.ACCENT_TURQUOISE,
            command=self._new_product,
        ).pack(fill="x", pady=(0, 4))
        ctk.CTkButton(
            actions,
            text="✏ Modifier",
            height=30,
            corner_radius=10,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            command=self._edit_product,
        ).pack(fill="x", pady=2)
        ctk.CTkButton(
            actions,
            text="📄 Dupliquer",
            height=30,
            corner_radius=10,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            command=self._duplicate_product,
        ).pack(fill="x", pady=2)
        ctk.CTkButton(
            actions,
            text="🗑 Supprimer",
            height=30,
            corner_radius=10,
            fg_color=theme.DANGER,
            hover_color=theme.WARNING,
            command=self._delete_product,
        ).pack(fill="x", pady=(2, 0))

        self._cat_menu = ctk.CTkOptionMenu(
            self._left,
            variable=self._cat_var,
            values=["Toutes"],
            height=36,
            corner_radius=12,
            fg_color=theme.BG_CARD,
            button_color=theme.BG_CARD,
            button_hover_color=theme.BG_CARD_HOVER,
            command=lambda _: self._apply_filter(),
        )
        self._cat_menu.pack(fill="x", padx=14, pady=(0, 10))

        ctk.CTkFrame(self._left, height=1, fg_color=theme.BORDER).pack(fill="x", padx=14)

        self._list_scroll = ctk.CTkScrollableFrame(
            self._left,
            fg_color="transparent",
            scrollbar_button_color=theme.BORDER,
        )
        self._list_scroll.pack(fill="both", expand=True, padx=6, pady=6)

        self._right = ctk.CTkScrollableFrame(
            body,
            fg_color=theme.BG_CARD,
            corner_radius=20,
            scrollbar_button_color=theme.BORDER,
        )
        self._right.pack(side="left", fill="both", expand=True)
        self._show_empty_fiche()

    def _load_data(self) -> None:
        if not self.db:
            return

        self._all_products = sorted(self.db.products, key=lambda p: str(p.get("nom", "")).lower())
        cats = sorted({str(p.get("categorie", "")).strip() for p in self._all_products if p.get("categorie")})
        self._cat_menu.configure(values=["Toutes"] + cats)
        if self._cat_var.get() not in ["Toutes"] + cats:
            self._cat_var.set("Toutes")
        self._apply_filter()

    def _apply_filter(self) -> None:
        q = self._search_var.get().strip().lower()
        cat = self._cat_var.get()

        self._filtered_products = [
            p
            for p in self._all_products
            if (not q or q in str(p.get("nom", "")).lower() or q in str(p.get("sku", "")).lower() or q in str(p.get("reference", "")).lower())
            and (cat == "Toutes" or str(p.get("categorie", "")) == cat)
        ]
        self._render_list()

    def _schedule_filter(self) -> None:
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
            self._search_after_id = None
        self._search_after_id = self.after(self._search_debounce_ms, self._apply_filter)

    def _render_list(self) -> None:
        for w in self._list_scroll.winfo_children():
            w.destroy()
        self._list_buttons.clear()

        if not self._filtered_products:
            ctk.CTkLabel(self._list_scroll, text="Aucun produit", text_color=theme.TEXT_SECONDARY).pack(pady=20)
            self._show_empty_fiche()
            return

        for p in self._filtered_products:
            pid = str(p.get("id", ""))
            stock = int(p.get("stock", 0) or 0)

            row = ctk.CTkFrame(self._list_scroll, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=2)

            ref = p.get("sku", "") or p.get("reference", "—")
            line2 = f"  {ref}   ·   Stock: {stock}"

            btn = ctk.CTkButton(
                row,
                text=f"  {p.get('nom', 'Sans nom')}\n{line2}",
                anchor="w",
                height=52,
                corner_radius=12,
                fg_color="transparent",
                hover_color=theme.BG_CARD,
                text_color=theme.TEXT_PRIMARY,
                font=ctk.CTkFont(size=12),
                command=lambda rid=pid: self._select_product(rid),
            )
            btn.pack(fill="x")

            self._list_buttons[pid] = btn

        target = self._selected_id if self._selected_id in self._list_buttons else str(self._filtered_products[0].get("id", ""))
        if target and target != self._selected_id:
            self._select_product(target)
        elif target:
            for rid, btn in self._list_buttons.items():
                active = rid == target
                btn.configure(
                    fg_color=theme.BG_CARD if active else "transparent",
                    text_color=theme.ACCENT_TURQUOISE if active else theme.TEXT_PRIMARY,
                )

    def _select_product(self, product_id: str) -> None:
        current = next((p for p in self._filtered_products if str(p.get("id", "")) == product_id), None)
        if not current:
            return

        if self._selected_id == product_id:
            return

        self._selected_id = product_id
        for rid, btn in self._list_buttons.items():
            active = rid == product_id
            btn.configure(
                fg_color=theme.BG_CARD if active else "transparent",
                text_color=theme.ACCENT_TURQUOISE if active else theme.TEXT_PRIMARY,
            )

        self._render_fiche(current)

    def _render_fiche(self, p: dict) -> None:
        for w in self._right.winfo_children():
            w.destroy()

        pad = {"padx": 24}

        ctk.CTkLabel(
            self._right,
            text="FICHE PRODUIT",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(20, 4), **pad)
        ctk.CTkFrame(self._right, height=1, fg_color=theme.BORDER).pack(fill="x", **pad)

        top = ctk.CTkFrame(self._right, fg_color="transparent")
        top.pack(fill="x", pady=16, **pad)

        photo_box = ctk.CTkFrame(top, width=220, height=220, fg_color=theme.BG_SIDEBAR, corner_radius=20)
        photo_box.pack(side="left", padx=(0, 24), anchor="n")
        photo_box.pack_propagate(False)

        self._photo_img = load_ctk_image(self.db, p, size=(200, 200), use_thumb=False)
        if self._photo_img is None:
            ctk.CTkLabel(photo_box, text="📷", font=ctk.CTkFont(size=44), text_color=theme.TEXT_SECONDARY).pack(pady=(62, 4))
            ctk.CTkLabel(photo_box, text="Image indisponible", text_color=theme.TEXT_SECONDARY).pack()
        else:
            ctk.CTkLabel(photo_box, text="", image=self._photo_img).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkButton(
            photo_box,
            text="Importer une image",
            height=30,
            corner_radius=10,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            command=lambda: self._import_image(p),
        ).pack(side="bottom", fill="x", padx=10, pady=10)

        info = ctk.CTkFrame(top, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)

        pa = float(p.get("prix_achat", 0.0) or 0.0)
        pv = float(p.get("prix_vente", 0.0) or 0.0)
        marge = pv - pa

        details = [
            ("Reference", p.get("sku", "") or p.get("reference", "—")),
            ("Nom", p.get("nom", "—")),
            ("Prix de revient", self._money(pa)),
            ("Prix de vente", self._money(pv)),
            ("Marge", self._money(marge)),
            ("Stock", str(int(p.get("stock", 0) or 0))),
            ("Categorie", p.get("categorie", "—")),
        ]

        for label, value in details:
            row = ctk.CTkFrame(info, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=label, width=130, anchor="w", text_color=theme.TEXT_SECONDARY).pack(side="left")
            ctk.CTkLabel(row, text=str(value), anchor="w", text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(weight="bold")).pack(side="left")

        kpi = ctk.CTkFrame(self._right, fg_color="transparent")
        kpi.pack(fill="x", pady=(0, 14), **pad)
        cards = [
            ("💶", self._money(pa), "Prix revient", theme.INFO),
            ("🏷", self._money(pv), "Prix vente", theme.ACCENT_TURQUOISE),
            ("📈", self._money(marge), "Marge", theme.SUCCESS if marge >= 0 else theme.DANGER),
            ("📦", str(int(p.get("stock", 0) or 0)), "Stock", theme.WARNING),
        ]
        for i, (icon, value, label, accent) in enumerate(cards):
            KPICard(kpi, icon=icon, value=value, label=label, accent=accent).grid(row=0, column=i, padx=6, sticky="nsew")
        for i in range(4):
            kpi.columnconfigure(i, weight=1)

    def _import_image(self, product: dict) -> None:
        source = fd.askopenfilename(
            title="Importer une image produit",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")],
        )
        if not source:
            return

        ok, msg = import_image_for_item(self.db, product, "produits", source)
        if not ok:
            mb.showerror("Image", msg)
            return

        if self.db:
            self.db.save_products()
        self._render_fiche(product)

    def _show_empty_fiche(self) -> None:
        for w in self._right.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._right, text="🛍", font=ctk.CTkFont(size=42), text_color=theme.TEXT_SECONDARY).pack(expand=True, pady=(60, 8))
        ctk.CTkLabel(self._right, text="Selectionnez un produit", text_color=theme.TEXT_SECONDARY).pack()

    def _new_product(self) -> None:
        ProductEditor(self, self.db, "new", None, self._on_editor_submit)

    def _edit_product(self) -> None:
        product = self._current_product()
        if product is None:
            mb.showinfo("Produits", "Sélectionnez un produit à modifier.", parent=self)
            return
        ProductEditor(self, self.db, "edit", dict(product), self._on_editor_submit)

    def _duplicate_product(self) -> None:
        product = self._current_product()
        if product is None:
            mb.showinfo("Produits", "Sélectionnez un produit à dupliquer.", parent=self)
            return
        clone = dict(product)
        clone["id"] = str(uuid.uuid4())
        ProductEditor(self, self.db, "duplicate", clone, self._on_editor_submit)

    def _delete_product(self) -> None:
        product = self._current_product()
        if product is None:
            mb.showinfo("Produits", "Sélectionnez un produit à supprimer.", parent=self)
            return
        if not mb.askyesno("Suppression", "Supprimer définitivement ce produit ?", parent=self):
            return

        ok_backup, msg_backup = backup_before_delete(self.db, "produit")
        if not ok_backup:
            mb.showerror("Sauvegarde", msg_backup, parent=self)
            return

        pid = str(product.get("id", ""))
        old_len = len(self.db.products) if self.db else 0
        if self.db:
            self.db.products = [p for p in self.db.products if str(p.get("id", "")) != pid]
            if len(self.db.products) != old_len:
                self.db.save_products()

        append_local_history(self.db, "produit", "suppression", product, None)
        self._selected_id = None
        self._load_data()
        self._refresh_global_index()

    def _on_editor_submit(self, payload: dict) -> bool:
        if not self.db:
            return False

        pid = str(payload.get("id", "") or "")
        if not pid:
            return False

        existing = next((p for p in self.db.products if str(p.get("id", "")) == pid), None)
        if existing is not None:
            self.db.products = [p for p in self.db.products if str(p.get("id", "")) != pid]

        self.db.products.append(payload)
        self.db.save_products()

        ref = str(payload.get("sku", payload.get("reference", "")) or "").upper()
        if ref.startswith("PRO-"):
            try:
                num = int(ref.split("-", 1)[1])
                current = int(self.db.settings.get("phase1c_counter_pro", 0) or 0)
                if num > current:
                    self.db.settings["phase1c_counter_pro"] = num
                    self.db.save_settings()
            except (ValueError, IndexError):
                pass

        action = "modification" if existing is not None else "creation"
        append_local_history(self.db, "produit", action, payload, None)

        self._selected_id = pid
        self._load_data()
        self._select_product(pid)
        self._refresh_global_index()
        return True

    def _current_product(self) -> dict | None:
        if not self._selected_id:
            return None
        return next((p for p in self._all_products if str(p.get("id", "")) == self._selected_id), None)

    def _refresh_global_index(self) -> None:
        root = self.winfo_toplevel()
        if hasattr(root, "_global_index_dirty"):
            root._global_index_dirty = True

    def apply_external_search(self, row: dict) -> None:
        target = str(row.get("id", ""))
        if target:
            self._search_var.set("")
            self._select_product(target)

    @staticmethod
    def _money(value: float) -> str:
        return f"{value:,.2f} EUR".replace(",", " ").replace(".", ",")
