import pathlib, sys

f = pathlib.Path('pdf_generator.py')
if not f.exists():
    print("Fichier pdf_generator.py introuvable.")
    sys.exit(1)

t = f.read_text()

# 1) Espacement entre "Ordre de montage" et l'en-tête du tableau
old1 = 'y -= 6\n\n        th_h = chosen_size + 5'
new1 = 'y -= 20\n\n        th_h = chosen_size + 5'
if old1 in t:
    t = t.replace(old1, new1)
    print("✔ Espacement 'Ordre de montage' corrigé.")
else:
    print("✘ Espacement 'Ordre de montage' non trouvé (deja corrigé ou format different).")

# 2) Symbole euro dans le sous-total des composants
old2 = 'c.drawRightString(col_sub, y, f"{sub:.2f}E")'
new2 = 'c.drawRightString(col_sub, y, f"{sub:.2f} \\u20ac")'
if old2 in t:
    t = t.replace(old2, new2)
    print("✔ Symbole euro corrigé.")
else:
    print("✘ Symbole euro non trouvé (deja corrigé ou format different).")

f.write_text(t, encoding='utf-8')
print("Fichier pdf_generator.py patché.")
