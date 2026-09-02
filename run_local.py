# run_local.py
"""
Script de conveniencia para ejecutar el servidor Backend en modo desarrollo local.
"""

import sys
import asyncio
# pyrefly: ignore [missing-import]
import uvicorn

def main():
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    print("=========================================")
    print("  🚀 Iniciando Web Scraper API (Backend)")
    print("  Documentación: http://localhost:8000/docs")
    print("  Health check:  http://localhost:8000/health")
    print("=========================================")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

if __name__ == "__main__":
    main()
