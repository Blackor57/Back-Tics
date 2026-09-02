#!/bin/bash

echo ""
echo "========================================="
echo " Web Scraper API Backend - Modo Desarrollo"
echo " (El frontend se ejecuta en su propio repo)"
echo "========================================="
echo ""

echo "📡 [API] Iniciando servidor en http://localhost:8000"
echo "📚 [DOCS] Documentación interactiva en http://localhost:8000/docs"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
