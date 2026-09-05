# tests/test_schemas.py
import unittest
from pydantic import ValidationError
from app.schemas.auth import UserCreate, UserLogin, ResendVerificationRequest
from app.schemas.tracking import TrackTargetCreate, TrackTargetUpdate
from app.schemas.schemas import ScrapeIndexRequest, FullPipelineRequest, DeepScrapeRequest


class TestSchemas(unittest.TestCase):
    def test_user_create_valid(self):
        """Verifica la creación válida y normalización de correo en minúsculas."""
        user = UserCreate(
            email="  Usuario.Prueba@Dominio.COM  ",
            password="passwordSeguro123",
            nombre_completo="Juan Pérez"
        )
        self.assertEqual(user.email, "usuario.prueba@dominio.com")
        self.assertEqual(user.nombre_completo, "Juan Pérez")

    def test_user_create_invalid_email_format(self):
        """Verifica que correos con formato inválido lancen ValidationError."""
        correos_invalidos = ["sin-arroba.com", "@dominio.com", "usuario@", "usuario@dominio"]
        for correo in correos_invalidos:
            with self.assertRaises(ValidationError):
                UserCreate(email=correo, password="password123")

    def test_user_create_short_password(self):
        """Verifica que contraseñas menores a 6 caracteres sean rechazadas."""
        with self.assertRaises(ValidationError):
            UserCreate(email="valido@ejemplo.com", password="12345")

    def test_resend_verification_valid_and_invalid(self):
        """Verifica la validación y normalización en ResendVerificationRequest."""
        req = ResendVerificationRequest(email="  MiCorreo@Dominio.COM ")
        self.assertEqual(req.email, "micorreo@dominio.com")

        with self.assertRaises(ValidationError):
            ResendVerificationRequest(email="no-es-correo")

    def test_track_target_create_valid(self):
        """Verifica la creación correcta de parámetros de seguimiento."""
        target = TrackTargetCreate(
            url="https://rpp.pe/",
            dias_duracion=7,
            frecuencia_horas=6,
            notificar_email=True
        )
        self.assertEqual(target.dias_duracion, 7)
        self.assertEqual(target.frecuencia_horas, 6)
        self.assertTrue(target.notificar_email)

    def test_track_target_duration_out_of_bounds(self):
        """Verifica que la duración de seguimiento no pueda exceder 30 días ni ser menor a 1."""
        # Menor a 1 día
        with self.assertRaises(ValidationError):
            TrackTargetCreate(url="https://rpp.pe/", dias_duracion=0)

        # Mayor a 30 días
        with self.assertRaises(ValidationError):
            TrackTargetCreate(url="https://rpp.pe/", dias_duracion=31)

    def test_track_target_frequency_out_of_bounds(self):
        """Verifica que la frecuencia en horas deba estar entre 1 y 48 horas."""
        with self.assertRaises(ValidationError):
            TrackTargetCreate(url="https://rpp.pe/", frecuencia_horas=0)

        with self.assertRaises(ValidationError):
            TrackTargetCreate(url="https://rpp.pe/", frecuencia_horas=50)

    def test_scrape_index_request_valid(self):
        """Verifica la validación de URL en ScrapeIndexRequest."""
        req = ScrapeIndexRequest(url="https://elcomercio.pe/")
        self.assertEqual(str(req.url), "https://elcomercio.pe/")

    def test_full_pipeline_request_limit_bounds(self):
        """Verifica que el límite de noticias en FullPipelineRequest esté entre 1 y 20."""
        req = FullPipelineRequest(url="https://elcomercio.pe/", limit=10)
        self.assertEqual(req.limit, 10)

        with self.assertRaises(ValidationError):
            FullPipelineRequest(url="https://elcomercio.pe/", limit=0)

        with self.assertRaises(ValidationError):
            FullPipelineRequest(url="https://elcomercio.pe/", limit=25)


if __name__ == "__main__":
    unittest.main()
