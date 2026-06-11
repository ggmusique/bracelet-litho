"""pages/parametres.py
Page Paramètres — Lithothérapie Pro V2.
Phase 1B : affichage des vraies valeurs depuis settings + backup.
"""
from __future__ import annotations
import customtkinter as ctk
import theme
from phase1c_services import get_backup_stats, run_rotating_backup
from widgets import SectionHeader, Divider
from version import APP_VERSION, APP_NAME


class ParametresPage(ctk.CTkFrame):
    """Page des paramètres du logiciel."""

    def __init__(self, parent, db=None, **kwargs) -> None:
        kwargs.setdefault("fg_color", theme.BG_MAIN)
        super().__init__(parent, **kwargs)
        self.db = db
        self._entries: dict[str, ctk.CTkEntry] = {}
        self._backup_values: dict[str, ctk.CTkLabel] = {}
        self._build()

    # ── Construction ─────────────────────────────────────────────────

    def _build(self) -> None:
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=theme.BG_MAIN, scrollbar_button_color=theme.BORDER
        )
        scroll.pack(fill="both", expand=True)

        SectionHeader(scroll, title="⚙  Paramètres",
                      subtitle="Configuration de Lithothérapie Pro").pack(fill="x", padx=32, pady=(28, 0))
        Divider(scroll).pack(fill="x", padx=32, pady=20)

        s = self.db.settings if self.db else {}

        # ── Apparence ────────────────────────────────────────────────
        self._section(scroll, "🎨  Apparence", [
            ("Thème",              s.get("theme", "clair"),         "theme"),
            ("Police étiquettes",  s.get("label_font", "Helvetica"), "label_font"),
        ])

        # ── Sauvegarde ───────────────────────────────────────────────
        self._section(scroll, "💾  Sauvegarde", [
            ("Autosave (secondes)", str(s.get("autosave_seconds", 120)), "autosave_seconds"),
            ("Dossier base",        str(self.db.base_dir) if self.db else "—", None),
            ("Logo actuel",         str(s.get("logo_path", "")) or "(aucun)", "logo_path"),
        ])
        self._build_backup_stats(scroll)
        # Bouton Créer backup
        self._action_btn(scroll, "💾  Créer une sauvegarde maintenant", self._do_backup)
        self._action_btn(scroll, "🛡  Forcer une rotation des sauvegardes", self._do_rotation_backup)
        self._action_btn(scroll, "📦  Exporter toutes mes donnees (ZIP)", self._do_export_archive)
        self._action_btn(scroll, "♻  Restaurer une sauvegarde…", self._do_restore)

        # ── Stock ─────────────────────────────────────────────────────
        self._section(scroll, "📦  Stock", [
            ("Seuil d'alerte",    str(s.get("stock_alert_threshold", 5)),  "stock_alert_threshold"),
            ("Objectif de stock", str(s.get("stock_target", 20)),          "stock_target"),
        ])

        # ── Impression ────────────────────────────────────────────────
        self._section(scroll, "🖨  Impression", [
            ("QR Code par défaut", "Oui" if s.get("default_qr") else "Non", None),
        ])

        # ── Mise à jour ───────────────────────────────────────────────
        self._section(scroll, "🔗  Mise à jour", [
            ("URL manifeste",      s.get("update_manifest_url", "—"),  "update_manifest_url"),
            ("URL téléchargement", s.get("update_download_url", "—"),  "update_download_url"),
        ])

        # ── À propos ─────────────────────────────────────────────────
        self._build_about(scroll)

    # ── Helpers construction ──────────────────────────────────────────

    def _section(self, parent, title: str, fields: list[tuple[str, str, str | None]]) -> None:
        panel = ctk.CTkFrame(parent, fg_color=theme.BG_CARD, corner_radius=16)
        panel.pack(fill="x", padx=32, pady=(0, 16))

        ctk.CTkLabel(panel, text=title, font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=theme.TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(16, 8))
        ctk.CTkFrame(panel, height=1, fg_color=theme.BORDER).pack(fill="x", padx=20, pady=(0, 10))

        for label, value, key in fields:
            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=5)

            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=13),
                         text_color=theme.TEXT_SECONDARY, width=200, anchor="w").pack(side="left")

            entry = ctk.CTkEntry(
                row, height=34, width=320, corner_radius=10,
                fg_color=theme.BG_INPUT, border_color=theme.BORDER,
                text_color=theme.TEXT_PRIMARY,
                state="normal" if key else "disabled",
            )
            entry.insert(0, value)
            if not key:
                entry.configure(state="disabled")
            entry.pack(side="left")

            if key:
                self._entries[key] = entry

        ctk.CTkFrame(panel, fg_color="transparent", height=12).pack()

    def _action_btn(self, parent, label: str, cmd) -> None:
        ctk.CTkButton(
            parent, text=label, height=38, corner_radius=16,
            fg_color=theme.BG_CARD, text_color=theme.ACCENT_TURQUOISE,
            hover_color=theme.BG_CARD_HOVER, border_color=theme.ACCENT_TURQUOISE,
            border_width=1, font=ctk.CTkFont(size=13),
            command=cmd,
        ).pack(fill="x", padx=32, pady=(0, 16))

    def _build_about(self, parent) -> None:
        panel = ctk.CTkFrame(parent, fg_color=theme.BG_CARD, corner_radius=16)
        panel.pack(fill="x", padx=32, pady=(0, 32))

        ctk.CTkLabel(panel, text="ℹ  À propos", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=theme.TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(16, 8))
        ctk.CTkFrame(panel, height=1, fg_color=theme.BORDER).pack(fill="x", padx=20, pady=(0, 10))

        db_version = self.db.settings.get("version", APP_VERSION) if self.db else APP_VERSION

        for lbl, val in [
            ("Logiciel",       APP_NAME),
            ("Version DB",     db_version),
            ("Version V2",     f"v{APP_VERSION}  —  Phase 1B"),
            ("Interface",      "CustomTkinter 5.2+"),
            ("Python",         "3.14+"),
        ]:
            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=4)
            ctk.CTkLabel(row, text=lbl, font=ctk.CTkFont(size=12),
                         text_color=theme.TEXT_SECONDARY, width=130, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=val, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=theme.TEXT_PRIMARY, anchor="w").pack(side="left")

        ctk.CTkFrame(panel, fg_color="transparent", height=12).pack()

    def _build_backup_stats(self, parent) -> None:
        panel = ctk.CTkFrame(parent, fg_color=theme.BG_CARD, corner_radius=16)
        panel.pack(fill="x", padx=32, pady=(0, 16))

        ctk.CTkLabel(
            panel,
            text="📊  Etat des sauvegardes auto",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=20, pady=(16, 8))
        ctk.CTkFrame(panel, height=1, fg_color=theme.BORDER).pack(fill="x", padx=20, pady=(0, 10))

        for key, label in [
            ("last", "Derniere sauvegarde"),
            ("count", "Nombre de sauvegardes"),
            ("size", "Taille totale"),
        ]:
            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=4)
            ctk.CTkLabel(row, text=label, width=180, anchor="w", text_color=theme.TEXT_SECONDARY).pack(side="left")
            value_lbl = ctk.CTkLabel(row, text="—", anchor="w", text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(weight="bold"))
            value_lbl.pack(side="left")
            self._backup_values[key] = value_lbl

        ctk.CTkFrame(panel, fg_color="transparent", height=12).pack()
        self._refresh_backup_stats()

    def _refresh_backup_stats(self) -> None:
        stats = get_backup_stats(self.db)
        for key, lbl in self._backup_values.items():
            lbl.configure(text=stats.get(key, "—"))

    # ── Actions ───────────────────────────────────────────────────────

    def _do_backup(self) -> None:
        if not self.db:
            return
        import tkinter.filedialog as fd
        import tkinter.messagebox as mb
        path = fd.asksaveasfilename(
            title="Enregistrer la sauvegarde",
            defaultextension=".zip",
            filetypes=[("Archive ZIP", "*.zip")],
        )
        if not path:
            return
        ok, msg = self.db.create_backup(path)
        if ok:
            mb.showinfo("Sauvegarde", f"Sauvegarde créée :\n{path}")
            self._refresh_backup_stats()
        else:
            mb.showerror("Erreur", msg)

    def _do_rotation_backup(self) -> None:
        if not self.db:
            return
        import tkinter.messagebox as mb

        ok, msg = run_rotating_backup(self.db)
        if ok:
            mb.showinfo("Sauvegarde", msg)
            self._refresh_backup_stats()
        else:
            mb.showerror("Erreur", msg)


    def _do_export_archive(self) -> None:
        if not self.db:
            return
        import tkinter.filedialog as fd
        import tkinter.messagebox as mb
        from datetime import datetime
        suggested = f"lithotherapie_export_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
        path = fd.asksaveasfilename(
            title="Exporter toutes mes donnees",
            defaultextension=".zip",
            filetypes=[("Archive ZIP", "*.zip")],
            initialfile=suggested,
        )
        if not path:
            return
        ok, msg = self.db.export_full_archive(path)
        if ok:
            mb.showinfo("Export", f"Export complet reussi : {path}")
            self._refresh_backup_stats()
        else:
            mb.showerror("Erreur", msg)

    def _do_restore(self) -> None:
        if not self.db:
            return
        import tkinter.filedialog as fd
        import tkinter.messagebox as mb
        path = fd.askopenfilename(
            title="Choisir une sauvegarde a restaurer",
            filetypes=[("Sauvegardes", "*.zip *.json"), ("Archive ZIP", "*.zip"), ("JSON", "*.json")],
        )
        if not path:
            return
        if not mb.askyesno("Restauration", "Cette operation remplacera toutes les donnees actuelles. Continuer ?"):
            return
        if str(path).lower().endswith(".zip"):
            ok, msg = self.db.restore_full_archive(path)
        else:
            ok, msg = self.db.restore_backup(path)
        if ok:
            mb.showinfo("Restauration", f"{msg} Redemarrez l'application pour voir les donnees restaurees.")
            self._refresh_backup_stats()
        else:
            mb.showerror("Erreur", msg)