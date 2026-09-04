# run_local.py
"""
Script de conveniencia para ejecutar el servidor Backend en modo desarrollo local.
"""

import sys
import asyncio
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import uvicorn

def main():
    if sys.platform == 'win32' and sys.version_info < (3, 14):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass
    
    print("==================================================")
    print("  [*] Iniciando Web Scraper & Intelligence API")
    print("  Documentacion Swagger: http://localhost:8000/docs")
    print("  Analisis Inteligente:  http://localhost:8000/api/v1/intelligence/analyze")
    print("  Health check:          http://localhost:8000/health")
    print("==================================================")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

if __name__ == "__main__":
    main()

