# app/services/email_service.py
import asyncio
import logging
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from pathlib import Path
from typing import List, Dict, Any, Optional, Sequence, Union
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

    @staticmethod
    def _construir_html_reporte(
        nombre_usuario: Optional[str],
        url_fuente: str,
        titulo_reporte: str,
        mensaje_principal: str,
        total_registros: int = 0,
        resumen_ejecutivo: Optional[str] = None,
        sentimiento_general: Optional[str] = None,
        nombre_adjunto: Optional[str] = None,
    ) -> str:
        """Plantilla HTML para el envío del archivo Excel generado por scraping."""
        saludo = f"Hola <strong>{escape(nombre_usuario)}</strong>," if nombre_usuario else "Hola,"
        fecha_hora = datetime.now().strftime("%d/%m/%Y a las %H:%M")
        url_segura = escape(url_fuente)
        resumen_bloque = ""
        if resumen_ejecutivo:
            resumen_bloque = f"""
                                    <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 16px 20px; margin: 24px 0;">
                                        <h3 style="margin: 0 0 8px 0; font-size: 15px; color: #166534;">
                                            🤖 Resumen Ejecutivo (Análisis IA)
                                        </h3>
                                        <p style="margin: 0; font-size: 14px; color: #14532d; line-height: 1.6;">
                                            {escape(str(resumen_ejecutivo))}
                                        </p>
                                        {f'<p style="margin: 8px 0 0 0; font-size: 12px; color: #15803d;"><strong>Sentimiento del contenido:</strong> {escape(str(sentimiento_general))}</p>' if sentimiento_general else ''}
                                    </div>
            """
        adjunto_bloque = ""
        if nombre_adjunto:
            adjunto_bloque = f"""
                                    <div style="background-color: #eff6ff; border: 1px dashed #93c5fd; border-radius: 8px; padding: 14px 18px; margin: 22px 0;">
                                        <p style="margin: 0; font-size: 13px; color: #1e40af;">
                                            📎 <strong>Archivo adjunto:</strong> {escape(nombre_adjunto)}
                                        </p>
                                    </div>
            """

        return f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{escape(titulo_reporte)}</title>
        </head>
        <body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f1f5f9; padding: 30px 15px;">
                <tr>
                    <td align="center">
                        <table role="presentation" width="100%" style="max-width: 650px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);">
                            <tr>
                                <td style="padding: 32px 30px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); color: #ffffff;">
                                    <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 1.5px; color: #38bdf8; font-weight: 700; margin-bottom: 8px;">
                                        SISTEMA DE SCRAPING AUTOMATIZADO
                                    </div>
                                    <h1 style="margin: 0; font-size: 24px; font-weight: 800; color: #ffffff;">
                                        {escape(titulo_reporte)}
                                    </h1>
                                    <p style="margin: 8px 0 0 0; font-size: 14px; color: #94a3b8;">
                                        Generado el {fecha_hora}
                                    </p>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 30px;">
                                    <p style="font-size: 15px; color: #334155; margin-top: 0; line-height: 1.6;">
                                        {saludo}
                                    </p>
                                    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
                                        {escape(mensaje_principal)}
                                    </p>

                                    <div style="background-color: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 4px; margin: 18px 0; word-break: break-all;">
                                        <span style="font-size: 12px; color: #64748b; font-weight: 600; text-transform: uppercase;">URL procesada:</span><br>
                                        <a href="{url_segura}" target="_blank" style="color: #2563eb; font-size: 14px; text-decoration: none; font-weight: 500;">
                                            {url_segura}
                                        </a>
                                    </div>

                                    <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse: collapse; margin: 18px 0;">
                                        <tr>
                                            <td style="padding: 12px 16px; background-color: #f8fafc; border: 1px solid #e2e8f0; font-size: 13px; color: #475569;">
                                                <strong>Registros extraídos:</strong> {total_registros}
                                            </td>
                                        </tr>
                                    </table>

                                    {resumen_bloque}
                                    {adjunto_bloque}

                                    <p style="margin-top: 28px; font-size: 13px; color: #64748b; line-height: 1.5;">
                                        El archivo Excel adjunto contiene los datos extraídos, la fuente de consulta y los metadatos del reporte. Si deseas gestionar tus alertas, ingresa al panel de control de tu cuenta.
                                    </p>
                                </td>
                            </tr>
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

    @classmethod
    def _enviar_correo_sincrono(
        cls,
        destinatario: str,
        asunto: str,
        cuerpo_html: str,
        enlace_accion: Optional[str] = None,
        adjuntos: Optional[Sequence[Union[str, Path]]] = None,
    ) -> bool:
        """Lógica síncrona de envío SMTP ejecutada en un threadpool worker."""
        adjuntos = list(adjuntos or [])
        adjuntos_validos = [Path(ruta) for ruta in adjuntos if Path(ruta).is_file()]

        if not SMTP_HOST or not SMTP_USER:
            aviso = (
                f"\n{'='*70}\n"
                f"  ⚠️ [MODO SIMULACIÓN SMTP - CORREO NO ENVIADO A INTERNET]\n"
                f"  Motivo: 'SMTP_HOST' o 'SMTP_USER' están vacíos en el archivo .env\n"
                f"  Para:   {destinatario}\n"
                f"  Asunto: {asunto}\n"
            )
            if adjuntos_validos:
                aviso += "  Adjuntos: " + ", ".join(a.name for a in adjuntos_validos) + "\n"
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

            if adjuntos_validos:
                msg = MIMEMultipart("mixed")
                cuerpo = MIMEMultipart("alternative")
                cuerpo.attach(MIMEText(cuerpo_html, "html", "utf-8"))
                msg.attach(cuerpo)
                for ruta in adjuntos_validos:
                    parte = MIMEBase("application", "octet-stream")
                    parte.set_payload(ruta.read_bytes())
                    encoders.encode_base64(parte)
                    parte.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{ruta.name}"',
                    )
                    msg.attach(parte)
            else:
                msg = MIMEMultipart("alternative")
                msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

            msg["Subject"] = asunto
            msg["From"] = remitente
            msg["To"] = destinatario

            # Conectar al servidor SMTP
            if SMTP_PORT == 465:
                servidor = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
            else:
                servidor = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
                if SMTP_TLS:
                    servidor.starttls()

            # Gmail/Outlook muestran las contraseñas de aplicación con espacios,
            # pero el valor real no los incluye.
            usuario_smtp = (SMTP_USER or "").strip()
            password_smtp = (SMTP_PASSWORD or "").replace(" ", "").strip()
            if usuario_smtp and password_smtp:
                servidor.login(usuario_smtp, password_smtp)

            servidor.sendmail(remitente, [destinatario], msg.as_string())
            servidor.quit()

            logger.info(
                f"Correo enviado exitosamente a {destinatario} vía {SMTP_HOST}"
                + (f" con {len(adjuntos_validos)} adjunto(s)" if adjuntos_validos else "")
            )
            return True

        except Exception as e:
            logger.error(f"Error al enviar correo SMTP a {destinatario}: {str(e)}")
            if enlace_accion:
                print(
                    f"\n{'='*70}\n"
                    f"  ⚠️ [AVISO SIMAP] Falló el despacho SMTP a {destinatario} ({str(e)}).\n"
                    f"  🔗 Enlace directo de verificación generado:\n"
                    f"  {enlace_accion}\n"
                    f"{'='*70}\n"
                )
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
        sentimiento_general: Optional[str] = None,
        adjuntos: Optional[Sequence[Union[str, Path]]] = None,
    ) -> bool:
        """
        Despacha de forma no bloqueante (asíncrona) la alerta por correo,
        adjuntando opcionalmente el Excel con el detalle de los cambios.
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
        return await asyncio.to_thread(
            cls._enviar_correo_sincrono,
            destinatario,
            asunto,
            cuerpo_html,
            None,
            adjuntos,
        )

    @classmethod
    async def enviar_reporte_excel(
        cls,
        destinatario: str,
        nombre_usuario: Optional[str],
        url_fuente: str,
        archivo_excel: Union[str, Path],
        total_registros: int = 0,
        resumen_ejecutivo: Optional[str] = None,
        sentimiento_general: Optional[str] = None,
        cambios_detectados: bool = False,
        titulo_reporte: Optional[str] = None,
    ) -> bool:
        """
        Envía por correo el archivo Excel generado por cualquier ejecución de scraping.

        Se invoca tanto desde la extracción RPA manual como desde el analizador
        inteligente y el monitor continuo (cuando detecta cambios).
        """
        adjunto = Path(archivo_excel)
        if not adjunto.is_file():
            logger.warning(f"No se envió el reporte: el archivo no existe ({adjunto}).")
            return False

        if cambios_detectados:
            titulo = titulo_reporte or "Cambios detectados en tu URL monitoreada"
            mensaje = (
                f"El monitor continuo ejecutó un nuevo scraping y detectó cambios relevantes. "
                f"Adjuntamos el reporte Excel actualizado de la fuente consultada."
            )
            asunto = f"🚨 Reporte Excel con cambios detectados: {url_fuente[:45]}"
        else:
            titulo = titulo_reporte or "Reporte Excel de scraping"
            mensaje = (
                f"Se ejecutó un nuevo scraping de la URL indicada y el reporte Excel "
                f"fue generado correctamente. Encontrarás el detalle en el archivo adjunto."
            )
            asunto = f"📊 Reporte Excel de scraping: {url_fuente[:45]}"

        if total_registros:
            mensaje += f" Total de registros extraídos: {total_registros}."

        cuerpo_html = cls._construir_html_reporte(
            nombre_usuario=nombre_usuario,
            url_fuente=url_fuente,
            titulo_reporte=titulo,
            mensaje_principal=mensaje,
            total_registros=total_registros,
            resumen_ejecutivo=resumen_ejecutivo,
            sentimiento_general=sentimiento_general,
            nombre_adjunto=adjunto.name,
        )

        return await asyncio.to_thread(
            cls._enviar_correo_sincrono,
            destinatario,
            asunto,
            cuerpo_html,
            None,
            [adjunto],
        )

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
