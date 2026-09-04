# scripts/test_smtp.py
"""
Script de diagnóstico para verificar la conexión y el envío de correos SMTP reales.
Uso:
    python scripts/test_smtp.py [correo_destino]
Ejemplo:
    python scripts/test_smtp.py tu_correo@gmail.com
"""

import os
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Asegurar carga del .env en la raíz del backend
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "").strip()
SMTP_TLS = os.getenv("SMTP_TLS", "true").lower() in ("true", "1", "yes")

def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def main():
    print_header("DIAGNÓSTICO DE CONFIGURACIÓN SMTP (SIMAP)")

    print(f"Archivo .env detectado en: {env_path}")
    print(f"SMTP_HOST:       '{SMTP_HOST}'")
    print(f"SMTP_PORT:       {SMTP_PORT}")
    print(f"SMTP_USER:       '{SMTP_USER}'")
    print(f"SMTP_PASSWORD:   {'********' if SMTP_PASSWORD else '(VACÍO)'}")
    print(f"SMTP_FROM_EMAIL: '{SMTP_FROM_EMAIL}'")
    print(f"SMTP_TLS:        {SMTP_TLS}")
    print("-" * 60)

    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        print("\n[!] ERROR: Faltan credenciales SMTP en tu archivo .env.")
        print("El sistema actualmente se encuentra en [MODO SIMULACION].")
        print("Para enviar correos reales, debes configurar en Backend/.env:")
        print("  - SMTP_HOST (ej: smtp.gmail.com)")
        print("  - SMTP_USER (ej: tu_correo@gmail.com)")
        print("  - SMTP_PASSWORD (ej: contrasena de aplicacion de 16 caracteres de Google)")
        print("  - SMTP_FROM_EMAIL (ej: tu_correo@gmail.com)")
        print("\nSi usas Gmail, recuerda:")
        print("  1. Activar 'Verificacion en dos pasos' en tu cuenta de Google.")
        print("  2. Ir a https://myaccount.google.com/apppasswords y crear una Contrasena de Aplicacion.")
        print("  3. Colocar esa clave de 16 caracteres en SMTP_PASSWORD.")
        sys.exit(1)

    destinatario = sys.argv[1] if len(sys.argv) > 1 else SMTP_USER
    print(f"\nIntentando conectar y enviar correo de prueba a: {destinatario}...")

    remitente = SMTP_FROM_EMAIL or SMTP_USER

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Prueba de Conexion SMTP - SIMAP"
    msg["From"] = remitente
    msg["To"] = destinatario

    html_content = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; background-color: #f8fafc; border-radius: 8px;">
        <h2 style="color: #0284c7;">Conexion SMTP Exitosa</h2>
        <p>Este es un correo de prueba enviado desde el sistema de alertas de <strong>SIMAP</strong>.</p>
        <p>Tu servidor SMTP (<code>{SMTP_HOST}:{SMTP_PORT}</code>) está correctamente configurado y listo para despachar:</p>
        <ul>
            <li>Correos de confirmación de cuenta.</li>
            <li>Alertas y recordatorios periódicos de monitoreo.</li>
        </ul>
    </div>
    """
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        if SMTP_PORT == 465:
            print(f"[*] Conectando a {SMTP_HOST}:{SMTP_PORT} con SSL...")
            servidor = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
        else:
            print(f"[*] Conectando a {SMTP_HOST}:{SMTP_PORT}...")
            servidor = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            if SMTP_TLS:
                print("[*] Iniciando negociacion STARTTLS...")
                servidor.starttls()

        print(f"[*] Autenticando con usuario: {SMTP_USER}...")
        servidor.login(SMTP_USER, SMTP_PASSWORD)

        print(f"[*] Despachando correo a {destinatario}...")
        servidor.sendmail(remitente, [destinatario], msg.as_string())
        servidor.quit()

        print("\n[OK] EXITO TOTAL!")
        print(f"El correo de prueba ha sido entregado exitosamente a: {destinatario}")
        print("Revisa tu bandeja de entrada (o carpeta de Spam/Promociones).")

    except smtplib.SMTPAuthenticationError as auth_err:
        print("\n[!] ERROR DE AUTENTICACION SMTP:")
        print(f"Detalle: {auth_err}")
        if "gmail.com" in SMTP_HOST.lower():
            print("\nNOTA PARA GMAIL:")
            print("Google ya no permite usar la contrasena estandar de la cuenta.")
            print("Debes generar una 'Contrasena de Aplicacion' de 16 caracteres:")
            print("1. Ve a https://myaccount.google.com/apppasswords")
            print("2. Genera una contrasena para 'SIMAP / Correo'.")
            print("3. Pega los 16 caracteres en SMTP_PASSWORD dentro de tu archivo .env.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[!] ERROR INESPERADO AL CONECTAR CON EL SERVIDOR SMTP: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
