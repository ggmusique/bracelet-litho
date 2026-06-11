@echo off
setlocal
cd /d %~dp0

echo Demarrage du watcher de build automatique...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0auto_update_exe.ps1"
