"""pages/composants.py
Page Composants - Lithotherapie Pro V2.
Phase 1C.2 : optimisation ciblée de la fiche composant (update incrémental).
"""
from __future__ import annotations

import time
import tkinter.filedialog as fd
import tkinter.messagebox as mb
from datetime import datetime
import uuid

import customtkinter as ctk

import theme
from pages.crud_editors import ComponentEditor
from phase1c_services import (
    append_local_history,
    backup_before_delete,
    import_image_for_item,
    load_ctk_image,
    open_supplier_site,
)
from widgets import Divider, KPICard, SectionHeader

_SUBCATEGORIES: list[tuple[str, str]] = [
    ("💎", "Pierres"),
    ("✨", "Breloques"),
    ("⭕", "Intercalaires"),
    ("🔒", "Cache-nœuds"),
]

_PAGE_SUB_TO_EDITOR_CAT: dict[str, str] = {
    "Pierres": "Pierre",
    "Breloques": "Breloque",
    "Intercalaires": "Intercalaire",
    "Cache-nœuds": "Cache-noeud",
}

_EDITOR_CAT_TO_PAGE_SUB: dict[str, str] = {v: k for k, v in _PAGE_SUB_TO_EDITOR_CAT.items()}
_MAX_USED_BRACELETS = 8


class ComposantsPage(ctk.CTkFrame):
    def __init__(self, parent, db=None, **kwargs) -> None:
        kwargs.setdefault("fg_color", theme.BG_MAIN)
        super().__init__(parent, **kwargs)
        self.db = db
        self._active_sub: str = "Pierres"
        self._all_items: list[dict] = []
        self._all_by_id: dict[str, dict] = {}
        self._filtered_ids: list[str] = []
        self._selected_id: str | None = None
        self._styled_selected_id: str | None = None
        self._list_buttons: dict[str, ctk.CTkButton] = {}
        self._search_after_id: str | None = None
        self._search_debounce_ms = 250
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._schedule_filter())
        self._stock_filter_var = ctk.StringVar(value="Tous")
        self._sort_var = ctk.StringVar(value="Nom A-Z")
        for _v in (self._stock_filter_var, self._sort_var):
            _v.trace_add("write", lambda *_: self._apply_filter())

        self._item_cache: dict[str, dict] = {}
        self._current_supplier_url = ""
        self._current_image_key: str | None = None
        self._photo_img = None

        self._perf_detail: dict[str, list[float]] = {
            "selection_composant": [],
            "chargement_image": [],
            "maj_kpi": [],
            "maj_fournisseur": [],
            "rafraichissement_fiche": [],
        }

        self._build()
        self._load_data()

    def _build(self) -> None:
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=32, pady=(28, 0))
        SectionHeader(
            top,
            title="📦  Composants",
            subtitle="Fiches techniques, fournisseurs et photos",
        ).pack(side="left", fill="x", expand=True)

        Divider(self).pack(fill="x", padx=32, pady=20)

        self._global_kpi_row = ctk.CTkFrame(self, fg_color="transparent")
        self._global_kpi_row.pack(fill="x", padx=32, pady=(0, 14))
        self._kpi_total = KPICard(self._global_kpi_row, icon="🧩", value="0", label="Total composants", accent=theme.INFO)
        self._kpi_stock_total = KPICard(self._global_kpi_row, icon="💰", value=self._money(0.0), label="Valeur stock total", accent=theme.SUCCESS)
        self._kpi_rupture = KPICard(self._global_kpi_row, icon="🚨", value="0", label="En rupture", accent=theme.DANGER)
        self._kpi_stock_avg = KPICard(self._global_kpi_row, icon="📊", value="0", label="Stock moyen", accent=theme.ACCENT_TURQUOISE)
        self._kpi_total.grid(row=0, column=0, padx=6, sticky="nsew")
        self._kpi_stock_total.grid(row=0, column=1, padx=6, sticky="nsew")
        self._kpi_rupture.grid(row=0, column=2, padx=6, sticky="nsew")
        self._kpi_stock_avg.grid(row=0, column=3, padx=6, sticky="nsew")
        for i in range(4):
            self._global_kpi_row.columnconfigure(i, weight=1)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        self._build_list_panel(body)
        self._build_fiche_panel(body)

    def _build_list_panel(self, parent) -> None:
        left = ctk.CTkFrame(parent, fg_color=theme.BG_SIDEBAR, corner_radius=20, width=340)
        left.pack(side="left", fill="y", padx=(0, 16))
        left.pack_propagate(False)

        tabs = ctk.CTkFrame(left, fg_color="transparent")
        tabs.pack(fill="x", padx=12, pady=(14, 10))
        self._sub_buttons: dict[str, ctk.CTkButton] = {}
        for icon, name in _SUBCATEGORIES:
            btn = ctk.CTkButton(
                tabs,
                text=f"{icon} {name}",
                height=34,
                corner_radius=12,
                fg_color="transparent",
                text_color=theme.TEXT_SECONDARY,
                hover_color=theme.BG_CARD,
                border_width=1,
                border_color=theme.BORDER,
                command=lambda n=name: self._switch_sub(n),
            )
            btn.pack(fill="x", pady=2)
            self._sub_buttons[name] = btn

        actions = ctk.CTkFrame(left, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(6, 10))
        ctk.CTkButton(
            actions,
            text="+ Nouveau",
            height=30,
            corner_radius=10,
            fg_color=theme.SUCCESS,
            hover_color=theme.ACCENT_TURQUOISE,
            command=self._new_component,
        ).pack(fill="x", pady=(0, 4))
        ctk.CTkButton(
            actions,
            text="✏ Modifier",
            height=30,
            corner_radius=10,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            command=self._edit_component,
        ).pack(fill="x", pady=2)
        ctk.CTkButton(
            actions,
            text="📄 Dupliquer",
            height=30,
            corner_radius=10,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            command=self._duplicate_component,
        ).pack(fill="x", pady=2)
        ctk.CTkButton(
            actions,
            text="🗑 Supprimer",
            height=30,
            corner_radius=10,
            fg_color=theme.DANGER,
            hover_color=theme.WARNING,
            command=self._delete_component,
        ).pack(fill="x", pady=(2, 0))

        ctk.CTkEntry(
            left,
            textvariable=self._search_var,
            placeholder_text="Rechercher (nom, ref, fournisseur)",
            height=36,
            corner_radius=12,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
        ).pack(fill="x", padx=12, pady=(0, 10))
        cfilters = ctk.CTkFrame(left, fg_color="transparent")
        cfilters.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkOptionMenu(cfilters, variable=self._stock_filter_var, values=["Tous", "En stock", "Rupture (0)"], fg_color=theme.BG_INPUT, button_color=theme.BG_CARD, button_hover_color=theme.BG_CARD_HOVER).pack(fill="x", pady=2)
        ctk.CTkOptionMenu(cfilters, variable=self._sort_var, values=["Nom A-Z", "Nom Z-A", "Prix croissant", "Prix decroissant", "Stock croissant", "Stock decroissant"], fg_color=theme.BG_INPUT, button_color=theme.BG_CARD, button_hover_color=theme.BG_CARD_HOVER).pack(fill="x", pady=2)

        ctk.CTkFrame(left, height=1, fg_color=theme.BORDER).pack(fill="x", padx=12)

        self._list_scroll = ctk.CTkScrollableFrame(
            left,
            fg_color="transparent",
            scrollbar_button_color=theme.BORDER,
        )
        self._list_scroll.pack(fill="both", expand=True, padx=6, pady=6)

        self._activate_tab(self._active_sub)

    def _build_fiche_panel(self, parent) -> None:
        self._right = ctk.CTkScrollableFrame(
            parent,
            fg_color=theme.BG_CARD,
            corner_radius=20,
            scrollbar_button_color=theme.BORDER,
        )
        self._right.pack(side="left", fill="both", expand=True)

        pad = {"padx": 24}

        ctk.CTkLabel(
            self._right,
            text="FICHE COMPOSANT",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(20, 4), **pad)
        ctk.CTkFrame(self._right, height=1, fg_color=theme.BORDER).pack(fill="x", **pad)

        top = ctk.CTkFrame(self._right, fg_color="transparent")
        top.pack(fill="x", pady=16, **pad)

        photo_box = ctk.CTkFrame(top, width=220, height=220, fg_color=theme.BG_SIDEBAR, corner_radius=20)
        photo_box.pack(side="left", padx=(0, 24), anchor="n")
        photo_box.pack_propagate(False)

        self._photo_lbl = ctk.CTkLabel(photo_box, text="", image=None)
        self._photo_lbl.place(relx=0.5, rely=0.5, anchor="center")

        self._photo_icon_lbl = ctk.CTkLabel(photo_box, text="📷", font=ctk.CTkFont(size=44), text_color=theme.TEXT_SECONDARY)
        self._photo_icon_lbl.place(relx=0.5, rely=0.42, anchor="center")
        self._photo_text_lbl = ctk.CTkLabel(photo_box, text="Image indisponible", text_color=theme.TEXT_SECONDARY)
        self._photo_text_lbl.place(relx=0.5, rely=0.58, anchor="center")

        self._import_btn = ctk.CTkButton(
            photo_box,
            text="Importer une image",
            height=30,
            corner_radius=10,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            command=self._import_image_current,
        )
        self._import_btn.pack(side="bottom", pady=10, padx=10, fill="x")

        info = ctk.CTkFrame(top, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)

        self._detail_values: dict[str, ctk.CTkLabel] = {}
        for key, label in [
            ("reference", "Reference"),
            ("nom", "Nom"),
            ("categorie", "Categorie"),
            ("prix_unitaire", "Prix unitaire"),
            ("stock", "Stock"),
            ("fournisseur", "Fournisseur"),
            ("updated", "Derniere modification"),
            ("valeur_stock", "Valeur du stock"),
        ]:
            row = ctk.CTkFrame(info, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=label, width=160, anchor="w", text_color=theme.TEXT_SECONDARY).pack(side="left")
            val = ctk.CTkLabel(row, text="—", anchor="w", text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(weight="bold"))
            val.pack(side="left")
            self._detail_values[key] = val

        self._kpi_row = ctk.CTkFrame(self._right, fg_color="transparent")
        self._kpi_row.pack(fill="x", pady=(0, 14), **pad)
        self._kpi_stock = KPICard(self._kpi_row, icon="📦", value="—", label="Stock", accent=theme.ACCENT_TURQUOISE)
        self._kpi_price = KPICard(self._kpi_row, icon="💶", value="—", label="Prix unitaire", accent=theme.INFO)
        self._kpi_value = KPICard(self._kpi_row, icon="💰", value="—", label="Valeur stock", accent=theme.SUCCESS)
        self._kpi_stock.grid(row=0, column=0, padx=6, sticky="nsew")
        self._kpi_price.grid(row=0, column=1, padx=6, sticky="nsew")
        self._kpi_value.grid(row=0, column=2, padx=6, sticky="nsew")
        for i in range(3):
            self._kpi_row.columnconfigure(i, weight=1)

        self._quick_restock_btn = ctk.CTkButton(
            self._right,
            text="⚡ Réappro rapide",
            height=34,
            corner_radius=12,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            border_color=theme.ACCENT_TURQUOISE,
            border_width=1,
            state="disabled",
            command=self._quick_restock,
        )
        self._quick_restock_btn.pack(anchor="w", pady=(0, 14), **pad)

        ctk.CTkFrame(self._right, height=1, fg_color=theme.BORDER).pack(fill="x", **pad)

        ctk.CTkLabel(
            self._right,
            text="🏷  Fiche fournisseur",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(12, 8), **pad)

        supplier_wrap = ctk.CTkFrame(self._right, fg_color=theme.BG_SIDEBAR, corner_radius=12)
        supplier_wrap.pack(fill="x", pady=(0, 16), **pad)

        self._supplier_values: dict[str, ctk.CTkLabel] = {}
        for key, label in [
            ("name", "Nom fournisseur"),
            ("ref", "Reference fournisseur"),
            ("site", "Site web"),
            ("email", "Email"),
            ("price", "Prix d'achat"),
            ("last_buy", "Date dernier achat"),
        ]:
            row = ctk.CTkFrame(supplier_wrap, fg_color="transparent")
            row.pack(fill="x", pady=2, padx=14)
            ctk.CTkLabel(row, text=label, width=180, anchor="w", text_color=theme.TEXT_SECONDARY).pack(side="left")
            val = ctk.CTkLabel(row, text="—", anchor="w", text_color=theme.TEXT_PRIMARY)
            val.pack(side="left")
            self._supplier_values[key] = val

        self._supplier_btn = ctk.CTkButton(
            supplier_wrap,
            text="Ouvrir le site fournisseur",
            height=34,
            corner_radius=12,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            border_color=theme.ACCENT_TURQUOISE,
            border_width=1,
            state="disabled",
            command=self._open_current_supplier,
        )
        self._supplier_btn.pack(anchor="w", pady=(10, 12), padx=14)

        ctk.CTkLabel(
            self._right,
            text="🔗  Utilisé dans les bracelets",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(2, 8), **pad)

        self._used_bracelets_box = ctk.CTkFrame(self._right, fg_color="transparent")
        self._used_bracelets_box.pack(fill="x", pady=(0, 16), **pad)

        self._show_empty_fiche()

    def _get_source_and_saver(self) -> tuple[list[dict], callable]:
        if not self.db:
            return [], lambda: None
        mapping = {
            "Pierres": (self.db.stones, self.db.save_stones),
            "Breloques": (getattr(self.db, "breloques", []), getattr(self.db, "save_breloques", lambda: None)),
            "Intercalaires": (getattr(self.db, "intercalaires", []), getattr(self.db, "save_intercalaires", lambda: None)),
            "Cache-nœuds": (getattr(self.db, "finitions", []), getattr(self.db, "save_finitions", lambda: None)),
        }
        return mapping.get(self._active_sub, ([], lambda: None))

    def _load_data(self) -> None:
        source, _ = self._get_source_and_saver()
        self._all_items = sorted(source, key=lambda x: str(x.get("nom", "")).lower())
        self._all_by_id = {str(i.get("id", "")): i for i in self._all_items if i.get("id")}
        self._rebuild_item_cache()
        self._update_global_kpis()
        self._apply_filter()

    def _rebuild_item_cache(self) -> None:
        self._item_cache.clear()
        for item_id, item in self._all_by_id.items():
            price = self._item_price(item)
            stock = int(item.get("stock", 0) or 0)
            self._item_cache[item_id] = {
                "price": price,
                "stock": stock,
                "value": stock * price,
                "updated": self._format_date(item.get("updated_at", "")),
                "supplier": {
                    "name": item.get("fournisseur", "—") or "—",
                    "ref": item.get("fournisseur_ref", "—") or "—",
                    "site": item.get("fournisseur_site", "—") or "—",
                    "email": item.get("fournisseur_email", "—") or "—",
                    "last_buy": item.get("date_dernier_achat", "—") or "—",
                },
                "photo_key": str(item.get("photo_thumb", "") or item.get("photo", "") or ""),
            }

    def _schedule_filter(self) -> None:
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
            self._search_after_id = None
        self._search_after_id = self.after(self._search_debounce_ms, self._apply_filter)

    def _apply_filter(self) -> None:
        q = self._search_var.get().strip().lower()
        stock_f = self._stock_filter_var.get()

        def _match(item):
            if q and q not in str(item.get("nom", "")).lower() and q not in str(item.get("reference", "")).lower() and q not in str(item.get("fournisseur", "")).lower():
                return False
            st = int(item.get("stock", 0) or 0)
            if stock_f == "En stock" and st <= 0:
                return False
            if stock_f == "Rupture (0)" and st > 0:
                return False
            return True

        items = [(iid, it) for iid, it in self._all_by_id.items() if _match(it)]

        sort_mode = self._sort_var.get()
        if sort_mode == "Nom Z-A":
            items.sort(key=lambda kv: str(kv[1].get("nom", "")).lower(), reverse=True)
        elif sort_mode == "Prix croissant":
            items.sort(key=lambda kv: self._item_price(kv[1]))
        elif sort_mode == "Prix decroissant":
            items.sort(key=lambda kv: self._item_price(kv[1]), reverse=True)
        elif sort_mode == "Stock croissant":
            items.sort(key=lambda kv: int(kv[1].get("stock", 0) or 0))
        elif sort_mode == "Stock decroissant":
            items.sort(key=lambda kv: int(kv[1].get("stock", 0) or 0), reverse=True)
        else:
            items.sort(key=lambda kv: str(kv[1].get("nom", "")).lower())

        self._filtered_ids = [iid for iid, _ in items]
        self._render_list()

    def _render_list(self) -> None:
        for w in self._list_scroll.winfo_children():
            w.destroy()
        self._list_buttons.clear()

        if not self._filtered_ids:
            ctk.CTkLabel(self._list_scroll, text="Aucun composant trouve", text_color=theme.TEXT_SECONDARY).pack(pady=20)
            self._show_empty_fiche()
            return

        for item_id in self._filtered_ids:
            item = self._all_by_id[item_id]
            stock = int(item.get("stock", 0) or 0)
            badge = self._stock_badge(stock)
            line2 = f"  {item.get('reference', '—')}   ·   {badge} {stock}"

            row = ctk.CTkFrame(self._list_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2, padx=4)

            btn = ctk.CTkButton(
                row,
                text=f"  {item.get('nom', '—')}\n{line2}",
                anchor="w",
                height=52,
                corner_radius=12,
                fg_color="transparent",
                hover_color=theme.BG_CARD,
                text_color=theme.TEXT_PRIMARY,
                font=ctk.CTkFont(size=12),
                command=lambda rid=item_id: self._select_item(rid),
            )
            btn.pack(fill="x")
            self._list_buttons[item_id] = btn

        target = self._selected_id if self._selected_id in self._list_buttons else self._filtered_ids[0]
        if target and target != self._selected_id:
            self._select_item(target)
        elif target:
            self._apply_selected_style(target)

    def _select_item(self, item_id: str) -> None:
        item = self._all_by_id.get(item_id)
        if item is None:
            return

        if self._selected_id == item_id:
            self._apply_selected_style(item_id)
            return

        t_total = time.perf_counter()

        self._selected_id = item_id
        self._apply_selected_style(item_id)

        t_img = time.perf_counter()
        self._update_image(item_id, item)
        self._perf_detail["chargement_image"].append(time.perf_counter() - t_img)

        t_kpi = time.perf_counter()
        self._update_kpis(item_id)
        self._perf_detail["maj_kpi"].append(time.perf_counter() - t_kpi)

        t_sup = time.perf_counter()
        self._update_supplier(item_id)
        self._perf_detail["maj_fournisseur"].append(time.perf_counter() - t_sup)

        t_ref = time.perf_counter()
        self._update_details(item_id, item)
        self._perf_detail["rafraichissement_fiche"].append(time.perf_counter() - t_ref)

        self._perf_detail["selection_composant"].append(time.perf_counter() - t_total)

    def _apply_selected_style(self, selected_id: str) -> None:
        prev_id = self._styled_selected_id
        if prev_id and prev_id != selected_id:
            prev_btn = self._list_buttons.get(prev_id)
            if prev_btn is not None:
                prev_btn.configure(fg_color="transparent", text_color=theme.TEXT_PRIMARY)

        current_btn = self._list_buttons.get(selected_id)
        if current_btn is not None:
            current_btn.configure(fg_color=theme.BG_CARD, text_color=theme.ACCENT_TURQUOISE)
            self._styled_selected_id = selected_id

    def _update_image(self, item_id: str, item: dict) -> None:
        cached = self._item_cache.get(item_id, {})
        image_key = str(cached.get("photo_key", ""))

        if self._current_image_key == image_key and self._photo_img is not None:
            self._photo_lbl.configure(image=self._photo_img)
            self._photo_icon_lbl.place_forget()
            self._photo_text_lbl.place_forget()
            return

        self._photo_img = load_ctk_image(self.db, item, size=(200, 200), use_thumb=True)
        self._current_image_key = image_key

        if self._photo_img is None:
            self._photo_lbl.configure(image=None)
            self._photo_icon_lbl.place(relx=0.5, rely=0.42, anchor="center")
            self._photo_text_lbl.place(relx=0.5, rely=0.58, anchor="center")
        else:
            self._photo_lbl.configure(image=self._photo_img)
            self._photo_icon_lbl.place_forget()
            self._photo_text_lbl.place_forget()

    def _update_kpis(self, item_id: str) -> None:
        cached = self._item_cache.get(item_id, {})
        stock = int(cached.get("stock", 0))
        price = float(cached.get("price", 0.0))
        value = float(cached.get("value", 0.0))
        self._kpi_stock.set_value(str(stock))
        self._kpi_price.set_value(self._money(price))
        self._kpi_value.set_value(self._money(value))

    def _update_supplier(self, item_id: str) -> None:
        supplier = self._item_cache.get(item_id, {}).get("supplier", {})
        self._supplier_values["name"].configure(text=str(supplier.get("name", "—")))
        self._supplier_values["ref"].configure(text=str(supplier.get("ref", "—")))
        self._supplier_values["site"].configure(text=str(supplier.get("site", "—")))
        self._supplier_values["email"].configure(text=str(supplier.get("email", "—")))
        self._supplier_values["last_buy"].configure(text=str(supplier.get("last_buy", "—")))

        price = float(self._item_cache.get(item_id, {}).get("price", 0.0))
        self._supplier_values["price"].configure(text=self._money(price))

        self._current_supplier_url = str(supplier.get("site", "") or "").strip()
        self._supplier_btn.configure(state="normal" if self._current_supplier_url else "disabled")

    def _update_details(self, item_id: str, item: dict) -> None:
        cached = self._item_cache.get(item_id, {})
        self._detail_values["reference"].configure(text=str(item.get("reference", "—")))
        self._detail_values["nom"].configure(text=str(item.get("nom", "—")))
        self._detail_values["categorie"].configure(text=self._active_sub)
        self._detail_values["prix_unitaire"].configure(text=self._money(float(cached.get("price", 0.0))))
        self._detail_values["stock"].configure(text=str(int(cached.get("stock", 0))))
        self._detail_values["fournisseur"].configure(text=str(cached.get("supplier", {}).get("name", "—")))
        self._detail_values["updated"].configure(text=str(cached.get("updated", "—")))
        self._detail_values["valeur_stock"].configure(text=self._money(float(cached.get("value", 0.0))))
        self._quick_restock_btn.configure(state="normal")
        self._update_used_in_bracelets(item_id, item)

    def _import_image_current(self) -> None:
        if not self._selected_id:
            return
        item = self._all_by_id.get(self._selected_id)
        if item is None:
            return
        self._import_image(item)

    def _import_image(self, item: dict) -> None:
        source = fd.askopenfilename(
            title="Importer une image composant",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")],
        )
        if not source:
            return

        ok, msg = import_image_for_item(self.db, item, "composants", source)
        if not ok:
            mb.showerror("Image", msg)
            return

        _, saver = self._get_source_and_saver()
        saver()
        self._rebuild_item_cache()
        self._current_image_key = None
        if self._selected_id:
            self._select_item(self._selected_id)

    def _open_current_supplier(self) -> None:
        if self._current_supplier_url:
            open_supplier_site(self._current_supplier_url)

    def _show_empty_fiche(self) -> None:
        self._photo_lbl.configure(image=None)
        self._photo_icon_lbl.place(relx=0.5, rely=0.42, anchor="center")
        self._photo_text_lbl.place(relx=0.5, rely=0.58, anchor="center")

        for lbl in self._detail_values.values():
            lbl.configure(text="—")
        for lbl in self._supplier_values.values():
            lbl.configure(text="—")

        self._kpi_stock.set_value("0")
        self._kpi_price.set_value(self._money(0.0))
        self._kpi_value.set_value(self._money(0.0))
        self._supplier_btn.configure(state="disabled")
        self._quick_restock_btn.configure(state="disabled")
        self._current_supplier_url = ""
        self._render_used_bracelets([])

    def _new_component(self) -> None:
        editor_cat = _PAGE_SUB_TO_EDITOR_CAT.get(self._active_sub, "Pierre")
        ComponentEditor(self, self.db, "new", None, editor_cat, self._on_component_submit)

    def _edit_component(self) -> None:
        item = self._selected_item()
        if item is None:
            mb.showinfo("Composants", "Sélectionnez un composant à modifier.", parent=self)
            return
        editor_cat = _PAGE_SUB_TO_EDITOR_CAT.get(self._active_sub, "Pierre")
        ComponentEditor(self, self.db, "edit", dict(item), editor_cat, self._on_component_submit)

    def _duplicate_component(self) -> None:
        item = self._selected_item()
        if item is None:
            mb.showinfo("Composants", "Sélectionnez un composant à dupliquer.", parent=self)
            return
        editor_cat = _PAGE_SUB_TO_EDITOR_CAT.get(self._active_sub, "Pierre")
        cloned = dict(item)
        cloned["id"] = str(uuid.uuid4())
        ComponentEditor(self, self.db, "duplicate", cloned, editor_cat, self._on_component_submit)

    def _delete_component(self) -> None:
        item = self._selected_item()
        if item is None:
            mb.showinfo("Composants", "Sélectionnez un composant à supprimer.", parent=self)
            return

        confirm = mb.askyesno("Suppression", "Supprimer définitivement ce composant ?", parent=self)
        if not confirm:
            return

        ok_backup, msg_backup = backup_before_delete(self.db, "composant")
        if not ok_backup:
            mb.showerror("Sauvegarde", msg_backup, parent=self)
            return

        removed = self._remove_component_everywhere(str(item.get("id", "")))
        if not removed:
            mb.showerror("Composants", "Composant introuvable.", parent=self)
            return

        append_local_history(self.db, "composant", "suppression", item, {"subcat": self._active_sub})
        self._refresh_after_crud(None)

    def _selected_item(self) -> dict | None:
        if not self._selected_id:
            return None
        return self._all_by_id.get(self._selected_id)

    def _on_component_submit(self, payload: dict, category_label: str) -> bool:
        if not self.db:
            return False

        target_sub = _EDITOR_CAT_TO_PAGE_SUB.get(category_label, self._active_sub)
        target_list, target_saver = self._source_and_saver_for_sub(target_sub)
        if target_list is None:
            return False

        item_id = str(payload.get("id", "") or "")
        if not item_id:
            return False

        payload["id"] = item_id
        payload.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
        payload["updated_at"] = datetime.now().isoformat(timespec="seconds")

        price = float(payload.get("prix_achat", 0.0) or 0.0)
        payload["prix_achat"] = price
        payload["prix_moyen"] = price
        payload["cout_unitaire"] = price
        payload.setdefault("reference", "")
        payload.setdefault("photo", "")
        payload.setdefault("photo_thumb", "")
        payload.setdefault("fournisseur", "")
        payload.setdefault("fournisseur_ref", "")
        payload.setdefault("fournisseur_site", "")
        payload.setdefault("fournisseur_email", "")
        payload.setdefault("date_dernier_achat", "")

        existing_old = self._find_component_everywhere(item_id)
        old_sub = existing_old[0] if existing_old else None
        old_item = existing_old[1] if existing_old else None

        if old_item is not None:
            self._remove_component_everywhere(item_id)

        target_list.append(payload)
        target_saver()

        self._bump_component_counter(payload.get("reference", ""), category_label)
        action = "modification" if old_item is not None else "creation"
        if old_item is not None and self._selected_id and self._selected_id == item_id and old_sub != target_sub:
            action = "modification"
        if old_item is not None and old_item.get("nom") != payload.get("nom") and str(payload.get("nom", "")).endswith("(Copie)"):
            action = "duplication"
        append_local_history(self.db, "composant", action, payload, {"subcat": target_sub})

        self._active_sub = target_sub
        self._activate_tab(target_sub)
        self._refresh_after_crud(item_id)
        return True

    def _refresh_after_crud(self, selected_id: str | None) -> None:
        self._selected_id = selected_id
        self._styled_selected_id = None
        self._load_data()
        if selected_id and selected_id in self._all_by_id:
            self._select_item(selected_id)
        self._refresh_global_index()

    def _source_and_saver_for_sub(self, sub: str):
        if not self.db:
            return None, None
        mapping = {
            "Pierres": (self.db.stones, self.db.save_stones),
            "Breloques": (self.db.breloques, self.db.save_breloques),
            "Intercalaires": (self.db.intercalaires, self.db.save_intercalaires),
            "Cache-nœuds": (self.db.finitions, self.db.save_finitions),
        }
        return mapping.get(sub, (None, None))

    def _find_component_everywhere(self, item_id: str):
        for sub in ["Pierres", "Breloques", "Intercalaires", "Cache-nœuds"]:
            coll, _ = self._source_and_saver_for_sub(sub)
            if coll is None:
                continue
            for item in coll:
                if str(item.get("id", "")) == item_id:
                    return sub, item
        return None

    def _remove_component_everywhere(self, item_id: str) -> bool:
        removed = False
        for sub in ["Pierres", "Breloques", "Intercalaires", "Cache-nœuds"]:
            coll, saver = self._source_and_saver_for_sub(sub)
            if coll is None:
                continue
            old_len = len(coll)
            coll[:] = [item for item in coll if str(item.get("id", "")) != item_id]
            if len(coll) != old_len:
                saver()
                removed = True
        return removed

    def _bump_component_counter(self, reference: str, category_label: str) -> None:
        if not self.db:
            return
        ref = str(reference or "").strip().upper()
        if len(ref) < 5 or "-" not in ref:
            return
        number = ref.split("-", 1)[1]
        if not number.isdigit():
            return
        counter_key = {
            "Pierre": "phase1c_counter_pie",
            "Breloque": "phase1c_counter_bre",
            "Intercalaire": "phase1c_counter_int",
            "Cache-noeud": "phase1c_counter_fin",
        }.get(category_label)
        if not counter_key:
            return
        current = int(self.db.settings.get(counter_key, 0) or 0)
        value = int(number)
        if value > current:
            self.db.settings[counter_key] = value
            self.db.save_settings()

    def _refresh_global_index(self) -> None:
        root = self.winfo_toplevel()
        if hasattr(root, "_global_index_dirty"):
            root._global_index_dirty = True

    def _activate_tab(self, name: str) -> None:
        for n, btn in self._sub_buttons.items():
            active = n == name
            btn.configure(
                fg_color=theme.BG_CARD if active else "transparent",
                text_color=theme.ACCENT_TURQUOISE if active else theme.TEXT_SECONDARY,
                border_width=0 if active else 1,
            )

    def _switch_sub(self, name: str) -> None:
        if name == self._active_sub:
            return
        self._active_sub = name
        self._selected_id = None
        self._activate_tab(name)
        self._load_data()

    def apply_external_search(self, row: dict) -> None:
        sub = row.get("subcat")
        if sub in self._sub_buttons and sub != self._active_sub:
            self._active_sub = sub
            self._activate_tab(sub)
            self._load_data()

        target_id = str(row.get("id", ""))
        if target_id:
            self._search_var.set("")
            self._select_item(target_id)

    def get_perf_stats(self) -> dict[str, dict[str, float | int]]:
        out: dict[str, dict[str, float | int]] = {}
        for key, vals in self._perf_detail.items():
            if not vals:
                out[key] = {"avg_ms": 0.0, "max_ms": 0.0, "n": 0}
                continue
            out[key] = {
                "avg_ms": round((sum(vals) / len(vals)) * 1000.0, 2),
                "max_ms": round(max(vals) * 1000.0, 2),
                "n": len(vals),
            }
        return out

    @staticmethod
    def _item_price(item: dict) -> float:
        return float(item.get("prix_achat", item.get("cout_unitaire", item.get("prix_moyen", 0.0))) or 0.0)

    def _update_global_kpis(self) -> None:
        stocks = [int(cached.get("stock", 0) or 0) for cached in self._item_cache.values()]
        total_items = len(stocks)
        stock_total_value = sum(float(cached.get("value", 0.0) or 0.0) for cached in self._item_cache.values())
        ruptures = sum(1 for st in stocks if st <= 0)
        non_zero_stocks = [st for st in stocks if st != 0]
        stock_avg = (sum(non_zero_stocks) / len(non_zero_stocks)) if non_zero_stocks else 0.0

        self._kpi_total.set_value(str(total_items))
        self._kpi_stock_total.set_value(self._money(stock_total_value))
        self._kpi_rupture.set_value(f"🔴 {ruptures}" if ruptures > 0 else "0")
        self._kpi_stock_avg.set_value(f"{stock_avg:.1f}")
        self._kpi_rupture.set_value_color(theme.DANGER if ruptures > 0 else theme.TEXT_PRIMARY)

    @staticmethod
    def _stock_badge(stock: int) -> str:
        if stock <= 0:
            return "🔴"
        if stock <= 5:
            return "🟠"
        return "🟢"

    def _quick_restock(self) -> None:
        if not self._selected_id:
            return
        item = self._all_by_id.get(self._selected_id)
        if item is None:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Réappro rapide")
        dialog.geometry("320x150")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Nouveau stock :", text_color=theme.TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(16, 6))
        stock_var = ctk.StringVar(value=str(int(item.get("stock", 0) or 0)))
        entry = ctk.CTkEntry(dialog, textvariable=stock_var, fg_color=theme.BG_INPUT, border_color=theme.BORDER, text_color=theme.TEXT_PRIMARY)
        entry.pack(fill="x", padx=16)
        entry.focus_set()

        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(12, 12))
        ctk.CTkButton(
            actions,
            text="Annuler",
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            command=dialog.destroy,
        ).pack(side="right", padx=(8, 0))

        def _validate_restock() -> None:
            try:
                new_stock = int(stock_var.get().strip())
            except ValueError:
                mb.showerror("Réappro rapide", "Le stock doit être un nombre entier.", parent=dialog)
                return
            if not self._set_item_stock(self._selected_id or "", new_stock):
                mb.showerror("Réappro rapide", "Impossible de mettre à jour le stock.", parent=dialog)
                return
            dialog.destroy()
            self._refresh_after_crud(self._selected_id)

        ctk.CTkButton(
            actions,
            text="Valider",
            fg_color=theme.SUCCESS,
            hover_color=theme.ACCENT_TURQUOISE,
            command=_validate_restock,
        ).pack(side="right")
        dialog.bind("<Return>", lambda _e: _validate_restock())

    def _set_item_stock(self, item_id: str, stock: int) -> bool:
        row = self._all_by_id.get(item_id)
        if row is None:
            return False
        _, saver = self._get_source_and_saver()
        row["stock"] = int(stock)
        row["updated_at"] = datetime.now().isoformat(timespec="seconds")
        saver()
        return True

    def _update_used_in_bracelets(self, item_id: str, item: dict) -> None:
        used_names: list[str] = []
        bracelets = list(getattr(self.db, "bracelets", []) or [])
        component_name = str(item.get("nom", "") or "").strip().lower()
        component_id = str(item_id or "").strip()

        for bracelet in bracelets:
            if self._bracelet_contains_component(bracelet, component_id, component_name):
                name = str(bracelet.get("nom", "—") or "—")
                if name not in used_names:
                    used_names.append(name)
            if len(used_names) >= _MAX_USED_BRACELETS:
                break

        self._render_used_bracelets(used_names)

    def _render_used_bracelets(self, names: list[str]) -> None:
        for child in self._used_bracelets_box.winfo_children():
            child.destroy()
        if not names:
            ctk.CTkLabel(
                self._used_bracelets_box,
                text="Non utilisé dans les bracelets actuels",
                text_color=theme.TEXT_SECONDARY,
            ).pack(anchor="w")
            return
        for name in names:
            ctk.CTkLabel(
                self._used_bracelets_box,
                text=f"• {name}",
                text_color=theme.TEXT_PRIMARY,
            ).pack(anchor="w", pady=1)

    def _bracelet_contains_component(self, bracelet: dict, component_id: str, component_name: str) -> bool:
        targets = {component_id.lower(), component_name.lower()}
        for field in ("composition", "composants"):
            values = bracelet.get(field)
            for candidate in self._extract_component_candidates(values):
                if candidate and candidate.lower() in targets:
                    return True
        return False

    def _extract_component_candidates(self, payload) -> list[str]:
        if payload is None:
            return []
        if isinstance(payload, dict):
            results: list[str] = []
            for key in ("id", "composant_id", "id_composant", "component_id", "composant", "nom", "name"):
                if key in payload:
                    results.append(str(payload.get(key, "")).strip())
            for value in payload.values():
                results.extend(self._extract_component_candidates(value))
            return results
        if isinstance(payload, list):
            results: list[str] = []
            for row in payload:
                results.extend(self._extract_component_candidates(row))
            return results
        raw = str(payload).strip()
        if not raw:
            return []
        parts = [p.strip() for p in raw.replace("|", ",").replace(";", ",").split(",")]
        return [p for p in parts if p]

    @staticmethod
    def _money(value: float) -> str:
        return f"{value:,.2f} EUR".replace(",", " ").replace(".", ",")

    @staticmethod
    def _format_date(raw: str) -> str:
        if not raw:
            return "—"
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", ""))
            return dt.strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return str(raw)
