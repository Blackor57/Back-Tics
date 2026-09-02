@echo off
REM Script para iniciar la API Backend en Windows

echo.
echo =========================================
echo   Web Scraper API Backend - Modo Desarrollo
echo   (El frontend se ejecuta en su propio repo)
echo =========================================
echo.

REM Iniciar API con Uvicorn apuntando a app.main:app
echo [API] Iniciando servidor en http://localhost:8000
echo [DOCS] Documentacion interactiva en http://localhost:8000/docs
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause