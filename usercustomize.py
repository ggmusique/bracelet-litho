from __future__ import annotations

"""
Correctif runtime complementaire pour la fiche de creation PDF.

But : corriger sans toucher aux donnees utilisateur :
- eviter que "Ordre de montage" chevauche l'en-tete du tableau ;
- afficher le symbole euro correct dans le sous-total des composants.
"""

import importlib.abc
import importlib.machinery
import sys
from types import ModuleType


class _PdfGeneratorPatchLoader(importlib.abc.Loader):
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def create_module(self, spec):
        if hasattr(self.wrapped, "create_module"):
            return self.wrapped.create_module(spec)
        return None

    def exec_module(self, module: ModuleType) -> None:
        origin = getattr(module.__spec__, "origin", None)
        if not origin:
            self.wrapped.exec_module(module)
            return

        try:
            with open(origin, "r", encoding="utf-8") as f:
                source = f.read()

            # 1) Plus d'espace entre le titre "Ordre de montage" et l'en-tete du tableau.
            source = source.replace(
                '        c.setFont(font_b, 12)\n'
                '        c.drawString(x0, y, "Ordre de montage")\n'
                '        y -= 6\n\n'
                '        th_h = chosen_size + 5',
                '        c.setFont(font_b, 12)\n'
                '        c.drawString(x0, y, "Ordre de montage")\n'
                '        y -= 20  # espace pour eviter le chevauchement avec l en-tete\n\n'
                '        th_h = chosen_size + 5',
            )

            # 2) Sous-total : remplacer E par le symbole euro ReportLab/Helvetica.
            source = source.replace(
                '            c.drawRightString(col_sub, y, f"{sub:.2f}E")',
                '            c.drawRightString(col_sub, y, f"{sub:.2f} \\u20ac")',
            )

            code = compile(source, origin, "exec")
            exec(code, module.__dict__)
        except Exception:
            # En cas de souci, on garde le comportement original pour ne jamais bloquer l'appli.
            self.wrapped.exec_module(module)


class _PdfGeneratorPatchFinder(importlib.abc.MetaPathFinder):
    target = "pdf_generator"

    def find_spec(self, fullname, path=None, target=None):
        if fullname != self.target:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec and spec.loader:
            spec.loader = _PdfGeneratorPatchLoader(spec.loader)
        return spec


if "pdf_generator" in sys.modules:
    # Si le module est deja charge, on ne tente pas de le recharger ici.
    # Au prochain redemarrage de l'application, le correctif s'appliquera avant import.
    pass
elif not any(isinstance(f, _PdfGeneratorPatchFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _PdfGeneratorPatchFinder())
