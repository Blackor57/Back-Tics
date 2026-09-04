# tests/test_security.py
import unittest
from datetime import timedelta
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    create_email_verification_token,
    decode_email_verification_token
)


class TestSecurity(unittest.TestCase):
    def test_hash_and_verify_password_success(self):
        """Verifica que el hasheo con bcrypt sea unidireccional y coincida con la contraseña original."""
        password_plano = "ClaveSecreta2026!"
        hashed = hash_password(password_plano)

        self.assertNotEqual(password_plano, hashed)
        self.assertTrue(hashed.startswith("$2b$"))
        self.assertTrue(verify_password(password_plano, hashed))

    def test_verify_password_failure_on_wrong_password(self):
        """Verifica que contraseñas incorrectas sean rechazadas rotundamente."""
        hashed = hash_password("PasswordValido123")
        self.assertFalse(verify_password("PasswordIncorrecto", hashed))
        self.assertFalse(verify_password("", hashed))

    def test_jwt_token_generation_and_payload(self):
        """Verifica que el token JWT incluya el sub, email y tiempo de expiración."""
        payload_data = {"sub": "100", "email": "auditor@empresa.com"}
        token = create_access_token(payload_data)

        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 20)

        decoded = decode_access_token(token)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.get("sub"), "100")
        self.assertEqual(decoded.get("email"), "auditor@empresa.com")
        self.assertIn("exp", decoded)
        self.assertIn("iat", decoded)

    def test_tampered_jwt_token_returns_none(self):
        """Verifica que un token alterado o con firma falsa sea rechazado (retorne None)."""
        token = create_access_token({"sub": "50"})
        token_manipulado = token[:-5] + "XXXXX"

        decoded = decode_access_token(token_manipulado)
        self.assertIsNone(decoded)

    def test_expired_jwt_token_returns_none(self):
        """Verifica que un token expirado no sea aceptado."""
        delta_negativo = timedelta(minutes=-10)
        token_expirado = create_access_token({"sub": "1"}, expires_delta=delta_negativo)

        decoded = decode_access_token(token_expirado)
        self.assertIsNone(decoded)

    def test_email_verification_token_valid(self):
        """Verifica que un token de verificación de email se genere y decodifique correctamente."""
        correo = "nuevo.usuario@empresa.com"
        token = create_email_verification_token(correo, expires_hours=24)

        self.assertIsInstance(token, str)
        email_extraido = decode_email_verification_token(token)
        self.assertEqual(email_extraido, correo)

    def test_email_verification_token_expired(self):
        """Verifica que un token de verificación expirado retorne None."""
        correo = "expirado@empresa.com"
        token = create_email_verification_token(correo, expires_hours=-1)

        email_extraido = decode_email_verification_token(token)
        self.assertIsNone(email_extraido)

    def test_email_verification_token_tampered(self):
        """Verifica que un token de verificación adulterado retorne None."""
        token = create_email_verification_token("test@empresa.com")
        token_corrupto = token[:-4] + "zzzz"

        email_extraido = decode_email_verification_token(token_corrupto)
        self.assertIsNone(email_extraido)

    def test_access_token_cannot_be_used_as_email_verification_token(self):
        """Verifica que un access_token normal no sea aceptado como token de verificación de correo."""
        token_login = create_access_token({"sub": "100", "email": "hacker@test.com"})
        email_extraido = decode_email_verification_token(token_login)
        self.assertIsNone(email_extraido)


if __name__ == "__main__":
    unittest.main()
