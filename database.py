from __future__ import annotations

import csv
import json
import os
import sys
import unicodedata
import uuid
import zipfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


class DatabaseManager:
    """Gestionnaire de persistance JSON pour pierres, bracelets, ventes et paramètres."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        if base_dir:
            resolved_base = Path(base_dir)
        elif getattr(sys, "frozen", False):
            # En mode exécutable, on stocke les JSON à côté du .exe.
            resolved_base = Path(sys.executable).resolve().parent
        else:
            resolved_base = Path(__file__).resolve().parent

        self.base_dir = resolved_base
        self.stones_path = self.base_dir / "pierres.json"
        self.bracelets_path = self.base_dir / "bracelets.json"
        self.products_path = self.base_dir / "produits.json"
        self.sales_path = self.base_dir / "ventes.json"
        self.stock_movements_path = self.base_dir / "mouvements_stock.json"
        self.settings_path = self.base_dir / "settings.json"
        self.breloques_path = self.base_dir / "breloques.json"
        self.intercalaires_path = self.base_dir / "intercalaires.json"
        self.finitions_path = self.base_dir / "finitions.json"

        self.stones: list[dict[str, Any]] = []
        self.bracelets: list[dict[str, Any]] = []
        self.products: list[dict[str, Any]] = []
        self.sales: list[dict[str, Any]] = []
        self.stock_movements: list[dict[str, Any]] = []
        self.settings: dict[str, Any] = {}
        self.breloques: list[dict[str, Any]] = []
        self.intercalaires: list[dict[str, Any]] = []
        self.finitions: list[dict[str, Any]] = []

        # Index O(1) id→item pour les accès fréquents
        self._stone_index: dict[str, dict] = {}
        self._bracelet_index: dict[str, dict] = {}
        self._product_index: dict[str, dict] = {}

        # Cache métriques bracelet (invalidé après chaque mutation)
        self._metrics_cache: dict[str, dict] = {}

        self._ensure_files()
        self.reload_all()

    def _ensure_files(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)

        if not self.stones_path.exists():
            self._atomic_write(self.stones_path, [])
        if not self.bracelets_path.exists():
            self._atomic_write(self.bracelets_path, [])
        if not self.products_path.exists():
            self._atomic_write(self.products_path, [])
        if not self.sales_path.exists():
            self._atomic_write(self.sales_path, [])
        if not self.stock_movements_path.exists():
            self._atomic_write(self.stock_movements_path, [])
        if not self.settings_path.exists():
            self._atomic_write(
                self.settings_path,
                {
                    "version": "1.0.0",
                    "autosave_seconds": 120,
                    "default_qr": False,
                    "last_export_dir": str(self.base_dir),
                    "theme": "clair",
                    "label_font": "Helvetica",
                    "logo_path": "",
                    "stock_alert_threshold": 5,
                    "stock_target": 20,
                    "update_manifest_url": "https://example.com/lithotherapie/version.json",
                    "update_download_url": "https://example.com/lithotherapie/Lithotherapie.exe",
                },
            )
        if not self.breloques_path.exists():
            self._atomic_write(self.breloques_path, self._seed_breloques())
        if not self.intercalaires_path.exists():
            self._atomic_write(self.intercalaires_path, self._seed_intercalaires())
        if not self.finitions_path.exists():
            self._atomic_write(self.finitions_path, self._seed_finitions())

    def reload_all(self) -> None:
        self.stones = self._read_json(self.stones_path, [])
        self.bracelets = self._read_json(self.bracelets_path, [])
        self.products = self._read_json(self.products_path, [])
        self.sales = self._read_json(self.sales_path, [])
        self.stock_movements = self._read_json(self.stock_movements_path, [])
        self.breloques = self._read_json(self.breloques_path, [])
        self.intercalaires = self._read_json(self.intercalaires_path, [])
        self.finitions = self._read_json(self.finitions_path, [])
        self.settings = self._read_json(
            self.settings_path,
            {
                "version": "1.0.0",
                "autosave_seconds": 120,
                "default_qr": False,
                "last_export_dir": str(self.base_dir),
                "theme": "clair",
                "label_font": "Helvetica",
                "logo_path": "",
                "stock_alert_threshold": 5,
                "stock_target": 20,
                "update_manifest_url": "https://example.com/lithotherapie/version.json",
                "update_download_url": "https://example.com/lithotherapie/Lithotherapie.exe",
            },
        )
        self.settings.setdefault("version", "1.0.0")
        self.settings.setdefault("update_manifest_url", "https://example.com/lithotherapie/version.json")
        self.settings.setdefault("update_download_url", "https://example.com/lithotherapie/Lithotherapie.exe")
        self._rebuild_indexes()
        self._seed_stones_if_needed()
        self._normalize_existing_data()

    def _rebuild_indexes(self) -> None:
        self._stone_index = {s.get("id", ""): s for s in self.stones if s.get("id")}
        self._bracelet_index = {b.get("id", ""): b for b in self.bracelets if b.get("id")}
        self._product_index = {p.get("id", ""): p for p in self.products if p.get("id")}
        self._metrics_cache.clear()

    def _invalidate_caches(self) -> None:
        self._metrics_cache.clear()

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        try:
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except (json.JSONDecodeError, OSError):
            return deepcopy(default)

    @staticmethod
    def _atomic_write(path: Path, data: Any) -> None:
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        os.replace(temp_path, path)

    def save_stones(self) -> None:
        self._atomic_write(self.stones_path, self.stones)
        self._rebuild_indexes()

    def save_bracelets(self) -> None:
        self._atomic_write(self.bracelets_path, self.bracelets)
        self._rebuild_indexes()

    def save_settings(self) -> None:
        self._atomic_write(self.settings_path, self.settings)
        self._invalidate_caches()

    def save_sales(self) -> None:
        self._atomic_write(self.sales_path, self.sales)

    def save_products(self) -> None:
        self._atomic_write(self.products_path, self.products)
        self._rebuild_indexes()

    def save_stock_movements(self) -> None:
        self._atomic_write(self.stock_movements_path, self.stock_movements)

    def save_breloques(self) -> None:
        self._atomic_write(self.breloques_path, self.breloques)
        self._rebuild_indexes()

    def save_intercalaires(self) -> None:
        self._atomic_write(self.intercalaires_path, self.intercalaires)
        self._rebuild_indexes()

    def save_finitions(self) -> None:
        self._atomic_write(self.finitions_path, self.finitions)
        self._rebuild_indexes()

    # ------------------------------------------------------------------ #
    #  Seed data                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _seed_breloques() -> list[dict[str, Any]]:
        import uuid as _uuid
        items = [
            ("Breloque Arbre de Vie", 1.50), ("Breloque Lotus", 1.20),
            ("Breloque Om", 0.80), ("Breloque Etoile", 0.60),
            ("Breloque Croix Ankh", 1.00), ("Breloque Fleur de Vie", 1.20),
            ("Breloque Mandala", 1.50), ("Breloque Hamsa", 1.00),
            ("Breloque Coeur", 0.60), ("Breloque Lune", 0.80),
            ("Breloque Soleil", 0.80), ("Breloque Papillon", 0.70),
            ("Breloque Dauphin", 0.90), ("Breloque Tortue", 0.90),
            ("Breloque Plume", 0.60),
        ]
        return [
            {"id": str(_uuid.uuid4()), "nom": nom, "cout_unitaire": cout, "stock": 50, "fournisseur": ""}
            for nom, cout in items
        ]

    @staticmethod
    def _seed_intercalaires() -> list[dict[str, Any]]:
        import uuid as _uuid
        items = [
            ("Intercalaire rond argente 4mm", 0.10),
            ("Intercalaire rond dore 4mm", 0.10),
            ("Intercalaire rondelle argente 6mm", 0.15),
            ("Intercalaire rondelle dore 6mm", 0.15),
            ("Intercalaire etoile argente", 0.20),
            ("Intercalaire etoile dore", 0.20),
            ("Intercalaire tube argente", 0.12),
            ("Intercalaire tube dore", 0.12),
        ]
        return [
            {"id": str(_uuid.uuid4()), "nom": nom, "cout_unitaire": cout, "stock": 200, "fournisseur": ""}
            for nom, cout in items
        ]

    @staticmethod
    def _seed_finitions() -> list[dict[str, Any]]:
        import uuid as _uuid
        items = [
            ("Cache-noeud dore 2mm", "Cache-noeud", 0.15),
            ("Cache-noeud argente 2mm", "Cache-noeud", 0.15),
            ("Cache-noeud bronze 2mm", "Cache-noeud", 0.12),
            ("Fil elastique transparent 0.5mm", "Fil", 0.05),
            ("Fil elastique blanc 0.5mm", "Fil", 0.05),
            ("Fil nylon tresse 0.4mm", "Fil", 0.08),
            ("Fil en acier cable 0.3mm", "Fil", 0.10),
            ("Fermoir magnetique dore", "Fermoir", 0.80),
            ("Fermoir magnetique argente", "Fermoir", 0.80),
            ("Fermoir mousqueton dore 8mm", "Fermoir", 0.50),
            ("Fermoir mousqueton argente 8mm", "Fermoir", 0.50),
            ("Fermoir toggle dore", "Fermoir", 0.60),
            ("Fermoir toggle argente", "Fermoir", 0.60),
        ]
        return [
            {"id": str(_uuid.uuid4()), "nom": nom, "categorie": cat, "cout_unitaire": cout, "stock": 100, "fournisseur": ""}
            for nom, cat, cout in items
        ]

    # ------------------------------------------------------------------ #
    #  CRUD Breloques                                                      #
    # ------------------------------------------------------------------ #

    def add_breloque(self, breloque: dict[str, Any]) -> dict[str, Any]:
        item = {
            "id": self._new_id(),
            "nom": breloque.get("nom", "").strip(),
            "cout_unitaire": float(breloque.get("cout_unitaire", 0.0) or 0.0),
            "stock": int(breloque.get("stock", 0) or 0),
            "fournisseur": breloque.get("fournisseur", "").strip(),
        }
        self.breloques.append(item)
        self.save_breloques()
        return item

    def update_breloque(self, breloque_id: str, data: dict[str, Any]) -> bool:
        item = next((b for b in self.breloques if b.get("id") == breloque_id), None)
        if not item:
            return False
        item.update({
            "nom": data.get("nom", item.get("nom", "")).strip(),
            "cout_unitaire": float(data.get("cout_unitaire", item.get("cout_unitaire", 0.0)) or 0.0),
            "stock": int(data.get("stock", item.get("stock", 0)) or 0),
            "fournisseur": data.get("fournisseur", item.get("fournisseur", "")).strip(),
        })
        self.save_breloques()
        return True

    def delete_breloque(self, breloque_id: str) -> bool:
        old = len(self.breloques)
        self.breloques = [b for b in self.breloques if b.get("id") != breloque_id]
        if len(self.breloques) == old:
            return False
        self.save_breloques()
        return True

    # ------------------------------------------------------------------ #
    #  CRUD Intercalaires                                                  #
    # ------------------------------------------------------------------ #

    def add_intercalaire(self, intercalaire: dict[str, Any]) -> dict[str, Any]:
        item = {
            "id": self._new_id(),
            "nom": intercalaire.get("nom", "").strip(),
            "cout_unitaire": float(intercalaire.get("cout_unitaire", 0.0) or 0.0),
            "stock": int(intercalaire.get("stock", 0) or 0),
            "fournisseur": intercalaire.get("fournisseur", "").strip(),
        }
        self.intercalaires.append(item)
        self.save_intercalaires()
        return item

    def update_intercalaire(self, intercalaire_id: str, data: dict[str, Any]) -> bool:
        item = next((i for i in self.intercalaires if i.get("id") == intercalaire_id), None)
        if not item:
            return False
        item.update({
            "nom": data.get("nom", item.get("nom", "")).strip(),
            "cout_unitaire": float(data.get("cout_unitaire", item.get("cout_unitaire", 0.0)) or 0.0),
            "stock": int(data.get("stock", item.get("stock", 0)) or 0),
            "fournisseur": data.get("fournisseur", item.get("fournisseur", "")).strip(),
        })
        self.save_intercalaires()
        return True

    def delete_intercalaire(self, intercalaire_id: str) -> bool:
        old = len(self.intercalaires)
        self.intercalaires = [i for i in self.intercalaires if i.get("id") != intercalaire_id]
        if len(self.intercalaires) == old:
            return False
        self.save_intercalaires()
        return True

    # ------------------------------------------------------------------ #
    #  CRUD Finitions                                                      #
    # ------------------------------------------------------------------ #

    def add_finition(self, finition: dict[str, Any]) -> dict[str, Any]:
        item = {
            "id": self._new_id(),
            "nom": finition.get("nom", "").strip(),
            "categorie": finition.get("categorie", "Autre").strip(),
            "cout_unitaire": float(finition.get("cout_unitaire", 0.0) or 0.0),
            "stock": int(finition.get("stock", 0) or 0),
            "fournisseur": finition.get("fournisseur", "").strip(),
        }
        self.finitions.append(item)
        self.save_finitions()
        return item

    def update_finition(self, finition_id: str, data: dict[str, Any]) -> bool:
        item = next((f for f in self.finitions if f.get("id") == finition_id), None)
        if not item:
            return False
        item.update({
            "nom": data.get("nom", item.get("nom", "")).strip(),
            "categorie": data.get("categorie", item.get("categorie", "Autre")).strip(),
            "cout_unitaire": float(data.get("cout_unitaire", item.get("cout_unitaire", 0.0)) or 0.0),
            "stock": int(data.get("stock", item.get("stock", 0)) or 0),
            "fournisseur": data.get("fournisseur", item.get("fournisseur", "")).strip(),
        })
        self.save_finitions()
        return True

    def delete_finition(self, finition_id: str) -> bool:
        old = len(self.finitions)
        self.finitions = [f for f in self.finitions if f.get("id") != finition_id]
        if len(self.finitions) == old:
            return False
        self.save_finitions()
        return True

    def autosave_all(self) -> None:
        self.save_stones()
        self.save_bracelets()
        self.save_products()
        self.save_sales()
        self.save_stock_movements()
        self.save_settings()
        self.save_breloques()
        self.save_intercalaires()
        self.save_finitions()
        self._create_auto_snapshot()

    @staticmethod
    def _new_id() -> str:
        return str(uuid.uuid4())

    def get_stone_by_id(self, stone_id: str) -> dict[str, Any] | None:
        return self._stone_index.get(stone_id)

    def get_stone_by_name(self, name: str) -> dict[str, Any] | None:
        key = str(name or "").strip().lower()
        if not key:
            return None
        for s in self.stones:
            if str(s.get("nom", "")).strip().lower() == key:
                return s
        return None

    def get_bracelet_by_id(self, bracelet_id: str) -> dict[str, Any] | None:
        return self._bracelet_index.get(bracelet_id)

    def get_product_by_id(self, product_id: str) -> dict[str, Any] | None:
        return self._product_index.get(product_id)

    @staticmethod
    def _new_sku(category: str) -> str:
        stamp = datetime.now().strftime("%y%m%d")
        token = str(uuid.uuid4())[:4].upper()
        prefix = {
            "bracelets": "BRC",
            "pierres roulees": "PRL",
            "pendentifs": "PND",
            "geodes": "GEO",
            "arbres de vie": "ADV",
        }.get(category.lower(), "PRD")
        return f"{prefix}-{stamp}-{token}"

    def _add_stock_movement(self, item_type: str, item_id: str, item_name: str, delta: int, reason: str) -> None:
        self.stock_movements.append(
            {
                "id": self._new_id(),
                "type": item_type,
                "item_id": item_id,
                "item_nom": item_name,
                "delta": int(delta),
                "motif": reason,
                "date": datetime.now().isoformat(timespec="seconds"),
            }
        )

    def add_stone(self, stone: dict[str, Any]) -> dict[str, Any]:
        prix_moyen = float(stone.get("prix_moyen", stone.get("prix_achat", 0.0)) or 0.0)
        chakras_value = stone.get("chakras", stone.get("chakra", ""))
        item = {
            "id": self._new_id(),
            "nom": stone.get("nom", "").strip(),
            "vertus": stone.get("vertus", "").strip(),
            "chakra": str(chakras_value).strip(),
            "chakras": str(chakras_value).strip(),
            "prix_achat": float(stone.get("prix_achat", prix_moyen) or 0.0),
            "prix_moyen": prix_moyen,
            "prix_vente": float(stone.get("prix_vente", 0.0) or 0.0),
            "stock": int(stone.get("stock", 30) or 0),
            "photo": stone.get("photo", "").strip(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.stones.append(item)
        self.save_stones()
        return item

    def update_stone(self, stone_id: str, data: dict[str, Any]) -> bool:
        stone = self.get_stone_by_id(stone_id)
        if not stone:
            return False

        chakras_value = data.get("chakras", data.get("chakra", stone.get("chakras", stone.get("chakra", ""))))

        stone.update(
            {
                "nom": data.get("nom", stone.get("nom", "")).strip(),
                "vertus": data.get("vertus", stone.get("vertus", "")).strip(),
                "chakra": str(chakras_value).strip(),
                "chakras": str(chakras_value).strip(),
                "prix_achat": float(data.get("prix_achat", stone.get("prix_achat", 0.0)) or 0.0),
                "prix_moyen": float(data.get("prix_moyen", stone.get("prix_moyen", stone.get("prix_achat", 0.0))) or 0.0),
                "prix_vente": float(data.get("prix_vente", stone.get("prix_vente", 0.0)) or 0.0),
                "stock": int(data.get("stock", stone.get("stock", 0)) or 0),
                "photo": data.get("photo", stone.get("photo", "")).strip(),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        self.save_stones()
        return True

    def delete_stone(self, stone_id: str) -> bool:
        old_count = len(self.stones)
        self.stones = [s for s in self.stones if s.get("id") != stone_id]
        if len(self.stones) == old_count:
            return False

        for bracelet in self.bracelets:
            bracelet["pierres"] = [sid for sid in bracelet.get("pierres", []) if sid != stone_id]
            bracelet["composition"] = [
                row for row in bracelet.get("composition", [])
                if row.get("stone_id", "") != stone_id
            ]
            bracelet["updated_at"] = datetime.now().isoformat(timespec="seconds")

        self.save_stones()
        self.save_bracelets()
        return True

    def add_bracelet(self, bracelet: dict[str, Any]) -> dict[str, Any]:
        comp = [dict(row) for row in bracelet.get("composition", []) if row.get("composant")]
        item = {
            "id": self._new_id(),
            "nom": bracelet.get("nom", "").strip(),
            "reference": bracelet.get("reference", "").strip(),
            "prix_vente": float(bracelet.get("prix_vente", 0.0) or 0.0),
            "composition": comp,
            "stock": int(bracelet.get("stock", 10) or 0),
            "photo": bracelet.get("photo", "").strip(),
            "qr_enabled": bool(bracelet.get("qr_enabled", self.settings.get("default_qr", False))),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.bracelets.append(item)
        self._add_stock_movement("bracelet", item["id"], item["nom"], int(item.get("stock", 0) or 0), "Création article")
        self.save_bracelets()
        self.save_stock_movements()
        return item

    def update_bracelet(self, bracelet_id: str, data: dict[str, Any]) -> bool:
        bracelet = self.get_bracelet_by_id(bracelet_id)
        if not bracelet:
            return False

        old_stock = int(bracelet.get("stock", 0) or 0)

        comp = [
            dict(row)
            for row in data.get("composition", bracelet.get("composition", []))
            if row.get("composant")
        ]
        bracelet.update(
            {
                "nom": data.get("nom", bracelet.get("nom", "")).strip(),
                "reference": data.get("reference", bracelet.get("reference", "")).strip(),
                "prix_vente": float(data.get("prix_vente", bracelet.get("prix_vente", 0.0)) or 0.0),
                "composition": comp,
                "stock": int(data.get("stock", bracelet.get("stock", 0)) or 0),
                "photo": data.get("photo", bracelet.get("photo", "")).strip(),
                "qr_enabled": bool(data.get("qr_enabled", bracelet.get("qr_enabled", False))),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        new_stock = int(bracelet.get("stock", 0) or 0)
        delta = new_stock - old_stock
        if delta:
            self._add_stock_movement("bracelet", bracelet["id"], bracelet.get("nom", ""), delta, "Ajustement manuel")
        self.save_bracelets()
        self.save_stock_movements()
        return True

    def delete_bracelet(self, bracelet_id: str) -> bool:
        old_count = len(self.bracelets)
        self.bracelets = [b for b in self.bracelets if b.get("id") != bracelet_id]
        if len(self.bracelets) == old_count:
            return False
        self.save_bracelets()
        return True

    def duplicate_bracelet(self, bracelet_id: str) -> dict[str, Any] | None:
        source = self.get_bracelet_by_id(bracelet_id)
        if not source:
            return None

        clone = deepcopy(source)
        clone["id"] = self._new_id()
        clone["nom"] = f"{source.get('nom', 'Bracelet')} (Copie)"
        clone["reference"] = f"{source.get('reference', '')}-COPY"
        clone["created_at"] = datetime.now().isoformat(timespec="seconds")
        clone["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.bracelets.append(clone)
        self._add_stock_movement("bracelet", clone["id"], clone.get("nom", ""), int(clone.get("stock", 0) or 0), "Duplication article")
        self.save_bracelets()
        self.save_stock_movements()
        return clone

    def add_product(self, product: dict[str, Any]) -> dict[str, Any]:
        category = product.get("categorie", "bracelets").strip().lower()
        item = {
            "id": self._new_id(),
            "categorie": category,
            "nom": product.get("nom", "").strip(),
            "sku": product.get("sku", "").strip() or self._new_sku(category),
            "prix_achat": float(product.get("prix_achat", 0.0) or 0.0),
            "prix_vente": float(product.get("prix_vente", 0.0) or 0.0),
            "stock": int(product.get("stock", 0) or 0),
            "seuil_alerte": int(product.get("seuil_alerte", self.settings.get("stock_alert_threshold", 5)) or 0),
            "fournisseur": product.get("fournisseur", "").strip(),
            "photo": product.get("photo", "").strip(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.products.append(item)
        self._add_stock_movement("produit", item["id"], item["nom"], int(item["stock"]), "Création article")
        self.save_products()
        self.save_stock_movements()
        return item

    def update_product(self, product_id: str, data: dict[str, Any]) -> bool:
        item = self.get_product_by_id(product_id)
        if not item:
            return False

        old_stock = int(item.get("stock", 0) or 0)
        item.update(
            {
                "categorie": data.get("categorie", item.get("categorie", "bracelets")).strip().lower(),
                "nom": data.get("nom", item.get("nom", "")).strip(),
                "sku": data.get("sku", item.get("sku", "")).strip() or item.get("sku", ""),
                "prix_achat": float(data.get("prix_achat", item.get("prix_achat", 0.0)) or 0.0),
                "prix_vente": float(data.get("prix_vente", item.get("prix_vente", 0.0)) or 0.0),
                "stock": int(data.get("stock", item.get("stock", 0)) or 0),
                "seuil_alerte": int(data.get("seuil_alerte", item.get("seuil_alerte", self.settings.get("stock_alert_threshold", 5))) or 0),
                "fournisseur": data.get("fournisseur", item.get("fournisseur", "")).strip(),
                "photo": data.get("photo", item.get("photo", "")).strip(),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        delta = int(item.get("stock", 0) or 0) - old_stock
        if delta:
            self._add_stock_movement("produit", item["id"], item.get("nom", ""), delta, "Ajustement manuel")
        self.save_products()
        self.save_stock_movements()
        return True

    def delete_product(self, product_id: str) -> bool:
        old_count = len(self.products)
        self.products = [item for item in self.products if item.get("id") != product_id]
        if len(self.products) == old_count:
            return False
        self.save_products()
        return True

    def duplicate_product(self, product_id: str) -> dict[str, Any] | None:
        source = self.get_product_by_id(product_id)
        if not source:
            return None

        clone = deepcopy(source)
        clone["id"] = self._new_id()
        clone["nom"] = f"{source.get('nom', 'Produit')} (Copie)"
        clone["sku"] = self._new_sku(source.get("categorie", "produit"))
        clone["created_at"] = datetime.now().isoformat(timespec="seconds")
        clone["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.products.append(clone)
        self._add_stock_movement("produit", clone["id"], clone.get("nom", ""), int(clone.get("stock", 0) or 0), "Duplication article")
        self.save_products()
        self.save_stock_movements()
        return clone

    def search_products(self, query: str = "", category: str = "toutes") -> list[dict[str, Any]]:
        text = query.strip().lower()
        selected = category.strip().lower()
        results = self.products
        if selected and selected != "toutes":
            results = [item for item in results if item.get("categorie", "").lower() == selected]

        if not text:
            return list(results)

        return [
            item
            for item in results
            if text in item.get("nom", "").lower()
            or text in item.get("sku", "").lower()
            or text in item.get("categorie", "").lower()
            or text in item.get("fournisseur", "").lower()
        ]

    def adjust_product_stock(self, product_id: str, delta: int, reason: str = "Ajustement") -> tuple[bool, str]:
        item = self.get_product_by_id(product_id)
        if not item:
            return False, "Produit introuvable."

        item["stock"] = max(0, int(item.get("stock", 0) or 0) + int(delta))
        item["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self._add_stock_movement("produit", item["id"], item.get("nom", ""), int(delta), reason)
        self.save_products()
        self.save_stock_movements()
        return True, "Stock mis à jour."

    def search_stones(self, query: str) -> list[dict[str, Any]]:
        text = query.strip().lower()
        if not text:
            results = list(self.stones)
        else:
            results = [
                s
                for s in self.stones
                if text in s.get("nom", "").lower()
                or text in s.get("vertus", "").lower()
                or text in s.get("chakra", "").lower()
                or text in str(s.get("stock", "")).lower()
            ]
        return sorted(results, key=lambda s: unicodedata.normalize("NFD", s.get("nom", "").casefold()))

    def next_bracelet_ref(self) -> str:
        """Génère la prochaine référence BRA-XXXX non utilisée."""
        used: set[int] = set()
        for b in self.bracelets:
            ref = b.get("reference", "")
            if ref.startswith("BRA-") and ref[4:].isdigit():
                used.add(int(ref[4:]))
        n = 1
        while n in used:
            n += 1
        return f"BRA-{n:04d}"

    # ------------------------------------------------------------------
    # Gestion de la feuille d'étiquettes Action (3 col × 8 lignes = 24)
    # ------------------------------------------------------------------

    def get_feuille_positions(self) -> list[dict]:
        """Retourne les 24 positions avec leurs données {used, bracelet_id, bracelet_nom, model}.

        Rétrocompatible avec l'ancien format booléen.
        """
        raw = self.settings.get("feuille_positions", [])
        result: list[dict] = []
        for i in range(24):
            entry = raw[i] if isinstance(raw, list) and i < len(raw) else None
            if entry is None or entry is False:
                result.append({"used": False})
            elif entry is True:
                # Migration depuis l'ancien format booléen
                result.append({"used": True, "bracelet_id": "", "bracelet_nom": "?", "model": "bracelet"})
            elif isinstance(entry, dict):
                result.append(entry)
            else:
                result.append({"used": False})
        return result

    def use_feuille_position(
        self,
        pos: int,
        bracelet_id: str = "",
        bracelet_nom: str = "",
        model: str = "bracelet",
    ) -> None:
        """Marque la position pos (1–24) comme utilisée et enregistre les données du bracelet."""
        positions = self.get_feuille_positions()
        if 1 <= pos <= 24:
            positions[pos - 1] = {
                "used": True,
                "bracelet_id": bracelet_id,
                "bracelet_nom": bracelet_nom,
                "model": model,
            }
        self.settings["feuille_positions"] = positions
        self.save_settings()

    def free_feuille_position(self, pos: int) -> None:
        """Libère une seule position (remet à l'état libre sans toucher aux autres)."""
        positions = self.get_feuille_positions()
        if 1 <= pos <= 24:
            positions[pos - 1] = {"used": False}
        self.settings["feuille_positions"] = positions
        self.save_settings()

    def reset_feuille(self) -> None:
        """Remet les 24 positions à libre et sauvegarde."""
        self.settings["feuille_positions"] = [{"used": False}] * 24
        self.save_settings()

    def search_bracelets(self, query: str) -> list[dict[str, Any]]:
        text = query.strip().lower()
        if not text:
            return list(self.bracelets)

        def _in_composition(b: dict[str, Any]) -> bool:
            return any(
                text in str(row.get("composant", "")).lower()
                or text in str(row.get("categorie", "")).lower()
                for row in b.get("composition", [])
            )

        return [
            b
            for b in self.bracelets
            if text in b.get("nom", "").lower()
            or text in b.get("reference", "").lower()
            or text in str(b.get("prix_vente", "")).lower()
            or text in str(b.get("stock", "")).lower()
            or _in_composition(b)
        ]

    def calculate_bracelet_metrics(self, bracelet: dict[str, Any]) -> dict[str, Any]:
        bid = bracelet.get("id", "")
        if bid and bid in self._metrics_cache:
            return self._metrics_cache[bid]
        comp_rows = bracelet.get("composition", [])
        # Compatibilité ascendante: si pas de composition mais ancienne liste pierres
        if not comp_rows and bracelet.get("pierres"):
            comp_rows = []
            for stone_id in bracelet.get("pierres", []):
                stone = self.get_stone_by_id(stone_id)
                if stone:
                    comp_rows.append({
                        "composant": stone.get("nom", ""),
                        "categorie": "Pierre",
                        "quantite": 1,
                        "cout_unitaire": float(stone.get("prix_achat", 0.0) or 0.0),
                        "stone_id": stone_id,
                    })

        composition_display: list[str] = []
        vertus_set: set[str] = set()
        chakra_set: set[str] = set()
        cout_revient = 0.0

        for row in comp_rows:
            qty = int(row.get("quantite", 1) or 1)
            cout = float(row.get("cout_unitaire", 0.0) or 0.0)
            nom = str(row.get("composant", "")).strip()
            cout_revient += qty * cout
            if nom:
                composition_display.append(f"{qty}x {nom}" if qty > 1 else nom)
            stone_id = row.get("stone_id", "")
            stone = self.get_stone_by_id(stone_id) if stone_id else None
            if stone is None and str(row.get("categorie", "")).strip().lower().startswith("pierre"):
                stone = self.get_stone_by_name(nom)
            if stone:
                for v in str(stone.get("vertus", "") or "").split(","):
                    if v.strip():
                        vertus_set.add(v.strip())
                chakra_raw = stone.get("chakra", "") or stone.get("chakras", "") or ""
                chakra_iter = chakra_raw if isinstance(chakra_raw, list) else str(chakra_raw).split(",")
                for ch in chakra_iter:
                    if str(ch).strip():
                        chakra_set.add(str(ch).strip())

        # Vertus / chakras : on privilegie le catalogue de reference (riche), sinon la base.
        try:
            from catalogue_services import aggregate_vertus, aggregate_chakras
            _cat_v = aggregate_vertus(bracelet, self)
            _cat_c = aggregate_chakras(bracelet, self)
        except Exception:
            _cat_v, _cat_c = [], []
        vertus_list = _cat_v if _cat_v else sorted(vertus_set)
        chakras_list = _cat_c if _cat_c else sorted(chakra_set)

        # Prix de vente : pilote par le coefficient si le mode automatique est actif.
        try:
            coef = float(self.settings.get("price_coefficient", 0) or 0)
        except (AttributeError, TypeError, ValueError):
            coef = 0.0
        if coef <= 0:
            coef = 2.5
        prix_auto = bool(bracelet.get("prix_auto", False))
        manual_pv = float(bracelet.get("prix_vente", 0.0) or 0.0)
        prix_vente = round(cout_revient * coef, 2) if prix_auto else manual_pv
        marge = prix_vente - cout_revient

        result = {
            "composition": composition_display,
            "vertus": vertus_list,
            "chakras": chakras_list,
            "cout_revient": round(cout_revient, 2),
            "prix_vente": round(prix_vente, 2),
            "prix_auto": prix_auto,
            "coefficient": coef,
            "marge": round(marge, 2),
            "benefice": round(marge, 2),
        }
        if bid:
            self._metrics_cache[bid] = result
        return result

    def register_sale(self, bracelet_id: str, qty: int = 1) -> tuple[bool, str]:
        bracelet = self.get_bracelet_by_id(bracelet_id)
        if not bracelet:
            return False, "Bracelet introuvable."
        if qty <= 0:
            return False, "Quantité invalide."
        if int(bracelet.get("stock", 0) or 0) < qty:
            return False, "Stock bracelet insuffisant."

        bracelet["stock"] = int(bracelet.get("stock", 0) or 0) - qty
        bracelet["updated_at"] = datetime.now().isoformat(timespec="seconds")

        for row in bracelet.get("composition", []):
            stone_id = row.get("stone_id", "")
            if stone_id:
                stone = self.get_stone_by_id(stone_id)
                if stone:
                    qty_to_deduct = int(row.get("quantite", 1) or 1) * qty
                    stone["stock"] = max(0, int(stone.get("stock", 0) or 0) - qty_to_deduct)
                    stone["updated_at"] = datetime.now().isoformat(timespec="seconds")
        # Compatibilité ascendante: ancienne liste pierres
        if not bracelet.get("composition") and bracelet.get("pierres"):
            for stone_id in bracelet.get("pierres", []):
                stone = self.get_stone_by_id(stone_id)
                if stone:
                    stone["stock"] = max(0, int(stone.get("stock", 0) or 0) - qty)
                    stone["updated_at"] = datetime.now().isoformat(timespec="seconds")

        self.sales.append(
            {
                "id": self._new_id(),
                "type": "bracelet",
                "bracelet_id": bracelet_id,
                "reference": bracelet.get("reference", ""),
                "nom": bracelet.get("nom", ""),
                "qty": qty,
                "unit_cost": round(self.calculate_bracelet_metrics(bracelet)["cout_revient"], 2),
                "prix_unitaire": float(bracelet.get("prix_vente", 0.0) or 0.0),
                "total": round(float(bracelet.get("prix_vente", 0.0) or 0.0) * qty, 2),
                "marge_total": round((float(bracelet.get("prix_vente", 0.0) or 0.0) - self.calculate_bracelet_metrics(bracelet)["cout_revient"]) * qty, 2),
                "date": datetime.now().isoformat(timespec="seconds"),
            }
        )

        self._add_stock_movement("bracelet", bracelet["id"], bracelet.get("nom", ""), -qty, "Vente")

        self.save_bracelets()
        self.save_stones()
        self.save_sales()
        self.save_stock_movements()
        return True, "Vente enregistrée."

    def register_product_sale(self, product_id: str, qty: int = 1) -> tuple[bool, str]:
        item = self.get_product_by_id(product_id)
        if not item:
            return False, "Produit introuvable."
        if qty <= 0:
            return False, "Quantité invalide."
        if int(item.get("stock", 0) or 0) < qty:
            return False, "Stock produit insuffisant."

        item["stock"] = int(item.get("stock", 0) or 0) - qty
        item["updated_at"] = datetime.now().isoformat(timespec="seconds")

        unit_price = float(item.get("prix_vente", 0.0) or 0.0)
        unit_cost = float(item.get("prix_achat", 0.0) or 0.0)
        self.sales.append(
            {
                "id": self._new_id(),
                "type": "produit",
                "product_id": item["id"],
                "reference": item.get("sku", ""),
                "nom": item.get("nom", ""),
                "categorie": item.get("categorie", ""),
                "qty": qty,
                "unit_cost": unit_cost,
                "prix_unitaire": unit_price,
                "total": round(unit_price * qty, 2),
                "marge_total": round((unit_price - unit_cost) * qty, 2),
                "date": datetime.now().isoformat(timespec="seconds"),
            }
        )
        self._add_stock_movement("produit", item["id"], item.get("nom", ""), -qty, "Vente")

        self.save_products()
        self.save_sales()
        self.save_stock_movements()
        return True, "Vente enregistrée."

    def register_refund(self, sale_id: str) -> tuple[bool, str]:
        sale = next((s for s in self.sales if s.get("id") == sale_id), None)
        if not sale:
            return False, "Vente introuvable."
        if sale.get("refund"):
            return False, "Vente déjà remboursée."

        qty = int(sale.get("qty", 0) or 0)
        if qty <= 0:
            return False, "Quantité de vente invalide."

        if sale.get("type") == "produit":
            product_id = sale.get("product_id", "")
            item = self.get_product_by_id(product_id)
            if item:
                item["stock"] = int(item.get("stock", 0) or 0) + qty
                item["updated_at"] = datetime.now().isoformat(timespec="seconds")
                self._add_stock_movement("produit", item["id"], item.get("nom", ""), qty, "Remboursement")
                self.save_products()

        if sale.get("type") == "bracelet":
            bracelet = self.get_bracelet_by_id(sale.get("bracelet_id", ""))
            if bracelet:
                bracelet["stock"] = int(bracelet.get("stock", 0) or 0) + qty
                bracelet["updated_at"] = datetime.now().isoformat(timespec="seconds")
                self._add_stock_movement("bracelet", bracelet["id"], bracelet.get("nom", ""), qty, "Remboursement")
                self.save_bracelets()

        sale["refund"] = True
        sale["refund_at"] = datetime.now().isoformat(timespec="seconds")
        self.save_sales()
        self.save_stock_movements()
        return True, "Remboursement effectué."

    def get_low_stock_alerts(self) -> dict[str, list[dict[str, Any]]]:
        threshold = int(self.settings.get("stock_alert_threshold", 5) or 5)
        return {
            "pierres": [s for s in self.stones if int(s.get("stock", 0) or 0) <= threshold],
            "bracelets": [b for b in self.bracelets if int(b.get("stock", 0) or 0) <= threshold],
            "produits": [p for p in self.products if int(p.get("stock", 0) or 0) <= int(p.get("seuil_alerte", threshold) or threshold)],
        }

    def get_restock_suggestions(self) -> list[dict[str, Any]]:
        target = int(self.settings.get("stock_target", 20) or 20)
        suggestions: list[dict[str, Any]] = []
        for item in self.products:
            stock = int(item.get("stock", 0) or 0)
            if stock < target:
                suggestions.append(
                    {
                        "nom": item.get("nom", ""),
                        "categorie": item.get("categorie", ""),
                        "sku": item.get("sku", ""),
                        "stock": stock,
                        "a_commander": target - stock,
                        "fournisseur": item.get("fournisseur", ""),
                    }
                )
        return suggestions

    def get_kpis(self) -> dict[str, Any]:
        now = datetime.now()
        today = now.date()
        month_key = now.strftime("%Y-%m")

        ca_jour = 0.0
        marge_jour = 0.0
        ventes_jour = 0
        ca_mois = 0.0
        ventes_mois = 0
        by_product: dict[str, int] = {}

        for sale in self.sales:
            sale_date = str(sale.get("date", ""))
            qty = int(sale.get("qty", 0) or 0)
            total = float(sale.get("total", 0.0) or 0.0)
            margin = float(sale.get("marge_total", 0.0) or 0.0)
            if sale.get("refund"):
                continue

            if sale_date[:10] == str(today):
                ca_jour += total
                marge_jour += margin
                ventes_jour += qty

            if sale_date[:7] == month_key:
                ca_mois += total
                ventes_mois += qty

            by_product[sale.get("nom", "Inconnu")] = by_product.get(sale.get("nom", "Inconnu"), 0) + qty

        top = sorted(by_product.items(), key=lambda item: item[1], reverse=True)[:5]
        return {
            "ca_jour": round(ca_jour, 2),
            "marge_jour": round(marge_jour, 2),
            "ventes_jour": ventes_jour,
            "ca_mois": round(ca_mois, 2),
            "ventes_mois": ventes_mois,
            "top_ventes": top,
        }

    def create_backup(self, output_path: str | Path) -> tuple[bool, str]:
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "pierres": self.stones,
            "bracelets": self.bracelets,
            "produits": self.products,
            "ventes": self.sales,
            "mouvements_stock": self.stock_movements,
            "settings": self.settings,
            "breloques": self.breloques,
            "intercalaires": self.intercalaires,
            "finitions": self.finitions,
        }
        try:
            self._atomic_write(Path(output_path), payload)
            return True, "Sauvegarde créée."
        except OSError as exc:
            return False, str(exc)

    def restore_backup(self, backup_path: str | Path) -> tuple[bool, str]:
        data = self._read_json(Path(backup_path), None)
        if not isinstance(data, dict):
            return False, "Fichier de sauvegarde invalide."

        self.stones = data.get("pierres", [])
        self.bracelets = data.get("bracelets", [])
        self.products = data.get("produits", [])
        self.sales = data.get("ventes", [])
        self.stock_movements = data.get("mouvements_stock", [])
        self.settings.update(data.get("settings", {}))
        if "breloques" in data:
            self.breloques = data.get("breloques", [])
        if "intercalaires" in data:
            self.intercalaires = data.get("intercalaires", [])
        if "finitions" in data:
            self.finitions = data.get("finitions", [])
        self._normalize_existing_data()
        self.autosave_all()
        return True, "Restauration terminée."

    def export_full_archive(self, zip_path: str | Path) -> tuple[bool, str]:
        """Exporte toutes les donnees (JSON + medias) dans une archive ZIP portable."""
        try:
            zip_path = Path(zip_path)
            json_files = [
                self.stones_path, self.bracelets_path, self.products_path,
                self.sales_path, self.stock_movements_path, self.settings_path,
                self.breloques_path, self.intercalaires_path, self.finitions_path,
            ]
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for pth in json_files:
                    if Path(pth).exists():
                        zf.write(pth, Path(pth).name)
                media_dir = self.base_dir / "media"
                if media_dir.exists():
                    for f in media_dir.rglob("*"):
                        if f.is_file():
                            zf.write(f, str(f.relative_to(self.base_dir)))
            return True, f"Export complet cree : {zip_path}"
        except (OSError, zipfile.BadZipFile) as exc:
            return False, str(exc)

    def restore_full_archive(self, zip_path: str | Path) -> tuple[bool, str]:
        """Restaure une archive ZIP creee par export_full_archive (JSON + medias)."""
        try:
            zip_path = Path(zip_path)
            if not zip_path.exists():
                return False, "Archive introuvable."
            known = {
                "pierres.json", "bracelets.json", "produits.json", "ventes.json",
                "mouvements_stock.json", "settings.json", "breloques.json",
                "intercalaires.json", "finitions.json",
            }
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                if not any(Path(n).name in known for n in names):
                    return False, "Archive invalide (aucun fichier de donnees reconnu)."
                for name in names:
                    if name.endswith("/"):
                        continue
                    safe = Path(name)
                    if safe.is_absolute() or ".." in safe.parts:
                        continue
                    dest = self.base_dir / safe
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as src, open(dest, "wb") as out:
                        out.write(src.read())
            self.reload_all()
            return True, "Restauration complete terminee."
        except (OSError, zipfile.BadZipFile) as exc:
            return False, str(exc)

    def export_bracelets_to_excel(self, file_path: str | Path) -> tuple[bool, str]:
        try:
            from openpyxl import Workbook
        except ImportError:
            return False, "Le module 'openpyxl' n'est pas installé."

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Bracelets"

        headers = [
            "Nom",
            "Référence",
            "Prix vente",
            "Coût de revient",
            "Marge",
            "Bénéfice",
            "Composition",
            "Vertus",
            "Chakras",
            "Stock",
            "QR",
        ]
        sheet.append(headers)

        for bracelet in self.bracelets:
            metrics = self.calculate_bracelet_metrics(bracelet)
            sheet.append(
                [
                    bracelet.get("nom", ""),
                    bracelet.get("reference", ""),
                    float(bracelet.get("prix_vente", 0.0) or 0.0),
                    metrics["cout_revient"],
                    metrics["marge"],
                    metrics["benefice"],
                    ", ".join(metrics["composition"]),
                    ", ".join(metrics["vertus"]),
                    ", ".join(metrics["chakras"]),
                    int(bracelet.get("stock", 0) or 0),
                    "Oui" if bracelet.get("qr_enabled") else "Non",
                ]
            )

        workbook.save(str(file_path))
        return True, "Export Excel terminé."

    def export_bracelets_to_csv(self, file_path: str | Path) -> tuple[bool, str]:
        headers = [
            "nom",
            "reference",
            "prix_vente",
            "cout_revient",
            "marge",
            "benefice",
            "stock",
            "composition",
            "vertus",
            "chakras",
            "qr_enabled",
        ]
        try:
            with Path(file_path).open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file, delimiter=";")
                writer.writerow(headers)
                for bracelet in self.bracelets:
                    metrics = self.calculate_bracelet_metrics(bracelet)
                    writer.writerow(
                        [
                            bracelet.get("nom", ""),
                            bracelet.get("reference", ""),
                            float(bracelet.get("prix_vente", 0.0) or 0.0),
                            metrics["cout_revient"],
                            metrics["marge"],
                            metrics["benefice"],
                            int(bracelet.get("stock", 0) or 0),
                            ", ".join(metrics["composition"]),
                            ", ".join(metrics["vertus"]),
                            ", ".join(metrics["chakras"]),
                            bool(bracelet.get("qr_enabled", False)),
                        ]
                    )
            return True, "Export CSV terminé."
        except OSError as exc:
            return False, str(exc)

    def export_products_to_csv(self, file_path: str | Path) -> tuple[bool, str]:
        headers = ["categorie", "nom", "sku", "prix_achat", "prix_vente", "stock", "seuil_alerte", "fournisseur"]
        try:
            with Path(file_path).open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file, delimiter=";")
                writer.writerow(headers)
                for item in self.products:
                    writer.writerow(
                        [
                            item.get("categorie", ""),
                            item.get("nom", ""),
                            item.get("sku", ""),
                            float(item.get("prix_achat", 0.0) or 0.0),
                            float(item.get("prix_vente", 0.0) or 0.0),
                            int(item.get("stock", 0) or 0),
                            int(item.get("seuil_alerte", self.settings.get("stock_alert_threshold", 5)) or 0),
                            item.get("fournisseur", ""),
                        ]
                    )
            return True, "Export produits CSV terminé."
        except OSError as exc:
            return False, str(exc)

    def export_products_to_excel(self, file_path: str | Path) -> tuple[bool, str]:
        try:
            from openpyxl import Workbook
        except ImportError:
            return False, "Le module 'openpyxl' n'est pas installé."

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Produits"
        sheet.append(["Catégorie", "Nom", "SKU", "Prix achat", "Prix vente", "Marge unitaire", "Stock", "Seuil alerte", "Fournisseur"])

        for item in self.products:
            pa = float(item.get("prix_achat", 0.0) or 0.0)
            pv = float(item.get("prix_vente", 0.0) or 0.0)
            sheet.append(
                [
                    item.get("categorie", ""),
                    item.get("nom", ""),
                    item.get("sku", ""),
                    pa,
                    pv,
                    round(pv - pa, 2),
                    int(item.get("stock", 0) or 0),
                    int(item.get("seuil_alerte", self.settings.get("stock_alert_threshold", 5)) or 0),
                    item.get("fournisseur", ""),
                ]
            )

        workbook.save(str(file_path))
        return True, "Export produits Excel terminé."

    def import_products_from_csv(self, file_path: str | Path) -> tuple[bool, str]:
        imported = 0
        try:
            with Path(file_path).open("r", encoding="utf-8") as file:
                reader = csv.DictReader(file, delimiter=";")
                for row in reader:
                    if not row.get("nom", "").strip():
                        continue

                    self.products.append(
                        {
                            "id": self._new_id(),
                            "categorie": row.get("categorie", "bracelets").strip().lower(),
                            "nom": row.get("nom", "").strip(),
                            "sku": row.get("sku", "").strip() or self._new_sku(row.get("categorie", "produits")),
                            "prix_achat": float(row.get("prix_achat", "0") or 0.0),
                            "prix_vente": float(row.get("prix_vente", "0") or 0.0),
                            "stock": int(row.get("stock", "0") or 0),
                            "seuil_alerte": int(row.get("seuil_alerte", str(self.settings.get("stock_alert_threshold", 5))) or 0),
                            "fournisseur": row.get("fournisseur", "").strip(),
                            "photo": "",
                            "created_at": datetime.now().isoformat(timespec="seconds"),
                            "updated_at": datetime.now().isoformat(timespec="seconds"),
                        }
                    )
                    imported += 1
        except (OSError, ValueError) as exc:
            return False, str(exc)

        self.save_products()
        return True, f"Import terminé: {imported} produit(s)."

    def update_category_prices(self, category: str, percent: float) -> int:
        count = 0
        ratio = 1 + (percent / 100.0)
        for item in self.products:
            if item.get("categorie", "").lower() == category.lower():
                item["prix_vente"] = round(float(item.get("prix_vente", 0.0) or 0.0) * ratio, 2)
                item["updated_at"] = datetime.now().isoformat(timespec="seconds")
                count += 1
        if count:
            self.save_products()
        return count

    def build_receipt_text(self, sale_id: str) -> str:
        sale = next((s for s in self.sales if s.get("id") == sale_id), None)
        if not sale:
            return "Vente introuvable."
        return (
            "Boutique Lithothérapie\n"
            f"Date: {str(sale.get('date', ''))[:19].replace('T', ' ')}\n"
            f"Article: {sale.get('nom', '')}\n"
            f"Réf: {sale.get('reference', '')}\n"
            f"Qté: {sale.get('qty', 0)}\n"
            f"PU: {float(sale.get('prix_unitaire', 0.0) or 0.0):.2f} EUR\n"
            f"Total: {float(sale.get('total', 0.0) or 0.0):.2f} EUR\n"
            "Merci pour votre achat."
        )

    def _create_auto_snapshot(self) -> None:
        snapshots_dir = self.base_dir / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d")
        snap_file = snapshots_dir / f"auto_backup_{stamp}.json"
        if snap_file.exists():
            return
        self.create_backup(snap_file)

    def _normalize_existing_data(self) -> None:
        for stone in self.stones:
            stone.setdefault("prix_moyen", float(stone.get("prix_achat", 0.0) or 0.0))
            stone.setdefault("stock", 0)
            stone.setdefault("photo", "")
            stone.setdefault("chakras", str(stone.get("chakra", "")))
            stone["chakra"] = str(stone.get("chakras", stone.get("chakra", "")))
        # Migration automatique: anciens bracelets sans composition
        for bracelet in self.bracelets:
            if "composition" not in bracelet and bracelet.get("pierres"):
                comp = []
                for stone_id in bracelet.get("pierres", []):
                    stone = self.get_stone_by_id(stone_id)
                    if stone:
                        comp.append({
                            "composant": stone.get("nom", ""),
                            "categorie": "Pierre",
                            "quantite": 1,
                            "cout_unitaire": float(stone.get("prix_achat", 0.0) or 0.0),
                            "stone_id": stone_id,
                        })
                bracelet["composition"] = comp
                bracelet.setdefault("updated_at", datetime.now().isoformat(timespec="seconds"))

        for bracelet in self.bracelets:
            bracelet.setdefault("stock", 10)
            bracelet.setdefault("photo", "")
            bracelet.setdefault("qr_enabled", bool(self.settings.get("default_qr", False)))

        for product in self.products:
            product.setdefault("categorie", "bracelets")
            product.setdefault("sku", self._new_sku(product.get("categorie", "produits")))
            product.setdefault("prix_achat", 0.0)
            product.setdefault("prix_vente", 0.0)
            product.setdefault("stock", 0)
            product.setdefault("seuil_alerte", int(self.settings.get("stock_alert_threshold", 5) or 5))
            product.setdefault("fournisseur", "")
            product.setdefault("photo", "")

    def _seed_stones_if_needed(self) -> None:
        if len(self.stones) >= 100:
            return

        catalog = self._seed_catalog()
        existing_names = {s.get("nom", "").lower() for s in self.stones}
        added = 0
        for idx, item in enumerate(catalog):
            if item["nom"].lower() in existing_names:
                continue
            base_price = item["prix_moyen"]
            self.stones.append(
                {
                    "id": self._new_id(),
                    "nom": item["nom"],
                    "vertus": item["vertus"],
                    "chakra": item["chakra"],
                    "prix_achat": base_price,
                    "prix_moyen": base_price,
                    "prix_vente": round(base_price * 2.2, 2),
                    "stock": 0,
                    "photo": "",
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                }
            )
            added += 1
            if len(self.stones) >= 100:
                break

        if added > 0:
            self.save_stones()

    @staticmethod
    def _seed_catalog() -> list[dict[str, Any]]:
        """Catalogue des 100 pierres les plus utilisees en lithotherapie.

        Stock initial a 0 : les quantites sont mises a jour ensuite
        par l utilisateur (demarrage avec un stock vide).
        """
        stones: list[tuple[str, str, str]] = [
            ("Amethyste", "Apaisement, intuition, sommeil", "Couronne, 3e oeil"),
            ("Quartz rose", "Amour, douceur, guerison emotionnelle", "Coeur"),
            ("Cristal de roche", "Amplification, clarte, purification", "Couronne"),
            ("Citrine", "Joie, abondance, confiance", "Plexus solaire"),
            ("Labradorite", "Protection, intuition", "3e oeil, Gorge"),
            ("Oeil de tigre", "Protection, ancrage, confiance", "Plexus solaire, Racine"),
            ("Lapis-lazuli", "Communication, sagesse, verite", "Gorge, 3e oeil"),
            ("Aventurine verte", "Chance, apaisement, coeur", "Coeur"),
            ("Cornaline", "Energie, creativite, vitalite", "Sacre"),
            ("Obsidienne noire", "Protection, ancrage, nettoyage", "Racine"),
            ("Tourmaline noire", "Protection, ancrage, anti-ondes", "Racine"),
            ("Sodalite", "Communication, logique, calme", "Gorge, 3e oeil"),
            ("Pierre de lune", "Feminite, intuition, douceur", "Sacre, Couronne"),
            ("Hematite", "Ancrage, protection, vitalite", "Racine"),
            ("Amazonite", "Apaisement, communication, harmonie", "Gorge, Coeur"),
            ("Fluorite", "Concentration, clarte mentale", "3e oeil"),
            ("Jaspe rouge", "Ancrage, energie, courage", "Racine"),
            ("Howlite", "Calme, sommeil, patience", "Couronne"),
            ("Selenite", "Purification, paix, lumiere", "Couronne"),
            ("Malachite", "Transformation, protection, coeur", "Coeur"),
            ("Lepidolite", "Anti-stress, apaisement, transition", "Coeur, Couronne"),
            ("Pyrite", "Abondance, protection, volonte", "Plexus solaire"),
            ("Turquoise", "Protection, communication, guerison", "Gorge"),
            ("Quartz fume", "Ancrage, anti-stress, protection", "Racine"),
            ("Aigue-marine", "Apaisement, communication, courage", "Gorge"),
            ("Rhodonite", "Amour, pardon, equilibre emotionnel", "Coeur"),
            ("Onyx noir", "Ancrage, protection, force", "Racine"),
            ("Calcedoine bleue", "Communication, douceur, apaisement", "Gorge"),
            ("Agate mousse", "Abondance, lien a la nature, croissance", "Coeur"),
            ("Agate du Botswana", "Reconfort, transition, ancrage", "Racine"),
            ("Oeil de faucon", "Intuition, protection, vision", "3e oeil, Gorge"),
            ("Peridot", "Abondance, renouveau, coeur", "Coeur, Plexus solaire"),
            ("Grenat", "Energie, passion, vitalite", "Racine, Sacre"),
            ("Apatite bleue", "Motivation, communication", "Gorge"),
            ("Kunzite", "Amour inconditionnel, douceur", "Coeur"),
            ("Larimar", "Serenite, communication, feminite", "Gorge"),
            ("Chrysocolle", "Communication, apaisement, feminite", "Gorge, Coeur"),
            ("Angelite", "Communication, paix, serenite", "Gorge, Couronne"),
            ("Celestine", "Serenite, spiritualite, paix", "Gorge, Couronne"),
            ("Sugilite", "Protection spirituelle, amour", "3e oeil, Couronne"),
            ("Charoite", "Transformation, intuition, protection", "3e oeil, Couronne"),
            ("Prehnite", "Guerison, intuition, lacher-prise", "Coeur"),
            ("Unakite", "Equilibre emotionnel, vision, croissance", "Coeur, 3e oeil"),
            ("Rhodochrosite", "Amour de soi, joie, guerison", "Coeur"),
            ("Azurite", "Intuition, clarte, vision interieure", "3e oeil"),
            ("Iolite", "Vision, intuition, equilibre", "3e oeil"),
            ("Jade nephrite", "Serenite, chance, harmonie", "Coeur"),
            ("Serpentine", "Energie, protection, regeneration", "Coeur, Racine"),
            ("Shungite", "Purification, protection, anti-ondes", "Racine"),
            ("Magnesite", "Calme, meditation, detente", "Couronne"),
            ("Cyanite bleue", "Alignement, communication, calme", "Gorge, 3e oeil"),
            ("Topaze bleue", "Communication, expression, calme", "Gorge, 3e oeil"),
            ("Tanzanite", "Spiritualite, transformation", "3e oeil, Couronne"),
            ("Tourmaline rose", "Amour, coeur, douceur", "Coeur"),
            ("Tourmaline verte", "Guerison, coeur, vitalite", "Coeur"),
            ("Emeraude", "Amour, guerison, prosperite", "Coeur"),
            ("Rubis", "Passion, energie vitale, courage", "Racine, Coeur"),
            ("Saphir", "Sagesse, intuition, serenite", "3e oeil, Gorge"),
            ("Spinelle noir", "Energie, revitalisation, ancrage", "Racine"),
            ("Morganite", "Amour divin, compassion", "Coeur"),
            ("Aventurine bleue", "Calme, communication, discipline", "Gorge, 3e oeil"),
            ("Quartz rutile", "Energie, manifestation, protection", "Plexus solaire, Couronne"),
            ("Quartz tourmaline", "Purification, protection, equilibre", "Racine, Couronne"),
            ("Calcite orange", "Joie, creativite, energie", "Sacre"),
            ("Calcite bleue", "Calme, communication, apaisement", "Gorge"),
            ("Calcite jaune", "Confiance, optimisme", "Plexus solaire"),
            ("Dumortierite", "Patience, discipline, calme mental", "3e oeil, Gorge"),
            ("Chrysoprase", "Joie, guerison du coeur, espoir", "Coeur"),
            ("Jaspe paysage", "Ancrage, lien a la terre, serenite", "Racine"),
            ("Jaspe ocean", "Apaisement, positivite, lacher-prise", "Coeur, Gorge"),
            ("Jaspe dalmatien", "Joie, ancrage, protection", "Racine"),
            ("Mookaite", "Vitalite, ancrage, decision", "Racine, Sacre"),
            ("Pierre de soleil", "Joie, vitalite, optimisme", "Sacre, Plexus solaire"),
            ("Heliotrope", "Vitalite, courage, purification", "Racine, Coeur"),
            ("Ambre", "Purification, energie, protection", "Plexus solaire, Sacre"),
            ("Oeil de taureau", "Courage, protection, ancrage", "Racine"),
            ("Obsidienne flocon de neige", "Equilibre, calme, recentrage", "Racine"),
            ("Obsidienne oeil celeste", "Protection, intuition", "Racine, 3e oeil"),
            ("Opale blanche", "Inspiration, creativite, emotions", "Couronne, Sacre"),
            ("Opale de feu", "Passion, energie, creativite", "Sacre"),
            ("Nuummite", "Protection, ancrage, force interieure", "Racine"),
            ("Apophyllite", "Spiritualite, paix, energie elevee", "Couronne, 3e oeil"),
            ("Stilbite", "Amour, creativite, intuition", "Coeur, Couronne"),
            ("Scolecite", "Paix interieure, sommeil, lien spirituel", "Couronne"),
            ("Danburite", "Paix, amour inconditionnel, elevation", "Couronne, Coeur"),
            ("Petalite", "Serenite, lacher-prise, protection", "Couronne"),
            ("Moldavite", "Transformation, eveil spirituel", "Coeur, 3e oeil"),
            ("Epidote", "Abondance, liberation, regeneration", "Coeur"),
            ("Vesuvianite", "Courage, lacher-prise", "Coeur, Plexus solaire"),
            ("Variscite", "Calme, espoir, coeur", "Coeur"),
            ("Smithsonite", "Apaisement, harmonie emotionnelle", "Coeur, Gorge"),
            ("Hemimorphite", "Bien-etre emotionnel, communication", "Gorge, Coeur"),
            ("Dioptase", "Guerison du coeur, pardon", "Coeur"),
            ("Jaspe kambaba", "Ancrage, apaisement, lien a la nature", "Racine, Coeur"),
            ("Agate de feu", "Vitalite, protection, ancrage", "Sacre, Racine"),
            ("Quartz hematoide", "Ancrage, vitalite, energie", "Racine"),
            ("Prasiolite", "Coeur, transformation, apaisement", "Coeur"),
            ("Bronzite", "Ancrage, protection, decision", "Racine"),
            ("Sardonyx", "Force, protection, volonte", "Racine"),
            ("Tektite", "Eveil, energie, expansion", "3e oeil, Couronne"),
        ]
        catalog: list[dict[str, Any]] = []
        for idx, (nom, vertus, chakra) in enumerate(stones):
            base_price = round(1.0 + (idx % 10) * 0.5, 2)
            catalog.append(
                {
                    "nom": nom,
                    "vertus": vertus,
                    "chakra": chakra,
                    "chakras": chakra,
                    "prix_moyen": base_price,
                    "stock": 0,
                    "photo": "",
                }
            )
        return catalog
