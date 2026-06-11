from __future__ import annotations

import tkinter.filedialog as fd
import tkinter.messagebox as mb
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import customtkinter as ctk

import theme
from phase1c_services import import_image_for_item


_COMPONENT_CATEGORY_CONFIG: dict[str, dict[str, str]] = {
    "Pierre": {"prefix": "PIE", "attr": "stones", "field": "reference", "counter": "phase1c_counter_pie", "page_sub": "Pierres"},
    "Breloque": {"prefix": "BRE", "attr": "breloques", "field": "reference", "counter": "phase1c_counter_bre", "page_sub": "Breloques"},
    "Intercalaire": {"prefix": "INT", "attr": "intercalaires", "field": "reference", "counter": "phase1c_counter_int", "page_sub": "Intercalaires"},
    "Cache-noeud": {"prefix": "FIN", "attr": "finitions", "field": "reference", "counter": "phase1c_counter_fin", "page_sub": "Cache-nœuds"},
}


class ScrollableComboBox(ctk.CTkFrame):
    """Liste deroulante avec recherche au clavier et barre de defilement.

    Remplace CTkComboBox: taper filtre la liste; molette et barre laterale
    permettent de faire defiler les resultats.
    """

    _open_instance = None

    def __init__(self, master, variable, values=None, command=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._variable = variable
        self._values = [str(v) for v in (values or [])]
        self._command = command
        self._popup = None
        self._click_bind = None
        self._suppress_filter = False

        self.columnconfigure(0, weight=1)
        self._text_var = ctk.StringVar(value=variable.get())
        self._entry = ctk.CTkEntry(
            self,
            textvariable=self._text_var,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
        )
        self._entry.grid(row=0, column=0, sticky="ew")
        self._button = ctk.CTkButton(
            self,
            text=chr(0x25BC),
            width=28,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            command=self._toggle_popup,
        )
        self._button.grid(row=0, column=1, padx=(2, 0))

        self._entry.bind("<KeyRelease>", self._on_keyrelease)
        self._entry.bind("<Button-1>", lambda _e: self._open_popup())
        self._entry.bind("<Down>", lambda _e: self._open_popup())
        self._var_trace = variable.trace_add("write", self._on_var_changed)
        self.bind("<Destroy>", self._on_destroy)

    def set_values(self, values) -> None:
        self._values = [str(v) for v in (values or [])]
        if self._popup is not None:
            self._render_items()

    def _on_var_changed(self, *_args) -> None:
        try:
            current = self._variable.get()
        except Exception:
            return
        if self._text_var.get() != current:
            self._text_var.set(current)

    def _needle(self) -> str:
        return self._text_var.get().strip().lower()

    def _matches(self) -> list:
        if getattr(self, "_suppress_filter", False):
            return list(self._values)
        needle = self._needle()
        if not needle:
            return list(self._values)
        return [v for v in self._values if needle in v.lower()]

    def _toggle_popup(self) -> None:
        if self._popup is not None:
            self._close_popup()
        else:
            self._open_popup()

    def _open_popup(self) -> None:
        if self._popup is not None:
            self._render_items()
            return
        if not self.winfo_ismapped():
            return
        other = ScrollableComboBox._open_instance
        if other is not None and other is not self:
            try:
                other._close_popup()
            except Exception:
                pass
        container = self.winfo_toplevel()
        container.update_idletasks()
        x = self._entry.winfo_rootx() - container.winfo_rootx()
        y = self._entry.winfo_rooty() - container.winfo_rooty() + self._entry.winfo_height() + 2
        width = max(self._entry.winfo_width() + self._button.winfo_width() + 2, 200)
        self._popup = ctk.CTkScrollableFrame(container, fg_color=theme.BG_CARD, width=width, height=240)
        self._popup.place(x=x, y=y)
        self._popup.lift()
        ScrollableComboBox._open_instance = self
        self._suppress_filter = True
        self._render_items()
        self._entry.focus_set()
        try:
            self._entry.select_range(0, "end")
        except Exception:
            pass
        self._click_bind = container.bind("<Button-1>", self._maybe_close_on_click, add="+")

    def _render_items(self) -> None:
        if self._popup is None:
            return
        for child in self._popup.winfo_children():
            child.destroy()
        matches = self._matches()
        if not matches:
            ctk.CTkLabel(self._popup, text="(aucun resultat)", text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=8, pady=4)
            return
        for val in matches:
            ctk.CTkButton(
                self._popup,
                text=val,
                anchor="w",
                fg_color="transparent",
                hover_color=theme.BG_CARD_HOVER,
                text_color=theme.TEXT_PRIMARY,
                command=lambda v=val: self._choose(v),
            ).pack(fill="x", padx=2, pady=1)

    def _choose(self, val: str) -> None:
        self._close_popup()
        self._variable.set(val)
        self._text_var.set(val)
        if self._command is not None:
            try:
                self._command(val)
            except Exception:
                pass

    def _on_keyrelease(self, event) -> None:
        keysym = getattr(event, "keysym", "")
        if keysym == "Escape":
            self._close_popup()
            return
        if keysym in ("Return", "KP_Enter"):
            matches = self._matches()
            if matches:
                self._choose(matches[0])
            return
        if keysym in ("Up", "Down", "Left", "Right"):
            return
        if self._popup is None:
            self._open_popup()
        self._suppress_filter = False
        self._render_items()

    def _maybe_close_on_click(self, event) -> None:
        try:
            path = str(event.widget)
            if path.startswith(str(self)):
                return
            if self._popup is not None and path.startswith(str(self._popup)):
                return
        except Exception:
            pass
        self._close_popup()

    def _close_popup(self) -> None:
        if self._click_bind is not None:
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._click_bind)
            except Exception:
                pass
            self._click_bind = None
        if self._popup is not None:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None
        if ScrollableComboBox._open_instance is self:
            ScrollableComboBox._open_instance = None
        self._suppress_filter = False
        try:
            self._text_var.set(self._variable.get())
        except Exception:
            pass

    def _on_destroy(self, event) -> None:
        if event.widget is self:
            try:
                self._variable.trace_remove("write", self._var_trace)
            except Exception:
                pass
            self._close_popup()


class BaseEditor(ctk.CTkToplevel):
    def __init__(self, parent, title: str) -> None:
        super().__init__(parent)
        self.configure(fg_color=theme.BG_MAIN)
        self.title(title)
        self.geometry("980x740")
        self.minsize(900, 700)

        self._dirty = False
        self._closing = False

        self.protocol("WM_DELETE_WINDOW", self._on_close_request)
        self.transient(parent)
        self.grab_set()

    def _mark_dirty(self, *_args) -> None:
        if not self._closing:
            self._dirty = True

    def _on_close_request(self) -> None:
        if self._dirty:
            ok = mb.askyesno(
                "Modifications non enregistrées",
                "Des modifications non enregistrées existent.\n\nVoulez-vous quitter ?",
                parent=self,
            )
            if not ok:
                return
        self._closing = True
        self.grab_release()
        self.destroy()


class ComponentEditor(BaseEditor):
    def __init__(
        self,
        parent,
        db: Any,
        mode: str,
        initial_item: dict[str, Any] | None,
        initial_category: str,
        on_submit: Callable[[dict[str, Any], str], bool],
    ) -> None:
        super().__init__(parent, "Composant")
        self.db = db
        self.mode = mode
        self.initial_item = initial_item or {}
        self.on_submit = on_submit

        self._item_data = dict(self.initial_item)
        self._preview_img = None

        self._cat_var = ctk.StringVar(value=initial_category)
        self._ref_var = ctk.StringVar(value="")
        self._nom_var = ctk.StringVar(value=str(self.initial_item.get("nom", "")))
        self._price_var = ctk.StringVar(value=str(self._item_price(self.initial_item)))
        self._stock_var = ctk.StringVar(value=str(int(self.initial_item.get("stock", 0) or 0)))
        self._supplier_var = ctk.StringVar(value=str(self.initial_item.get("fournisseur", "")))
        self._supplier_ref_var = ctk.StringVar(value=str(self.initial_item.get("fournisseur_ref", "")))
        self._site_var = ctk.StringVar(value=str(self.initial_item.get("fournisseur_site", "")))
        self._email_var = ctk.StringVar(value=str(self.initial_item.get("fournisseur_email", "")))
        self._last_buy_var = ctk.StringVar(value=str(self.initial_item.get("date_dernier_achat", "")))

        self._build_ui()
        self._bind_dirty_tracking()

        if mode == "edit":
            self._ref_var.set(str(self.initial_item.get("reference", "")))
        else:
            self._ref_var.set(self._next_component_ref(self._cat_var.get()))
        self._update_preview()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=22, pady=(18, 8))
        ctk.CTkLabel(header, text="Composant", font=ctk.CTkFont(size=20, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w")

        tabs = ctk.CTkTabview(self, fg_color=theme.BG_CARD, segmented_button_fg_color=theme.BG_SIDEBAR)
        tabs.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        info_tab = tabs.add("Informations")
        photo_tab = tabs.add("Photo")
        supplier_tab = tabs.add("Fournisseur")

        self._build_info_tab(info_tab)
        self._build_photo_tab(photo_tab)
        self._build_supplier_tab(supplier_tab)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkButton(footer, text="Annuler", fg_color=theme.BG_SIDEBAR, hover_color=theme.BG_CARD_HOVER, command=self._on_close_request).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="Enregistrer", fg_color=theme.SUCCESS, hover_color=theme.ACCENT_TURQUOISE, command=self._save).pack(side="right")

    def _build_info_tab(self, tab) -> None:
        for col in range(2):
            tab.columnconfigure(col, weight=1)

        self._add_labeled_entry(tab, 0, 0, "Référence (auto)", self._ref_var, state="readonly")

        cat_menu = ctk.CTkOptionMenu(
            tab,
            variable=self._cat_var,
            values=list(_COMPONENT_CATEGORY_CONFIG.keys()),
            fg_color=theme.BG_INPUT,
            button_color=theme.BG_CARD,
            button_hover_color=theme.BG_CARD_HOVER,
            command=lambda _v: self._on_category_change(),
        )
        self._add_labeled_widget(tab, 0, 1, "Catégorie", cat_menu)

        self._add_labeled_entry(tab, 1, 0, "Nom", self._nom_var)
        self._add_labeled_entry(tab, 1, 1, "Prix unitaire", self._price_var)
        self._add_labeled_entry(tab, 2, 0, "Stock", self._stock_var)

    def _build_photo_tab(self, tab) -> None:
        box = ctk.CTkFrame(tab, fg_color=theme.BG_SIDEBAR, corner_radius=16, width=280, height=280)
        box.pack(padx=20, pady=(20, 12), anchor="w")
        box.pack_propagate(False)

        self._preview_label = ctk.CTkLabel(box, text="", image=None)
        self._preview_label.place(relx=0.5, rely=0.5, anchor="center")

        self._photo_empty = ctk.CTkLabel(box, text="Image indisponible", text_color=theme.TEXT_SECONDARY)
        self._photo_empty.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkButton(tab, text="Importer une image", fg_color=theme.BG_CARD, hover_color=theme.BG_CARD_HOVER, command=self._import_image).pack(anchor="w", padx=20)

    def _build_supplier_tab(self, tab) -> None:
        for col in range(2):
            tab.columnconfigure(col, weight=1)
        self._add_labeled_entry(tab, 0, 0, "Fournisseur", self._supplier_var)
        self._add_labeled_entry(tab, 0, 1, "Référence fournisseur", self._supplier_ref_var)
        self._add_labeled_entry(tab, 1, 0, "Site web", self._site_var)
        self._add_labeled_entry(tab, 1, 1, "Email", self._email_var)
        self._add_labeled_entry(tab, 2, 0, "Date dernier achat", self._last_buy_var)

    def _bind_dirty_tracking(self) -> None:
        for var in [
            self._cat_var,
            self._nom_var,
            self._price_var,
            self._stock_var,
            self._supplier_var,
            self._supplier_ref_var,
            self._site_var,
            self._email_var,
            self._last_buy_var,
        ]:
            var.trace_add("write", self._mark_dirty)

    def _on_category_change(self) -> None:
        if self.mode in {"new", "duplicate"}:
            self._ref_var.set(self._next_component_ref(self._cat_var.get()))

    def _import_image(self) -> None:
        source = fd.askopenfilename(
            title="Importer une image composant",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")],
        )
        if not source:
            return

        ok, msg = import_image_for_item(self.db, self._item_data, "composants", source)
        if not ok:
            mb.showerror("Image", msg, parent=self)
            return
        self._mark_dirty()
        self._update_preview()

    def _update_preview(self) -> None:
        from PIL import Image

        raw = str(self._item_data.get("photo_thumb", "") or self._item_data.get("photo", ""))
        if not raw:
            self._preview_img = None
            self._preview_label.configure(image=None)
            self._photo_empty.place(relx=0.5, rely=0.5, anchor="center")
            return

        path = Path(self.db.base_dir) / raw
        if not path.exists():
            self._preview_img = None
            self._preview_label.configure(image=None)
            self._photo_empty.place(relx=0.5, rely=0.5, anchor="center")
            return

        img = Image.open(path)
        self._preview_img = ctk.CTkImage(light_image=img, dark_image=img, size=(240, 240))
        self._preview_label.configure(image=self._preview_img)
        self._photo_empty.place_forget()

    def _save(self) -> None:
        nom = self._nom_var.get().strip()
        if not nom:
            mb.showerror("Validation", "Le nom est obligatoire.", parent=self)
            return

        price = self._parse_float(self._price_var.get(), "Prix unitaire")
        if price is None or price < 0:
            mb.showerror("Validation", "Le prix unitaire doit être >= 0.", parent=self)
            return

        stock = self._parse_int(self._stock_var.get(), "Stock")
        if stock is None or stock < 0:
            mb.showerror("Validation", "Le stock doit être >= 0.", parent=self)
            return

        now = datetime.now().isoformat(timespec="seconds")
        payload: dict[str, Any] = {
            "id": str(self.initial_item.get("id", "") or uuid.uuid4()),
            "reference": self._ref_var.get().strip(),
            "nom": nom,
            "prix_achat": price,
            "prix_moyen": price,
            "stock": stock,
            "fournisseur": self._supplier_var.get().strip(),
            "fournisseur_ref": self._supplier_ref_var.get().strip(),
            "fournisseur_site": self._site_var.get().strip(),
            "fournisseur_email": self._email_var.get().strip(),
            "date_dernier_achat": self._last_buy_var.get().strip(),
            "photo": str(self._item_data.get("photo", "")),
            "photo_thumb": str(self._item_data.get("photo_thumb", "")),
            "updated_at": now,
        }
        if "created_at" in self.initial_item:
            payload["created_at"] = self.initial_item.get("created_at")
        else:
            payload["created_at"] = now

        ok = self.on_submit(payload, self._cat_var.get())
        if not ok:
            return

        self._dirty = False
        self._on_close_request()

    def _next_component_ref(self, label: str) -> str:
        cfg = _COMPONENT_CATEGORY_CONFIG[label]
        items = list(getattr(self.db, cfg["attr"], []))
        used: set[int] = set()
        for item in items:
            ref = str(item.get(cfg["field"], "") or "").strip().upper()
            if ref.startswith(f"{cfg['prefix']}-") and ref[4:].isdigit():
                used.add(int(ref[4:]))

        counter = int(self.db.settings.get(cfg["counter"], 0) or 0)
        if used:
            counter = max(counter, max(used))
        n = counter + 1
        while n in used:
            n += 1
        return f"{cfg['prefix']}-{n:04d}"

    @staticmethod
    def _item_price(item: dict[str, Any]) -> float:
        return float(item.get("prix_achat", item.get("cout_unitaire", item.get("prix_moyen", 0.0))) or 0.0)

    @staticmethod
    def _parse_float(raw: str, _name: str) -> float | None:
        text = (raw or "").strip().replace(",", ".")
        try:
            return float(text or "0")
        except ValueError:
            return None

    @staticmethod
    def _parse_int(raw: str, _name: str) -> int | None:
        text = (raw or "").strip()
        try:
            return int(text or "0")
        except ValueError:
            return None

    @staticmethod
    def _add_labeled_widget(parent, row: int, col: int, label: str, widget) -> None:
        ctk.CTkLabel(parent, text=label, text_color=theme.TEXT_SECONDARY).grid(row=row * 2, column=col, sticky="w", padx=16, pady=(16, 6))
        widget.grid(row=row * 2 + 1, column=col, sticky="ew", padx=16)

    @classmethod
    def _add_labeled_entry(cls, parent, row: int, col: int, label: str, var: ctk.StringVar, state: str = "normal"):
        entry = ctk.CTkEntry(
            parent,
            textvariable=var,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
            state=state,
        )
        cls._add_labeled_widget(parent, row, col, label, entry)
        return entry


class BraceletEditor(BaseEditor):
    def __init__(self, parent, db: Any, mode: str, initial_item: dict[str, Any] | None, on_submit: Callable[[dict[str, Any]], bool]) -> None:
        super().__init__(parent, "Bracelet")
        self.db = db
        self.mode = mode
        self.initial_item = initial_item or {}
        self.on_submit = on_submit

        self._item_data = dict(self.initial_item)
        self._preview_img = None
        self._composition_rows: list[dict[str, Any]] = []
        _has_vc = bool(str(self.initial_item.get("vertus", "")).strip() or str(self.initial_item.get("chakras", self.initial_item.get("chakra", ""))).strip())
        self._vc_user_edited = _has_vc

        self._components_catalog = self._build_components_catalog()
        options = [c["label"] for c in self._components_catalog]
        self._component_options = options if options else ["(Aucun composant)"]
        self._component_by_label = {c["label"]: c for c in self._components_catalog}
        self._index_catalog()

        self._ref_var = ctk.StringVar(value="")
        self._nom_var = ctk.StringVar(value=str(self.initial_item.get("nom", "")))
        self._stock_var = ctk.StringVar(value=str(int(self.initial_item.get("stock", 0) or 0)))
        self._pv_var = ctk.StringVar(value=str(float(self.initial_item.get("prix_vente", 0.0) or 0.0)))
        self._genre_var = ctk.StringVar(value=(str(self.initial_item.get("genre", "") or "") or "Mixte"))

        self._cout_var = ctk.StringVar(value="0,00 EUR")
        self._conseille_var = ctk.StringVar(value="0,00 EUR")
        self._marge_var = ctk.StringVar(value="0,00 EUR")
        self._rent_var = ctk.StringVar(value="0,0 %")

        self._build_ui()
        self._bind_dirty_tracking()

        if mode == "edit":
            self._ref_var.set(str(self.initial_item.get("reference", "")))
        else:
            self._ref_var.set(self.db.next_bracelet_ref())

        self._load_initial_composition()
        self._update_preview()
        self._recompute_metrics()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=22, pady=(18, 8))
        ctk.CTkLabel(header, text="Bracelet", font=ctk.CTkFont(size=20, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w")

        tabs = ctk.CTkTabview(self, fg_color=theme.BG_CARD, segmented_button_fg_color=theme.BG_SIDEBAR)
        tabs.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        info_tab = tabs.add("Informations")
        photo_tab = tabs.add("Photo")
        comp_tab = tabs.add("Composition")

        self._build_info_tab(info_tab)
        self._build_photo_tab(photo_tab)
        self._build_composition_tab(comp_tab)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkButton(footer, text="Annuler", fg_color=theme.BG_SIDEBAR, hover_color=theme.BG_CARD_HOVER, command=self._on_close_request).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="Enregistrer", fg_color=theme.SUCCESS, hover_color=theme.ACCENT_TURQUOISE, command=self._save).pack(side="right")

    def _build_info_tab(self, tab) -> None:
        for col in range(2):
            tab.columnconfigure(col, weight=1)

        self._add_labeled_entry(tab, 0, 0, "Référence (auto)", self._ref_var, state="readonly")
        self._add_labeled_entry(tab, 0, 1, "Nom", self._nom_var)
        self._add_labeled_entry(tab, 1, 0, "Stock", self._stock_var)
        self._add_labeled_entry(tab, 1, 1, "Prix de vente", self._pv_var)

        values = [
            ("Prix de revient", self._cout_var),
            ("Prix conseillé", self._conseille_var),
            ("Marge", self._marge_var),
            ("Rentabilité", self._rent_var),
        ]
        for idx, (label, var) in enumerate(values):
            col = idx % 2
            row = 2 + idx // 2
            self._add_labeled_entry(tab, row, col, label, var, state="readonly")

        self._vertus_box = ctk.CTkTextbox(tab, fg_color=theme.BG_INPUT, border_color=theme.BORDER, text_color=theme.TEXT_PRIMARY, height=90)
        self._chakras_box = ctk.CTkTextbox(tab, fg_color=theme.BG_INPUT, border_color=theme.BORDER, text_color=theme.TEXT_PRIMARY, height=90)
        self._add_labeled_widget(tab, 4, 0, "Vertus", self._vertus_box)
        self._add_labeled_widget(tab, 4, 1, "Chakras", self._chakras_box)
        self._vertus_box.insert("1.0", self._extract_text(self.initial_item.get("vertus", "")))
        self._chakras_box.insert("1.0", self._extract_text(self.initial_item.get("chakras", self.initial_item.get("chakra", ""))))
        genre_menu = ctk.CTkOptionMenu(tab, variable=self._genre_var, values=["Homme", "Femme", "Mixte", "Enfant"], fg_color=theme.BG_INPUT, button_color=theme.BG_CARD, button_hover_color=theme.BG_CARD_HOVER)
        self._add_labeled_widget(tab, 5, 0, "Genre", genre_menu)
        self._coef_var = ctk.StringVar(value=str(self._default_coef()))
        self._prix_auto_var = ctk.StringVar(value=("1" if bool(self.initial_item.get("prix_auto", self.mode != "edit")) else "0"))
        coef_frame = ctk.CTkFrame(tab, fg_color="transparent")
        ctk.CTkCheckBox(coef_frame, text="Auto", variable=self._prix_auto_var, onvalue="1", offvalue="0", command=self._on_prix_auto_toggle).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(coef_frame, text="Coefficient ×", text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        ctk.CTkEntry(coef_frame, textvariable=self._coef_var, width=70, fg_color=theme.BG_INPUT, border_color=theme.BORDER).pack(side="left")
        ctk.CTkButton(coef_frame, text="Calculer le prix de vente", fg_color=theme.ACCENT_TURQUOISE, hover_color=theme.BG_CARD_HOVER, command=self._apply_price_coef).pack(side="left", padx=8)
        self._add_labeled_widget(tab, 5, 1, "Tarif automatique", coef_frame)
        self._coef_var.trace_add("write", lambda *_: self._on_coef_changed())

    def _build_photo_tab(self, tab) -> None:
        box = ctk.CTkFrame(tab, fg_color=theme.BG_SIDEBAR, corner_radius=16, width=320, height=320)
        box.pack(padx=20, pady=(20, 12), anchor="w")
        box.pack_propagate(False)

        self._preview_label = ctk.CTkLabel(box, text="", image=None)
        self._preview_label.place(relx=0.5, rely=0.5, anchor="center")

        self._photo_empty = ctk.CTkLabel(box, text="Image indisponible", text_color=theme.TEXT_SECONDARY)
        self._photo_empty.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkButton(tab, text="Importer une image", fg_color=theme.BG_CARD, hover_color=theme.BG_CARD_HOVER, command=self._import_image).pack(anchor="w", padx=20)

    def _build_composition_tab(self, tab) -> None:
        ctk.CTkButton(tab, text="+ Ajouter un composant", fg_color=theme.BG_CARD, hover_color=theme.BG_CARD_HOVER, command=self._add_comp_row).pack(anchor="w", padx=16, pady=(12, 8))
        ctk.CTkButton(tab, text="✨ Générer un nom", fg_color=theme.ACCENT_AMETHYSTE, hover_color=theme.BG_CARD_HOVER, command=self._suggest_bracelet_name).pack(anchor="w", padx=16, pady=(0, 6))
        ctk.CTkLabel(tab, text="↑/↓ : ordre de placement   •   Qté : quantité   •   PU : prix unitaire en EUR (modifiable)", text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=16, pady=(0, 6))

        self._comp_scroll = ctk.CTkScrollableFrame(tab, fg_color=theme.BG_SIDEBAR)
        self._comp_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))

    def _bind_dirty_tracking(self) -> None:
        for var in [self._nom_var, self._stock_var, self._pv_var]:
            var.trace_add("write", lambda *_: (self._mark_dirty(), self._recompute_metrics()))

        self._vertus_box.bind("<KeyRelease>", lambda _e: self._on_vc_edited())
        self._chakras_box.bind("<KeyRelease>", lambda _e: self._on_vc_edited())

    def _suggest_bracelet_name(self) -> None:
        agg: dict[str, int] = {}
        order: list[str] = []
        for row in self._composition_rows:
            comp = self._row_component(row)
            if not comp or not str(comp.get("categorie", "")).strip().lower().startswith("pierre"):
                continue
            nom = str(comp.get("nom", "")).strip()
            if not nom:
                continue
            try:
                qty = self._parse_int(row["qty_var"].get())
            except Exception:
                qty = 1
            if nom not in agg:
                agg[nom] = 0
                order.append(nom)
            agg[nom] += max(qty, 1)
        if not order:
            mb.showinfo("Nom du bracelet", "Ajoutez au moins une pierre a la composition pour generer un nom.", parent=self)
            return
        ranked = sorted(order, key=lambda n: (-agg[n], n))
        top = ranked[:3]
        if len(top) == 1:
            base = top[0]
        elif len(top) == 2:
            base = f"{top[0]} & {top[1]}"
        else:
            base = f"{top[0]}, {top[1]} & {top[2]}"
        self._nom_var.set(f"Bracelet {base}")
        self._mark_dirty()

    def _build_components_catalog(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        def append_rows(items: list[dict[str, Any]], category: str) -> None:
            for item in items:
                nom = str(item.get("nom", "")).strip()
                if not nom:
                    continue
                unit = float(item.get("prix_achat", item.get("cout_unitaire", item.get("prix_moyen", 0.0))) or 0.0)
                rows.append({
                    "label": f"{nom} ({category})",
                    "nom": nom,
                    "categorie": category,
                    "cout_unitaire": unit,
                })

        append_rows(list(getattr(self.db, "stones", [])), "Pierre")
        append_rows(list(getattr(self.db, "breloques", [])), "Breloque")
        append_rows(list(getattr(self.db, "intercalaires", [])), "Intercalaire")
        append_rows(list(getattr(self.db, "finitions", [])), "Cache-noeud")
        return rows

    def _load_initial_composition(self) -> None:
        rows = list(self.initial_item.get("composition", []))
        if rows:
            for row in rows:
                cat = str(row.get("categorie", "")).strip()
                nom = str(row.get("composant", "")).strip()
                if cat not in self._categories:
                    low = cat.lower()
                    match = None
                    for cc in self._categories:
                        if cc.lower() == low:
                            match = cc
                            break
                    if match is None and low.startswith("pierre") and "Pierre" in self._categories:
                        match = "Pierre"
                    cat = match or (self._categories[0] if self._categories else "Pierre")
                qty = int(row.get("quantite", 1) or 1)
                try:
                    pu = float(row.get("cout_unitaire", 0.0) or 0.0)
                except (TypeError, ValueError):
                    pu = 0.0
                self._add_comp_row(cat=cat, name=nom, qty=qty, pu=pu)
        else:
            self._add_comp_row()

    def _closest_component_label(self, nom: str, cat: str) -> str:
        exact = f"{nom} ({cat})"
        if exact in self._component_by_label:
            return exact
        for label in self._component_by_label:
            if label.startswith(f"{nom} ("):
                return label
        return self._component_options[0]

    def _add_comp_row(self, cat: str | None = None, name: str | None = None, qty: int = 1, pu: float | None = None, label: str | None = None) -> None:
        if label and (cat is None or name is None):
            comp = self._component_by_label.get(label)
            if comp:
                cat = comp.get("categorie")
                name = comp.get("nom")
        cat = cat if cat in self._categories else (self._categories[0] if self._categories else "Pierre")
        names = self._names_by_cat.get(cat, [])
        if not name:
            name = names[0] if names else ""

        row_wrap = ctk.CTkFrame(self._comp_scroll, fg_color=theme.BG_CARD, corner_radius=10)
        row_wrap.pack(fill="x", padx=4, pady=4)
        row_wrap.columnconfigure(2, weight=1)

        pos_label = ctk.CTkLabel(row_wrap, text="1", width=24, text_color=theme.TEXT_SECONDARY)
        pos_label.grid(row=0, column=0, padx=(8, 0), pady=8)

        cat_var = ctk.StringVar(value=cat)
        comp_var = ctk.StringVar(value=name)
        qty_var = ctk.StringVar(value=str(max(1, int(qty))))
        if pu is None:
            pu = self._price_for(cat, name)
        pu_var = ctk.StringVar(value=self._fmt_pu(pu))

        cat_menu = ctk.CTkOptionMenu(
            row_wrap,
            variable=cat_var,
            values=self._categories,
            width=120,
            fg_color=theme.BG_INPUT,
            button_color=theme.BG_CARD,
            button_hover_color=theme.BG_CARD_HOVER,
        )
        cat_menu.grid(row=0, column=1, padx=(8, 4), pady=8)

        comp_box = ScrollableComboBox(
            row_wrap,
            variable=comp_var,
            values=(names or ["(Aucun)"]),
            command=lambda _v=None: self._on_component_selected(row),
        )
        comp_box.grid(row=0, column=2, sticky="ew", padx=4, pady=8)

        qty_entry = ctk.CTkEntry(row_wrap, textvariable=qty_var, width=54, fg_color=theme.BG_INPUT, border_color=theme.BORDER)
        qty_entry.grid(row=0, column=3, padx=6)

        pu_entry = ctk.CTkEntry(row_wrap, textvariable=pu_var, width=74, fg_color=theme.BG_INPUT, border_color=theme.BORDER)
        pu_entry.grid(row=0, column=4, padx=6)

        row = {"frame": row_wrap, "cat_var": cat_var, "comp_var": comp_var, "comp_box": comp_box, "qty_var": qty_var, "pu_var": pu_var, "pos_label": pos_label}

        cat_var.trace_add("write", lambda *_: self._on_category_changed(row))
        comp_var.trace_add("write", lambda *_: self._on_comp_row_changed())
        qty_var.trace_add("write", lambda *_: self._on_comp_row_changed())
        pu_var.trace_add("write", lambda *_: self._on_comp_row_changed())

        ctk.CTkButton(
            row_wrap, text=chr(0x2191), width=34,
            fg_color=theme.BG_INPUT, hover_color=theme.BG_CARD_HOVER,
            command=lambda: self._move_comp_row(row, -1),
        ).grid(row=0, column=5, padx=(8, 2))
        ctk.CTkButton(
            row_wrap, text=chr(0x2193), width=34,
            fg_color=theme.BG_INPUT, hover_color=theme.BG_CARD_HOVER,
            command=lambda: self._move_comp_row(row, 1),
        ).grid(row=0, column=6, padx=2)
        ctk.CTkButton(
            row_wrap, text="Supprimer", width=90,
            fg_color=theme.DANGER, hover_color=theme.WARNING,
            command=lambda: self._remove_comp_row(row_wrap),
        ).grid(row=0, column=7, padx=8)

        self._composition_rows.append(row)
        self._refresh_comp_positions()
        self._on_comp_row_changed()

    def _index_catalog(self) -> None:
        """Indexe le catalogue par categorie (listes triees alphabetiquement)."""
        self._categories_all = ["Pierre", "Breloque", "Intercalaire", "Cache-noeud"]
        self._names_by_cat: dict[str, list[str]] = {}
        self._comp_by_cat_name: dict[tuple[str, str], dict[str, Any]] = {}
        for comp in self._components_catalog:
            cat = str(comp.get("categorie", "")).strip()
            nom = str(comp.get("nom", "")).strip()
            if not cat or not nom:
                continue
            self._names_by_cat.setdefault(cat, []).append(nom)
            self._comp_by_cat_name[(cat, nom.lower())] = comp
        for cat in list(self._names_by_cat.keys()):
            uniq = list(dict.fromkeys(self._names_by_cat[cat]))
            self._names_by_cat[cat] = sorted(uniq, key=lambda s: s.lower())
        self._categories = [c for c in self._categories_all if self._names_by_cat.get(c)]
        for cat in self._names_by_cat:
            if cat not in self._categories:
                self._categories.append(cat)
        if not self._categories:
            self._categories = ["Pierre"]

    def _price_for(self, cat: str, name: str) -> float:
        comp = self._comp_by_cat_name.get((str(cat).strip(), str(name).strip().lower()))
        return float(comp["cout_unitaire"]) if comp else 0.0

    def _row_component(self, row: dict[str, Any]):
        cat = row["cat_var"].get() if "cat_var" in row else ""
        name = row["comp_var"].get() if "comp_var" in row else ""
        return self._comp_by_cat_name.get((str(cat).strip(), str(name).strip().lower()))

    @staticmethod
    def _fmt_pu(value: float) -> str:
        return f"{float(value or 0.0):.2f}"

    def _on_component_selected(self, row: dict[str, Any]) -> None:
        cat = row["cat_var"].get()
        name = row["comp_var"].get()
        row["pu_var"].set(self._fmt_pu(self._price_for(cat, name)))
        self._on_comp_row_changed()

    def _on_category_changed(self, row: dict[str, Any]) -> None:
        cat = row["cat_var"].get()
        names = self._names_by_cat.get(cat, [])
        box = row.get("comp_box")
        if box is not None:
            box.set_values(names or ["(Aucun)"])
        new_name = names[0] if names else ""
        row["comp_var"].set(new_name)
        row["pu_var"].set(self._fmt_pu(self._price_for(cat, new_name)))
        self._on_comp_row_changed()

    def _move_comp_row(self, row: dict[str, Any], direction: int) -> None:
        rows = self._composition_rows
        try:
            i = rows.index(row)
        except ValueError:
            return
        j = i + direction
        if j < 0 or j >= len(rows):
            return
        rows[i], rows[j] = rows[j], rows[i]
        for r in rows:
            r["frame"].pack_forget()
        for r in rows:
            r["frame"].pack(fill="x", padx=4, pady=4)
        self._refresh_comp_positions()
        self._on_comp_row_changed()

    def _refresh_comp_positions(self) -> None:
        for idx, r in enumerate(self._composition_rows, start=1):
            lbl = r.get("pos_label")
            if lbl is not None:
                lbl.configure(text=str(idx))

    def _remove_comp_row(self, frame) -> None:
        self._composition_rows = [r for r in self._composition_rows if r["frame"] != frame]
        frame.destroy()
        self._refresh_comp_positions()
        self._on_comp_row_changed()

    def _on_comp_row_changed(self) -> None:
        self._mark_dirty()
        self._auto_fill_vertus_chakras()
        self._recompute_metrics()

    def _composition_payload(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in self._composition_rows:
            comp = self._row_component(row)
            if not comp:
                continue
            qty = self._parse_int(row["qty_var"].get())
            if qty is None or qty <= 0:
                continue
            pu = self._parse_float(row["pu_var"].get()) if "pu_var" in row else None
            if pu is None or pu < 0:
                pu = float(comp["cout_unitaire"])
            rows.append(
                {
                    "composant": comp["nom"],
                    "categorie": comp["categorie"],
                    "quantite": qty,
                    "cout_unitaire": float(pu),
                }
            )
        return rows

    def _recompute_metrics(self) -> None:
        composition = self._composition_payload()
        cout = sum(float(r.get("cout_unitaire", 0.0) or 0.0) * int(r.get("quantite", 0) or 0) for r in composition)
        if self._prix_auto_on():
            coef = self._parse_float(self._coef_var.get()) or 0.0
            if coef <= 0:
                coef = self._default_coef()
            auto_pv = round(cout * coef, 2)
            if self._pv_var.get() != str(auto_pv):
                self._pv_var.set(str(auto_pv))
        pv = self._parse_float(self._pv_var.get())
        pv = pv if pv is not None else 0.0
        marge = pv - cout
        conseille = cout * 2.0
        rent = 0.0 if cout <= 0 else (marge / cout) * 100.0

        self._cout_var.set(self._money(cout))
        self._conseille_var.set(self._money(conseille))
        self._marge_var.set(self._money(marge))
        self._rent_var.set(f"{rent:.1f} %".replace(".", ","))

    def _prix_auto_on(self) -> bool:
        try:
            return self._prix_auto_var.get() == "1"
        except (AttributeError, TypeError):
            return False

    def _on_prix_auto_toggle(self) -> None:
        self._mark_dirty()
        self._recompute_metrics()

    def _on_coef_changed(self) -> None:
        if self._prix_auto_on():
            self._recompute_metrics()

    def _on_vc_edited(self) -> None:
        self._vc_user_edited = True
        self._mark_dirty()

    def _auto_fill_vertus_chakras(self) -> None:
        if getattr(self, "_vc_user_edited", False):
            return
        try:
            from catalogue_services import aggregate_vertus, aggregate_chakras
        except Exception:
            return
        comp = []
        for row in self._composition_rows:
            cat = str(row["cat_var"].get()).strip() if "cat_var" in row else ""
            nom = str(row["comp_var"].get()).strip() if "comp_var" in row else ""
            comp.append({"categorie": cat, "composant": nom})
        fake = {"composition": comp}
        try:
            vertus = aggregate_vertus(fake, self.db)
            chakras = aggregate_chakras(fake, self.db)
        except Exception:
            return
        self._set_box_text(self._vertus_box, ", ".join(vertus))
        self._set_box_text(self._chakras_box, ", ".join(chakras))

    @staticmethod
    def _set_box_text(box, text: str) -> None:
        try:
            box.delete("1.0", "end")
            if text:
                box.insert("1.0", text)
        except Exception:
            pass

    def _default_coef(self) -> float:
        try:
            val = float(self.db.settings.get("price_coefficient", 2.5))
            return val if val > 0 else 2.5
        except (AttributeError, TypeError, ValueError):
            return 2.5

    def _apply_price_coef(self) -> None:
        coef = self._parse_float(self._coef_var.get())
        if coef is None or coef <= 0:
            mb.showerror("Tarif", "Coefficient invalide.", parent=self)
            return
        composition = self._composition_payload()
        cout = sum(float(r.get("cout_unitaire", 0.0) or 0.0) * int(r.get("quantite", 0) or 0) for r in composition)
        if cout <= 0:
            mb.showinfo("Tarif", "Ajoutez d'abord des composants pour calculer un prix.", parent=self)
            return
        pv = round(cout * coef, 2)
        self._pv_var.set(str(pv))
        try:
            self.db.settings["price_coefficient"] = coef
            self.db.save_settings()
        except (AttributeError, TypeError):
            pass
        self._recompute_metrics()

    def _import_image(self) -> None:
        source = fd.askopenfilename(
            title="Importer une image bracelet",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")],
        )
        if not source:
            return

        ok, msg = import_image_for_item(self.db, self._item_data, "bracelets", source)
        if not ok:
            mb.showerror("Image", msg, parent=self)
            return
        self._mark_dirty()
        self._update_preview()

    def _update_preview(self) -> None:
        from PIL import Image

        raw = str(self._item_data.get("photo", ""))
        path = Path(self.db.base_dir) / raw if raw else None
        if not path or not path.exists():
            self._preview_img = None
            self._preview_label.configure(image=None)
            self._photo_empty.place(relx=0.5, rely=0.5, anchor="center")
            return
        img = Image.open(path)
        self._preview_img = ctk.CTkImage(light_image=img, dark_image=img, size=(300, 300))
        self._preview_label.configure(image=self._preview_img)
        self._photo_empty.place_forget()

    def _save(self) -> None:
        nom = self._nom_var.get().strip()
        if not nom:
            mb.showerror("Validation", "Le nom est obligatoire.", parent=self)
            return

        stock = self._parse_int(self._stock_var.get())
        if stock is None or stock < 0:
            mb.showerror("Validation", "Le stock doit être >= 0.", parent=self)
            return

        pv = self._parse_float(self._pv_var.get())
        if pv is None or pv < 0:
            mb.showerror("Validation", "Le prix de vente doit être >= 0.", parent=self)
            return

        composition = self._composition_payload()
        now = datetime.now().isoformat(timespec="seconds")

        payload: dict[str, Any] = {
            "id": str(self.initial_item.get("id", "") or uuid.uuid4()),
            "reference": self._ref_var.get().strip(),
            "nom": nom,
            "composition": composition,
            "prix_vente": pv,
            "stock": stock,
            "genre": self._genre_var.get().strip(),
            "prix_auto": self._prix_auto_on(),
            "vertus": self._vertus_box.get("1.0", "end").strip(),
            "chakras": self._chakras_box.get("1.0", "end").strip(),
            "photo": str(self._item_data.get("photo", "")),
            "photo_thumb": str(self._item_data.get("photo_thumb", "")),
            "updated_at": now,
            "qr_enabled": bool(self.initial_item.get("qr_enabled", False)),
        }
        payload["created_at"] = self.initial_item.get("created_at", now)

        ok = self.on_submit(payload)
        if not ok:
            return

        self._dirty = False
        self._on_close_request()

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, list):
            return "\n".join(str(v) for v in raw)
        return str(raw or "")

    @staticmethod
    def _money(value: float) -> str:
        return f"{value:,.2f} EUR".replace(",", " ").replace(".", ",")

    @staticmethod
    def _parse_float(raw: str) -> float | None:
        text = (raw or "").strip().replace(",", ".")
        try:
            return float(text or "0")
        except ValueError:
            return None

    @staticmethod
    def _parse_int(raw: str) -> int | None:
        text = (raw or "").strip()
        try:
            return int(text or "0")
        except ValueError:
            return None

    @staticmethod
    def _add_labeled_widget(parent, row: int, col: int, label: str, widget) -> None:
        ctk.CTkLabel(parent, text=label, text_color=theme.TEXT_SECONDARY).grid(row=row * 2, column=col, sticky="w", padx=16, pady=(16, 6))
        widget.grid(row=row * 2 + 1, column=col, sticky="ew", padx=16)

    @classmethod
    def _add_labeled_entry(cls, parent, row: int, col: int, label: str, var: ctk.StringVar, state: str = "normal"):
        entry = ctk.CTkEntry(parent, textvariable=var, fg_color=theme.BG_INPUT, border_color=theme.BORDER, text_color=theme.TEXT_PRIMARY, state=state)
        cls._add_labeled_widget(parent, row, col, label, entry)
        return entry


class ProductEditor(BaseEditor):
    def __init__(self, parent, db: Any, mode: str, initial_item: dict[str, Any] | None, on_submit: Callable[[dict[str, Any]], bool]) -> None:
        super().__init__(parent, "Produit")
        self.db = db
        self.mode = mode
        self.initial_item = initial_item or {}
        self.on_submit = on_submit

        self._item_data = dict(self.initial_item)
        self._preview_img = None

        self._ref_var = ctk.StringVar(value="")
        self._nom_var = ctk.StringVar(value=str(self.initial_item.get("nom", "")))
        self._cat_var = ctk.StringVar(value=str(self.initial_item.get("categorie", "bracelets")))
        self._pa_var = ctk.StringVar(value=str(float(self.initial_item.get("prix_achat", 0.0) or 0.0)))
        self._pv_var = ctk.StringVar(value=str(float(self.initial_item.get("prix_vente", 0.0) or 0.0)))
        self._stock_var = ctk.StringVar(value=str(int(self.initial_item.get("stock", 0) or 0)))

        self._build_ui()
        self._bind_dirty_tracking()

        if mode == "edit":
            self._ref_var.set(str(self.initial_item.get("sku", self.initial_item.get("reference", ""))))
        else:
            self._ref_var.set(self._next_product_ref())

        self._update_preview()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=22, pady=(18, 8))
        ctk.CTkLabel(header, text="Produit", font=ctk.CTkFont(size=20, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w")

        tabs = ctk.CTkTabview(self, fg_color=theme.BG_CARD, segmented_button_fg_color=theme.BG_SIDEBAR)
        tabs.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        info_tab = tabs.add("Informations")
        photo_tab = tabs.add("Photo")

        self._build_info_tab(info_tab)
        self._build_photo_tab(photo_tab)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkButton(footer, text="Annuler", fg_color=theme.BG_SIDEBAR, hover_color=theme.BG_CARD_HOVER, command=self._on_close_request).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="Enregistrer", fg_color=theme.SUCCESS, hover_color=theme.ACCENT_TURQUOISE, command=self._save).pack(side="right")

    def _build_info_tab(self, tab) -> None:
        for col in range(2):
            tab.columnconfigure(col, weight=1)

        self._add_labeled_entry(tab, 0, 0, "Référence (auto)", self._ref_var, state="readonly")
        self._add_labeled_entry(tab, 0, 1, "Nom", self._nom_var)

        cat_menu = ctk.CTkOptionMenu(
            tab,
            variable=self._cat_var,
            values=self._product_categories(),
            fg_color=theme.BG_INPUT,
            button_color=theme.BG_CARD,
            button_hover_color=theme.BG_CARD_HOVER,
        )
        self._add_labeled_widget(tab, 1, 0, "Catégorie", cat_menu)

        self._add_labeled_entry(tab, 1, 1, "Prix revient", self._pa_var)
        self._add_labeled_entry(tab, 2, 0, "Prix vente", self._pv_var)
        self._add_labeled_entry(tab, 2, 1, "Stock", self._stock_var)

    def _build_photo_tab(self, tab) -> None:
        box = ctk.CTkFrame(tab, fg_color=theme.BG_SIDEBAR, corner_radius=16, width=280, height=280)
        box.pack(padx=20, pady=(20, 12), anchor="w")
        box.pack_propagate(False)

        self._preview_label = ctk.CTkLabel(box, text="", image=None)
        self._preview_label.place(relx=0.5, rely=0.5, anchor="center")

        self._photo_empty = ctk.CTkLabel(box, text="Image indisponible", text_color=theme.TEXT_SECONDARY)
        self._photo_empty.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkButton(tab, text="Importer une image", fg_color=theme.BG_CARD, hover_color=theme.BG_CARD_HOVER, command=self._import_image).pack(anchor="w", padx=20)

    def _bind_dirty_tracking(self) -> None:
        for var in [self._nom_var, self._cat_var, self._pa_var, self._pv_var, self._stock_var]:
            var.trace_add("write", self._mark_dirty)

    def _import_image(self) -> None:
        source = fd.askopenfilename(
            title="Importer une image produit",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")],
        )
        if not source:
            return

        ok, msg = import_image_for_item(self.db, self._item_data, "produits", source)
        if not ok:
            mb.showerror("Image", msg, parent=self)
            return
        self._mark_dirty()
        self._update_preview()

    def _update_preview(self) -> None:
        from PIL import Image

        raw = str(self._item_data.get("photo_thumb", "") or self._item_data.get("photo", ""))
        path = Path(self.db.base_dir) / raw if raw else None
        if not path or not path.exists():
            self._preview_img = None
            self._preview_label.configure(image=None)
            self._photo_empty.place(relx=0.5, rely=0.5, anchor="center")
            return

        img = Image.open(path)
        self._preview_img = ctk.CTkImage(light_image=img, dark_image=img, size=(240, 240))
        self._preview_label.configure(image=self._preview_img)
        self._photo_empty.place_forget()

    def _save(self) -> None:
        nom = self._nom_var.get().strip()
        if not nom:
            mb.showerror("Validation", "Le nom est obligatoire.", parent=self)
            return

        pa = self._parse_float(self._pa_var.get())
        if pa is None or pa < 0:
            mb.showerror("Validation", "Le prix revient doit être >= 0.", parent=self)
            return

        pv = self._parse_float(self._pv_var.get())
        if pv is None or pv < 0:
            mb.showerror("Validation", "Le prix vente doit être >= 0.", parent=self)
            return

        stock = self._parse_int(self._stock_var.get())
        if stock is None or stock < 0:
            mb.showerror("Validation", "Le stock doit être >= 0.", parent=self)
            return

        now = datetime.now().isoformat(timespec="seconds")
        ref = self._ref_var.get().strip()

        payload: dict[str, Any] = {
            "id": str(self.initial_item.get("id", "") or uuid.uuid4()),
            "categorie": self._cat_var.get().strip().lower(),
            "nom": nom,
            "sku": ref,
            "reference": ref,
            "prix_achat": pa,
            "prix_vente": pv,
            "stock": stock,
            "seuil_alerte": int(self.initial_item.get("seuil_alerte", self.db.settings.get("stock_alert_threshold", 5))),
            "fournisseur": str(self.initial_item.get("fournisseur", "")),
            "photo": str(self._item_data.get("photo", "")),
            "photo_thumb": str(self._item_data.get("photo_thumb", "")),
            "updated_at": now,
            "created_at": self.initial_item.get("created_at", now),
        }

        ok = self.on_submit(payload)
        if not ok:
            return

        self._dirty = False
        self._on_close_request()

    def _next_product_ref(self) -> str:
        used: set[int] = set()
        for item in self.db.products:
            ref = str(item.get("sku", item.get("reference", "")) or "").strip().upper()
            if ref.startswith("PRO-") and ref[4:].isdigit():
                used.add(int(ref[4:]))

        counter = int(self.db.settings.get("phase1c_counter_pro", 0) or 0)
        if used:
            counter = max(counter, max(used))
        n = counter + 1
        while n in used:
            n += 1
        return f"PRO-{n:04d}"

    def _product_categories(self) -> list[str]:
        base = {"bracelets", "pendentifs", "geodes", "arbres de vie", "autres"}
        for p in self.db.products:
            cat = str(p.get("categorie", "")).strip().lower()
            if cat:
                base.add(cat)
        return sorted(base)

    @staticmethod
    def _parse_float(raw: str) -> float | None:
        text = (raw or "").strip().replace(",", ".")
        try:
            return float(text or "0")
        except ValueError:
            return None

    @staticmethod
    def _parse_int(raw: str) -> int | None:
        text = (raw or "").strip()
        try:
            return int(text or "0")
        except ValueError:
            return None

    @staticmethod
    def _add_labeled_widget(parent, row: int, col: int, label: str, widget) -> None:
        ctk.CTkLabel(parent, text=label, text_color=theme.TEXT_SECONDARY).grid(row=row * 2, column=col, sticky="w", padx=16, pady=(16, 6))
        widget.grid(row=row * 2 + 1, column=col, sticky="ew", padx=16)

    @classmethod
    def _add_labeled_entry(cls, parent, row: int, col: int, label: str, var: ctk.StringVar, state: str = "normal"):
        entry = ctk.CTkEntry(parent, textvariable=var, fg_color=theme.BG_INPUT, border_color=theme.BORDER, text_color=theme.TEXT_PRIMARY, state=state)
        cls._add_labeled_widget(parent, row, col, label, entry)
        return entry
