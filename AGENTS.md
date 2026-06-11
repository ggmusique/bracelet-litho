# Règles du projet — Lithothérapie

## Architecture V1 / V2

- **V1** : `ui.py` (Tkinter) + `database.py` + `pdf_generator.py`
- **V2** : `ui_v2.py` (CustomTkinter) + `pages/` + `theme.py` + `widgets.py`

## Règle de migration

- Toute **nouvelle fonctionnalité** doit être développée uniquement dans l'architecture **V2**.
- **Interdiction** de modifier `ui.py`.
- **Interdiction** d'ajouter du code métier dans l'ancienne interface.
- `ui.py` devient progressivement une branche **legacy**.

## Objectif

Quand la **Phase 2** sera terminée, `ui.py` pourra être supprimé complètement.

### Avant suppression :
- [ ] Audit des dépendances
- [ ] Vérification des imports
- [ ] Vérification des fonctions encore utilisées
- [ ] Vérification impression/PDF

Aucune suppression immédiate. Préparer la suppression.

## Build

### Commande de build

```powershell
py -m PyInstaller Lithotherapie_App.spec
```

Ou build.bat :

```powershell
& ".\build.bat"
```

### Post-build

- Ajouter `--uac-admin` à `requestedExecutionLevel` dans le manifeste de l'exe généré (pour les droits admin sur l'impression PDF directe).
- Copier l'exe buildé vers `dist/Lithotherapie/`.
- Tester l'impression PDF avec `pdf_generator.py`.

### Dépendances

- Python 3.14+
- Packages : `reportlab`, `qrcode[pil]`, `openpyxl`, `Pillow`, `customtkinter`, `pyinstaller`
- Pas besoin de `pywin32` : l'impression PDF est gérée par `reportlab` et `win32print` est optionnel.

## Phase 1C — Terminée

- Normalisation des données Phase 1C
- Import d'images
- Cache CTkImage
- Backup rotatif
- Ouverture site fournisseur

Prochaine phase : Phase 1D (à définir).
