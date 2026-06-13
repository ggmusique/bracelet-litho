from __future__ import annotations

"""
Correctifs runtime V2.

Charge les petits correctifs non intrusifs au demarrage :
- migration pierres 8 mm / 6 mm ;
- diametre des pierres dans l'editeur composant ;
- filtre diametre dans la composition bracelet ;
- poignet conseille ;
- fiche client PDF compacte.

La fiche vierge PDF (2 tableaux x 50 lignes) est geree directement
dans pdf_generator.py — aucun patch runtime necessaire.
"""

import importlib.abc
import importlib.machinery
import json
import re
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any


def _migrate_stones_to_6_8mm_inventory() -> None:
    try:
        base = Path(__file__).resolve().parent
        stones_path = base / "pierres.json"
        bracelets_path = base / "bracelets.json"
        if not stones_path.exists():
            return
        stones = json.loads(stones_path.read_text(encoding="utf-8"))
        if not isinstance(stones, list) or not stones:
            return
        now = datetime.now().isoformat(timespec="seconds")
        suffix_re = re.compile(r"\s+(6|8)\s*mm\s*$", re.I)

        def split_name(name: str):
            txt = str(name or "").strip()
            m = suffix_re.search(txt)
            return (txt[:m.start()].strip(), m.group(1)) if m else (txt, None)

        def make_name(base_name: str, diameter: int) -> str:
            return f"{base_name} {diameter} mm"

        def ref_num(ref: Any):
            txt = str(ref or "").strip().upper()
            return int(txt[4:]) if txt.startswith("PIE-") and txt[4:].isdigit() else None

        max_ref = max([ref_num(s.get("reference")) or 0 for s in stones if isinstance(s, dict)] or [0])

        def next_ref() -> str:
            nonlocal max_ref
            max_ref += 1
            return f"PIE-{max_ref:04d}"

        existing = {str(s.get("nom", "")).strip().casefold() for s in stones if isinstance(s, dict)}
        changed = False
        created = []
        for stone in [s for s in stones if isinstance(s, dict)]:
            raw = str(stone.get("nom", "") or "").strip()
            base_name, suffix = split_name(raw)
            if not base_name:
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
            name8 = make_name(base_name, 8)
            if raw != name8:
                stone["nom"] = name8
                changed = True
            if stone.get("diametre") != 8 or stone.get("diametre_mm") != 8:
                stone["diametre"] = 8
                stone["diametre_mm"] = 8
                changed = True
            stone["updated_at"] = now
            name6 = make_name(base_name, 6)
            if name6.casefold() not in existing:
                import uuid
                clone = deepcopy(stone)
                clone.update({
                    "id": str(uuid.uuid4()),
                    "reference": next_ref(),
                    "nom": name6,
                    "diametre": 6,
                    "diametre_mm": 6,
                    "stock": 0,
                    "stock_reserve": 0,
                    "created_at": now,
                    "updated_at": now,
                })
                created.append(clone)
                existing.add(name6.casefold())
                changed = True
        if created:
            stones.extend(created)
        if changed:
            stones_path.write_text(json.dumps(stones, indent=2, ensure_ascii=False), encoding="utf-8")

        if bracelets_path.exists():
            bracelets = json.loads(bracelets_path.read_text(encoding="utf-8"))
            b_changed = False
            if isinstance(bracelets, list):
                for bracelet in bracelets:
                    if not isinstance(bracelet, dict):
                        continue
                    changed_this = False
                    for row in bracelet.get("composition", []) or []:
                        if not isinstance(row, dict):
                            continue
                        if not str(row.get("categorie", "") or "").strip().lower().startswith("pierre"):
                            continue
                        bname, suffix = split_name(str(row.get("composant", "") or "").strip())
                        if bname and suffix is None:
                            row["composant"] = make_name(bname, 8)
                            changed_this = True
                    if changed_this:
                        bracelet["updated_at"] = now
                        b_changed = True
                if b_changed:
                    bracelets_path.write_text(json.dumps(bracelets, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


_migrate_stones_to_6_8mm_inventory()


def _safe_configure(widget: Any, **kwargs: Any) -> None:
    try:
        widget.configure(**kwargs)
    except Exception:
        pass


class _Loader(importlib.abc.Loader):
    def __init__(self, wrapped, patch_func):
        self.wrapped = wrapped
        self.patch_func = patch_func

    def create_module(self, spec):
        if hasattr(self.wrapped, "create_module"):
            return self.wrapped.create_module(spec)
        return None

    def exec_module(self, module):
        self.wrapped.exec_module(module)
        self.patch_func(module)


class _Finder(importlib.abc.MetaPathFinder):
    def __init__(self, target: str, patch_func):
        self.target = target
        self.patch_func = patch_func

    def find_spec(self, fullname, path=None, target=None):
        if fullname != self.target:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec and spec.loader:
            spec.loader = _Loader(spec.loader, self.patch_func)
        return spec


def _install(target: str, patch_func) -> None:
    if target in sys.modules:
        patch_func(sys.modules[target])
    elif not any(isinstance(f, _Finder) and f.target == target for f in sys.meta_path):
        sys.meta_path.insert(0, _Finder(target, patch_func))


# ---------------------------------------------------------------------------
# pages.crud_editors
# ---------------------------------------------------------------------------
def _patch_crud_editors(module: ModuleType) -> None:
    if getattr(module, "_runtime_patch_applied_v2", False):
        return
    ctk = module.ctk
    mb = module.mb
    theme = module.theme
    BaseEditor = module.BaseEditor
    ComponentEditor = module.ComponentEditor
    BraceletEditor = module.BraceletEditor

    def _adaptive_maximize_window(self) -> None:
        try:
            self.update_idletasks()
            sw, sh = int(self.winfo_screenwidth()), int(self.winfo_screenheight())
            try:
                parent = self.master.winfo_toplevel()
                parent.update_idletasks()
                px, py, pw, ph = int(parent.winfo_rootx()), int(parent.winfo_rooty()), int(parent.winfo_width()), int(parent.winfo_height())
            except Exception:
                parent = None
                px, py, pw, ph = 0, 0, sw, sh
            if pw < 700 or ph < 500:
                px, py, pw, ph = 0, 0, sw, sh
            ww = min(max(980, pw - 36), sw - 20)
            wh = min(max(660, ph - 106), sh - 60)
            self.minsize(min(980, max(860, ww - 80)), min(700, max(600, wh - 80)))
            self.geometry(f"{int(ww)}x{int(wh)}+{max(0, min(px + 18, sw - ww - 10))}+{max(0, min(py + 34, sh - wh - 45))}")
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

    orig_comp_build = ComponentEditor._build_info_tab
    orig_comp_cat = ComponentEditor._on_category_change
    orig_comp_save = ComponentEditor._save

    def _fmt_diam(value: Any) -> str:
        if value in (None, ""):
            return ""
        try:
            n = float(str(value).replace(",", "."))
            return str(int(n)) if n.is_integer() else str(n).replace(".", ",")
        except Exception:
            return str(value)

    def _update_diameter_state(self) -> None:
        entry = getattr(self, "_diametre_entry", None)
        if entry is None:
            return
        try:
            if self._cat_var.get() == "Pierre":
                entry.configure(state="normal", placeholder_text="ex : 6, 8, 10")
            else:
                entry.configure(state="disabled", placeholder_text="Reserve aux pierres")
        except Exception:
            pass

    def _component_build(self, tab) -> None:
        orig_comp_build(self, tab)
        try:
            raw = self.initial_item.get("diametre", self.initial_item.get("diametre_mm", ""))
            self._diametre_var = ctk.StringVar(value=_fmt_diam(raw))
            self._diametre_entry = self._add_labeled_entry(tab, 2, 1, "Diametre pierre (mm)", self._diametre_var)
            self._diametre_var.trace_add("write", self._mark_dirty)
            _update_diameter_state(self)
        except Exception:
            pass

    def _component_cat(self) -> None:
        orig_comp_cat(self)
        _update_diameter_state(self)

    def _component_save(self) -> None:
        original_submit = self.on_submit

        def submit(payload: dict[str, Any], category_label: str) -> bool:
            try:
                raw = getattr(self, "_diametre_var", None).get().strip() if getattr(self, "_diametre_var", None) is not None else ""
                if category_label == "Pierre":
                    if raw:
                        val = float(raw.replace(",", "."))
                        if val < 0:
                            raise ValueError
                        payload["diametre"] = val
                        payload["diametre_mm"] = val
                    else:
                        payload["diametre"] = ""
                        payload["diametre_mm"] = ""
                else:
                    payload.pop("diametre", None)
                    payload.pop("diametre_mm", None)
            except Exception:
                mb.showerror("Validation", "Le diametre doit etre un nombre positif, en millimetres.", parent=self)
                return False
            return original_submit(payload, category_label)

        self.on_submit = submit
        try:
            orig_comp_save(self)
        finally:
            self.on_submit = original_submit

    ComponentEditor._build_info_tab = _component_build
    ComponentEditor._on_category_change = _component_cat
    ComponentEditor._save = _component_save

    orig_br_info = BraceletEditor._build_info_tab
    orig_br_save = BraceletEditor._save
    orig_build_comp = BraceletEditor._build_composition_tab
    orig_add_row = BraceletEditor._add_comp_row
    orig_cat_changed = BraceletEditor._on_category_changed

    def _br_info(self, tab) -> None:
        orig_br_info(self, tab)
        try:
            raw = str(self.initial_item.get("poignet_conseille", self.initial_item.get("poignet", "") or "")).strip()
            if raw not in ("Gauche", "Droit", "Au choix"):
                raw = "Au choix"
            self._poignet_var = ctk.StringVar(value=raw)
            menu = ctk.CTkOptionMenu(tab, variable=self._poignet_var, values=["Au choix", "Gauche", "Droit"], fg_color=theme.BG_INPUT, button_color=theme.BG_CARD, button_hover_color=theme.BG_CARD_HOVER)
            self._add_labeled_widget(tab, 6, 0, "Poignet conseille", menu)
            self._poignet_var.trace_add("write", self._mark_dirty)
        except Exception:
            pass

    def _br_save(self) -> None:
        original_submit = self.on_submit

        def submit(payload: dict[str, Any]) -> bool:
            try:
                wrist = self._poignet_var.get().strip() or "Au choix"
                payload["poignet_conseille"] = wrist
                payload["poignet"] = wrist
            except Exception:
                pass
            return original_submit(payload)

        self.on_submit = submit
        try:
            orig_br_save(self)
        finally:
            self.on_submit = original_submit

    BraceletEditor._build_info_tab = _br_info
    BraceletEditor._save = _br_save

    diam_re = re.compile(r"\s+(\d+(?:[\.,]\d+)?)\s*mm\s*$", re.I)

    def norm_diam(v: Any) -> str:
        if v in (None, ""):
            return ""
        txt = str(v).strip().lower().replace("mm", "").replace(",", ".")
        try:
            n = float(txt)
        except Exception:
            return ""
        if n <= 0:
            return ""
        return str(int(n)) if n.is_integer() else str(n).rstrip("0").rstrip(".")

    def comp_diam(comp: dict[str, Any] | None) -> str:
        if not comp:
            return ""
        for field in ("diametre", "diametre_mm"):
            key = norm_diam(comp.get(field))
            if key:
                return key
        m = diam_re.search(str(comp.get("nom", "") or ""))
        return norm_diam(m.group(1)) if m else ""

    def diameter_choices(self) -> list[str]:
        keys = set()
        for comp in getattr(self, "_components_catalog", []) or []:
            if str(comp.get("categorie", "")) == "Pierre":
                key = comp_diam(comp)
                if key:
                    keys.add(key)
        ordered = sorted(keys, key=lambda k: float(k.replace(",", ".")))
        return [f"{k.replace('.', ',')} mm" for k in ordered] or ["Tous"]

    def selected_key(self) -> str:
        var = getattr(self, "_stone_diameter_filter_var", None)
        raw = var.get() if var is not None else ""
        return "" if not raw or raw == "Tous" else norm_diam(raw)

    def filtered_names(self, cat: str) -> list[str]:
        if cat != "Pierre":
            return list(self._names_by_cat.get(cat, []))
        key = selected_key(self)
        if not key:
            return list(self._names_by_cat.get(cat, []))
        names = []
        for comp in getattr(self, "_components_catalog", []) or []:
            if str(comp.get("categorie", "")) == "Pierre" and comp_diam(comp) == key:
                name = str(comp.get("nom", "") or "").strip()
                if name:
                    names.append(name)
        return sorted(list(dict.fromkeys(names)), key=lambda s: s.lower())

    def apply_diameter_to_row(self, row: dict[str, Any], keep_current: bool = True) -> None:
        if row not in getattr(self, "_composition_rows", []):
            return
        cat = row.get("cat_var").get() if row.get("cat_var") else ""
        if cat != "Pierre":
            return
        names = filtered_names(self, "Pierre")
        box = row.get("comp_box")
        if box is not None:
            try:
                box.set_values(names or ["(Aucune pierre)"])
            except Exception:
                pass
        current = row.get("comp_var").get() if row.get("comp_var") else ""
        if (not keep_current or current not in names) and names:
            row["comp_var"].set(names[0])
            row["pu_var"].set(self._fmt_pu(self._price_for("Pierre", names[0])))

    def refresh_diam(self) -> None:
        for row in getattr(self, "_composition_rows", []) or []:
            apply_diameter_to_row(self, row, keep_current=True)
        try:
            self._on_comp_row_changed()
        except Exception:
            pass

    def _build_comp(self, tab) -> None:
        orig_build_comp(self, tab)
        try:
            choices = diameter_choices(self)
            default = "8 mm" if "8 mm" in choices else choices[0]
            self._stone_diameter_filter_var = ctk.StringVar(value=default)
            ctk.CTkFrame(self._recap_bar, fg_color=theme.BORDER, width=1, height=30).pack(side="left", padx=(10, 8), pady=6)
            ctk.CTkLabel(self._recap_bar, text="Diametre pierres", text_color=theme.TEXT_SECONDARY, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 6), pady=6)
            ctk.CTkOptionMenu(self._recap_bar, variable=self._stone_diameter_filter_var, values=choices, width=92, height=32, fg_color=theme.BG_INPUT, button_color=theme.BG_CARD, button_hover_color=theme.BG_CARD_HOVER, command=lambda _v: refresh_diam(self)).pack(side="left", padx=(0, 8), pady=6)
            refresh_diam(self)
        except Exception:
            pass

    def _add_row(self, *args, **kwargs):
        result = orig_add_row(self, *args, **kwargs)
        try:
            if self._composition_rows:
                apply_diameter_to_row(self, self._composition_rows[-1], keep_current=True)
        except Exception:
            pass
        return result

    def _cat_changed(self, row: dict[str, Any]) -> None:
        orig_cat_changed(self, row)
        try:
            apply_diameter_to_row(self, row, keep_current=False)
        except Exception:
            pass

    BraceletEditor._build_composition_tab = _build_comp
    BraceletEditor._add_comp_row = _add_row
    BraceletEditor._on_category_changed = _cat_changed
    module._runtime_patch_applied_v2 = True


# ---------------------------------------------------------------------------
# catalogue_services : fiche client compacte
# ---------------------------------------------------------------------------
def _patch_catalogue_services(module: ModuleType) -> None:
    if getattr(module, "_client_postcard_pdf_patch_applied", False):
        return
    original_export = module.export_fiche_pdf

    def stone_names(bracelet: dict[str, Any]) -> list[str]:
        out, seen = [], set()
        for comp in bracelet.get("composition", []) or []:
            if not str(comp.get("categorie", "") or "").strip().lower().startswith("pierre"):
                continue
            name = str(comp.get("composant", "") or "").strip()
            key = name.casefold()
            if name and key not in seen:
                seen.add(key)
                out.append(name)
        return out

    def export_client(bracelet: dict[str, Any], db: Any, output_path: str) -> bool:
        try:
            from reportlab.lib.units import mm
            from reportlab.lib.utils import simpleSplit
            from reportlab.pdfgen import canvas
            page_w, page_h = 120 * mm, 85 * mm
            c = canvas.Canvas(output_path, pagesize=(page_w, page_h))
            cream, ink, gold, soft_gold = (0.992, 0.965, 0.905), (0.17, 0.13, 0.10), (0.62, 0.45, 0.20), (0.83, 0.70, 0.45)
            amethyst, turquoise = (0.38, 0.22, 0.48), (0.05, 0.48, 0.52)
            c.setFillColorRGB(*cream); c.rect(0, 0, page_w, page_h, stroke=0, fill=1)
            c.setStrokeColorRGB(*gold); c.setLineWidth(1.2); c.roundRect(5*mm, 5*mm, page_w-10*mm, page_h-10*mm, 8*mm, stroke=1, fill=0)
            c.setStrokeColorRGB(*soft_gold); c.setLineWidth(0.45); c.roundRect(8*mm, 8*mm, page_w-16*mm, page_h-16*mm, 6*mm, stroke=1, fill=0)
            margin = 11 * mm; inner_w = page_w - 2 * margin; y = page_h - 14 * mm

            def centered(text, font, size, y0, max_lines=2, width=inner_w):
                lines = simpleSplit(text or "", font, size, width)
                if len(lines) > max_lines:
                    lines = lines[:max_lines]
                    lines[-1] = lines[-1].rstrip(" .,;") + "..."
                c.setFont(font, size)
                for line in lines:
                    c.drawCentredString(page_w/2, y0, line)
                    y0 -= size + 3
                return y0

            c.setFillColorRGB(*ink); c.setFont("Times-Italic", 7.8); c.drawCentredString(page_w/2, y, "Bracelet energetique")
            y -= 13
            c.setFillColorRGB(*ink); y = centered(str(bracelet.get("nom", "") or "Bracelet"), "Times-Bold", 13.6, y, 2)
            stones = stone_names(bracelet)
            if stones:
                y -= 2; c.setFillColorRGB(*gold); c.setFont("Times-Bold", 7.6); c.drawCentredString(page_w/2, y, "Pierres"); y -= 12
                c.setFillColorRGB(*ink); y = centered("  -  ".join(stones), "Times-Roman", 7.7, y, 2, inner_w - 8*mm)
            wrist = str(bracelet.get("poignet_conseille", bracelet.get("poignet", "") or "")).strip()
            if wrist and wrist not in ("Au choix", "Non specifie"):
                c.setFillColorRGB(*amethyst); c.setFont("Times-Italic", 7.0); c.drawCentredString(page_w/2, y, f"A porter au poignet {wrist.lower()}")
            vertus = module.aggregate_vertus(bracelet, db) if db is not None else []
            chakras = module.aggregate_chakras(bracelet, db) if db is not None else []
            col_gap = 7*mm; col_w = (inner_w - col_gap) / 2; lx = margin; rx = margin + col_w + col_gap; sy = 31*mm
            c.setFillColorRGB(*turquoise); c.setFont("Times-Bold", 7.7); c.drawString(lx, sy, "Vertus")
            c.setFillColorRGB(*ink); c.setFont("Times-Roman", 6.6)
            for i, line in enumerate(simpleSplit(", ".join(vertus[:4]) if vertus else "Harmonie, douceur et equilibre.", "Times-Roman", 6.6, col_w)[:2]): c.drawString(lx, sy-10-i*8, line)
            c.setFillColorRGB(*amethyst); c.setFont("Times-Bold", 7.7); c.drawString(rx, sy, "Chakras")
            c.setFillColorRGB(*ink); c.setFont("Times-Roman", 6.6)
            for i, line in enumerate(simpleSplit(", ".join(chakras[:3]) if chakras else "Energies associees aux pierres.", "Times-Roman", 6.6, col_w)[:2]): c.drawString(rx, sy-10-i*8, line)
            advice_y = 15.8*mm; c.setStrokeColorRGB(*soft_gold); c.line(margin+10*mm, advice_y+7*mm, page_w-margin-10*mm, advice_y+7*mm)
            c.setFillColorRGB(*gold); c.setFont("Times-Bold", 7.2); c.drawCentredString(page_w/2, advice_y+3.6*mm, "Conseils")
            c.setFillColorRGB(*ink); c.setFont("Times-Italic", 5.9); c.drawCentredString(page_w/2, advice_y, "Porter avec intention - Purifier regulierement - Recharger a la lune")
            c.setFont("Times-Italic", 5.2); c.drawCentredString(page_w/2, 7.8*mm, "Une creation pensee pour accompagner votre energie au quotidien")
            c.showPage(); c.save(); return True
        except Exception:
            return False

    def export_patched(bracelet: dict, db: Any, format_type: str, output_path: str) -> bool:
        if str(format_type).strip().lower() == "client":
            return export_client(bracelet, db, output_path)
        return original_export(bracelet, db, format_type, output_path)

    module.export_fiche_pdf = export_patched
    module._client_postcard_pdf_patch_applied = True


# ---------------------------------------------------------------------------
# pages.composants : affichage diametre
# ---------------------------------------------------------------------------
def _patch_composants_page(module: ModuleType) -> None:
    if getattr(module, "_stone_diameter_display_patch_applied", False):
        return
    ctk = module.ctk
    theme = module.theme
    Page = module.ComposantsPage
    orig_build = Page._build_fiche_panel
    orig_update = Page._update_details

    def fmt(v: Any) -> str:
        if v in (None, ""):
            return "-"
        try:
            n = float(str(v).replace(",", "."))
            if n <= 0:
                return "-"
            return f"{int(n) if n.is_integer() else str(n).replace('.', ',')} mm"
        except Exception:
            t = str(v).strip()
            return f"{t} mm" if t else "-"

    def build(self, parent) -> None:
        orig_build(self, parent)
        try:
            anchor = self._detail_values.get("valeur_stock") or self._detail_values.get("stock")
            info = anchor.master.master if anchor is not None else None
            if info is None:
                return
            row = ctk.CTkFrame(info, fg_color="transparent"); row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text="Diametre", width=160, anchor="w", text_color=theme.TEXT_SECONDARY).pack(side="left")
            val = ctk.CTkLabel(row, text="-", anchor="w", text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(weight="bold")); val.pack(side="left")
            self._detail_values["diametre"] = val
        except Exception:
            pass

    def update(self, item_id: str, item: dict) -> None:
        orig_update(self, item_id, item)
        try:
            label = self._detail_values.get("diametre")
            if label is not None:
                label.configure(text=fmt(item.get("diametre", item.get("diametre_mm", ""))) if getattr(self, "_active_sub", "") == "Pierres" else "-")
        except Exception:
            pass

    Page._build_fiche_panel = build
    Page._update_details = update
    module._stone_diameter_display_patch_applied = True


_install("pages.crud_editors", _patch_crud_editors)
_install("catalogue_services", _patch_catalogue_services)
_install("pages.composants", _patch_composants_page)
# NOTE: pdf_generator est gere directement dans pdf_generator.py -- pas de patch runtime.
