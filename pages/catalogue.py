"""pages/catalogue.py — Catalogue commercial & fiches produits (Phase 2C)."""
from __future__ import annotations
import time
import tkinter.messagebox as mb
from tkinter import filedialog
import customtkinter as ctk
import theme
from widgets import Divider, SectionHeader
from catalogue_services import (
    generate_short_description,
    generate_long_description,
    suggest_names,
    suggest_themes,
    aggregate_vertus,
    aggregate_chakras,
    format_theme,
    export_fiche_pdf,
    export_catalogue_pdf,
    export_fiche_png,
    _find_stone_info,
)
from phase1c_services import load_ctk_image


class CataloguePage(ctk.CTkFrame):
    def __init__(self, parent, db=None, **kwargs) -> None:
        super().__init__(parent, fg_color=theme.BG_MAIN, **kwargs)
        self.db = db
        self._all_bracelets: list[dict] = []
        self._selected_id: str | None = None
        self._list_buttons: dict[str, ctk.CTkButton] = {}
        self._search_var = ctk.StringVar()
        self._search_after_id: str | None = None
        self._search_debounce_ms = 250
        self._photo_img = None
        self._generated_short: str = ""
        self._generated_long: str = ""
        self._name_suggestions: list[str] = []
        self._themes: list[str] = []

        self._build()
        self._load_list()

    def _build(self) -> None:
        SectionHeader(
            self, title="🛍  Catalogue",
            subtitle="Fiches commerciales automatiques — génération de contenu",
        ).pack(fill="x", padx=24, pady=(20, 0))
        Divider(self).pack(fill="x", padx=24, pady=(10, 0))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=(8, 16))
        body.grid_columnconfigure(0, weight=0, minsize=300)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_left(body)
        self._build_right(body)

    def _build_left(self, parent: ctk.CTkFrame) -> None:
        left = ctk.CTkFrame(parent, fg_color=theme.BG_SIDEBAR, corner_radius=16)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        ctk.CTkLabel(
            left, text="Bracelets",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=16, pady=(16, 8))

        search_entry = ctk.CTkEntry(
            left,
            placeholder_text="Rechercher...",
            height=34, corner_radius=10,
            fg_color=theme.BG_INPUT, border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
        )
        search_entry.pack(fill="x", padx=12, pady=(0, 8))
        self._search_var.trace_add("write", lambda *_: self._schedule_filter())
        search_entry.configure(textvariable=self._search_var)

        self._list_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self._list_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 12))

    def _build_right(self, parent: ctk.CTkFrame) -> None:
        self._right = ctk.CTkScrollableFrame(
            parent, fg_color=theme.BG_CARD, corner_radius=16,
        )
        self._right.grid(row=0, column=1, sticky="nsew")
        self._show_empty()

    def _show_empty(self) -> None:
        for w in self._right.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._right,
            text="Sélectionnez un bracelet\npour générer sa fiche commerciale",
            font=ctk.CTkFont(size=14),
            text_color=theme.TEXT_SECONDARY,
        ).pack(pady=80)

    # ── Data ───────────────────────────────────────────────────────

    def _load_list(self) -> None:
        self._all_bracelets = sorted(
            self.db.bracelets, key=lambda b: str(b.get("nom", "")).lower(),
        ) if self.db else []
        self._apply_filter()

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
        self._list_buttons.clear()

        for b in bracelets:
            bid = str(b.get("id", ""))
            ref = b.get("reference", "—")
            nom = b.get("nom", "Sans nom")
            btn = ctk.CTkButton(
                self._list_scroll,
                text=f"  {ref}\n  {nom}",
                anchor="w", height=48, corner_radius=12,
                fg_color="transparent", hover_color=theme.BG_CARD,
                text_color=theme.TEXT_PRIMARY,
                font=ctk.CTkFont(size=12),
                command=lambda rid=bid: self._select(rid),
            )
            btn.pack(fill="x", pady=2)
            self._list_buttons[bid] = btn

        if not bracelets:
            ctk.CTkLabel(
                self._list_scroll, text="Aucun bracelet",
                text_color=theme.TEXT_SECONDARY,
            ).pack(pady=20)

        auto = self._selected_id if self._selected_id in self._list_buttons else (
            str(bracelets[0].get("id", "")) if bracelets else None
        )
        if auto:
            self._select(auto)

    def _select(self, bracelet_id: str) -> None:
        if self._selected_id == bracelet_id:
            return
        self._selected_id = bracelet_id
        for rid, btn in self._list_buttons.items():
            active = rid == bracelet_id
            btn.configure(
                fg_color=theme.BG_CARD if active else "transparent",
                text_color=theme.ACCENT_TURQUOISE if active else theme.TEXT_PRIMARY,
                font=ctk.CTkFont(size=12, weight="bold") if active else ctk.CTkFont(size=12),
            )

        b = next((bb for bb in self._all_bracelets if str(bb.get("id", "")) == bracelet_id), None)
        if b is None:
            return

        self._generated_short = generate_short_description(b, self.db)
        self._generated_long = generate_long_description(b, self.db)
        self._name_suggestions = suggest_names(b, self.db)
        self._themes = suggest_themes(b, self.db)

        self._render_fiche(b)

    # ── Fiche ──────────────────────────────────────────────────────

    def _render_fiche(self, b: dict) -> None:
        t0 = time.perf_counter()
        for w in self._right.winfo_children():
            w.destroy()

        pad = 24
        cont = ctk.CTkFrame(self._right, fg_color="transparent")
        cont.pack(fill="both", expand=True, padx=pad, pady=pad)

        # ── Bloc principal ─────────────────────────────────────────
        main = ctk.CTkFrame(cont, fg_color=theme.BG_INPUT, corner_radius=12)
        main.pack(fill="x", pady=(0, 12))
        row0 = ctk.CTkFrame(main, fg_color="transparent")
        row0.pack(fill="x", padx=16, pady=12)
        row0.grid_columnconfigure(1, weight=1)

        photo = ctk.CTkFrame(row0, fg_color=theme.BG_CARD, corner_radius=10, width=120, height=120)
        photo.grid(row=0, column=0, rowspan=4, padx=(0, 16), sticky="nw")
        photo.pack_propagate(False)
        img = load_ctk_image(self.db, b, size=(110, 110), use_thumb=True) if self.db else None
        self._photo_img = img
        if img:
            ctk.CTkLabel(photo, image=img, text="").pack(padx=5, pady=5)
        else:
            ctk.CTkLabel(photo, text="📷", font=ctk.CTkFont(size=36),
                         text_color=theme.TEXT_SECONDARY).pack(expand=True)

        info_data = [
            ("Nom", b.get("nom", "—")),
            ("Référence", b.get("reference", "—")),
            ("Prix", f"{float(b.get('prix_vente', 0) or 0):.2f} €".replace(".", ",")),
        ]
        stock = int(b.get("stock", 0) or 0)
        disc = "✅ En stock" if stock > 0 else "❌ Rupture"
        disc_color = theme.SUCCESS if stock > 0 else theme.DANGER
        info_data.append(("Disponibilité", disc))

        for i, (label, value) in enumerate(info_data):
            ctk.CTkLabel(
                row0, text=f"{label} :",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=theme.TEXT_SECONDARY,
            ).grid(row=i, column=1, sticky="w", padx=(0, 8), pady=2)
            ctk.CTkLabel(
                row0, text=value,
                font=ctk.CTkFont(size=14),
                text_color=disc_color if label == "Disponibilité" else theme.TEXT_PRIMARY,
            ).grid(row=i, column=2, sticky="w", pady=2)

        Divider(cont).pack(fill="x", pady=(0, 12))

        # ── Composition ────────────────────────────────────────────
        SectionHeader(cont, title="Composition", subtitle="Pierres et composants").pack(fill="x")
        comp_frame = ctk.CTkFrame(cont, fg_color=theme.BG_INPUT, corner_radius=8)
        comp_frame.pack(fill="x", pady=(8, 12))
        for comp in b.get("composition", []):
            c = comp.get("composant", "?")
            qty = comp.get("quantite", 1)
            ctk.CTkLabel(
                comp_frame, text=f"  •  {c}  x{qty}",
                font=ctk.CTkFont(size=13),
                text_color=theme.TEXT_PRIMARY,
            ).pack(anchor="w", padx=16, pady=3)

        # ── Vertus & Chakras ──────────────────────────────────────
        vertus = aggregate_vertus(b, self.db)
        chakras = aggregate_chakras(b, self.db)
        if vertus:
            SectionHeader(cont, title="Vertus", subtitle="Propriétés des pierres utilisées").pack(fill="x")
            vf = ctk.CTkFrame(cont, fg_color=theme.BG_INPUT, corner_radius=8)
            vf.pack(fill="x", pady=(8, 12))
            ctk.CTkLabel(
                vf, text="  " + "   •   ".join(vertus[:6]),
                font=ctk.CTkFont(size=13),
                text_color=theme.ACCENT_TURQUOISE,
            ).pack(anchor="w", padx=16, pady=8)

        if chakras:
            SectionHeader(cont, title="Chakras", subtitle="Énergies associées").pack(fill="x")
            cf = ctk.CTkFrame(cont, fg_color=theme.BG_INPUT, corner_radius=8)
            cf.pack(fill="x", pady=(8, 12))
            ctk.CTkLabel(
                cf, text="  " + "   •   ".join(chakras),
                font=ctk.CTkFont(size=13),
                text_color=theme.ACCENT_AMETHYSTE,
            ).pack(anchor="w", padx=16, pady=8)

        Divider(cont).pack(fill="x", pady=(0, 12))

        # ── Descriptions éditables ────────────────────────────────
        SectionHeader(cont, title="Descriptions", subtitle="Générées — modifiables").pack(fill="x")

        ctk.CTkLabel(
            cont, text="Courte",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(8, 4))
        short_text = ctk.CTkTextbox(cont, height=50, corner_radius=8,
                                     fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY,
                                     font=ctk.CTkFont(size=12))
        short_text.pack(fill="x", pady=(0, 8))
        saved_short = b.get("description_courte", "") or self._generated_short
        short_text.insert("0.0", saved_short)

        ctk.CTkLabel(
            cont, text="Longue",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(4, 4))
        long_text = ctk.CTkTextbox(cont, height=90, corner_radius=8,
                                    fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY,
                                    font=ctk.CTkFont(size=12))
        long_text.pack(fill="x", pady=(0, 8))
        saved_long = b.get("description_longue", "") or self._generated_long
        long_text.insert("0.0", saved_long)

        save_desc_btn = ctk.CTkButton(
            cont, text="💾 Enregistrer descriptions",
            font=ctk.CTkFont(size=12), height=32, corner_radius=8,
            fg_color=theme.BG_CARD, text_color=theme.ACCENT_TURQUOISE,
            hover_color=theme.BG_CARD_HOVER,
            command=lambda: self._save_descriptions(b, short_text, long_text),
        )
        save_desc_btn.pack(anchor="w", pady=(0, 12))

        Divider(cont).pack(fill="x", pady=(0, 12))

        # ── Noms proposés ──────────────────────────────────────────
        if self._name_suggestions:
            SectionHeader(cont, title="Noms proposés",
                          subtitle="Générés à partir de la composition").pack(fill="x")
            nf = ctk.CTkFrame(cont, fg_color=theme.BG_INPUT, corner_radius=8)
            nf.pack(fill="x", pady=(8, 12))
            for name in self._name_suggestions:
                nr = ctk.CTkFrame(nf, fg_color="transparent")
                nr.pack(fill="x", padx=12, pady=3)
                ctk.CTkLabel(
                    nr, text=f"  ✨  {name}",
                    font=ctk.CTkFont(size=13),
                    text_color=theme.TEXT_PRIMARY,
                ).pack(side="left")
                accept_btn = ctk.CTkButton(
                    nr, text="Accepter",
                    font=ctk.CTkFont(size=10), height=24, corner_radius=6,
                    fg_color=theme.SUCCESS, text_color="white",
                    hover_color="#059669",
                    command=lambda n=name, bb=b: self._accept_name(bb, n),
                )
                accept_btn.pack(side="right")

        # ── Thèmes ─────────────────────────────────────────────────
        if self._themes:
            Divider(cont).pack(fill="x", pady=(0, 12))
            SectionHeader(cont, title="Thèmes", subtitle="Associés aux pierres").pack(fill="x")
            tf = ctk.CTkFrame(cont, fg_color=theme.BG_INPUT, corner_radius=8)
            tf.pack(fill="x", pady=(8, 12))
            tags = "    ".join(format_theme(t) for t in self._themes)
            ctk.CTkLabel(
                tf, text=f"  {tags}",
                font=ctk.CTkFont(size=13),
                text_color=theme.TEXT_PRIMARY,
            ).pack(anchor="w", padx=16, pady=8)

        # ── Stone details ──────────────────────────────────────────
        pierres = [c for c in b.get("composition", []) if c.get("categorie", "") == "Pierre"]
        if pierres:
            Divider(cont).pack(fill="x", pady=(0, 12))
            SectionHeader(cont, title="Bibliothèque des pierres",
                          subtitle="Détail des pierres utilisées").pack(fill="x")
            for comp in pierres:
                name = comp.get("composant", "")
                sf = ctk.CTkFrame(cont, fg_color=theme.BG_INPUT, corner_radius=8)
                sf.pack(fill="x", pady=(4, 4))
                inner = ctk.CTkFrame(sf, fg_color="transparent")
                inner.pack(fill="x", padx=14, pady=8)

                ctk.CTkLabel(
                    inner, text=f"💎  {name}",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=theme.ACCENT_TURQUOISE,
                ).pack(anchor="w")

                info = _find_stone_info(name)
                if info:
                    if info.get("signes"):
                        ctk.CTkLabel(
                            inner,
                            text=f"Signes : {', '.join(info['signes'][:3])}",
                            font=ctk.CTkFont(size=11),
                            text_color=theme.TEXT_SECONDARY,
                        ).pack(anchor="w", pady=(2, 0))
                    if info.get("purification"):
                        ctk.CTkLabel(
                            inner,
                            text=f"Purification : {info['purification']}",
                            font=ctk.CTkFont(size=11),
                            text_color=theme.TEXT_SECONDARY,
                        ).pack(anchor="w")
                    if info.get("rechargement"):
                        ctk.CTkLabel(
                            inner,
                            text=f"Rechargement : {info['rechargement']}",
                            font=ctk.CTkFont(size=11),
                            text_color=theme.TEXT_SECONDARY,
                        ).pack(anchor="w")
                    if info.get("description"):
                        ctk.CTkLabel(
                            inner,
                            text=info["description"],
                            font=ctk.CTkFont(size=11),
                            text_color=theme.TEXT_PRIMARY,
                            wraplength=500,
                        ).pack(anchor="w", pady=(4, 0))

        # ── Export ─────────────────────────────────────────────────
        Divider(cont).pack(fill="x", pady=(12, 12))
        SectionHeader(cont, title="Export", subtitle="Fiches et catalogue").pack(fill="x")

        exp_row = ctk.CTkFrame(cont, fg_color="transparent")
        exp_row.pack(fill="x", pady=(8, 4))

        exports = [
            ("📄 Fiche Boutique", self._export_boutique, theme.ACCENT_TURQUOISE),
            ("📄 Fiche Client", self._export_client, theme.ACCENT_AMETHYSTE),
            ("📄 Fiche Marché", self._export_marche, theme.WARNING),
            ("🖼️  Export PNG", self._export_png, theme.SUCCESS),
        ]
        for text, cmd, color in exports:
            ctk.CTkButton(
                exp_row, text=text,
                font=ctk.CTkFont(size=12), height=34, corner_radius=8,
                fg_color=color, text_color="white",
                hover_color=theme.BG_CARD_HOVER,
                command=cmd,
            ).pack(side="left", padx=4)

        ctk.CTkButton(
            cont, text="📕 Catalogue complet PDF",
            font=ctk.CTkFont(size=13, weight="bold"), height=40, corner_radius=10,
            fg_color=theme.BG_CARD, text_color=theme.ACCENT_TURQUOISE,
            hover_color=theme.BG_CARD_HOVER, border_width=1, border_color=theme.ACCENT_TURQUOISE,
            command=self._export_catalogue,
        ).pack(anchor="w", pady=(8, 0))

        ms = (time.perf_counter() - t0) * 1000
        ctk.CTkLabel(
            cont, text=f"Fiche générée en {ms:.0f} ms",
            font=ctk.CTkFont(size=10),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(6, 0))

    # ── Actions ────────────────────────────────────────────────────

    def _save_descriptions(self, b: dict, short_w: ctk.CTkTextbox, long_w: ctk.CTkTextbox) -> None:
        short = short_w.get("0.0", "end").strip()
        long = long_w.get("0.0", "end").strip()
        b["description_courte"] = short
        b["description_longue"] = long
        b["updated_at"] = __import__("datetime").datetime.now().isoformat()
        self.db.save_bracelets()
        mb.showinfo("Descriptions", "Descriptions enregistrées.")

    def _accept_name(self, b: dict, name: str) -> None:
        old = b.get("nom", "")
        b["nom"] = name
        b["updated_at"] = __import__("datetime").datetime.now().isoformat()
        self.db.save_bracelets()
        self._load_list()
        self._select(str(b.get("id", "")))
        mb.showinfo("Nom", f"✅ Bracelet renommé :\n« {old} » → « {name} »")

    def _export_boutique(self) -> None:
        self._export_pdf("boutique")

    def _open_file(self, file_path: str) -> None:
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

    def _export_client(self) -> None:
        self._export_pdf("client")

    def _export_marche(self) -> None:
        self._export_pdf("marche")

    def _export_pdf(self, fmt: str) -> None:
        b = self._current_bracelet()
        if not b:
            return
        import tempfile, os as _os
        from datetime import datetime as _dt
        path = _os.path.join(tempfile.gettempdir(), f"fiche_{fmt}_{_dt.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        ok = export_fiche_pdf(b, self.db, fmt, path)
        if ok:
            self._open_file(path)
        else:
            mb.showerror("Export", "Erreur lors de l'export PDF.")

    def _export_png(self) -> None:
        b = self._current_bracelet()
        if not b:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png")],
            title="Exporter fiche PNG",
        )
        if not path:
            return
        t0 = time.perf_counter()
        ok = export_fiche_png(b, self.db, path)
        ms = (time.perf_counter() - t0) * 1000
        if ok:
            mb.showinfo("Export", f"✅ PNG exporté ({ms:.0f} ms).")
        else:
            mb.showerror("Export", "Erreur lors de l'export PNG.")

    def _export_catalogue(self) -> None:
        import tempfile, os as _os
        from datetime import datetime as _dt
        path = _os.path.join(tempfile.gettempdir(), f"catalogue_{_dt.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        ok = export_catalogue_pdf(self._all_bracelets, self.db, path)
        if ok:
            self._open_file(path)
        else:
            mb.showerror("Export", "Erreur lors de l'export du catalogue.")

    def _current_bracelet(self) -> dict | None:
        return next((b for b in self._all_bracelets if str(b.get("id", "")) == self._selected_id), None)

    def refresh(self) -> None:
        self._load_list()



