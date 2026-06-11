@echo off
setlocal
cd /d %~dp0

echo Installation environnement application Lithotherapie...
echo [1/3] Verification de Python...
py -V
if errorlevel 1 (
	echo Python n'est pas installe ou n'est pas accessible via 'py'.
	pause
	exit /b 1
)

echo [2/3] Installation de pip et dependances...
py -m pip install --upgrade pip
py -m pip install -r requirements.txt

echo [3/3] Installation terminee.
echo Pour construire l'executable: build.bat
echo Pour lancer en mode script: py Lithotherapie_App.py
pause
