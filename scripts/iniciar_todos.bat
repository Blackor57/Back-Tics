@echo off
TITLE SIMAP - Iniciar Todos los Microservicios
echo ========================================================
echo   SIMAP - Plataforma de Scraping e Inteligencia Web
echo   Iniciando los 3 Microservicios en ventanas separadas...
echo ========================================================
echo.

cd /d "%~dp0\.."

echo [1/4] Verificando e Iniciando Ollama (Puerto 11434)...
start "SIMAP - Ollama (11434)" cmd /k "ollama serve"

echo [2/4] Iniciando Microservicio de Scraping (Puerto 8001)...
start "SIMAP - Scraper Service (8001)" cmd /k "python -m uvicorn scraper_service.main:app --host 0.0.0.0 --port 8001 --reload"

echo [3/4] Iniciando Core Backend API (Puerto 8000)...
start "SIMAP - Backend API (8000)" cmd /k "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo [4/4] Iniciando Asistente Chatbot Streamlit (Puerto 8501)...
start "SIMAP - Chatbot UI (8501)" cmd /k "python -m streamlit run streamlit_app.py --server.port 8501"

echo.
echo ========================================================
echo   Todos los servicios han sido lanzados:
echo   - Ollama LLM:        http://localhost:11434
echo   - Backend API:       http://localhost:8000/docs
echo   - Scraper Service:   http://localhost:8001/docs
echo   - Chatbot UI:        http://localhost:8501
echo ========================================================
echo.
pause
