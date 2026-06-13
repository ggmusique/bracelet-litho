"""ui_v2.py
Fenêtre principale — Lithothérapie Pro V2.
Interface moderne basée sur CustomTkinter 5.2+.

Lancement en mode test (sans modifier main.py) :
    py ui_v2.py
"""
from __future__ import annotations
import time
import customtkinter as ctk

# Charge les correctifs runtime du projet dès le démarrage de la V2.
# Important sous Windows : le module sitecustomize n'est pas toujours chargé
# automatiquement assez tôt selon la façon dont l'application est lancée.
import sitecustomize  # noqa: F401

import theme
from phase1c_services import normalize_phase1c_data, run_rotating_backup
from version import APP_NAME, APP_VERSION
from pages.dashboard    import DashboardPage
from pages.composants   import ComposantsPage
from pages.bracelets    import BraceletsPage
from pages.fabrication  import FabricationPage
from pages.niimbot      import NiimbotPage
from pages.catalogue    import CataloguePage
from pages.produits     import ProduitsPage
from pages.stock        import StockPage
from pages.parametres   import ParametresPage


# ── Définition de la navigation ───────────────────────────────────────
_NAV_ITEMS: list[tuple[str, str, str]] = [
    ("📊", "Tableau de bord", "dashboard"),
    ("📦", "Composants",      "composants"),
    ("📿", "Bracelets",       "bracelets"),
    ("🏭", "Fabrication",     "fabrication"),
    ("🏷",  "NIIMBOT",        "niimbot"),
    ("🛍",  "Catalogue",      "catalogue"),
    ("🛒",  "Produits",       "produits"),
    ("📈", "Stock",           "stock"),
    ("⚙",  "Paramètres",     "parametres"),
]

_PAGE_MAP: dict[str, type] = {
    "dashboard":  DashboardPage,
    "composants": ComposantsPage,
    "bracelets":  BraceletsPage,
    "fabrication": FabricationPage,
    "niimbot":    NiimbotPage,
    "catalogue":  CataloguePage,
    "produits":   ProduitsPage,
    "stock":      StockPage,
    "parametres": ParametresPage,
}


class LithotherapieV2(ctk.CTk):
    """Fenêtre racine de l'interface Lithothérapie Pro V2."""

    def __init__(self, db=None) -> None:
        super().__init__()
        self.db = db
        self._active_page: str = ""
        self._page_widget: ctk.CTkFrame | None = None
        self._page_cache: dict[str, ctk.CTkFrame] = {}
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._global_search_var = ctk.StringVar()
        self._global_results: list[dict] = []
        self._global_index: list[dict] = []
        self._global_debounce_ms = 250
        self._global_after_id: str | None = None
        self._global_index_dirty = False
        self._perf: dict[str, list[float]] = {
            "startup": [],
            "show_page": [],
            "global_search": [],
        }

        if self.db:
            normalize_phase1c_data(self.db)
            run_rotating_backup(self.db)
            self._build_global_index()

        # ── Fenêtre ──────────────────────────────────────────────────
        self.title(f"💎  {APP_NAME}  —  Pro V2")
        self.geometry("1400x900")
        self.minsize(1200, 800)
        self.configure(fg_color=theme.BG_MAIN)

        # ── Construction ─────────────────────────────────────────────
        self._build_sidebar()
        self._build_content_area()
        self._build_topbar()
        self._global_search_var.trace_add("write", lambda *_: self._on_global_search_change())

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Page d'accueil
        self.show_page("dashboard")

    # ── Sidebar ──────────────────────────────────────────────────────

    def _build_sidebar(self) -> None:
        self._sidebar = ctk.CTkFrame(
            self,
            width=280,
            fg_color=theme.BG_SIDEBAR,
            corner_radius=0,
        )
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        self._build_logo()
        self._build_nav_buttons()
        self._build_version_footer()

    def _build_logo(self) -> None:
        import os
        logo = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        logo.pack(fill="x", padx=22, pady=(32, 24))

        # Tente de charger logo.png si présent dans le dossier du db
        logo_path = ""
        if self.db:
            s = getattr(self.db, "settings", {})
            logo_path = str(s.get("logo_path", "") or "")

        if logo_path and os.path.isfile(logo_path):
            try:
                img = ctk.CTkImage(light_image=__import__("PIL").Image.open(logo_path),
                                   dark_image=__import__("PIL").Image.open(logo_path),
                                   size=(48, 48))
                ctk.CTkLabel(logo, image=img, text="").pack(anchor="w")
            except Exception:
                logo_path = ""  # fallback

        if not logo_path:
            ctk.CTkLabel(
                logo, text="💎",
                font=ctk.CTkFont(size=36),
                text_color=theme.ACCENT_TURQUOISE,
            ).pack(anchor="w")

        ctk.CTkLabel(
            logo, text="Lithothérapie",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(4, 0))

        ctk.CTkLabel(
            logo, text="Pro  V2",
            font=ctk.CTkFont(size=12),
            text_color=theme.ACCENT_TURQUOISE,
        ).pack(anchor="w")

        ctk.CTkFrame(self._sidebar, height=1, fg_color=theme.BORDER).pack(fill="x", padx=16, pady=(16, 8))

    def _build_nav_buttons(self) -> None:
        nav = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        nav.pack(fill="x", padx=10, pady=(4, 0))

        for icon, label, page_id in _NAV_ITEMS:
            btn = ctk.CTkButton(
                nav,
                text=f"  {icon}   {label}",
                anchor="w",
                height=46,
                corner_radius=16,
                border_width=0,
                fg_color="transparent",
                text_color=theme.TEXT_SECONDARY,
                hover_color=theme.BG_CARD,
                font=ctk.CTkFont(size=14),
                command=lambda pid=page_id: self.show_page(pid),
            )
            btn.pack(fill="x", pady=2)
            self._nav_buttons[page_id] = btn

    def _build_version_footer(self) -> None:
        footer = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=16, pady=16)

        ctk.CTkFrame(footer, height=1, fg_color=theme.BORDER).pack(
            fill="x", pady=(0, 12)
        )
        ctk.CTkLabel(
            footer,
            text=f"v{APP_VERSION}  •  V2 Preview",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            footer,
            text="Phase 2D — Autonomie V2",
            font=ctk.CTkFont(size=10),
            text_color=theme.BORDER,
        ).pack(anchor="w", pady=(2, 0))

    # ── Zone de contenu ───────────────────────────────────────────────

    def _build_content_area(self) -> None:
        self._content = ctk.CTkFrame(
            self,
            fg_color=theme.BG_MAIN,
            corner_radius=0,
        )
        self._content.pack(side="right", fill="both", expand=True)

    def _build_topbar(self) -> None:
        self._topbar = ctk.CTkFrame(self._content, fg_color="transparent")
        self._topbar.pack(fill="x", padx=24, pady=(16, 0))

        ctk.CTkLabel(
            self._topbar,
            text="Recherche globale",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(0, 6))

        self._global_entry = ctk.CTkEntry(
            self._topbar,
            textvariable=self._global_search_var,
            placeholder_text="Composants, bracelets, produits...",
            height=38,
            corner_radius=12,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
        )
        self._global_entry.pack(fill="x")

        self._results_wrap = ctk.CTkFrame(self._topbar, fg_color=theme.BG_CARD, corner_radius=12)
        self._results_wrap.pack(fill="x", pady=(6, 0))
        self._results_wrap.pack_forget()

        self._results_scroll = ctk.CTkScrollableFrame(
            self._results_wrap,
            fg_color="transparent",
            scrollbar_button_color=theme.BORDER,
            height=220,
        )
        self._results_scroll.pack(fill="both", expand=True, padx=8, pady=8)

    # ── Navigation ────────────────────────────────────────────────────

    def show_page(self, page_id: str) -> None:
        """Charge et affiche la page demandée dans la zone de contenu."""
        t0 = time.perf_counter()
        if self._active_page == page_id:
            return

        # Masquer la page courante (cache local pour éviter destroy/recreate)
        if self._page_widget is not None:
            self._page_widget.pack_forget()

        # Mettre à jour l'état visuel des boutons de navigation
        for pid, btn in self._nav_buttons.items():
            if pid == page_id:
                btn.configure(
                    fg_color=theme.BG_CARD,
                    text_color=theme.ACCENT_TURQUOISE,
                    font=ctk.CTkFont(size=14, weight="bold"),
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=theme.TEXT_SECONDARY,
                    font=ctk.CTkFont(size=14),
                )

        # Instancier et afficher la page
        if page_id in self._page_cache:
            self._page_widget = self._page_cache[page_id]
        else:
            cls = _PAGE_MAP.get(page_id)
            if cls is None:
                return
            self._page_widget = cls(self._content, db=self.db)
            self._page_cache[page_id] = self._page_widget

        self._page_widget.pack(fill="both", expand=True, pady=(8, 0))

        if hasattr(self._page_widget, "refresh"):
            self._page_widget.refresh()

        self._active_page = page_id
        self._perf["show_page"].append(time.perf_counter() - t0)

    def _on_global_search_change(self) -> None:
        if self._global_after_id:
            self.after_cancel(self._global_after_id)
            self._global_after_id = None
        self._global_after_id = self.after(self._global_debounce_ms, self._run_global_search)

    def _run_global_search(self) -> None:
        t0 = time.perf_counter()
        self._global_after_id = None
        q = self._global_search_var.get().strip().lower()
        if not q:
            self._hide_global_results()
            return

        # Reconstruction systematique de l index pour des resultats toujours a jour
        # (apres ajout / modification / suppression de composants, bracelets, produits).
        self._build_global_index()
        self._global_index_dirty = False

        matches = [row for row in self._global_index if q in row["search"]]
        self._global_results = matches[:15]
        self._render_global_results()
        self._perf["global_search"].append(time.perf_counter() - t0)

    def _build_global_index(self) -> None:
        if not self.db:
            self._global_index = []
            return

        rows: list[dict] = []

        def add(kind: str, label: str, sub: str, rid: str, subcat: str = "") -> None:
            rows.append(
                {
                    "kind": kind,
                    "label": label,
                    "sub": sub,
                    "id": rid,
                    "subcat": subcat,
                    "search": f"{label} {sub}".lower(),
                }
            )

        for item in self.db.stones:
            add("composants", f"💎 {item.get('nom', '—')}", str(item.get("reference", "—")), str(item.get("id", "")), "Pierres")
        for item in getattr(self.db, "breloques", []):
            add("composants", f"✨ {item.get('nom', '—')}", str(item.get("reference", "—")), str(item.get("id", "")), "Breloques")
        for item in getattr(self.db, "intercalaires", []):
            add("composants", f"⭕ {item.get('nom', '—')}", str(item.get("reference", "—")), str(item.get("id", "")), "Intercalaires")
        for item in getattr(self.db, "finitions", []):
            add("composants", f"🔒 {item.get('nom', '—')}", str(item.get("reference", "—")), str(item.get("id", "")), "Cache-nœuds")

        for b in self.db.bracelets:
            add("bracelets", f"📿 {b.get('nom', '—')}", str(b.get("reference", "—")), str(b.get("id", "")))

        for p in self.db.products:
            sku = str(p.get("sku", "") or p.get("reference", "—"))
            add("produits", f"🛍 {p.get('nom', '—')}", sku, str(p.get("id", "")))

        self._global_index = rows

    def _render_global_results(self) -> None:
        for w in self._results_scroll.winfo_children():
            w.destroy()

        if not self._global_results:
            self._hide_global_results()
            return

        self._results_wrap.pack(fill="x", pady=(6, 0))
        for r in self._global_results:
            btn = ctk.CTkButton(
                self._results_scroll,
                text=f"{r['label']}   ·   {r['sub']}",
                anchor="w",
                height=34,
                corner_radius=10,
                fg_color="transparent",
                hover_color=theme.BG_CARD_HOVER,
                text_color=theme.TEXT_PRIMARY,
                command=lambda row=r: self._focus_result(row),
            )
            btn.pack(fill="x", pady=2)

    def _hide_global_results(self) -> None:
        self._results_wrap.pack_forget()

    def _focus_result(self, row: dict) -> None:
        page_by_kind = {
            "composants": "composants",
            "bracelets": "bracelets",
            "produits": "produits",
        }
        page_id = page_by_kind.get(row.get("kind", ""), "dashboard")
        self.show_page(page_id)

        if self._page_widget and hasattr(self._page_widget, "apply_external_search"):
            self._page_widget.apply_external_search(row)

        self._global_search_var.set("")
        self._hide_global_results()

    def _on_close(self) -> None:
        if self.db:
            run_rotating_backup(self.db)
        self.destroy()


# ── Point d'entrée ────────────────────────────────────────────────────

def run_v2(db=None) -> None:
    """Lance l'interface V2. Appelable depuis main.py ou en direct."""
    theme.apply()
    app = LithotherapieV2(db=db)
    app.mainloop()


if __name__ == "__main__":
    # Lancement autonome : py ui_v2.py
    # Permet de tester la V2 sans toucher à main.py (qui reste sur ui.py).
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from database import DatabaseManager
    run_v2(db=DatabaseManager())
