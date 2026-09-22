# streamlit_app.py
# Acceso directo para desarrollo local hacia el Microservicio 5 (chatbot_service)
import runpy
from pathlib import Path

app_path = Path(__file__).parent / "chatbot_service" / "app.py"
runpy.run_path(str(app_path), run_name="__main__")
