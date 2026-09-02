@echo off
REM Script para iniciar la API y el Frontend en Windows

echo.
echo =========================================
echo  Web Scraper - Inicio Rápido
echo =========================================
echo.

REM Verificar si estamos en la carpeta correcta
if not exist "api.py" (
    echo Error: No se encontró api.py
    echo Asegúrate de ejecutar este script desde la carpeta raíz del proyecto
    pause
    exit /b 1
)

REM Crear archivos de log
set LOG_API=api.log
set LOG_FRONTEND=frontend.log

echo Iniciando servicios...
echo.

REM Iniciar API en una nueva ventana
echo [API] Iniciando servidor en http://localhost:8000
start "Web Scraper API" cmd /k "python -m uvicorn api:app --reload --host localhost --port 8000"
timeout /t 2 /nobreak

REM Iniciar Frontend en otra ventana
echo [Frontend] Iniciando servidor en http://localhost:8080
start "Web Scraper Frontend" cmd /k "cd frontend && python server.py"

echo.
echo =========================================
echo  Servicios iniciados:
echo  - API:      http://localhost:8000
echo  - Frontend: http://localhost:8080
echo  - Docs API: http://localhost:8000/docs
echo =========================================
echo.
echo Presiona Ctrl+C en cualquier ventana para detenerla
pause
