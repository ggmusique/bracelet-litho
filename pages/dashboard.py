"""pages/dashboard.py
Tableau de bord — Lithothérapie Pro V2.
Phase 1B : KPI réels + alertes stock depuis DatabaseManager.
"""
from __future__ import annotations
import time
import customtkinter as ctk
import theme
from widgets import KPICard, SectionHeader, Divider


class DashboardPage(ctk.CTkFrame):
    """Page d'accueil — Vue d'ensemble de l'activité."""

    def __init__(self, parent, db=None, **kwargs) -> None:
        kwargs.setdefault("fg_color", theme.BG_MAIN)
        super().__init__(parent, **kwargs)
        self.db = db
        self._kpi_cards: list[KPICard] = []
        self._alert_rows: list[ctk.CTkFrame] = []
        self._renta_cards: list = []
        self._cache_sig: tuple | None = None
        self._cache_at = 0.0
        self._build()
        self.refresh()

    # ── Construction ─────────────────────────────────────────────────

    def _build(self) -> None:
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=theme.BG_MAIN, scrollbar_button_color=theme.BORDER
        )
        self._scroll.pack(fill="both", expand=True)

        # En-tête
        SectionHeader(
            self._scroll,
            title="📊  Tableau de bord",
            subtitle="Vue d'ensemble de votre activité lithothérapie",
        ).pack(fill="x", padx=32, pady=(28, 0))

        Divider(self._scroll).pack(fill="x", padx=32, pady=20)

        ctk.CTkLabel(
            self._scroll,
            text="INDICATEURS CLÉS",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=32, pady=(0, 10))

        # Grille 3 × 2 KPI
        self._grid = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._grid.pack(fill="x", padx=32)
        for c in range(3):
            self._grid.columnconfigure(c, weight=1)

        _defs = [
            ("💰", "Valeur du stock",  "—", theme.SUCCESS),
            ("💎", "Composants",       "—", theme.ACCENT_TURQUOISE),
            ("📿", "Bracelets",        "—", theme.ACCENT_AMETHYSTE),
            ("🛍",  "Produits",        "—", theme.WARNING),
            ("📈", "CA du mois",       "—", theme.SUCCESS),
            ("💹", "Marge du jour",    "—", theme.INFO),
        ]
        for idx, (icon, label, value, accent) in enumerate(_defs):
            card = KPICard(self._grid, icon=icon, value=value, label=label, accent=accent)
            r, col = divmod(idx, 3)
            card.grid(row=r, column=col, padx=8, pady=8, sticky="nsew")
            self._kpi_cards.append(card)

        # Section production
        Divider(self._scroll).pack(fill="x", padx=32, pady=(24, 16))

        ctk.CTkLabel(
            self._scroll,
            text="PRODUCTION",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=32, pady=(0, 10))

        self._prod_grid = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._prod_grid.pack(fill="x", padx=32)
        for c in range(4):
            self._prod_grid.columnconfigure(c, weight=1)

        _prod_defs = [
            ("🏭", "Bracelets fabricables", "—", theme.SUCCESS),
            ("🚫", "Bracelets bloqués",     "—", theme.DANGER),
            ("💎", "Valeur matière première","—", theme.ACCENT_TURQUOISE),
            ("📊", "Production potentielle",  "—", theme.WARNING),
        ]
        for idx, (icon, label, value, accent) in enumerate(_prod_defs):
            card = KPICard(self._prod_grid, icon=icon, value=value, label=label, accent=accent)
            card.grid(row=0, column=idx, padx=8, pady=8, sticky="nsew")
            self._kpi_cards.append(card)

        # Section rentabilite bracelets
        Divider(self._scroll).pack(fill="x", padx=32, pady=(24, 16))

        ctk.CTkLabel(
            self._scroll,
            text="RENTABILITE BRACELETS",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=32, pady=(0, 10))

        self._renta_grid = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._renta_grid.pack(fill="x", padx=32)
        for c in range(3):
            self._renta_grid.columnconfigure(c, weight=1)

        _renta_defs = [
            ("📐", "Marge moyenne", "—", theme.SUCCESS),
            ("💶", "Benefice moyen / bracelet", "—", theme.INFO),
            ("🏷", "Prix de vente moyen", "—", theme.ACCENT_AMETHYSTE),
        ]
        for idx, (icon, label, value, accent) in enumerate(_renta_defs):
            card = KPICard(self._renta_grid, icon=icon, value=value, label=label, accent=accent)
            card.grid(row=0, column=idx, padx=8, pady=8, sticky="nsew")
            self._renta_cards.append(card)

        # Section alertes stock
        Divider(self._scroll).pack(fill="x", padx=32, pady=(24, 16))

        ctk.CTkLabel(
            self._scroll,
            text="ALERTES STOCK",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=32, pady=(0, 10))

        self._alerts_panel = ctk.CTkFrame(
            self._scroll, fg_color=theme.BG_CARD, corner_radius=16
        )
        self._alerts_panel.pack(fill="x", padx=32, pady=(0, 32))

    # ── Données réelles ───────────────────────────────────────────────

    def refresh(self) -> None:
        """Recharge KPIs et alertes depuis la base."""
        if self.db:
            sig = (
                len(self.db.stones),
                len(getattr(self.db, "breloques", [])),
                len(getattr(self.db, "intercalaires", [])),
                len(getattr(self.db, "finitions", [])),
                len(self.db.bracelets),
                len(self.db.products),
                len(self.db.sales),
                len(getattr(self.db, "stock_movements", [])),
            )
            now = time.perf_counter()
            if self._cache_sig == sig and (now - self._cache_at) < 2.0:
                return
            self._cache_sig = sig
            self._cache_at = now
        self._refresh_kpis()
        self._refresh_alerts()

    def _refresh_kpis(self) -> None:
        if self.db is None:
            return

        # Valeur stock composants (prix_achat × stock)
        valeur = 0.0
        for s in self.db.stones:
            valeur += float(s.get("prix_achat", 0.0) or 0.0) * int(s.get("stock", 0) or 0)
        for lst in (
            getattr(self.db, "breloques", []),
            getattr(self.db, "intercalaires", []),
            getattr(self.db, "finitions", []),
        ):
            for item in lst:
                valeur += float(item.get("prix_achat", 0.0) or 0.0) * int(item.get("stock", 0) or 0)

        nb_composants = (
            len(self.db.stones)
            + len(getattr(self.db, "breloques", []))
            + len(getattr(self.db, "intercalaires", []))
            + len(getattr(self.db, "finitions", []))
        )

        kpis = self.db.get_kpis()

        from fabrication_services import (
            count_fabricable_bracelets,
            count_blocked_bracelets,
            get_matiere_premiere_value,
            get_production_potential,
        )

        fab_count = count_fabricable_bracelets(self.db)
        blocked_count = count_blocked_bracelets(self.db)
        matiere_val = get_matiere_premiere_value(self.db)
        prod_potential = get_production_potential(self.db)

        def fmt_eur(v: float) -> str:
            return f"{v:,.2f} €".replace(",", "\u202f").replace(".", ",")

        values = [
            fmt_eur(valeur),
            str(nb_composants),
            str(len(self.db.bracelets)),
            str(len(self.db.products)),
            fmt_eur(kpis.get("ca_mois", 0.0)),
            fmt_eur(kpis.get("marge_jour", 0.0)),
            str(fab_count),
            str(blocked_count),
            fmt_eur(matiere_val),
            fmt_eur(prod_potential),
        ]
        for card, val in zip(self._kpi_cards, values):
            card.set_value(val)

        # Rentabilite bracelets
        margins_pct = []
        benefices = []
        prix_ventes = []
        for b in self.db.bracelets:
            pv = float(b.get("prix_vente", 0.0) or 0.0)
            m = self.db.calculate_bracelet_metrics(b)
            benef = float(m.get("benefice", 0.0) or 0.0)
            if pv > 0:
                prix_ventes.append(pv)
                benefices.append(benef)
                margins_pct.append((benef / pv) * 100.0)
        n = len(prix_ventes)
        marge_moy = (sum(margins_pct) / n) if n else 0.0
        benef_moy = (sum(benefices) / n) if n else 0.0
        pv_moy = (sum(prix_ventes) / n) if n else 0.0
        renta_values = [
            f"{marge_moy:.0f} %",
            fmt_eur(benef_moy),
            fmt_eur(pv_moy),
        ]
        for card, val in zip(self._renta_cards, renta_values):
            card.set_value(val)

    def _refresh_alerts(self) -> None:
        for w in self._alert_rows:
            w.destroy()
        self._alert_rows.clear()

        if self.db is None:
            self._add_alert_row("🔔", "Aucune base connectée.", "", theme.TEXT_SECONDARY)
            return

        alerts = self.db.get_low_stock_alerts()
        items: list[tuple[str, int]] = []
        for s in alerts.get("pierres", []):
            items.append((s.get("nom", "?"), int(s.get("stock", 0) or 0)))
        for p in alerts.get("produits", []):
            items.append((p.get("nom", "?"), int(p.get("stock", 0) or 0)))
        for b in alerts.get("bracelets", []):
            items.append((b.get("nom", "?"), int(b.get("stock", 0) or 0)))

        items = sorted(items, key=lambda x: x[1])[:10]

        if not items:
            self._add_alert_row("✅", "Stock en bonne santé — aucune alerte.", "", theme.SUCCESS)
            return

        for nom, stock in items:
            color = theme.DANGER if stock == 0 else theme.WARNING
            icon  = "🔴" if stock == 0 else "⚠"
            self._add_alert_row(icon, nom, f"{stock} unité{'s' if stock > 1 else ''}", color)

    def _add_alert_row(self, icon: str, nom: str, detail: str, color: str) -> None:
        row = ctk.CTkFrame(self._alerts_panel, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=5)
        self._alert_rows.append(row)

        ctk.CTkLabel(row, text=icon, font=ctk.CTkFont(size=15), text_color=color, width=22).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(row, text=nom, font=ctk.CTkFont(size=13, weight="bold"), text_color=theme.TEXT_PRIMARY, anchor="w").pack(side="left", expand=True, fill="x")
        if detail:
            ctk.CTkLabel(row, text=detail, font=ctk.CTkFont(size=12), text_color=color, anchor="e").pack(side="right")

        ctk.CTkFrame(self._alerts_panel, height=1, fg_color=theme.BORDER).pack(fill="x", padx=20)
