"""widgets.py
Composants UI réutilisables — Lithothérapie Pro V2.
Importez depuis ce module dans n'importe quelle page.
"""
from __future__ import annotations
import customtkinter as ctk
import theme


class KPICard(ctk.CTkFrame):
    """Carte KPI : icône + valeur numérique + libellé.

    Composant réutilisable partout dans le logiciel.

    Exemple :
        card = KPICard(parent, icon="📿", value="58", label="Bracelets",
                       accent=theme.ACCENT_AMETHYSTE)
        card.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")
        card.set_value("61")   # mise à jour dynamique
    """

    def __init__(
        self,
        parent,
        icon: str = "📊",
        value: str = "—",
        label: str = "",
        accent: str | None = None,
        **kwargs,
    ) -> None:
        accent = accent or theme.ACCENT_TURQUOISE
        kwargs.setdefault("fg_color", theme.BG_CARD)
        kwargs.setdefault("corner_radius", 20)
        super().__init__(parent, **kwargs)
        self._base_color = kwargs.get("fg_color", theme.BG_CARD)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=20, pady=20)

        # Icône
        ctk.CTkLabel(
            inner,
            text=icon,
            font=ctk.CTkFont(size=32),
            text_color=accent,
        ).pack(anchor="center")

        # Valeur (mise à jour via set_value)
        self._value_lbl = ctk.CTkLabel(
            inner,
            text=value,
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        self._value_lbl.pack(anchor="center", pady=(8, 4))

        # Libellé
        ctk.CTkLabel(
            inner,
            text=label,
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="center")

        self.bind("<Enter>", lambda _e: self.configure(fg_color=theme.BG_CARD_HOVER))
        self.bind("<Leave>", lambda _e: self.configure(fg_color=self._base_color))

    def set_value(self, value: str) -> None:
        """Met à jour la valeur affichée dans la carte."""
        self._value_lbl.configure(text=value)


class SectionHeader(ctk.CTkFrame):
    """En-tête de page avec titre et sous-titre."""

    def __init__(
        self,
        parent,
        title: str,
        subtitle: str = "",
        **kwargs,
    ) -> None:
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(parent, **kwargs)

        ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        if subtitle:
            ctk.CTkLabel(
                self,
                text=subtitle,
                font=ctk.CTkFont(size=13),
                text_color=theme.TEXT_SECONDARY,
            ).pack(anchor="w", pady=(6, 0))


class Divider(ctk.CTkFrame):
    """Ligne de séparation horizontale."""

    def __init__(self, parent, **kwargs) -> None:
        kwargs.setdefault("fg_color", theme.BORDER)
        kwargs.setdefault("height", 1)
        super().__init__(parent, **kwargs)
