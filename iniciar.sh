#!/bin/bash

# Script para iniciar la API y el Frontend en Linux/macOS

echo ""
echo "========================================="
echo " Web Scraper - Inicio Rápido"
echo "========================================="
echo ""

# Verificar si estamos en la carpeta correcta
if [ ! -f "api.py" ]; then
    echo "❌ Error: No se encontró api.py"
    echo "Asegúrate de ejecutar este script desde la carpeta raíz del proyecto"
    exit 1
fi

# Función para limpiar procesos al salir
cleanup() {
    echo ""
    echo ""
    echo "⛔ Deteniendo servicios..."
    kill $PID_API $PID_FRONTEND 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "🚀 Iniciando servicios..."
echo ""

# Iniciar API en background
echo "📡 [API] Iniciando servidor en http://localhost:8000"
python -m uvicorn api:app --reload --host localhost --port 8000 &
PID_API=$!
sleep 2

# Iniciar Frontend en background
echo "🌐 [Frontend] Iniciando servidor en http://localhost:8080"
(cd frontend && python server.py) &
PID_FRONTEND=$!

echo ""
echo "========================================="
echo "✅ Servicios iniciados:"
echo "  - API:      http://localhost:8000"
echo "  - Frontend: http://localhost:8080"
echo "  - Docs API: http://localhost:8000/docs"
echo "========================================="
echo ""
echo "Presiona Ctrl+C para detener los servicios"
echo ""

# Mantener el script ejecutándose
wait
