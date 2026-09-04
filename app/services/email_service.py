# app/services/email_service.py
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_FROM_EMAIL,
    SMTP_TLS,
    APP_BASE_URL
)

logger = logging.getLogger("email_service")


class EmailService:
    """
    Servicio para el despacho asíncrono de correos electrónicos con diseño HTML moderno.
    Informa a los usuarios sobre cambios importantes y novedades en sus URLs monitoreadas.
    """

    @staticmethod
    def _construir_html_alerta(
        nombre_usuario: Optional[str],
        url_monitoreada: str,
        total_nuevos: int,
        resumen_ejecutivo: str,
        novedades: List[Dict[str, Any]],
        sentimiento_general: Optional[str] = None
    ) -> str:
        filas_noticias = ""
        for item in novedades[:15]:  # Mostrar hasta 15 novedades o cambios principales
            titulo = item.get("titulo", "Cambio detectado")
            link = item.get("url") or url_monitoreada
            texto_boton = "Ver Enlace &rarr;" if item.get("url") else "Ver Sitio &rarr;"
            filas_noticias += f"""
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 12px 16px; font-size: 14px; color: #1e293b; line-height: 1.5;">
                    <strong>{titulo}</strong>
                </td>
                <td style="padding: 12px 16px; text-align: right;">
                    <a href="{link}" target="_blank" style="display: inline-block; padding: 6px 12px; background-color: #3b82f6; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 600;">
                        {texto_boton}
                    </a>
                </td>
            </tr>
            """


        saludo = f"Hola <strong>{nombre_usuario}</strong>," if nombre_usuario else "Hola,"
        fecha_hora = datetime.now().strftime("%d/%m/%Y a las %H:%M")

        html = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Alerta de Cambio Relevante</title>
        </head>
        <body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f1f5f9; padding: 30px 15px;">
                <tr>
                    <td align="center">
                        <table role="presentation" width="100%" style="max-width: 650px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);">
                            <!-- Header con Gradiente -->
                            <tr>
                                <td style="padding: 32px 30px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); color: #ffffff;">
                                    <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 1.5px; color: #38bdf8; font-weight: 700; margin-bottom: 8px;">
                                        SISTEMA DE MONITOREO CONTINUO
                                    </div>
                                    <h1 style="margin: 0; font-size: 24px; font-weight: 800; color: #ffffff;">
                                        🔔 Cambios Detectados en tu URL
                                    </h1>
                                    <p style="margin: 8px 0 0 0; font-size: 14px; color: #94a3b8;">
                                        Seguimiento activo ejecutado el {fecha_hora}
                                    </p>
                                </td>
                            </tr>

                            <!-- Cuerpo del mensaje -->
                            <tr>
                                <td style="padding: 30px;">
                                    <p style="font-size: 15px; color: #334155; margin-top: 0; line-height: 1.6;">
                                        {saludo}
                                    </p>
                                    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
                                        Hemos detectado <strong>{total_nuevos} nueva(s) novedad(es)</strong> relevante(s) durante la última inspección automática de tu URL monitoreada:
                                    </p>

                                    <!-- Tarjeta URL -->
                                    <div style="background-color: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 4px; margin: 18px 0; word-break: break-all;">
                                        <span style="font-size: 12px; color: #64748b; font-weight: 600; text-transform: uppercase;">URL en Seguimiento:</span><br>
                                        <a href="{url_monitoreada}" target="_blank" style="color: #2563eb; font-size: 14px; text-decoration: none; font-weight: 500;">
                                            {url_monitoreada}
                                        </a>
                                    </div>

                                    <!-- Resumen de Inteligencia Artificial -->
                                    <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 16px 20px; margin: 24px 0;">
                                        <h3 style="margin: 0 0 8px 0; font-size: 15px; color: #166534; display: flex; align-items: center;">
                                            🤖 Resumen Ejecutivo (Análisis IA)
                                        </h3>
                                        <p style="margin: 0; font-size: 14px; color: #14532d; line-height: 1.6;">
                                            {resumen_ejecutivo or "No se generó resumen semántico adicional."}
                                        </p>
                                        {f'<p style="margin: 8px 0 0 0; font-size: 12px; color: #15803d;"><strong>Sentimiento del contenido:</strong> {sentimiento_general}</p>' if sentimiento_general else ''}
                                    </div>

                                    <!-- Lista de novedades -->
                                    <h3 style="margin: 28px 0 12px 0; font-size: 16px; color: #0f172a; font-weight: 700;">
                                        Novedades y Noticias Recientes Detectadas:
                                    </h3>
                                    <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse: collapse; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
                                        <thead>
                                            <tr style="background-color: #f8fafc; border-bottom: 2px solid #e2e8f0;">
                                                <th align="left" style="padding: 10px 16px; font-size: 12px; color: #64748b; text-transform: uppercase;">Título / Contenido</th>
                                                <th align="right" style="padding: 10px 16px; font-size: 12px; color: #64748b; text-transform: uppercase;">Acción</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {filas_noticias}
                                        </tbody>
                                    </table>

                                    <p style="margin-top: 30px; font-size: 13px; color: #64748b; line-height: 1.5;">
                                        Este seguimiento seguirá activo hasta que finalice su período contratado. Si deseas gestionar tus alertas o cambiar la frecuencia, ingresa al panel de control de tu cuenta.
                                    </p>
                                </td>
                            </tr>

                            <!-- Footer -->
                            <tr>
                                <td style="padding: 20px 30px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center;">
                                    <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                                        Sistema Automatizado de Scraping e Inteligencia de Datos &copy; 2026.
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        return html

    @classmethod
    def _enviar_correo_sincrono(
        cls,
        destinatario: str,
        asunto: str,
        cuerpo_html: str,
        enlace_accion: Optional[str] = None
    ) -> bool:
        """Lógica síncrona de envío SMTP ejecutada en un threadpool worker."""
        if not SMTP_HOST or not SMTP_USER:
            aviso = (
                f"\n{'='*70}\n"
                f"  ⚠️ [MODO SIMULACIÓN SMTP - CORREO NO ENVIADO A INTERNET]\n"
                f"  Motivo: 'SMTP_HOST' o 'SMTP_USER' están vacíos en el archivo .env\n"
                f"  Para:   {destinatario}\n"
                f"  Asunto: {asunto}\n"
            )
            if enlace_accion:
                aviso += (
                    f"  --------------------------------------------------------------------\n"
                    f"  🔗 Enlace de confirmación generado para pruebas locales:\n"
                    f"  {enlace_accion}\n"
                    f"  (Abre este enlace en tu navegador para verificar la cuenta)\n"
                )
            aviso += f"{'='*70}\n"
            logger.warning(aviso)
            return True

        try:
            # Remitente: Si no se configuró o es el default, usar SMTP_USER para no ser bloqueado por Gmail/Outlook
            remitente = SMTP_FROM_EMAIL
            if not remitente or remitente == "notificaciones@simap.com":
                remitente = SMTP_USER or remitente

            msg = MIMEMultipart("alternative")
            msg["Subject"] = asunto
            msg["From"] = remitente
            msg["To"] = destinatario

            # Adjuntar versión HTML
            parte_html = MIMEText(cuerpo_html, "html", "utf-8")
            msg.attach(parte_html)

            # Conectar al servidor SMTP
            if SMTP_PORT == 465:
                servidor = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
            else:
                servidor = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
                if SMTP_TLS:
                    servidor.starttls()

            if SMTP_USER and SMTP_PASSWORD:
                servidor.login(SMTP_USER, SMTP_PASSWORD)

            servidor.sendmail(remitente, [destinatario], msg.as_string())
            servidor.quit()

            logger.info(f"Correo enviado exitosamente a {destinatario} vía {SMTP_HOST}")
            return True

        except Exception as e:
            logger.error(f"Error al enviar correo SMTP a {destinatario}: {str(e)}")
            return False

    @classmethod
    async def enviar_alerta_cambio_relevante(
        cls,
        destinatario: str,
        nombre_usuario: Optional[str],
        url_monitoreada: str,
        total_nuevos: int,
        resumen_ejecutivo: str,
        novedades: List[Dict[str, Any]],
        sentimiento_general: Optional[str] = None
    ) -> bool:
        """
        Despacha de forma no bloqueante (asíncrona) la alerta por correo.
        """
        asunto = f"🚨 Cambios detectados ({total_nuevos} novedades) en: {url_monitoreada[:35]}..."
        cuerpo_html = cls._construir_html_alerta(
            nombre_usuario=nombre_usuario,
            url_monitoreada=url_monitoreada,
            total_nuevos=total_nuevos,
            resumen_ejecutivo=resumen_ejecutivo,
            novedades=novedades,
            sentimiento_general=sentimiento_general
        )

        # Ejecutar en threadpool para no congelar el loop de asyncio
        return await asyncio.to_thread(cls._enviar_correo_sincrono, destinatario, asunto, cuerpo_html)

    @staticmethod
    def _construir_html_verificacion(
        nombre_usuario: Optional[str],
        enlace_verificacion: str
    ) -> str:
        saludo = f"Hola <strong>{nombre_usuario}</strong>," if nombre_usuario else "Hola,"
        fecha_hora = datetime.now().strftime("%d/%m/%Y")

        html = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Confirmación de Cuenta</title>
        </head>
        <body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f1f5f9; padding: 35px 15px;">
                <tr>
                    <td align="center">
                        <table role="presentation" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 10px -1px rgba(0, 0, 0, 0.08), 0 2px 4px -1px rgba(0, 0, 0, 0.04);">
                            <!-- Header Corporativo con Gradiente -->
                            <tr>
                                <td style="padding: 36px 30px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); color: #ffffff; text-align: center;">
                                    <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 2px; color: #38bdf8; font-weight: 700; margin-bottom: 10px;">
                                        SISTEMA INTELIGENTE DE MONITOREO
                                    </div>
                                    <h1 style="margin: 0; font-size: 24px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">
                                        ✉️ Confirma tu Cuenta
                                    </h1>
                                    <p style="margin: 10px 0 0 0; font-size: 13px; color: #94a3b8;">
                                        Bienvenido a nuestra plataforma &bull; {fecha_hora}
                                    </p>
                                </td>
                            </tr>

                            <!-- Cuerpo del Mensaje -->
                            <tr>
                                <td style="padding: 36px 32px;">
                                    <p style="font-size: 16px; color: #1e293b; margin-top: 0; line-height: 1.6;">
                                        {saludo}
                                    </p>
                                    <p style="font-size: 15px; color: #475569; line-height: 1.6; margin-bottom: 24px;">
                                        Gracias por registrarte. Para garantizar la seguridad de tu información y activar todas las funcionalidades de monitoreo, por favor confirma tu dirección de correo electrónico haciendo clic en el siguiente botón:
                                    </p>

                                    <!-- Botón Principal Interactivo -->
                                    <div style="text-align: center; margin: 36px 0;">
                                        <a href="{enlace_verificacion}" target="_blank" style="display: inline-block; background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: #ffffff; text-decoration: none; font-size: 15px; font-weight: 700; padding: 14px 34px; border-radius: 8px; box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35); letter-spacing: 0.3px;">
                                            &check; Confirmar Mi Correo
                                        </a>
                                    </div>

                                    <!-- Nota de Seguridad / Expiración -->
                                    <div style="background-color: #f8fafc; border-left: 4px solid #3b82f6; border-radius: 4px; padding: 14px 18px; margin: 28px 0;">
                                        <p style="margin: 0; font-size: 13px; color: #475569; line-height: 1.5;">
                                            ⏱️ <strong>Aviso de seguridad:</strong> Este enlace de verificación expirará en <strong>24 horas</strong>. Si no logras verificar tu cuenta a tiempo, podrás solicitar un nuevo enlace desde la plataforma.
                                        </p>
                                    </div>

                                    <!-- Enlace alternativo si el botón no responde -->
                                    <p style="font-size: 12px; color: #64748b; line-height: 1.5; margin-top: 24px;">
                                        ¿El botón no responde? Puedes copiar y pegar el siguiente enlace directamente en tu navegador:
                                    </p>
                                    <div style="background-color: #f1f5f9; padding: 10px 14px; border-radius: 6px; word-break: break-all; font-size: 11px; color: #2563eb; font-family: monospace;">
                                        {enlace_verificacion}
                                    </div>

                                    <p style="font-size: 12px; color: #94a3b8; line-height: 1.5; margin-top: 28px; border-top: 1px solid #f1f5f9; padding-top: 16px;">
                                        Si tú no has solicitado el registro en nuestra plataforma, no necesitas hacer nada; simplemente ignora este mensaje.
                                    </p>
                                </td>
                            </tr>

                            <!-- Footer -->
                            <tr>
                                <td style="padding: 20px 30px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center;">
                                    <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                                        Sistema Automatizado de Scraping e Inteligencia de Datos &copy; 2026.
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        return html

    @classmethod
    async def enviar_correo_verificacion(
        cls,
        destinatario: str,
        nombre_usuario: Optional[str],
        token: str
    ) -> bool:
        """
        Despacha de forma asíncrona el correo de verificación con enlace y botón.
        """
        enlace = f"{APP_BASE_URL.rstrip('/')}/api/v1/auth/verify?token={token}"
        asunto = "🔐 Confirma tu cuenta de correo electrónico"
        cuerpo_html = cls._construir_html_verificacion(
            nombre_usuario=nombre_usuario,
            enlace_verificacion=enlace
        )
        return await asyncio.to_thread(
            cls._enviar_correo_sincrono,
            destinatario,
            asunto,
            cuerpo_html,
            enlace
        )
