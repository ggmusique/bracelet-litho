"""theme.py
Palette centralisée — Lithothérapie Pro V2.
Toutes les couleurs de l'interface proviennent exclusivement de ce fichier.
Aucune couleur en dur n'est autorisée dans les pages ou les widgets.
"""
from __future__ import annotations
import customtkinter as ctk

# ── Fonds ─────────────────────────────────────────────────────────────
BG_MAIN        = "#1a1a2e"   # Fond principal de la fenêtre
BG_SIDEBAR     = "#16213e"   # Barre de navigation latérale
BG_CARD        = "#0f3460"   # Cartes, panneaux secondaires
BG_CARD_HOVER  = "#1a4a80"   # Survol des éléments interactifs
BG_INPUT       = "#0d2137"   # Champs de saisie

# ── Accents ───────────────────────────────────────────────────────────
ACCENT_TURQUOISE = "#00b4d8"  # Turquoise (élément actif, accent principal)
ACCENT_AMETHYSTE = "#7b2d8b"  # Améthyste (accent secondaire)

# ── Textes ────────────────────────────────────────────────────────────
TEXT_PRIMARY   = "#e0e0e0"   # Texte principal
TEXT_SECONDARY = "#9ca3af"   # Texte secondaire, sous-titres, placeholders

# ── Statuts ───────────────────────────────────────────────────────────
SUCCESS = "#10b981"   # Succès, positif, stock OK
WARNING = "#f59e0b"   # Avertissement, alerte stock
DANGER  = "#ef4444"   # Erreur, stock critique
INFO    = "#3b82f6"   # Information neutre

# ── Structurel ────────────────────────────────────────────────────────
BORDER = "#1e3a5f"    # Séparateurs, bordures


def apply() -> None:
    """Configure CustomTkinter pour le thème sombre lithothérapie.
    Doit être appelé AVANT la création de la fenêtre CTk.
    """
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
