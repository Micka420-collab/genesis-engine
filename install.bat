@echo off
REM Genesis Engine - lanceur double-clic pour Windows.
REM Ouvre l'installeur PowerShell stylise avec les bons droits d'execution.
echo.
echo   Lancement de l'installeur Genesis Engine...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
