"""Améliorations runtime pour l'éditeur de composition bracelet.

Ce module est chargé automatiquement par Python au démarrage. Il applique un
petit patch non intrusif à pages.crud_editors pour améliorer l'ergonomie de
l'onglet Composition sans toucher aux données métier.
"""
from __future__ import annotations

import importlib.abc
import importlib.machinery
import json
import re
import sys
from types import ModuleType
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

_TARGET = "pages.crud_editors"


def _migrate_stones_to_6_8mm_inventory() -> None:
    """Crée un inventaire pierre 8 mm / 6 mm sans perdre les stocks existants.

    - Les pierres existantes deviennent les variantes 8 mm, stock conservé.
    - Une variante 6 mm est créée pour chaque pierre, avec stock à 0.
    - Les compositions bracelet existantes sont redirigées vers la variante 8 mm.

    La migration est idempotente : elle peut être relancée sans recréer des
    doublons 6 mm.
    """
    try:
        base_dir = Path(__file__).resolve().parent
        stones_path = base_dir / "pierres.json"
        bracelets_path = base_dir / "bracelets.json"
        if not stones_path.exists():
            return

        stones = json.loads(stones_path.read_text(encoding="utf-8"))
        if not isinstance(stones, list) or not stones:
            return

        now = datetime.now().isoformat(timespec="seconds")
        suffix_re = re.compile(r"\s+(6|8)\s*mm\s*$", re.IGNORECASE)

        def split_name(name: str):
            text = str(name or "").strip()
            match = suffix_re.search(text)
            if not match:
                return text, None
            return text[: match.start()].strip(), match.group(1)

        def make_name(base: str, diameter: int) -> str:
            return f"{base} {diameter} mm"

        def ref_number(ref: Any) -> int | None:
            text = str(ref or "").strip().upper()
            if text.startswith("PIE-") and text[4:].isdigit():
                return int(text[4:])
            return None

        max_ref = 0
        for stone in stones:
            n = ref_number(stone.get("reference")) if isinstance(stone, dict) else None
            if n and n > max_ref:
                max_ref = n

        def next_ref() -> str:
            nonlocal max_ref
            max_ref += 1
            return f"PIE-{max_ref:04d}"

        existing_names = {
            str(stone.get("nom", "")).strip().casefold()
            for stone in stones
            if isinstance(stone, dict)
        }

        originals = [stone for stone in stones if isinstance(stone, dict)]
        changed = False
        created = []

        for stone in originals:
            raw_name = str(stone.get("nom", "") or "").strip()
            if not raw_name:
                continue
            base, suffix = split_name(raw_name)
            if not base:
                continue

            if suffix == "6":
                if stone.get("diametre") != 6 or stone.get("diametre_mm") != 6:
                    stone["diametre"] = 6
                    stone["diametre_mm"] = 6
                    changed = True
                if int(stone.get("stock", 0) or 0) != 0:
                    stone["stock"] = 0
                    stone["stock_reserve"] = 0
                    changed = True
                continue

            # Toute pierre existante non 6 mm devient la variante 8 mm.
            target_8_name = make_name(base, 8)
            if raw_name != target_8_name:
                stone["nom"] = target_8_name
                changed = True
            if stone.get("diametre") != 8 or stone.get("diametre_mm") != 8:
                stone["diametre"] = 8
                stone["diametre_mm"] = 8
                changed = True
            stone["updated_at"] = now

            target_6_name = make_name(base, 6)
            if target_6_name.casefold() not in existing_names:
                clone = deepcopy(stone)
                clone["id"] = __import__("uuid").uuid4().__str__()
                clone["reference"] = next_ref()
                clone["nom"] = target_6_name
                clone["diametre"] = 6
                clone["diametre_mm"] = 6
                clone["stock"] = 0
                clone["stock_reserve"] = 0
                clone["created_at"] = now
                clone["updated_at"] = now
                created.append(clone)
                existing_names.add(target_6_name.casefold())
                changed = True

        if created:
            stones.extend(created)

        if changed:
            stones_path.write_text(json.dumps(stones, indent=2, ensure_ascii=False), encoding="utf-8")

        # Redirige les anciennes compositions vers les variantes 8 mm.
        if bracelets_path.exists():
            bracelets = json.loads(bracelets_path.read_text(encoding="utf-8"))
            bracelets_changed = False
            if isinstance(bracelets, list):
                for bracelet in bracelets:
                    if not isinstance(bracelet, dict):
                        continue
                    for row in bracelet.get("composition", []) or []:
                        if not isinstance(row, dict):
                            continue
                        cat = str(row.get("categorie", "") or "").strip().lower()
                        if not cat.startswith("pierre"):
                            continue
                        comp_name = str(row.get("composant", "") or "").strip()
                        base, suffix = split_name(comp_name)
                        if base and suffix is None:
                            row["composant"] = make_name(base, 8)
                            bracelets_changed = True
                    if bracelets_changed:
                        bracelet["updated_at"] = now
                if bracelets_changed:
                    bracelets_path.write_text(json.dumps(bracelets, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        # Ne jamais bloquer le lancement de l'application pour une migration.
        pass


_migrate_stones_to_6_8mm_inventory()


def _safe_configure(widget: Any, **kwargs: Any) -> None:
    try:
        widget.configure(**kwargs)
    except Exception:
        pass


def _patch_crud_editors(module: ModuleType) -> None:
    if getattr(module, "_composition_runtime_patch_applied", False):
        return

    ctk = module.ctk
    mb = module.mb
    theme = module.theme
    BaseEditor = module.BaseEditor
    ComponentEditor = module.ComponentEditor
    BraceletEditor = module.BraceletEditor

    # ──────────────────────────────────────────────────────────────────────
    # Fenêtres éditeur : dimensionnement vraiment adapté à l'écran PC
    # ──────────────────────────────────────────────────────────────────────
    def _adaptive_maximize_window(self) -> None:
        """Ouvre l'éditeur calé sur la fenêtre principale.

        L'éditeur reste techniquement une fenêtre secondaire modale, mais il ne
        doit plus apparaître à un endroit aléatoire ni obliger à le replacer à
        chaque ouverture. On utilise d'abord la géométrie de la fenêtre racine
        (l'application V2), puis seulement l'écran en secours.
        """
        try:
            self.update_idletasks()
            screen_w = int(self.winfo_screenwidth())
            screen_h = int(self.winfo_screenheight())

            try:
                parent = self.master.winfo_toplevel()
                parent.update_idletasks()
                px = int(parent.winfo_rootx())
                py = int(parent.winfo_rooty())
                pw = int(parent.winfo_width())
                ph = int(parent.winfo_height())
            except Exception:
                parent = None
                px, py, pw, ph = 0, 0, screen_w, screen_h

            # Si la fenêtre principale n'est pas encore mesurée correctement,
            # on retombe sur l'écran complet.
            if pw < 700 or ph < 500:
                px, py, pw, ph = 0, 0, screen_w, screen_h

            margin_x = 18
            margin_top = 34
            margin_bottom = 72

            win_w = max(980, pw - (margin_x * 2))
            win_h = max(660, ph - margin_top - margin_bottom)
            win_w = min(win_w, screen_w - 20)
            win_h = min(win_h, screen_h - 60)

            min_w = min(980, max(860, win_w - 80))
            min_h = min(700, max(600, win_h - 80))
            self.minsize(min_w, min_h)

            # Calé dans la fenêtre principale : même zone de travail, léger
            # décalage sous la barre de titre/topbar, footer toujours visible.
            x = max(0, min(px + margin_x, screen_w - win_w - 10))
            y = max(0, min(py + margin_top, screen_h - win_h - 45))
            self.geometry(f"{int(win_w)}x{int(win_h)}+{int(x)}+{int(y)}")
            try:
                self.lift(parent)
            except Exception:
                self.lift()
        except Exception:
            try:
                self.state("zoomed")
            except Exception:
                pass

    BaseEditor._maximize_window = _adaptive_maximize_window

    # ──────────────────────────────────────────────────────────────────────
    # Sélection d'une ligne de composition + actions globales larges
    # ──────────────────────────────────────────────────────────────────────
    orig_component_build_info_tab = ComponentEditor._build_info_tab
    orig_component_on_category_change = ComponentEditor._on_category_change
    orig_component_save = ComponentEditor._save
    orig_build_info_tab = BraceletEditor._build_info_tab
    orig_save_bracelet = BraceletEditor._save
    orig_build_composition_tab = BraceletEditor._build_composition_tab
    orig_add_comp_row = BraceletEditor._add_comp_row
    orig_move_comp_row = BraceletEditor._move_comp_row
    orig_remove_comp_row = BraceletEditor._remove_comp_row
    orig_duplicate_comp_row = BraceletEditor._duplicate_comp_row
    orig_clear_all_rows = BraceletEditor._clear_all_rows
    orig_apply_filter = BraceletEditor._apply_filter
    orig_refresh_comp_positions = BraceletEditor._refresh_comp_positions
    orig_on_category_changed = BraceletEditor._on_category_changed

    def _format_diameter_value(value: Any) -> str:
        if value in (None, ""):
            return ""
        try:
            number = float(str(value).replace(",", "."))
            if number.is_integer():
                return str(int(number))
            return str(number).replace(".", ",")
        except Exception:
            return str(value)

    def _component_update_diameter_state(self) -> None:
        entry = getattr(self, "_diametre_entry", None)
        if entry is None:
            return
        try:
            if self._cat_var.get() == "Pierre":
                entry.configure(state="normal", placeholder_text="ex : 6, 8, 10")
            else:
                entry.configure(state="disabled", placeholder_text="Réservé aux pierres")
        except Exception:
            pass

    def _component_build_info_tab_with_diameter(self, tab) -> None:
        orig_component_build_info_tab(self, tab)
        try:
            raw = self.initial_item.get("diametre", self.initial_item.get("diametre_mm", ""))
            self._diametre_var = ctk.StringVar(value=_format_diameter_value(raw))
            self._diametre_entry = self._add_labeled_entry(tab, 2, 1, "Diamètre pierre (mm)", self._diametre_var)
            self._diametre_var.trace_add("write", self._mark_dirty)
            _component_update_diameter_state(self)
        except Exception:
            pass

    def _component_on_category_change_with_diameter(self) -> None:
        orig_component_on_category_change(self)
        _component_update_diameter_state(self)

    def _component_save_with_diameter(self) -> None:
        original_submit = self.on_submit

        def _submit_with_diameter(payload: dict[str, Any], category_label: str) -> bool:
            try:
                raw = getattr(self, "_diametre_var", None).get().strip() if getattr(self, "_diametre_var", None) is not None else ""
                if category_label == "Pierre":
                    if raw:
                        diam = float(raw.replace(",", "."))
                        if diam < 0:
                            raise ValueError
                        payload["diametre"] = diam
                        payload["diametre_mm"] = diam
                    else:
                        payload["diametre"] = ""
                        payload["diametre_mm"] = ""
                else:
                    payload.pop("diametre", None)
                    payload.pop("diametre_mm", None)
            except Exception:
                mb.showerror("Validation", "Le diamètre doit être un nombre positif, en millimètres.", parent=self)
                return False
            return original_submit(payload, category_label)

        self.on_submit = _submit_with_diameter
        try:
            orig_component_save(self)
        finally:
            try:
                self.on_submit = original_submit
            except Exception:
                pass

    ComponentEditor._build_info_tab = _component_build_info_tab_with_diameter
    ComponentEditor._on_category_change = _component_on_category_change_with_diameter
    ComponentEditor._save = _component_save_with_diameter

    def _build_info_tab_with_wrist(self, tab) -> None:
        orig_build_info_tab(self, tab)
        try:
            raw = str(self.initial_item.get("poignet_conseille", self.initial_item.get("poignet", "") or "")).strip()
            if raw not in ("Gauche", "Droit", "Au choix"):
                raw = "Au choix"
            self._poignet_var = ctk.StringVar(value=raw)
            poignet_menu = ctk.CTkOptionMenu(
                tab,
                variable=self._poignet_var,
                values=["Au choix", "Gauche", "Droit"],
                fg_color=theme.BG_INPUT,
                button_color=theme.BG_CARD,
                button_hover_color=theme.BG_CARD_HOVER,
            )
            self._add_labeled_widget(tab, 6, 0, "Poignet conseillé", poignet_menu)
            self._poignet_var.trace_add("write", self._mark_dirty)
        except Exception:
            pass

    def _save_bracelet_with_wrist(self) -> None:
        original_submit = self.on_submit

        def _submit_with_wrist(payload: dict[str, Any]) -> bool:
            try:
                wrist = self._poignet_var.get().strip() or "Au choix"
                payload["poignet_conseille"] = wrist
                payload["poignet"] = wrist
            except Exception:
                pass
            return original_submit(payload)

        self.on_submit = _submit_with_wrist
        try:
            orig_save_bracelet(self)
        finally:
            try:
                self.on_submit = original_submit
            except Exception:
                pass

    BraceletEditor._build_info_tab = _build_info_tab_with_wrist
    BraceletEditor._save = _save_bracelet_with_wrist

    def _row_title(self, row: dict[str, Any] | None) -> str:
        if row is None or row not in getattr(self, "_composition_rows", []):
            return "Aucune ligne sélectionnée"
        try:
            index = self._composition_rows.index(row) + 1
        except ValueError:
            index = "?"
        cat = str(row.get("cat_var").get() if row.get("cat_var") else "").strip()
        name = str(row.get("comp_var").get() if row.get("comp_var") else "").strip()
        if not name:
            name = "(sans composant)"
        return f"Ligne {index} · {cat} · {name}"

    def _update_selected_toolbar(self) -> None:
        row = getattr(self, "_selected_comp_row", None)
        rows = getattr(self, "_composition_rows", [])
        has_selection = row in rows
        try:
            self._selected_line_var.set(_row_title(self, row if has_selection else None))
        except Exception:
            pass

        state = "normal" if has_selection else "disabled"
        for attr in (
            "_selected_move_up_btn",
            "_selected_move_down_btn",
            "_selected_duplicate_btn",
            "_selected_delete_btn",
        ):
            btn = getattr(self, attr, None)
            if btn is not None:
                _safe_configure(btn, state=state)

    def _refresh_row_selection(self) -> None:
        rows = getattr(self, "_composition_rows", [])
        selected = getattr(self, "_selected_comp_row", None)
        if selected not in rows:
            selected = None
            self._selected_comp_row = None

        for idx, row in enumerate(rows):
            frame = row.get("frame")
            if frame is None:
                continue
            base = row.get("_base_fg_color")
            if not base:
                base = theme.BG_CARD if idx % 2 == 0 else theme.BG_SIDEBAR
                row["_base_fg_color"] = base
            if row is selected:
                _safe_configure(
                    frame,
                    fg_color=theme.BG_CARD_HOVER,
                    border_width=2,
                    border_color=theme.ACCENT_TURQUOISE,
                )
            else:
                _safe_configure(frame, fg_color=base, border_width=0)

        _update_selected_toolbar(self)

    def _select_comp_row(self, row: dict[str, Any] | None = None) -> None:
        rows = getattr(self, "_composition_rows", [])
        self._selected_comp_row = row if row in rows else None
        _refresh_row_selection(self)

    def _walk_widgets(widget: Any):
        yield widget
        try:
            children = widget.winfo_children()
        except Exception:
            children = []
        for child in children:
            yield from _walk_widgets(child)

    def _enhance_comp_row(self, row: dict[str, Any]) -> None:
        if row.get("_selection_enhanced"):
            return
        frame = row.get("frame")
        if frame is None:
            return
        try:
            row["_base_fg_color"] = frame.cget("fg_color")
        except Exception:
            row["_base_fg_color"] = theme.BG_CARD

        def _select(_event=None, r=row):
            try:
                self._select_comp_row(r)
            except Exception:
                pass

        # Cliquer n'importe où sur la ligne sélectionne la ligne, sans empêcher
        # les champs, listes et boutons de faire leur action normale.
        for widget in _walk_widgets(frame):
            try:
                widget.bind("<Button-1>", _select, add="+")
            except Exception:
                pass
            try:
                widget.configure(cursor="hand2")
            except Exception:
                pass

        row["_selection_enhanced"] = True

    # ──────────────────────────────────────────────────────────────────────
    # Composition bracelet : filtre de diamètre pour les pierres
    # ──────────────────────────────────────────────────────────────────────
    _diameter_suffix_re = re.compile(r"\s+(\d+(?:[\.,]\d+)?)\s*mm\s*$", re.IGNORECASE)

    def _normalize_diameter_key(value: Any) -> str:
        if value in (None, ""):
            return ""
        text = str(value).strip().lower().replace("mm", "").replace(",", ".")
        try:
            number = float(text)
        except Exception:
            return ""
        if number <= 0:
            return ""
        return str(int(number)) if number.is_integer() else str(number).rstrip("0").rstrip(".")

    def _diameter_label(key: str) -> str:
        if not key:
            return "Tous"
        return f"{key.replace('.', ',')} mm"

    def _component_diameter_key(comp: dict[str, Any] | None) -> str:
        if not comp:
            return ""
        for field in ("diametre", "diametre_mm"):
            key = _normalize_diameter_key(comp.get(field))
            if key:
                return key
        name = str(comp.get("nom", "") or "").strip()
        match = _diameter_suffix_re.search(name)
        return _normalize_diameter_key(match.group(1)) if match else ""

    def _stone_diameter_choices(self) -> list[str]:
        keys: set[str] = set()
        for comp in getattr(self, "_components_catalog", []) or []:
            if str(comp.get("categorie", "")) != "Pierre":
                continue
            key = _component_diameter_key(comp)
            if key:
                keys.add(key)
        ordered = sorted(keys, key=lambda k: float(k.replace(",", ".")))
        choices = [_diameter_label(k) for k in ordered]
        return choices or ["Tous"]

    def _selected_stone_diameter_key(self) -> str:
        var = getattr(self, "_stone_diameter_filter_var", None)
        raw = var.get() if var is not None else ""
        if not raw or raw == "Tous":
            return ""
        return _normalize_diameter_key(raw)

    def _filtered_names_for_category(self, cat: str) -> list[str]:
        cat = str(cat or "").strip()
        if cat != "Pierre":
            return list(self._names_by_cat.get(cat, []))
        selected_key = _selected_stone_diameter_key(self)
        if not selected_key:
            return list(self._names_by_cat.get(cat, []))
        names: list[str] = []
        for comp in getattr(self, "_components_catalog", []) or []:
            if str(comp.get("categorie", "")) != "Pierre":
                continue
            if _component_diameter_key(comp) == selected_key:
                name = str(comp.get("nom", "") or "").strip()
                if name:
                    names.append(name)
        return sorted(list(dict.fromkeys(names)), key=lambda s: s.lower())

    def _apply_stone_diameter_to_row(self, row: dict[str, Any], keep_current: bool = True) -> None:
        if row not in getattr(self, "_composition_rows", []):
            return
        cat = row.get("cat_var").get() if row.get("cat_var") else ""
        if cat != "Pierre":
            return
        names = _filtered_names_for_category(self, "Pierre")
        box = row.get("comp_box")
        if box is not None:
            box.set_values(names or ["(Aucune pierre)"])
        current = row.get("comp_var").get() if row.get("comp_var") else ""
        if (not keep_current or current not in names) and names:
            row["comp_var"].set(names[0])
            row["pu_var"].set(self._fmt_pu(self._price_for("Pierre", names[0])))

    def _refresh_stone_diameter_filter(self) -> None:
        for row in getattr(self, "_composition_rows", []) or []:
            _apply_stone_diameter_to_row(self, row, keep_current=True)
        self._on_comp_row_changed()

    def _build_composition_tab_patched(self, tab) -> None:
        self._selected_comp_row = None
        orig_build_composition_tab(self, tab)

        # Choix global du diamètre des pierres : les listes de pierres de la
        # composition ne montrent que le diamètre sélectionné.
        try:
            choices = _stone_diameter_choices(self)
            default_choice = "8 mm" if "8 mm" in choices else (choices[0] if choices else "Tous")
            self._stone_diameter_filter_var = ctk.StringVar(value=default_choice)

            ctk.CTkFrame(self._recap_bar, fg_color=theme.BORDER, width=1, height=30).pack(
                side="left", padx=(10, 8), pady=6
            )
            ctk.CTkLabel(
                self._recap_bar,
                text="Diamètre pierres",
                text_color=theme.TEXT_SECONDARY,
                font=ctk.CTkFont(size=12, weight="bold"),
            ).pack(side="left", padx=(0, 6), pady=6)
            ctk.CTkOptionMenu(
                self._recap_bar,
                variable=self._stone_diameter_filter_var,
                values=choices,
                width=92,
                height=32,
                fg_color=theme.BG_INPUT,
                button_color=theme.BG_CARD,
                button_hover_color=theme.BG_CARD_HOVER,
                command=lambda _v: _refresh_stone_diameter_filter(self),
            ).pack(side="left", padx=(0, 8), pady=6)
        except Exception:
            pass

        # La barre est placée dans le récapitulatif : elle reste visible et ne
        # réduit presque pas la hauteur utile de la liste.
        try:
            self._selected_line_var = ctk.StringVar(value="Aucune ligne sélectionnée")

            ctk.CTkFrame(self._recap_bar, fg_color=theme.BORDER, width=1, height=30).pack(
                side="left", padx=(10, 8), pady=6
            )
            ctk.CTkLabel(
                self._recap_bar,
                textvariable=self._selected_line_var,
                text_color=theme.TEXT_PRIMARY,
                font=ctk.CTkFont(size=12, weight="bold"),
            ).pack(side="left", padx=(0, 8), pady=6)

            self._selected_move_up_btn = ctk.CTkButton(
                self._recap_bar,
                text="⬆ Monter",
                width=92,
                height=32,
                fg_color=theme.BG_INPUT,
                hover_color=theme.BG_CARD_HOVER,
                command=lambda: self._move_selected_comp_row(-1),
            )
            self._selected_move_up_btn.pack(side="left", padx=3, pady=6)

            self._selected_move_down_btn = ctk.CTkButton(
                self._recap_bar,
                text="⬇ Descendre",
                width=112,
                height=32,
                fg_color=theme.BG_INPUT,
                hover_color=theme.BG_CARD_HOVER,
                command=lambda: self._move_selected_comp_row(1),
            )
            self._selected_move_down_btn.pack(side="left", padx=3, pady=6)

            self._selected_duplicate_btn = ctk.CTkButton(
                self._recap_bar,
                text="⧉ Dupliquer",
                width=104,
                height=32,
                fg_color=theme.ACCENT_TURQUOISE,
                hover_color=theme.BG_CARD_HOVER,
                text_color="#ffffff",
                command=self._duplicate_selected_comp_row,
            )
            self._selected_duplicate_btn.pack(side="left", padx=3, pady=6)

            self._selected_delete_btn = ctk.CTkButton(
                self._recap_bar,
                text="🗑 Supprimer",
                width=106,
                height=32,
                fg_color=theme.DANGER,
                hover_color=theme.WARNING,
                command=self._remove_selected_comp_row,
            )
            self._selected_delete_btn.pack(side="left", padx=3, pady=6)
        except Exception:
            pass

        _refresh_row_selection(self)

    def _add_comp_row_patched(self, *args, **kwargs):
        result = orig_add_comp_row(self, *args, **kwargs)
        try:
            if self._composition_rows:
                row = self._composition_rows[-1]
                _enhance_comp_row(self, row)
                _apply_stone_diameter_to_row(self, row, keep_current=True)
                self._select_comp_row(row)
        except Exception:
            pass
        return result

    def _on_category_changed_patched(self, row: dict[str, Any]) -> None:
        orig_on_category_changed(self, row)
        try:
            _apply_stone_diameter_to_row(self, row, keep_current=False)
        except Exception:
            pass

    def _move_comp_row_patched(self, row: dict[str, Any], direction: int) -> None:
        orig_move_comp_row(self, row, direction)
        try:
            if row in self._composition_rows:
                self._selected_comp_row = row
            self._apply_filter()
            _refresh_row_selection(self)
        except Exception:
            pass

    def _move_selected_comp_row(self, direction: int) -> None:
        row = getattr(self, "_selected_comp_row", None)
        if row not in getattr(self, "_composition_rows", []):
            _select_comp_row(self, None)
            return
        self._move_comp_row(row, direction)

    def _duplicate_comp_row_patched(self, row: dict[str, Any]) -> None:
        orig_duplicate_comp_row(self, row)
        try:
            if self._composition_rows:
                self._select_comp_row(self._composition_rows[-1])
        except Exception:
            pass

    def _duplicate_selected_comp_row(self) -> None:
        row = getattr(self, "_selected_comp_row", None)
        if row in getattr(self, "_composition_rows", []):
            self._duplicate_comp_row(row)

    def _remove_comp_row_patched(self, frame) -> None:
        rows = getattr(self, "_composition_rows", [])
        selected = getattr(self, "_selected_comp_row", None)
        removed_index = None
        for idx, row in enumerate(rows):
            if row.get("frame") == frame:
                removed_index = idx
                break

        orig_remove_comp_row(self, frame)

        try:
            rows = self._composition_rows
            if selected is not None and selected.get("frame") == frame:
                if rows:
                    next_index = min(removed_index if removed_index is not None else 0, len(rows) - 1)
                    self._selected_comp_row = rows[next_index]
                else:
                    self._selected_comp_row = None
            _refresh_row_selection(self)
        except Exception:
            pass

    def _remove_selected_comp_row(self) -> None:
        row = getattr(self, "_selected_comp_row", None)
        if row in getattr(self, "_composition_rows", []):
            self._remove_comp_row(row.get("frame"))

    def _clear_all_rows_patched(self) -> None:
        orig_clear_all_rows(self)
        try:
            if not self._composition_rows:
                self._selected_comp_row = None
            _refresh_row_selection(self)
        except Exception:
            pass

    def _apply_filter_patched(self) -> None:
        orig_apply_filter(self)
        try:
            _refresh_row_selection(self)
        except Exception:
            pass

    def _refresh_comp_positions_patched(self) -> None:
        orig_refresh_comp_positions(self)
        try:
            for row in getattr(self, "_composition_rows", []):
                _enhance_comp_row(self, row)
            _refresh_row_selection(self)
        except Exception:
            pass

    BraceletEditor._build_composition_tab = _build_composition_tab_patched
    BraceletEditor._add_comp_row = _add_comp_row_patched
    BraceletEditor._move_comp_row = _move_comp_row_patched
    BraceletEditor._move_selected_comp_row = _move_selected_comp_row
    BraceletEditor._duplicate_comp_row = _duplicate_comp_row_patched
    BraceletEditor._duplicate_selected_comp_row = _duplicate_selected_comp_row
    BraceletEditor._remove_comp_row = _remove_comp_row_patched
    BraceletEditor._remove_selected_comp_row = _remove_selected_comp_row
    BraceletEditor._clear_all_rows = _clear_all_rows_patched
    BraceletEditor._apply_filter = _apply_filter_patched
    BraceletEditor._refresh_comp_positions = _refresh_comp_positions_patched
    BraceletEditor._on_category_changed = _on_category_changed_patched
    BraceletEditor._select_comp_row = _select_comp_row
    BraceletEditor._refresh_row_selection = _refresh_row_selection

    module._composition_runtime_patch_applied = True


class _PatchLoader(importlib.abc.Loader):
    def __init__(self, wrapped):
        self._wrapped = wrapped

    def create_module(self, spec):
        if hasattr(self._wrapped, "create_module"):
            return self._wrapped.create_module(spec)
        return None

    def exec_module(self, module):
        self._wrapped.exec_module(module)
        _patch_crud_editors(module)


class _PatchFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname != _TARGET:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec and spec.loader:
            spec.loader = _PatchLoader(spec.loader)
        return spec


if _TARGET in sys.modules:
    _patch_crud_editors(sys.modules[_TARGET])
elif not any(isinstance(finder, _PatchFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, _PatchFinder())


# ─────────────────────────────────────────────────────────────────────────────
# Fiche client PDF — format carte postale professionnel
# ─────────────────────────────────────────────────────────────────────────────
_CATALOGUE_TARGET = "catalogue_services"


def _patch_catalogue_services(module: ModuleType) -> None:
    if getattr(module, "_client_postcard_pdf_patch_applied", False):
        return

    original_export_fiche_pdf = module.export_fiche_pdf

    def _stone_names_in_order(bracelet: dict[str, Any]) -> list[str]:
        """Retourne les pierres du bracelet sans répéter toute la composition.

        On conserve l'ordre de première apparition, mais chaque pierre n'apparaît
        qu'une seule fois. Les intercalaires, breloques, cache-nœuds et autres
        composants restent exclus de la fiche client.
        """
        names: list[str] = []
        seen: set[str] = set()
        for comp in bracelet.get("composition", []) or []:
            cat = str(comp.get("categorie", "") or "").strip().lower()
            if not cat.startswith("pierre"):
                continue
            name = str(comp.get("composant", "") or "").strip()
            key = name.casefold()
            if name and key not in seen:
                seen.add(key)
                names.append(name)
        return names

    def _draw_centered_wrapped(c, text: str, font: str, size: float, x: float, y: float, width: float, leading: float, max_lines: int = 3) -> float:
        from reportlab.lib.utils import simpleSplit
        lines = simpleSplit(text or "", font, size, width)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            if lines:
                lines[-1] = lines[-1].rstrip(" .,") + "…"
        c.setFont(font, size)
        for line in lines:
            c.drawCentredString(x + width / 2, y, line)
            y -= leading
        return y

    def _draw_wrapped(c, text: str, font: str, size: float, x: float, y: float, width: float, leading: float, max_lines: int = 4) -> float:
        from reportlab.lib.utils import simpleSplit
        lines = simpleSplit(text or "", font, size, width)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            if lines:
                lines[-1] = lines[-1].rstrip(" .,") + "…"
        c.setFont(font, size)
        for line in lines:
            c.drawString(x, y, line)
            y -= leading
        return y

    def _ornament(c, x: float, y: float, w: float, color=(0.45, 0.32, 0.18)) -> None:
        c.saveState()
        c.setStrokeColorRGB(*color)
        c.setFillColorRGB(*color)
        c.setLineWidth(0.8)
        c.line(x, y, x + w * 0.42, y)
        c.line(x + w * 0.58, y, x + w, y)
        c.circle(x + w * 0.50, y, 2.0, stroke=1, fill=0)
        c.circle(x + w * 0.47, y, 0.9, stroke=0, fill=1)
        c.circle(x + w * 0.53, y, 0.9, stroke=0, fill=1)
        c.restoreState()

    def _export_client_postcard_pdf(bracelet: dict[str, Any], db: Any, output_path: str) -> bool:
        try:
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas

            # Format carte produit : plus petit qu'une carte postale A6,
            # mais plus grand qu'une carte de visite standard.
            page_w, page_h = 120 * mm, 85 * mm
            c = canvas.Canvas(output_path, pagesize=(page_w, page_h))

            cream = (0.992, 0.965, 0.905)
            ink = (0.17, 0.13, 0.10)
            gold = (0.62, 0.45, 0.20)
            soft_gold = (0.83, 0.70, 0.45)
            amethyst = (0.38, 0.22, 0.48)
            turquoise = (0.05, 0.48, 0.52)

            # Fond chaud + double cadre fin.
            c.setFillColorRGB(*cream)
            c.rect(0, 0, page_w, page_h, stroke=0, fill=1)
            c.setStrokeColorRGB(*gold)
            c.setLineWidth(1.2)
            c.roundRect(5 * mm, 5 * mm, page_w - 10 * mm, page_h - 10 * mm, 8 * mm, stroke=1, fill=0)
            c.setStrokeColorRGB(*soft_gold)
            c.setLineWidth(0.45)
            c.roundRect(8 * mm, 8 * mm, page_w - 16 * mm, page_h - 16 * mm, 6 * mm, stroke=1, fill=0)

            # Petits ornements de coin.
            c.setStrokeColorRGB(*soft_gold)
            c.setLineWidth(0.6)
            for sx, sy, dx, dy in [
                (10 * mm, page_h - 13 * mm, 10 * mm, -10 * mm),
                (page_w - 10 * mm, page_h - 13 * mm, -10 * mm, -10 * mm),
                (10 * mm, 13 * mm, 10 * mm, 10 * mm),
                (page_w - 10 * mm, 13 * mm, -10 * mm, 10 * mm),
            ]:
                c.line(sx, sy, sx + dx, sy)
                c.line(sx, sy, sx, sy + dy)

            margin = 11 * mm
            inner_w = page_w - 2 * margin
            y = page_h - 14 * mm

            # Titre principal : nom du bracelet uniquement.
            c.setFillColorRGB(*ink)
            c.setFont("Times-Italic", 7.8)
            c.drawCentredString(page_w / 2, y, "Bracelet énergétique")
            y -= 6 * mm
            _ornament(c, margin + 15 * mm, y + 2 * mm, inner_w - 30 * mm, gold)
            y -= 4 * mm

            name = str(bracelet.get("nom", "") or "Bracelet").strip()
            y = _draw_centered_wrapped(c, name, "Times-Bold", 13.6, margin, y, inner_w, 4.9 * mm, max_lines=2)
            y -= 1.4 * mm

            # Pierres : uniquement les pierres, dans l'ordre, sans quantités.
            stones = _stone_names_in_order(bracelet)
            if stones:
                c.setFillColorRGB(*gold)
                c.setFont("Times-Bold", 7.6)
                c.drawCentredString(page_w / 2, y, "Pierres")
                y -= 4.2 * mm
                c.setFillColorRGB(*ink)
                stones_txt = "  •  ".join(stones)
                # Sur une petite carte, on garde l'ordre mais on limite à 2 lignes
                # pour éviter que la composition chevauche les sections du bas.
                y = _draw_centered_wrapped(c, stones_txt, "Times-Roman", 7.7, margin + 4 * mm, y, inner_w - 8 * mm, 3.45 * mm, max_lines=2)
                y -= 1.0 * mm
            else:
                c.setFillColorRGB(*ink)
                c.setFont("Times-Roman", 10)
                c.drawCentredString(page_w / 2, y, "Pierres non renseignées")
                y -= 6 * mm

            wrist = str(bracelet.get("poignet_conseille", bracelet.get("poignet", "") or "")).strip()
            if wrist and wrist not in ("Au choix", "Non spécifié", "Non specifie"):
                c.setFillColorRGB(*amethyst)
                c.setFont("Times-Italic", 7.0)
                c.drawCentredString(page_w / 2, y, f"À porter au poignet {wrist.lower()}")
                y -= 3.0 * mm

            _ornament(c, margin + 20 * mm, y + 1.0 * mm, inner_w - 40 * mm, soft_gold)
            y -= 3.0 * mm

            # Vertus + chakras : le reste utile de la fiche client.
            vertus = module.aggregate_vertus(bracelet, db) if db is not None else []
            chakras = module.aggregate_chakras(bracelet, db) if db is not None else []

            col_gap = 7 * mm
            col_w = (inner_w - col_gap) / 2
            left_x = margin
            right_x = margin + col_w + col_gap
            # Zone basse verrouillée : les textes sont limités pour garantir
            # une séparation nette avec les conseils et le pied de page.
            section_y = 31.0 * mm

            c.setFillColorRGB(*turquoise)
            c.setFont("Times-Bold", 7.7)
            c.drawString(left_x, section_y, "Vertus")
            c.setFillColorRGB(*ink)
            vertus_txt = ", ".join(vertus[:4]) if vertus else "Harmonie, douceur et équilibre."
            _draw_wrapped(c, vertus_txt, "Times-Roman", 6.6, left_x, section_y - 3.6 * mm, col_w, 3.0 * mm, max_lines=2)

            c.setFillColorRGB(*amethyst)
            c.setFont("Times-Bold", 7.7)
            c.drawString(right_x, section_y, "Chakras")
            c.setFillColorRGB(*ink)
            chakras_txt = ", ".join(chakras[:3]) if chakras else "Énergies associées aux pierres."
            _draw_wrapped(c, chakras_txt, "Times-Roman", 6.6, right_x, section_y - 3.6 * mm, col_w, 3.0 * mm, max_lines=2)

            # Conseils courts et élégants.
            advice_y = 15.8 * mm
            c.setStrokeColorRGB(*soft_gold)
            c.setLineWidth(0.45)
            c.line(margin + 10 * mm, advice_y + 7.0 * mm, page_w - margin - 10 * mm, advice_y + 7.0 * mm)
            c.setFillColorRGB(*gold)
            c.setFont("Times-Bold", 7.2)
            c.drawCentredString(page_w / 2, advice_y + 3.6 * mm, "Conseils")
            c.setFillColorRGB(*ink)
            c.setFont("Times-Italic", 5.9)
            c.drawCentredString(page_w / 2, advice_y, "Porter avec intention · Purifier régulièrement · Recharger à la lune")

            c.setFillColorRGB(0.38, 0.32, 0.25)
            c.setFont("Times-Italic", 5.2)
            c.drawCentredString(page_w / 2, 7.8 * mm, "Une création pensée pour accompagner votre énergie au quotidien")

            c.showPage()
            c.save()
            return True
        except Exception:
            return False

    def _export_fiche_pdf_patched(bracelet: dict, db: Any, format_type: str, output_path: str) -> bool:
        if str(format_type).strip().lower() == "client":
            return _export_client_postcard_pdf(bracelet, db, output_path)
        return original_export_fiche_pdf(bracelet, db, format_type, output_path)

    module.export_fiche_pdf = _export_fiche_pdf_patched
    module._client_postcard_pdf_patch_applied = True


class _CataloguePatchLoader(importlib.abc.Loader):
    def __init__(self, wrapped):
        self._wrapped = wrapped

    def create_module(self, spec):
        if hasattr(self._wrapped, "create_module"):
            return self._wrapped.create_module(spec)
        return None

    def exec_module(self, module):
        self._wrapped.exec_module(module)
        _patch_catalogue_services(module)


class _CataloguePatchFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname != _CATALOGUE_TARGET:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec and spec.loader:
            spec.loader = _CataloguePatchLoader(spec.loader)
        return spec


if _CATALOGUE_TARGET in sys.modules:
    _patch_catalogue_services(sys.modules[_CATALOGUE_TARGET])
elif not any(isinstance(finder, _CataloguePatchFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, _CataloguePatchFinder())



# ─────────────────────────────────────────────────────────────────────────────
# Page Composants — affichage du diamètre des pierres
# ─────────────────────────────────────────────────────────────────────────────
_COMPOSANTS_TARGET = "pages.composants"


def _patch_composants_page(module: ModuleType) -> None:
    if getattr(module, "_stone_diameter_display_patch_applied", False):
        return

    ctk = module.ctk
    theme = module.theme
    ComposantsPage = module.ComposantsPage

    original_build_fiche_panel = ComposantsPage._build_fiche_panel
    original_update_details = ComposantsPage._update_details

    def _format_diameter_display(value: Any) -> str:
        if value in (None, ""):
            return "—"
        try:
            number = float(str(value).replace(",", "."))
            if number <= 0:
                return "—"
            text = str(int(number)) if number.is_integer() else str(number).replace(".", ",")
            return f"{text} mm"
        except Exception:
            text = str(value).strip()
            return f"{text} mm" if text else "—"

    def _build_fiche_panel_with_diameter(self, parent) -> None:
        original_build_fiche_panel(self, parent)
        try:
            anchor_label = self._detail_values.get("valeur_stock") or self._detail_values.get("stock")
            info = anchor_label.master.master if anchor_label is not None else None
            if info is None:
                return
            row = ctk.CTkFrame(info, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text="Diamètre", width=160, anchor="w", text_color=theme.TEXT_SECONDARY).pack(side="left")
            val = ctk.CTkLabel(row, text="—", anchor="w", text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(weight="bold"))
            val.pack(side="left")
            self._detail_values["diametre"] = val
        except Exception:
            pass

    def _update_details_with_diameter(self, item_id: str, item: dict) -> None:
        original_update_details(self, item_id, item)
        try:
            label = self._detail_values.get("diametre")
            if label is not None:
                if getattr(self, "_active_sub", "") == "Pierres":
                    raw = item.get("diametre", item.get("diametre_mm", ""))
                    label.configure(text=_format_diameter_display(raw))
                else:
                    label.configure(text="—")
        except Exception:
            pass

    ComposantsPage._build_fiche_panel = _build_fiche_panel_with_diameter
    ComposantsPage._update_details = _update_details_with_diameter
    module._stone_diameter_display_patch_applied = True


class _ComposantsPatchLoader(importlib.abc.Loader):
    def __init__(self, wrapped):
        self._wrapped = wrapped

    def create_module(self, spec):
        if hasattr(self._wrapped, "create_module"):
            return self._wrapped.create_module(spec)
        return None

    def exec_module(self, module):
        self._wrapped.exec_module(module)
        _patch_composants_page(module)


class _ComposantsPatchFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname != _COMPOSANTS_TARGET:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec and spec.loader:
            spec.loader = _ComposantsPatchLoader(spec.loader)
        return spec


if _COMPOSANTS_TARGET in sys.modules:
    _patch_composants_page(sys.modules[_COMPOSANTS_TARGET])
elif not any(isinstance(finder, _ComposantsPatchFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, _ComposantsPatchFinder())