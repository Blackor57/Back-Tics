# tests/test_email_verification.py
import unittest
import asyncio
from app.services.email_service import EmailService
from app.core.security import create_email_verification_token, decode_email_verification_token
from app.api.v1.auth import _render_verification_html


class TestEmailVerification(unittest.TestCase):
    def test_construir_html_verificacion_con_nombre(self):
        """Verifica que el HTML generado incluya el saludo personalizado, botón y enlace."""
        enlace = "http://localhost:8000/api/v1/auth/verify?token=abc123token"
        html = EmailService._construir_html_verificacion("Carlos Alberto", enlace)

        self.assertIn("Carlos Alberto", html)
        self.assertIn(enlace, html)
        self.assertIn("Confirmar Mi Correo", html)
        self.assertIn("24 horas", html)
        self.assertIn("<!DOCTYPE html>", html)

    def test_construir_html_verificacion_sin_nombre(self):
        """Verifica que el HTML generado funcione adecuadamente cuando el usuario no tiene nombre registrado."""
        enlace = "http://localhost:8000/api/v1/auth/verify?token=xyz789token"
        html = EmailService._construir_html_verificacion(None, enlace)

        self.assertIn("Hola,", html)
        self.assertIn(enlace, html)
        self.assertIn("Confirmar Mi Correo", html)

    def test_enviar_correo_verificacion_simulado(self):
        """Verifica el envío asíncrono en modo simulación (sin credenciales SMTP configuradas)."""
        token = create_email_verification_token("usuario.demo@empresa.com")
        
        async def run_envio():
            return await EmailService.enviar_correo_verificacion(
                destinatario="usuario.demo@empresa.com",
                nombre_usuario="Demo User",
                token=token
            )

        resultado = asyncio.run(run_envio())
        self.assertTrue(resultado)

    def test_render_verification_html_success(self):
        """Verifica el renderizado de la tarjeta HTML de éxito de verificación."""
        html = _render_verification_html(
            titulo="¡Correo Confirmado Exitosamente!",
            mensaje="Tu cuenta ha sido verificada correctamente.",
            subtexto="Perfil activado.",
            es_exito=True
        )
        self.assertIn("¡Correo Confirmado Exitosamente!", html)
        self.assertIn("✅", html)
        self.assertIn("Perfil activado.", html)

    def test_render_verification_html_error(self):
        """Verifica el renderizado de la tarjeta HTML de fallo de verificación."""
        html = _render_verification_html(
            titulo="Enlace Inválido o Expirado",
            mensaje="El enlace ha caducado.",
            subtexto="Solicita uno nuevo.",
            es_exito=False
        )
        self.assertIn("Enlace Inválido o Expirado", html)
        self.assertIn("⚠️", html)
        self.assertIn("Solicita uno nuevo.", html)


if __name__ == "__main__":
    unittest.main()
