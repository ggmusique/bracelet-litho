"""Services métier pour la fabrication des bracelets (Phase 2A)."""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any

from phase1c_services import append_local_history

_CAT_TO_LIST_NAME: dict[str, str] = {
    "Pierre": "stones",
    "Breloque": "breloques",
    "Intercalaire": "intercalaires",
    "Cache-noeud": "finitions",
}

_CAT_TO_SAVER: dict[str, str] = {
    "Pierre": "save_stones",
    "Breloque": "save_breloques",
    "Intercalaire": "save_intercalaires",
    "Cache-noeud": "save_finitions",
}


def _get_db_list(db: Any, categorie: str) -> list[dict]:
    if categorie == "Pierre":
        return db.stones
    elif categorie == "Breloque":
        return db.breloques
    elif categorie == "Intercalaire":
        return db.intercalaires
    elif categorie == "Cache-noeud":
        return db.finitions
    return []


def _get_db_saver(db: Any, categorie: str):
    if categorie == "Pierre":
        return db.save_stones
    elif categorie == "Breloque":
        return db.save_breloques
    elif categorie == "Intercalaire":
        return db.save_intercalaires
    elif categorie == "Cache-noeud":
        return db.save_finitions
    return lambda: None


def _find_component(db: Any, categorie: str, nom: str, stone_id: str | None = None) -> dict | None:
    lst = _get_db_list(db, categorie)
    if stone_id:
        for item in lst:
            if str(item.get("id", "")) == stone_id:
                return item
    nom_lower = nom.strip().lower()
    for item in lst:
        if categorie == "Cache-noeud":
            cat_item = str(item.get("categorie", "") or "").strip().lower()
            # Les cache-noeuds zodiaque ont une categorie vide/non renseignee : on les accepte.
            if cat_item not in ("", "cache-noeud", "cache-nœud"):
                continue
        if str(item.get("nom", "")).strip().lower() == nom_lower:
            return item
    return None


def _available_stock(item: dict) -> int:
    return max(0, item.get("stock", 0) - item.get("stock_reserve", 0))


def check_fabrication(bracelet: dict, db: Any, quantity: int = 1) -> dict:
    """Vérifie si un bracelet peut être fabriqué en quantité donnée.
    Retourne: fabricable, max_possible, composants_status[], missing[]
    """
    missing: list[dict] = []
    statuses: list[dict] = []
    max_possible: int | None = None

    for comp in bracelet.get("composition", []):
        component = _find_component(
            db, comp.get("categorie", ""),
            comp.get("composant", ""),
            comp.get("stone_id"),
        )
        needed_unit = comp.get("quantite", 0)
        needed_total = needed_unit * quantity

        if component is None:
            entry = {
                "composant": comp.get("composant", ""),
                "categorie": comp.get("categorie", ""),
                "quantite_unitaire": needed_unit,
                "quantite_necessaire": needed_total,
                "stock_disponible": 0,
                "statut": "introuvable",
                "manque": needed_total,
            }
            statuses.append(entry)
            missing.append(entry)
            if max_possible is None:
                max_possible = 0
        else:
            stock = _available_stock(component)
            if stock < needed_total:
                entry = {
                    "composant": comp.get("composant", ""),
                    "categorie": comp.get("categorie", ""),
                    "quantite_unitaire": needed_unit,
                    "quantite_necessaire": needed_total,
                    "stock_disponible": stock,
                    "statut": "insuffisant",
                    "manque": needed_total - stock,
                }
                statuses.append(entry)
                missing.append(entry)
            elif stock < needed_total * 2:
                statuses.append({
                    "composant": comp.get("composant", ""),
                    "categorie": comp.get("categorie", ""),
                    "quantite_unitaire": needed_unit,
                    "quantite_necessaire": needed_total,
                    "stock_disponible": stock,
                    "statut": "faible",
                    "manque": 0,
                })
            else:
                statuses.append({
                    "composant": comp.get("composant", ""),
                    "categorie": comp.get("categorie", ""),
                    "quantite_unitaire": needed_unit,
                    "quantite_necessaire": needed_total,
                    "stock_disponible": stock,
                    "statut": "disponible",
                    "manque": 0,
                })

            if needed_unit > 0 and stock > 0:
                possible = stock // needed_unit
                if max_possible is None or possible < max_possible:
                    max_possible = possible

    if max_possible is None:
        max_possible = 0

    return {
        "fabricable": len(missing) == 0,
        "max_possible": max_possible,
        "composants": statuses,
        "missing": missing,
        "quantity": quantity,
    }


def simulate_fabrication(bracelet: dict, db: Any, quantity: int) -> list[dict]:
    """Calcule les stocks après fabrication sans modifier les données."""
    results: list[dict] = []
    for comp in bracelet.get("composition", []):
        component = _find_component(
            db, comp.get("categorie", ""),
            comp.get("composant", ""),
            comp.get("stone_id"),
        )
        needed = comp.get("quantite", 0) * quantity
        if component:
            apres = max(0, component.get("stock", 0) - needed)
        else:
            apres = 0
        results.append({
            "composant": comp.get("composant", ""),
            "stock_actuel": component.get("stock", 0) if component else 0,
            "stock_apres": apres,
            "necessite": needed,
        })
    return results


def execute_fabrication(bracelet: dict, quantity: int, db: Any) -> tuple[bool, str]:
    """Exécute la fabrication : déduit les composants, ajoute au stock bracelet."""
    check = check_fabrication(bracelet, db, quantity)
    if not check["fabricable"]:
        motifs = "; ".join(f"{m['composant']} (manque {m['manque']})" for m in check["missing"])
        return False, f"Stock insuffisant : {motifs}"

    now = datetime.now().isoformat()
    bracelet_id = str(bracelet.get("id", ""))
    bracelet_nom = bracelet.get("nom", "")

    for comp in bracelet.get("composition", []):
        component = _find_component(
            db, comp.get("categorie", ""),
            comp.get("composant", ""),
            comp.get("stone_id"),
        )
        if component is None:
            continue
        qty = comp.get("quantite", 0) * quantity
        component["stock"] = max(0, component.get("stock", 0) - qty)
        component["updated_at"] = now
        _get_db_saver(db, comp.get("categorie", ""))()

    bracelet["stock"] = bracelet.get("stock", 0) + quantity
    bracelet["updated_at"] = now
    db.save_bracelets()

    for comp in bracelet.get("composition", []):
        component = _find_component(
            db, comp.get("categorie", ""),
            comp.get("composant", ""),
            comp.get("stone_id"),
        )
        qty = comp.get("quantite", 0) * quantity
        if component:
            _add_stock_movement(
                db, "fabrication", str(component.get("id", "")),
                comp.get("composant", ""), -qty,
                f"Fabrication x{quantity}: {bracelet_nom}",
            )

    _add_stock_movement(
        db, "fabrication", bracelet_id, bracelet_nom, quantity,
        f"Fabrication x{quantity}",
    )

    append_local_history(db, "fabrication", "create", bracelet, {
        "quantity": quantity,
        "details": check,
    })

    return True, "Bracelet fabriqué avec succès."


def _add_stock_movement(db: Any, typ: str, item_id: str, item_nom: str, delta: int, motif: str) -> None:
    movement = {
        "id": str(uuid.uuid4()),
        "type": typ,
        "item_id": item_id,
        "item_nom": item_nom,
        "delta": delta,
        "motif": motif,
        "date": datetime.now().isoformat(),
    }
    db.stock_movements.append(movement)
    db.save_stock_movements()


def annuler_fabrication(movement_id: str, db: Any) -> tuple[bool, str]:
    """Annule une fabrication : restaure les stocks (correction fabrication)."""
    mov = next(
        (m for m in db.stock_movements if m.get("id") == movement_id),
        None,
    )
    if not mov:
        return False, "Mouvement introuvable."

    if mov.get("type") != "fabrication":
        return False, "Ce mouvement n'est pas une fabrication."

    item_nom = mov.get("item_nom", "")
    delta = mov.get("delta", 0)

    bracelet = next(
        (b for b in db.bracelets if b.get("nom", "") == item_nom),
        None,
    )
    if bracelet:
        bracelet["stock"] = max(0, bracelet.get("stock", 0) - delta)
        bracelet["updated_at"] = datetime.now().isoformat()
        db.save_bracelets()

    _add_stock_movement(
        db, "fabrication", str(mov.get("item_id", "")),
        item_nom, 0,
        f"Annulation fabrication {datetime.now().isoformat()}",
    )

    append_local_history(db, "fabrication", "cancel", bracelet or {}, {
        "movement_id": movement_id,
        "delta": delta,
    })

    return True, "Fabrication annulée."


def count_fabricable_bracelets(db: Any) -> int:
    """Nombre de bracelets dont la fabrication est possible (1 unité)."""
    count = 0
    for b in db.bracelets:
        check = check_fabrication(b, db, 1)
        if check["fabricable"]:
            count += 1
    return count


def count_blocked_bracelets(db: Any) -> int:
    """Nombre de bracelets non fabricables (1 unité)."""
    count = 0
    for b in db.bracelets:
        check = check_fabrication(b, db, 1)
        if not check["fabricable"]:
            count += 1
    return count


def get_rupture_risk(db: Any) -> list[dict]:
    """Pour chaque bracelet, combien d'unités peuvent encore être fabriquées."""
    risks: list[dict] = []
    for b in db.bracelets:
        check = check_fabrication(b, db, 1)
        risks.append({
            "id": b.get("id", ""),
            "nom": b.get("nom", ""),
            "reference": b.get("reference", ""),
            "fabricable": check["fabricable"],
            "max_possible": check["max_possible"],
        })
    risks.sort(key=lambda r: r["max_possible"])
    return risks


def get_production_potential(db: Any) -> float:
    """Valeur totale de production potentielle (prix_vente * max_possible)."""
    total = 0.0
    for b in db.bracelets:
        check = check_fabrication(b, db, 1)
        pv = float(b.get("prix_vente", 0) or 0)
        total += pv * check["max_possible"]
    return total


def get_matiere_premiere_value(db: Any) -> float:
    """Valeur des matières premières utilisées dans les bracelets."""
    all_comp_names: set[str] = set()
    for b in db.bracelets:
        for comp in b.get("composition", []):
            all_comp_names.add(comp.get("composant", "").strip().lower())

    total = 0.0
    for lst in (db.stones, db.breloques, db.intercalaires, db.finitions):
        for item in lst:
            if item.get("nom", "").strip().lower() in all_comp_names:
                stock = item.get("stock", 0) or 0
                prix = float(item.get("prix_achat", 0) or item.get("cout_unitaire", 0) or 0)
                total += stock * prix
    return total
