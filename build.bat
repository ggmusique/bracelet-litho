@echo off
setlocal
cd /d %~dp0

echo [1/2] Installation des dependances...
py -m pip install --upgrade pip
py -m pip install -r requirements.txt

echo [2/2] Build PyInstaller...
py -m PyInstaller --noconfirm --clean Lithotherapie_App.spec

if exist ".\dist\Lithotherapie_App.exe" (
	copy /Y ".\dist\Lithotherapie_App.exe" ".\Lithotherapie_App.exe" >nul
)

echo Build termine.
echo Executable: .\Lithotherapie_App.exe
echo (Copie egalement disponible dans .\dist\Lithotherapie_App.exe)
pause
