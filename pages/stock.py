"""pages/stock.py
Page Stock — Lithothérapie Pro V2.
Phase 1B : KPI réels, alertes, historique des mouvements.
"""
from __future__ import annotations
import customtkinter as ctk
import theme
from widgets import KPICard, SectionHeader, Divider


class StockPage(ctk.CTkFrame):
    """Page de suivi du stock."""

    def __init__(self, parent, db=None, **kwargs) -> None:
        kwargs.setdefault("fg_color", theme.BG_MAIN)
        super().__init__(parent, **kwargs)
        self.db = db
        self._kpi_cards: list[KPICard] = []
        self._alert_rows: list = []
        self._rupture_rows: list = []
        self._hist_rows: list  = []
        self._build()
        self.refresh()

    # ── Construction ─────────────────────────────────────────────────

    def _build(self) -> None:
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=theme.BG_MAIN, scrollbar_button_color=theme.BORDER
        )
        scroll.pack(fill="both", expand=True)
        self._scroll = scroll

        # En-tête
        top = ctk.CTkFrame(scroll, fg_color="transparent")
        top.pack(fill="x", padx=32, pady=(28, 0))
        SectionHeader(top, title="📦  Stock",
                      subtitle="Niveaux de stock et alertes de réapprovisionnement").pack(side="left", fill="x", expand=True)
        ctk.CTkButton(top, text="⬇  Exporter", height=38, corner_radius=16,
                      fg_color=theme.ACCENT_TURQUOISE, text_color="#ffffff",
                      hover_color=theme.BG_CARD_HOVER,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=lambda: None).pack(side="right", pady=(8, 0))

        Divider(scroll).pack(fill="x", padx=32, pady=20)

        # KPI strip
        ctk.CTkLabel(scroll, text="APERÇU GLOBAL", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=32, pady=(0, 10))

        kpi_row = ctk.CTkFrame(scroll, fg_color="transparent")
        kpi_row.pack(fill="x", padx=32, pady=(0, 24))
        for col, (icon, lbl, accent) in enumerate([
            ("📦", "Total articles",      theme.ACCENT_TURQUOISE),
            ("⚠",  "Alertes stock",       theme.WARNING),
            ("🔴", "Stock critique",       theme.DANGER),
            ("💰", "Valeur du stock",      theme.SUCCESS),
        ]):
            card = KPICard(kpi_row, icon=icon, value="—", label=lbl, accent=accent)
            card.grid(row=0, column=col, padx=8, sticky="nsew")
            self._kpi_cards.append(card)
        for c in range(4):
            kpi_row.columnconfigure(c, weight=1)

        # Alertes
        ctk.CTkLabel(scroll, text="ALERTES STOCK", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=32, pady=(0, 10))

        self._alerts_panel = ctk.CTkFrame(scroll, fg_color=theme.BG_CARD, corner_radius=16)
        self._alerts_panel.pack(fill="x", padx=32, pady=(0, 24))

        # Risque de rupture
        ctk.CTkLabel(scroll, text="RISQUE DE RUPTURE",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=32, pady=(0, 10))

        self._rupture_panel = ctk.CTkFrame(scroll, fg_color=theme.BG_CARD, corner_radius=16)
        self._rupture_panel.pack(fill="x", padx=32, pady=(0, 24))

        # Historique
        ctk.CTkLabel(scroll, text="HISTORIQUE DES MOUVEMENTS",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=32, pady=(0, 10))

        self._hist_panel = ctk.CTkFrame(scroll, fg_color=theme.BG_CARD, corner_radius=16)
        self._hist_panel.pack(fill="x", padx=32, pady=(0, 32))

    # ── Données ───────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._refresh_kpis()
        self._refresh_alerts()
        self._refresh_rupture_risk()
        self._refresh_history()

    def _refresh_kpis(self) -> None:
        if not self.db:
            return

        seuil = int(self.db.settings.get("stock_alert_threshold", 5) or 5)

        all_items = list(self.db.stones) + list(self.db.bracelets) + list(self.db.products)
        total = len(all_items)
        alertes = sum(1 for i in all_items if int(i.get("stock", 0) or 0) <= seuil)
        critique = sum(1 for i in all_items if int(i.get("stock", 0) or 0) == 0)

        valeur = sum(
            float(s.get("prix_achat", 0.0) or 0.0) * int(s.get("stock", 0) or 0)
            for s in self.db.stones
        )

        def fmt(v: float) -> str:
            return f"{v:,.2f} €".replace(",", "\u202f").replace(".", ",")

        for card, val in zip(self._kpi_cards, [str(total), str(alertes), str(critique), fmt(valeur)]):
            card.set_value(val)

    def _refresh_alerts(self) -> None:
        for w in self._alert_rows:
            w.destroy()
        self._alert_rows.clear()

        if not self.db:
            self._add_row(self._alerts_panel, self._alert_rows, "🔔", "Aucune base connectée.", "", theme.TEXT_SECONDARY)
            return

        alerts = self.db.get_low_stock_alerts()
        items: list[tuple[str, int, str]] = []
        for s in alerts.get("pierres", []):
            items.append((s.get("nom", "?"), int(s.get("stock", 0) or 0), "Pierre"))
        for p in alerts.get("produits", []):
            items.append((p.get("nom", "?"), int(p.get("stock", 0) or 0), "Produit"))
        for b in alerts.get("bracelets", []):
            items.append((b.get("nom", "?"), int(b.get("stock", 0) or 0), "Bracelet"))

        items = sorted(items, key=lambda x: x[1])

        if not items:
            self._add_row(self._alerts_panel, self._alert_rows,
                          "✅", "Aucune alerte — stock en bonne santé.", "", theme.SUCCESS)
            return

        for nom, stock, cat in items:
            color = theme.DANGER if stock == 0 else theme.WARNING
            icon  = "🔴" if stock == 0 else "⚠"
            detail = f"[{cat}]  {stock} unité{'s' if stock != 1 else ''}"
            self._add_row(self._alerts_panel, self._alert_rows, icon, nom, detail, color)

    def _refresh_rupture_risk(self) -> None:
        for w in self._rupture_rows:
            w.destroy()
        self._rupture_rows.clear()

        if not self.db:
            self._add_row(self._rupture_panel, self._rupture_rows,
                          "🔔", "Aucune base connectée.", "", theme.TEXT_SECONDARY)
            return

        from fabrication_services import get_rupture_risk
        risks = get_rupture_risk(self.db)
        fabricable_risks = [r for r in risks if r["fabricable"]]
        if not fabricable_risks:
            self._add_row(self._rupture_panel, self._rupture_rows,
                          "✅", "Aucun risque.", "", theme.SUCCESS)
            return

        self._add_row(self._rupture_panel, self._rupture_rows,
                      "📿", f"{len(fabricable_risks)} bracelet(s) en production :", "", theme.TEXT_SECONDARY)

        for r in fabricable_risks[:10]:
            qty = r["max_possible"]
            color = theme.WARNING if qty < 5 else theme.SUCCESS
            icon = "⚠" if qty < 5 else "✅"
            self._add_row(self._rupture_panel, self._rupture_rows,
                          icon, f"{r['nom']} ({r['reference']})",
                          f"Encore {qty} fabrication(s)", color)

    def _refresh_history(self) -> None:
        for w in self._hist_rows:
            w.destroy()
        self._hist_rows.clear()

        if not self.db:
            self._add_row(self._hist_panel, self._hist_rows, "🔄", "Historique indisponible.", "", theme.TEXT_SECONDARY)
            return

        movements = getattr(self.db, "stock_movements", [])
        recent = sorted(movements, key=lambda m: str(m.get("date", "")), reverse=True)[:20]

        if not recent:
            self._add_row(self._hist_panel, self._hist_rows, "🔄", "Aucun mouvement enregistré.", "", theme.TEXT_SECONDARY)
            return

        for mv in recent:
            delta = int(mv.get("delta", 0) or 0)
            icon  = "⬆" if delta >= 0 else "⬇"
            color = theme.SUCCESS if delta >= 0 else theme.DANGER
            nom   = str(mv.get("item_nom", mv.get("item_name", "?")))
            date  = str(mv.get("date", ""))[:10]
            reason = str(mv.get("motif", mv.get("reason", "")))
            detail = f"[{date}]  {reason}  ({'+' if delta >= 0 else ''}{delta})"
            self._add_row(self._hist_panel, self._hist_rows, icon, nom, detail, color)

    @staticmethod
    def _add_row(panel, rows_list: list, icon: str, nom: str, detail: str, color: str) -> None:
        row = ctk.CTkFrame(panel, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=5)
        rows_list.append(row)

        ctk.CTkLabel(row, text=icon, font=ctk.CTkFont(size=14), text_color=color, width=20).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(row, text=nom, font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=theme.TEXT_PRIMARY, anchor="w").pack(side="left", expand=True, fill="x")
        if detail:
            ctk.CTkLabel(row, text=detail, font=ctk.CTkFont(size=11),
                         text_color=color, anchor="e").pack(side="right")
        ctk.CTkFrame(panel, height=1, fg_color=theme.BORDER).pack(fill="x", padx=20)
