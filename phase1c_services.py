from __future__ import annotations

import json
import re
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

import customtkinter as ctk
from PIL import Image

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
_CTK_IMAGE_CACHE: dict[tuple[str, int, int], ctk.CTkImage] = {}


def _is_valid_ref(value: str, prefix: str) -> bool:
    return bool(re.fullmatch(rf"{prefix}-\d{{4}}", value or ""))


def _extract_ref_number(value: str, prefix: str) -> int | None:
    match = re.fullmatch(rf"{prefix}-(\d{{4}})", value or "")
    if not match:
        return None
    return int(match.group(1))


def _next_ref(prefix: str, current: int) -> tuple[str, int]:
    new_current = current + 1
    return f"{prefix}-{new_current:04d}", new_current


def _ensure_component_supplier_fields(item: dict[str, Any]) -> bool:
    changed = False
    defaults = {
        "fournisseur": "",
        "fournisseur_ref": "",
        "fournisseur_site": "",
        "fournisseur_email": "",
        "date_dernier_achat": "",
        "photo": item.get("photo", "") or "",
        "photo_thumb": item.get("photo_thumb", "") or "",
        "stock_reserve": 0,
    }
    for key, value in defaults.items():
        if key not in item:
            item[key] = value
            changed = True
    return changed


def normalize_phase1c_data(db: Any) -> None:
    """Normalize references and Phase 1C fields without changing business rules."""
    if not db:
        return

    changed_settings = False

    configs = [
        ("PIE", db.stones, "reference", "phase1c_counter_pie", db.save_stones),
        ("BRE", getattr(db, "breloques", []), "reference", "phase1c_counter_bre", getattr(db, "save_breloques", lambda: None)),
        ("INT", getattr(db, "intercalaires", []), "reference", "phase1c_counter_int", getattr(db, "save_intercalaires", lambda: None)),
        ("FIN", getattr(db, "finitions", []), "reference", "phase1c_counter_fin", getattr(db, "save_finitions", lambda: None)),
        ("BRA", db.bracelets, "reference", "phase1c_counter_bra", db.save_bracelets),
        ("PRO", db.products, "sku", "phase1c_counter_pro", db.save_products),
    ]

    for prefix, collection, field, counter_key, saver in configs:
        used: set[int] = set()
        seen_values: set[str] = set()

        for item in collection:
            value = str(item.get(field, "") or "").strip().upper()
            number = _extract_ref_number(value, prefix)
            if number is not None and value not in seen_values:
                seen_values.add(value)
                used.add(number)

        counter = int(db.settings.get(counter_key, 0) or 0)
        if used:
            counter = max(counter, max(used))

        changed = False
        seen_values.clear()

        for item in collection:
            current = str(item.get(field, "") or "").strip().upper()
            valid = _is_valid_ref(current, prefix) and current not in seen_values
            if valid:
                seen_values.add(current)
                continue

            new_ref, counter = _next_ref(prefix, counter)
            while new_ref in seen_values:
                new_ref, counter = _next_ref(prefix, counter)

            item[field] = new_ref
            seen_values.add(new_ref)
            changed = True

            if prefix == "PRO":
                item["reference"] = new_ref

        if prefix == "PRO":
            for item in collection:
                if str(item.get("reference", "") or "").strip().upper() != str(item.get("sku", "") or "").strip().upper():
                    item["reference"] = str(item.get("sku", "") or "").strip().upper()
                    changed = True

        if counter != int(db.settings.get(counter_key, 0) or 0):
            db.settings[counter_key] = counter
            changed_settings = True

        if prefix in {"PIE", "BRE", "INT", "FIN"}:
            for item in collection:
                if _ensure_component_supplier_fields(item):
                    changed = True

        if prefix in {"BRA", "PRO"}:
            for item in collection:
                if "photo_thumb" not in item:
                    item["photo_thumb"] = ""
                    changed = True

        if changed:
            saver()

    if changed_settings:
        db.save_settings()


def _ensure_media_dirs(base_dir: Path, category: str) -> tuple[Path, Path]:
    original_dir = base_dir / "media" / category
    thumbs_dir = original_dir / "thumbs"
    original_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    return original_dir, thumbs_dir


def import_image_for_item(db: Any, item: dict[str, Any], category: str, source_path: str | Path) -> tuple[bool, str]:
    if not db:
        return False, "Base de donnees indisponible."

    source = Path(source_path)
    if not source.exists():
        return False, "Image introuvable."

    if source.suffix.lower() not in _IMAGE_EXTS:
        return False, "Format non supporte (jpg, jpeg, png, webp)."

    original_dir, thumbs_dir = _ensure_media_dirs(Path(db.base_dir), category)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest_name = f"{stamp}.png"
    dest = original_dir / dest_name
    thumb = thumbs_dir / dest_name

    try:
        with Image.open(source) as img:
            rgb = img.convert("RGBA") if img.mode in {"RGBA", "LA", "P"} else img.convert("RGB")
            rgb.save(dest, format="PNG")

        with Image.open(dest) as img2:
            img2.thumbnail((128, 128), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
            x = (128 - img2.width) // 2
            y = (128 - img2.height) // 2
            canvas.paste(img2, (x, y))
            canvas.save(thumb, format="PNG")

        item["photo"] = str(dest.relative_to(db.base_dir)).replace("\\", "/")
        item["photo_thumb"] = str(thumb.relative_to(db.base_dir)).replace("\\", "/")
        item["updated_at"] = datetime.now().isoformat(timespec="seconds")
        return True, "Image importee."
    except OSError as exc:
        return False, str(exc)


def resolve_media_path(base_dir: Path, raw_path: str) -> Path | None:
    if not raw_path:
        return None
    path = Path(raw_path)
    if not path.is_absolute():
        path = base_dir / path
    if path.exists():
        return path
    return None


def load_ctk_image(db: Any, item: dict[str, Any], size: tuple[int, int], use_thumb: bool = False) -> ctk.CTkImage | None:
    if not db:
        return None
    key = "photo_thumb" if use_thumb else "photo"
    raw = str(item.get(key, "") or "")
    if not raw and use_thumb:
        raw = str(item.get("photo", "") or "")

    path = resolve_media_path(Path(db.base_dir), raw)
    if path is None:
        return None

    cache_key = (str(path), int(size[0]), int(size[1]))
    cached = _CTK_IMAGE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    try:
        img = Image.open(path)
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        _CTK_IMAGE_CACHE[cache_key] = ctk_img
        return ctk_img
    except OSError:
        return None


def open_supplier_site(url: str) -> bool:
    clean = (url or "").strip()
    if not clean:
        return False
    if not clean.startswith(("http://", "https://")):
        clean = f"https://{clean}"
    webbrowser.open(clean)
    return True


def _list_backups(folder: Path, prefix: str) -> list[Path]:
    return sorted(folder.glob(f"{prefix}_*.json"), key=lambda p: p.name, reverse=True)


def _prune_backups(folder: Path, prefix: str, keep: int) -> None:
    files = _list_backups(folder, prefix)
    for extra in files[keep:]:
        extra.unlink(missing_ok=True)


def run_rotating_backup(db: Any) -> tuple[bool, str]:
    if not db:
        return False, "Base de donnees indisponible."

    backup_dir = Path(db.base_dir) / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    daily = backup_dir / f"daily_{now.strftime('%Y-%m-%d')}.json"
    weekly = backup_dir / f"weekly_{now.strftime('%Y-W%W')}.json"
    monthly = backup_dir / f"monthly_{now.strftime('%Y-%m')}.json"

    created = 0
    for target in (daily, weekly, monthly):
        if not target.exists():
            ok, msg = db.create_backup(target)
            if not ok:
                return False, msg
            created += 1

    _prune_backups(backup_dir, "daily", 7)
    _prune_backups(backup_dir, "weekly", 4)
    _prune_backups(backup_dir, "monthly", 3)

    return True, f"Rotation terminee ({created} nouvelle(s) sauvegarde(s))."


def get_backup_stats(db: Any) -> dict[str, str]:
    if not db:
        return {"last": "—", "count": "0", "size": "0 B"}

    backup_dir = Path(db.base_dir) / "backup"
    if not backup_dir.exists():
        return {"last": "—", "count": "0", "size": "0 B"}

    files = sorted(backup_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    count = len(files)
    total_bytes = sum(f.stat().st_size for f in files)

    if files:
        last = datetime.fromtimestamp(files[0].stat().st_mtime).strftime("%d/%m/%Y %H:%M")
    else:
        last = "—"

    return {
        "last": last,
        "count": str(count),
        "size": _format_size(total_bytes),
    }


def _format_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(size_bytes)
    idx = 0
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    return f"{size:.1f} {units[idx]}"


def append_local_history(
    db: Any,
    entity: str,
    action: str,
    item: dict[str, Any],
    details: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Append a CRUD event to local history storage."""
    if not db:
        return False, "Base de donnees indisponible."

    history_file = Path(db.base_dir) / "history_local.json"
    try:
        if history_file.exists():
            with history_file.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            if not isinstance(payload, list):
                payload = []
        else:
            payload = []
    except (OSError, json.JSONDecodeError):
        payload = []

    payload.append(
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "entity": str(entity or ""),
            "action": str(action or ""),
            "id": str(item.get("id", "") or ""),
            "reference": str(item.get("reference", item.get("sku", "")) or ""),
            "name": str(item.get("nom", "") or ""),
            "details": details or {},
        }
    )

    try:
        with history_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return True, "Historique mis a jour."
    except OSError as exc:
        return False, str(exc)


def backup_before_delete(db: Any, entity: str) -> tuple[bool, str]:
    """Create an automatic backup snapshot before destructive operations."""
    if not db:
        return False, "Base de donnees indisponible."
    backup_dir = Path(db.base_dir) / "backup" / "pre_delete"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = backup_dir / f"{entity}_{stamp}.json"
    return db.create_backup(target)
